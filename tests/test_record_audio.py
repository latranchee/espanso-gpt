import io
import unittest
import wave

from record_audio import SAMPLE_RATE_HZ, encode_wav


def read_wav(wav_bytes: bytes) -> wave.Wave_read:
    return wave.open(io.BytesIO(wav_bytes), "rb")


class EncodeWavTest(unittest.TestCase):
    def test_uses_stt_sample_rate(self) -> None:
        self.assertEqual(read_wav(encode_wav(b"\x00\x00" * 160)).getframerate(), SAMPLE_RATE_HZ)

    def test_is_mono(self) -> None:
        self.assertEqual(read_wav(encode_wav(b"\x00\x00" * 160)).getnchannels(), 1)

    def test_frame_count_matches_16_bit_samples(self) -> None:
        self.assertEqual(read_wav(encode_wav(b"\x00\x00" * 160)).getnframes(), 160)

    def test_empty_audio_has_zero_frames(self) -> None:
        self.assertEqual(read_wav(encode_wav(b"")).getnframes(), 0)


if __name__ == "__main__":
    unittest.main()
