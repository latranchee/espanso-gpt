import unittest
from typing import Any

from record_audio import CHUNK_FRAMES, SAMPLE_RATE_HZ, start_recording, stop_recording


class FakeStream:
    def __init__(self, **options: Any) -> None:
        self.options = options
        self.calls: list[str] = []
        self.closed = False

    def start(self) -> None:
        self.calls.append("start")

    def stop(self) -> None:
        self.calls.append("stop")

    def close(self) -> None:
        self.calls.append("close")
        self.closed = True


class StartRecordingTest(unittest.TestCase):
    def test_records_at_stt_sample_rate(self) -> None:
        stream = start_recording(lambda chunk: None, open_stream=FakeStream)
        self.assertEqual(stream.options["samplerate"], SAMPLE_RATE_HZ)

    def test_uses_100ms_chunks(self) -> None:
        stream = start_recording(lambda chunk: None, open_stream=FakeStream)
        self.assertEqual(stream.options["blocksize"], CHUNK_FRAMES)

    def test_starts_the_stream(self) -> None:
        self.assertEqual(start_recording(lambda chunk: None, open_stream=FakeStream).calls, ["start"])

    def test_forwards_chunks_as_bytes(self) -> None:
        chunks: list[bytes] = []
        stream = start_recording(chunks.append, open_stream=FakeStream)
        stream.options["callback"](bytearray(b"\x01\x02"), 1, None, None)
        self.assertEqual(chunks, [b"\x01\x02"])


class StopRecordingTest(unittest.TestCase):
    def test_stops_then_closes(self) -> None:
        stream = FakeStream()
        stop_recording(stream)
        self.assertEqual(stream.calls, ["stop", "close"])

    def test_second_stop_is_a_no_op(self) -> None:
        stream = FakeStream()
        stop_recording(stream)
        stop_recording(stream)
        self.assertEqual(stream.calls, ["stop", "close"])


if __name__ == "__main__":
    unittest.main()
