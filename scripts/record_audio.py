#!/usr/bin/env python3
from typing import Any, Callable

import sounddevice

SAMPLE_RATE_HZ = 16000
CHANNEL_COUNT = 1
# 100 ms of audio per chunk, the pacing xAI recommends for streaming STT.
CHUNK_FRAMES = SAMPLE_RATE_HZ // 10


def start_recording(
    on_chunk: Callable[[bytes], None],
    open_stream: Callable[..., Any] = sounddevice.RawInputStream
) -> Any:
    def forward_chunk(data: Any, frame_count: int, time_info: Any, status: Any) -> None:
        on_chunk(bytes(data))

    stream = open_stream(
        samplerate=SAMPLE_RATE_HZ,
        channels=CHANNEL_COUNT,
        dtype="int16",
        blocksize=CHUNK_FRAMES,
        callback=forward_chunk,
    )
    stream.start()
    return stream


def stop_recording(stream: Any) -> None:
    # Failure recovery may stop a stream twice; PortAudio must never see a closed stream.
    if stream.closed:
        return
    stream.stop()
    stream.close()
