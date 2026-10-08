#!/usr/bin/env python3
import io
import wave
from dataclasses import dataclass
from typing import Any

import sounddevice

SAMPLE_RATE_HZ = 16000
CHANNEL_COUNT = 1
SAMPLE_WIDTH_BYTES = 2


@dataclass(frozen=True)
class Recording:
    stream: sounddevice.RawInputStream
    chunks: list[bytes]


def start_recording() -> Recording:
    chunks: list[bytes] = []

    def collect_chunk(data: Any, frame_count: int, time_info: Any, status: Any) -> None:
        chunks.append(bytes(data))

    stream = sounddevice.RawInputStream(
        samplerate=SAMPLE_RATE_HZ, channels=CHANNEL_COUNT, dtype="int16", callback=collect_chunk
    )
    stream.start()
    return Recording(stream, chunks)


def stop_recording(recording: Recording) -> bytes:
    recording.stream.stop()
    recording.stream.close()
    return encode_wav(b"".join(recording.chunks))


def encode_wav(pcm: bytes, sample_rate_hz: int = SAMPLE_RATE_HZ) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(CHANNEL_COUNT)
        wav_file.setsampwidth(SAMPLE_WIDTH_BYTES)
        wav_file.setframerate(sample_rate_hz)
        wav_file.writeframes(pcm)
    return buffer.getvalue()
