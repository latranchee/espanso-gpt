import unittest
from typing import Any

from transcribe_audio import STT_MODEL, STT_URL, extract_transcript, transcribe_audio


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any], text: str = "") -> None:
        self.status_code = status_code
        self.ok = status_code < 400
        self.text = text
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


def recording_post(response: FakeResponse, calls: list[dict[str, Any]]) -> Any:
    def post(url: str, **kwargs: Any) -> FakeResponse:
        calls.append({"url": url, **kwargs})
        return response
    return post


class ExtractTranscriptTest(unittest.TestCase):
    def test_returns_stripped_text(self) -> None:
        self.assertEqual(extract_transcript({"text": "  Hello world. "}), "Hello world.")

    def test_missing_text_returns_empty_string(self) -> None:
        self.assertEqual(extract_transcript({}), "")

    def test_null_text_returns_empty_string(self) -> None:
        self.assertEqual(extract_transcript({"text": None}), "")


class TranscribeAudioTest(unittest.TestCase):
    def test_returns_transcript_from_response(self) -> None:
        post = recording_post(FakeResponse(200, {"text": "Bonjour"}), [])
        self.assertEqual(transcribe_audio(b"wav", post=post), "Bonjour")

    def test_posts_to_shush_xai_route(self) -> None:
        calls: list[dict[str, Any]] = []
        transcribe_audio(b"wav", post=recording_post(FakeResponse(200, {"text": "x"}), calls))
        self.assertEqual(calls[0]["url"], STT_URL)

    def test_sends_transcribe_model(self) -> None:
        calls: list[dict[str, Any]] = []
        transcribe_audio(b"wav", post=recording_post(FakeResponse(200, {"text": "x"}), calls))
        self.assertEqual(calls[0]["data"]["model"], STT_MODEL)

    def test_uploads_audio_bytes(self) -> None:
        calls: list[dict[str, Any]] = []
        transcribe_audio(b"wav-bytes", post=recording_post(FakeResponse(200, {"text": "x"}), calls))
        self.assertEqual(calls[0]["files"]["file"][1], b"wav-bytes")

    def test_http_error_raises_with_proxy_message(self) -> None:
        post = recording_post(FakeResponse(502, {}, "SECRET_UNAVAILABLE"), [])
        with self.assertRaisesRegex(RuntimeError, "SECRET_UNAVAILABLE"):
            transcribe_audio(b"wav", post=post)


if __name__ == "__main__":
    unittest.main()
