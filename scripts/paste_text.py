#!/usr/bin/env python3
import ctypes
from ctypes import wintypes
from typing import Callable

import pyperclip

INPUT_KEYBOARD = 1
VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002

KeyStroke = tuple[int, int]  # (virtual key, flags)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class INPUT_UNION(ctypes.Union):
    # MOUSEINPUT is the largest member; without it sizeof(INPUT) is wrong and SendInput rejects the batch.
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


def build_paste_strokes() -> list[KeyStroke]:
    return [(VK_CONTROL, 0), (VK_V, 0), (VK_V, KEYEVENTF_KEYUP), (VK_CONTROL, KEYEVENTF_KEYUP)]


def send_key_strokes(strokes: list[KeyStroke]) -> None:
    inputs = (INPUT * len(strokes))(*(
        INPUT(INPUT_KEYBOARD, INPUT_UNION(ki=KEYBDINPUT(vk, 0, flags, 0, 0))) for vk, flags in strokes
    ))
    # One SendInput call is inserted atomically, so a key the user presses cannot split Ctrl from V.
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    sent = user32.SendInput(len(strokes), inputs, ctypes.sizeof(INPUT))
    if sent != len(strokes):
        raise RuntimeError(f"SendInput delivered {sent}/{len(strokes)} keys (error {ctypes.get_last_error()})")


def paste_text(
    text: str,
    copy: Callable[[str], None] = pyperclip.copy,
    send_strokes: Callable[[list[KeyStroke]], None] = send_key_strokes
) -> None:
    # Pasting (not typing) keeps apps' autocomplete and auto-closing brackets out of the text,
    # and leaves the dictation on the clipboard if the click landed somewhere that ignores Ctrl+V.
    copy(text)
    send_strokes(build_paste_strokes())
