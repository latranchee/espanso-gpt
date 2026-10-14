#!/usr/bin/env python3
import json
import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable, Literal
from urllib.parse import urlencode

import requests
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect

from llm_client import SHUSH_PROXY_URL
from record_audio import SAMPLE_RATE_HZ

# shush only relays HTTP, so it mints a short-lived token and the WebSocket goes straight to xAI.
TOKEN_URL = f"{SHUSH_PROXY_URL}/xai/v1/realtime/client_secrets"
STREAM_URL = "wss://api.x.ai/v1/stt"
STT_MODEL = "grok-voice-transcribe-2.0"
STT_KEYTERMS = ("Les Bunkers",)
# smart_turn ends an utterance as soon as the sentence sounds finished; the timeout forces it after 1s of silence.
SMART_TURN_THRESHOLD = 0.5
SMART_TURN_TIMEOUT_MS = 1000
TOKEN_LIFETIME_SECONDS = 300
TIMEOUT_SECONDS = 10
AUDIO_DONE_MESSAGE = json.dumps({"type": "audio.done"})

StreamEventKind = Literal["ready", "interim", "chunk_final", "utterance_final", "done", "error", "ignored"]
AudioItem = bytes | Literal["done", "abort"]
TRANSCRIPT_KINDS = ("interim", "chunk_final", "utterance_final")


@dataclass(frozen=True)
class TranscriptEvent:
    kind: StreamEventKind
    text: str = ""


def build_stream_url(keyterms: tuple[str, ...] = STT_KEYTERMS) -> str:
    params = [
        ("model", STT_MODEL),
        ("sample_rate", SAMPLE_RATE_HZ),
        ("encoding", "pcm"),
        ("interim_results", "true"),
        ("smart_turn", SMART_TURN_THRESHOLD),
        ("smart_turn_timeout", SMART_TURN_TIMEOUT_MS),
        *(("keyterm", keyterm) for keyterm in keyterms),
    ]
    return f"{STREAM_URL}?{urlencode(params)}"


def extract_token(payload: dict[str, Any]) -> str:
    # xAI documents both a top-level and a nested client_secret shape; the live API returns top-level.
    token = payload.get("value") or (payload.get("client_secret") or {}).get("value")
    if not token:
        raise RuntimeError(f"xAI token response has no value (keys: {sorted(payload)})")
    return token


def mint_stream_token(post: Callable[..., Any] = requests.post) -> str:
    response = post(TOKEN_URL, json={"expires_after": {"seconds": TOKEN_LIFETIME_SECONDS}}, timeout=TIMEOUT_SECONDS)
    if not response.ok:
        raise RuntimeError(f"xAI token error {response.status_code}: {response.text}")
    return extract_token(response.json())


def open_stream_connection(mint_token: Callable[[], str] = mint_stream_token) -> ClientConnection:
    headers = {"Authorization": f"Bearer {mint_token()}"}
    return connect(build_stream_url(), additional_headers=headers, open_timeout=TIMEOUT_SECONDS)


def classify_partial(payload: dict[str, Any]) -> StreamEventKind:
    if payload.get("speech_final"):
        return "utterance_final"
    return "chunk_final" if payload.get("is_final") else "interim"


def parse_transcript_event(message: str | bytes) -> TranscriptEvent:
    payload = json.loads(message)
    event_type = payload.get("type")
    if event_type == "transcript.created":
        return TranscriptEvent("ready")
    if event_type == "transcript.partial":
        return TranscriptEvent(classify_partial(payload), payload.get("text") or "")
    if event_type == "transcript.done":
        return TranscriptEvent("done", payload.get("text") or "")
    if event_type == "error":
        return TranscriptEvent("error", str(payload.get("message") or payload))
    return TranscriptEvent("ignored")


def send_audio(connection: Any, audio_items: "queue.Queue[AudioItem]") -> None:
    try:
        while True:
            item = audio_items.get()
            if item == "abort":
                connection.close()
                return
            connection.send(AUDIO_DONE_MESSAGE if item == "done" else item)
            if item == "done":
                return
    except ConnectionClosed:
        return


def wait_until_ready(connection: Any) -> None:
    event = parse_transcript_event(connection.recv(timeout=TIMEOUT_SECONDS))
    if event.kind != "ready":
        raise RuntimeError(f"xAI STT did not start: {event.kind} {event.text}")


def receive_transcript(
    connection: Any, audio_items: "queue.Queue[AudioItem]", on_event: Callable[[TranscriptEvent], None]
) -> None:
    wait_until_ready(connection)
    threading.Thread(target=send_audio, args=(connection, audio_items), daemon=True).start()
    for message in connection:
        event = parse_transcript_event(message)
        if event.kind == "error":
            raise RuntimeError(f"xAI STT error: {event.text}")
        if event.kind == "done":
            return
        if event.kind in TRANSCRIPT_KINDS:
            on_event(event)


def stream_transcription(
    audio_items: "queue.Queue[AudioItem]",
    on_event: Callable[[TranscriptEvent], None],
    open_connection: Callable[[], Any] = open_stream_connection
) -> None:
    connection = open_connection()
    try:
        receive_transcript(connection, audio_items, on_event)
    finally:
        # xAI answers the close handshake ~2s after transcript.done; the dictation must not wait for it.
        threading.Thread(target=connection.close, daemon=True).start()
