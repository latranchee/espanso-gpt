import ctypes
import unittest
from typing import Any

from paste_text import INPUT, KEYEVENTF_KEYUP, VK_CONTROL, VK_V, build_paste_strokes, paste_text


class BuildPasteStrokesTest(unittest.TestCase):
    def test_presses_ctrl_v_and_releases_in_reverse(self) -> None:
        self.assertEqual(
            build_paste_strokes(),
            [(VK_CONTROL, 0), (VK_V, 0), (VK_V, KEYEVENTF_KEYUP), (VK_CONTROL, KEYEVENTF_KEYUP)],
        )


class PasteTextTest(unittest.TestCase):
    def test_copies_before_sending_ctrl_v(self) -> None:
        calls: list[Any] = []
        paste_text("Bonjour", copy=lambda text: calls.append(("copy", text)), send_strokes=lambda s: calls.append("send"))
        self.assertEqual(calls, [("copy", "Bonjour"), "send"])


class InputStructTest(unittest.TestCase):
    def test_matches_windows_input_size(self) -> None:
        self.assertEqual(ctypes.sizeof(INPUT), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)


if __name__ == "__main__":
    unittest.main()
