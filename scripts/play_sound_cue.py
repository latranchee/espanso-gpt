#!/usr/bin/env python3
import io
import math
import threading
import wave
import winsound
from array import array
from dataclasses import dataclass
from typing import Literal

import logger

SoundCue = Literal["polish_started", "done"]
SAMPLE_RATE_HZ = 44100
ATTACK_SECONDS = 0.004
CUE_VOLUME = 0.3


@dataclass(frozen=True)
class Partial:
    frequency_hz: float
    amplitude: float
    decay_per_second: float


# Inharmonic partials (1, 2, 2.76, 5.4 times the fundamental) are what make a struck bell sound like a bell.
BELL_PARTIALS = (
    Partial(1046.5, 0.6, 3.0),
    Partial(2093.0, 0.25, 5.0),
    Partial(2888.3, 0.12, 7.0),
    Partial(5651.1, 0.05, 12.0),
)
BELL_SECONDS = 1.2
TICK_PARTIALS = (Partial(660.0, 0.5, 30.0), Partial(1320.0, 0.15, 40.0))
TICK_SECONDS = 0.15


def render_sample(partials: tuple[Partial, ...], time_seconds: float) -> float:
    attack = min(1.0, time_seconds / ATTACK_SECONDS)
    return attack * sum(
        partial.amplitude
        * math.exp(-partial.decay_per_second * time_seconds)
        * math.sin(2 * math.pi * partial.frequency_hz * time_seconds)
        for partial in partials
    )


def synthesize_tone(
    partials: tuple[Partial, ...],
    duration_seconds: float,
    volume: float = CUE_VOLUME,
    sample_rate_hz: int = SAMPLE_RATE_HZ
) -> bytes:
    samples = array("h", (
        int(max(-1.0, min(1.0, volume * render_sample(partials, frame / sample_rate_hz))) * 32767)
        for frame in range(int(duration_seconds * sample_rate_hz))
    ))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate_hz)
        wav_file.writeframes(samples.tobytes())
    return buffer.getvalue()


def build_cue_sounds() -> dict[SoundCue, bytes]:
    return {
        "polish_started": synthesize_tone(TICK_PARTIALS, TICK_SECONDS),
        "done": synthesize_tone(BELL_PARTIALS, BELL_SECONDS),
    }


def play_wav(wav: bytes) -> None:
    try:
        winsound.PlaySound(wav, winsound.SND_MEMORY)
    except RuntimeError as error:
        logger.error(f"Sound cue failed: {error}")


def play_sound_cue(sounds: dict[SoundCue, bytes], cue: SoundCue) -> None:
    # winsound cannot play from memory asynchronously, so a thread keeps the caller unblocked.
    threading.Thread(target=play_wav, args=(sounds[cue],), daemon=True).start()
