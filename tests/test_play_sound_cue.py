import io
import unittest
import wave
from array import array

from play_sound_cue import BELL_PARTIALS, Partial, build_cue_sounds, synthesize_tone

SAMPLE_RATE_HZ = 8000


def read_samples(wav: bytes) -> array:
    with wave.open(io.BytesIO(wav), "rb") as wav_file:
        return array("h", wav_file.readframes(wav_file.getnframes()))


def peak(samples: array) -> int:
    return max(abs(sample) for sample in samples)


class SynthesizeToneTest(unittest.TestCase):
    def test_length_matches_duration(self) -> None:
        wav = synthesize_tone(BELL_PARTIALS, 0.5, sample_rate_hz=SAMPLE_RATE_HZ)
        self.assertEqual(len(read_samples(wav)), 4000)

    def test_is_mono(self) -> None:
        wav = synthesize_tone(BELL_PARTIALS, 0.1, sample_rate_hz=SAMPLE_RATE_HZ)
        self.assertEqual(wave.open(io.BytesIO(wav), "rb").getnchannels(), 1)

    def test_bell_fades_out(self) -> None:
        samples = read_samples(synthesize_tone(BELL_PARTIALS, 1.2, sample_rate_hz=SAMPLE_RATE_HZ))
        self.assertLess(peak(samples[-800:]), peak(samples[:800]) / 10)

    def test_loud_partials_are_clipped_not_wrapped(self) -> None:
        wav = synthesize_tone((Partial(440.0, 10.0, 0.0),), 0.1, volume=1.0, sample_rate_hz=SAMPLE_RATE_HZ)
        self.assertEqual(peak(read_samples(wav)), 32767)

    def test_no_partials_is_silence(self) -> None:
        self.assertEqual(peak(read_samples(synthesize_tone((), 0.1, sample_rate_hz=SAMPLE_RATE_HZ))), 0)


class BuildCueSoundsTest(unittest.TestCase):
    def test_has_a_sound_for_every_cue(self) -> None:
        self.assertEqual(set(build_cue_sounds()), {"polish_started", "done"})


if __name__ == "__main__":
    unittest.main()
