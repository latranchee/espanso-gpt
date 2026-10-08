#!/usr/bin/env python3
from typing import Any, Callable

import requests

from llm_client import SHUSH_PROXY_URL

STT_URL = f"{SHUSH_PROXY_URL}/xai/v1/stt"
STT_MODEL = "grok-voice-transcribe-2.0"
STT_KEYTERMS = ("Les Bunkers",)
STT_TIMEOUT_SECONDS = 60


def transcribe_audio(wav_bytes: bytes, post: Callable[..., Any] = requests.post) -> str:
    response = post(
        STT_URL,
        data={"model": STT_MODEL, "keyterm": list(STT_KEYTERMS)},
        files={"file": ("speech.wav", wav_bytes, "audio/wav")},
        timeout=STT_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise RuntimeError(f"xAI STT error {response.status_code}: {response.text}")
    return extract_transcript(response.json())


def extract_transcript(payload: dict[str, Any]) -> str:
    return str(payload.get("text") or "").strip()
