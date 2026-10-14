import json
import queue
import unittest
from typing import Any
from urllib.parse import parse_qs, urlparse

from stream_transcription import (
    AUDIO_DONE_MESSAGE,
    TOKEN_URL,
    TranscriptEvent,
    build_stream_url,
    extract_token,
    mint_stream_token,
    parse_transcript_event,
    send_audio,
    stream_transcription,
)


def partial(text: str, is_final: bool = False, speech_final: bool = False) -> str:
    return json.dumps({"type": "transcript.partial", "text": text, "is_final": is_final, "speech_final": speech_final})


READY = json.dumps({"type": "transcript.created"})
DONE = json.dumps({"type": "transcript.done", "text": ""})


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self.ok = status_code < 400
        self.text = "error body"
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeConnection:
    def __init__(self, messages: list[str]) -> None:
        self.ready, *self.messages = messages
        self.sent: list[Any] = []
        self.closed = False

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.closed = True

    def recv(self, timeout: float | None = None) -> str:
        return self.ready

    def __iter__(self) -> Any:
        return iter(self.messages)

    def send(self, message: Any) -> None:
        self.sent.append(message)

    def close(self) -> None:
        self.closed = True


def queued(*items: Any) -> "queue.Queue[Any]":
    audio_items: "queue.Queue[Any]" = queue.Queue()
    for item in items:
        audio_items.put(item)
    return audio_items


def run_stream(messages: list[str]) -> list[TranscriptEvent]:
    events: list[TranscriptEvent] = []
    stream_transcription(queued("abort"), events.append, open_connection=lambda: FakeConnection(messages))
    return events


class BuildStreamUrlTest(unittest.TestCase):
    def test_requests_interim_results(self) -> None:
        self.assertEqual(parse_qs(urlparse(build_stream_url()).query)["interim_results"], ["true"])

    def test_enables_smart_turn(self) -> None:
        self.assertIn("smart_turn", parse_qs(urlparse(build_stream_url()).query))

    def test_repeats_keyterm_per_term(self) -> None:
        self.assertEqual(parse_qs(urlparse(build_stream_url(("A", "B"))).query)["keyterm"], ["A", "B"])

    def test_leaves_language_to_auto_detect(self) -> None:
        self.assertNotIn("language", parse_qs(urlparse(build_stream_url()).query))


class ExtractTokenTest(unittest.TestCase):
    def test_reads_top_level_value(self) -> None:
        self.assertEqual(extract_token({"value": "tok", "expires_at": 1}), "tok")

    def test_reads_nested_client_secret(self) -> None:
        self.assertEqual(extract_token({"client_secret": {"value": "tok"}}), "tok")

    def test_missing_value_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            extract_token({})


class MintStreamTokenTest(unittest.TestCase):
    def test_posts_to_shush_xai_route(self) -> None:
        calls: list[str] = []

        def post(url: str, **kwargs: Any) -> FakeResponse:
            calls.append(url)
            return FakeResponse(200, {"value": "tok"})

        mint_stream_token(post=post)
        self.assertEqual(calls, [TOKEN_URL])

    def test_http_error_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            mint_stream_token(post=lambda url, **kwargs: FakeResponse(502, {}))


class ParseTranscriptEventTest(unittest.TestCase):
    def test_created_is_ready(self) -> None:
        self.assertEqual(parse_transcript_event(READY).kind, "ready")

    def test_not_final_is_interim(self) -> None:
        self.assertEqual(parse_transcript_event(partial("hi")), TranscriptEvent("interim", "hi"))

    def test_is_final_is_chunk_final(self) -> None:
        self.assertEqual(parse_transcript_event(partial("hi", is_final=True)).kind, "chunk_final")

    def test_speech_final_is_utterance_final(self) -> None:
        self.assertEqual(parse_transcript_event(partial("hi", True, True)).kind, "utterance_final")

    def test_error_keeps_message(self) -> None:
        self.assertEqual(parse_transcript_event(json.dumps({"type": "error", "message": "bad"})).text, "bad")

    def test_unknown_type_is_ignored(self) -> None:
        self.assertEqual(parse_transcript_event(json.dumps({"type": "session.ping"})).kind, "ignored")


class SendAudioTest(unittest.TestCase):
    def test_sends_chunks_then_audio_done(self) -> None:
        connection = FakeConnection([READY])
        send_audio(connection, queued(b"pcm", "done"))
        self.assertEqual(connection.sent, [b"pcm", AUDIO_DONE_MESSAGE])

    def test_abort_closes_without_audio_done(self) -> None:
        connection = FakeConnection([READY])
        send_audio(connection, queued(b"pcm", "abort"))
        self.assertEqual((connection.sent, connection.closed), ([b"pcm"], True))


class StreamTranscriptionTest(unittest.TestCase):
    def test_forwards_transcript_events(self) -> None:
        events = run_stream([READY, partial("a"), partial("a.", True, True), DONE])
        self.assertEqual([event.kind for event in events], ["interim", "utterance_final"])

    def test_stops_at_done(self) -> None:
        self.assertEqual(run_stream([READY, DONE, partial("late")]), [])

    def test_error_event_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            run_stream([READY, json.dumps({"type": "error", "message": "timeout"})])

    def test_missing_ready_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            run_stream([json.dumps({"type": "error", "message": "unauthorized"})])


if __name__ == "__main__":
    unittest.main()
