import unittest

from push_to_talk import HOTKEY_VK_CODE, classify_hotkey_message, dictate_text

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
VK_F9 = 0x78
LLKHF_INJECTED = 0x10


def failing_clean(transcript: str) -> str:
    raise AssertionError("cleanup should not run")


class ClassifyHotkeyMessageTest(unittest.TestCase):
    def test_f8_key_down_is_hotkey_down(self) -> None:
        self.assertEqual(classify_hotkey_message(WM_KEYDOWN, HOTKEY_VK_CODE, 0), "hotkey_down")

    def test_f8_with_alt_held_is_hotkey_down(self) -> None:
        self.assertEqual(classify_hotkey_message(WM_SYSKEYDOWN, HOTKEY_VK_CODE, 0), "hotkey_down")

    def test_f8_key_up_is_hotkey_up(self) -> None:
        self.assertEqual(classify_hotkey_message(WM_KEYUP, HOTKEY_VK_CODE, 0), "hotkey_up")

    def test_f8_with_alt_released_is_hotkey_up(self) -> None:
        self.assertEqual(classify_hotkey_message(WM_SYSKEYUP, HOTKEY_VK_CODE, 0), "hotkey_up")

    def test_neighbouring_function_key_is_ignored(self) -> None:
        self.assertIsNone(classify_hotkey_message(WM_KEYDOWN, VK_F9, 0))

    def test_injected_f8_is_ignored(self) -> None:
        self.assertIsNone(classify_hotkey_message(WM_KEYDOWN, HOTKEY_VK_CODE, LLKHF_INJECTED))


class DictateTextTest(unittest.TestCase):
    def test_returns_cleaned_transcript(self) -> None:
        text = dictate_text(b"wav", transcribe=lambda _: "um hi", clean=lambda _: "Hi.")
        self.assertEqual(text, "Hi.")

    def test_silence_skips_cleanup(self) -> None:
        self.assertEqual(dictate_text(b"wav", transcribe=lambda _: "", clean=failing_clean), "")


if __name__ == "__main__":
    unittest.main()
