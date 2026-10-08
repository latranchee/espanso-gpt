#!/usr/bin/env python3
import ctypes
import queue
import threading
import time
import tkinter
from typing import Any, Callable

import pyperclip
from pynput import keyboard

import logger
from clean_transcript import clean_transcript
from next_hotkey_state import IDLE_STATE, HotkeyAction, HotkeyEvent, next_hotkey_state
from record_audio import Recording, start_recording, stop_recording
from transcribe_audio import transcribe_audio

HOTKEY_VK_CODE = 0x77  # F8
KEY_DOWN_MESSAGES = (0x0100, 0x0104)  # WM_KEYDOWN, WM_SYSKEYDOWN
INJECTED_KEY_FLAGS = 0x10 | 0x02  # LLKHF_INJECTED | LLKHF_LOWER_IL_INJECTED
MIN_HOLD_SECONDS = 0.4
UI_POLL_MS = 50
FLASH_MS = 4000
OVERLAY_ALPHA = 0.92
OVERLAY_BOTTOM_MARGIN_PX = 90
LISTENING_COLOR = "#c62828"
BUSY_COLOR = "#37474f"
ERROR_COLOR = "#e65100"
SINGLE_INSTANCE_MUTEX = "Local\\espanso_push_to_talk"
ERROR_ALREADY_EXISTS = 183
GWL_EXSTYLE = -20
# NOACTIVATE | TOOLWINDOW | TRANSPARENT | LAYERED: the overlay must never take focus,
# otherwise the transcript gets pasted into it instead of the user's window.
OVERLAY_EX_STYLE = 0x08000000 | 0x00000080 | 0x00000020 | 0x00080000

KeyEvent = tuple[HotkeyEvent, float]
UiUpdate = tuple[str, str, str]
HIDE_UPDATE: UiUpdate = ("hide", "", "")


def acquire_single_instance_mutex() -> int | None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return None
    return handle


def classify_hotkey_message(message: int, vk_code: int, flags: int) -> HotkeyEvent | None:
    if vk_code != HOTKEY_VK_CODE or flags & INJECTED_KEY_FLAGS:
        return None
    return "hotkey_down" if message in KEY_DOWN_MESSAGES else "hotkey_up"


def build_key_listener(key_events: "queue.Queue[KeyEvent]") -> keyboard.Listener:
    # Hook callbacks must return fast or Windows silently drops the hook, so only enqueue here.
    def on_press(key: Any, injected: bool) -> None:
        if not injected:
            key_events.put(("other_key_down", time.monotonic()))

    def capture_hotkey(message: int, data: Any) -> bool:
        event = classify_hotkey_message(message, data.vkCode, data.flags)
        if event is None:
            return True
        key_events.put((event, time.monotonic()))
        # Swallow F8 so apps never see it or its key repeat (Excel extend mode, debugger continue).
        listener.suppress_event()
        return False

    listener = keyboard.Listener(on_press=on_press, win32_event_filter=capture_hotkey)
    return listener


def start_recording_safely(ui_updates: "queue.Queue[UiUpdate]") -> Recording | None:
    try:
        return start_recording()
    except Exception as error:
        logger.error(f"Microphone failed to start: {error}")
        ui_updates.put(("flash", "Microphone unavailable", ERROR_COLOR))
        return None


def apply_hotkey_action(
    action: HotkeyAction,
    recording: Recording | None,
    jobs: "queue.Queue[bytes]",
    ui_updates: "queue.Queue[UiUpdate]"
) -> Recording | None:
    if action == "start":
        ui_updates.put(("show_after_hold", "● Listening", LISTENING_COLOR))
        return start_recording_safely(ui_updates)
    if recording is None:
        return None

    wav_bytes = stop_recording(recording)
    if action == "finish":
        jobs.put(wav_bytes)
        ui_updates.put(("show", "Transcribing…", BUSY_COLOR))
    else:
        ui_updates.put(HIDE_UPDATE)
    return None


def run_hotkey_controller(
    key_events: "queue.Queue[KeyEvent]",
    jobs: "queue.Queue[bytes]",
    ui_updates: "queue.Queue[UiUpdate]"
) -> None:
    state, recording = IDLE_STATE, None
    while True:
        event, timestamp = key_events.get()
        state, action = next_hotkey_state(state, event, timestamp, MIN_HOLD_SECONDS)
        if action is None:
            continue
        try:
            recording = apply_hotkey_action(action, recording, jobs, ui_updates)
        except Exception as error:
            logger.error(f"Hotkey action '{action}' failed: {error}")
            state, recording = IDLE_STATE, None
            ui_updates.put(("flash", "Recording failed, see logs", ERROR_COLOR))


def dictate_text(
    wav_bytes: bytes,
    transcribe: Callable[[bytes], str] = transcribe_audio,
    clean: Callable[[str], str] = clean_transcript
) -> str:
    transcript = transcribe(wav_bytes)
    logger.info(f"Transcript: {transcript}")
    if not transcript:
        return ""
    return clean(transcript)


def paste_text(text: str, keyboard_controller: keyboard.Controller) -> None:
    pyperclip.copy(text)
    with keyboard_controller.pressed(keyboard.Key.ctrl):
        keyboard_controller.tap("v")


def run_transcription_worker(
    jobs: "queue.Queue[bytes]",
    ui_updates: "queue.Queue[UiUpdate]",
    keyboard_controller: keyboard.Controller
) -> None:
    while True:
        wav_bytes = jobs.get()
        try:
            text = dictate_text(wav_bytes)
            if text:
                paste_text(text, keyboard_controller)
            ui_updates.put(HIDE_UPDATE)
        except Exception as error:
            logger.error(f"Dictation failed: {error}")
            ui_updates.put(("flash", "Dictation failed, see logs", ERROR_COLOR))


def create_overlay() -> tuple[tkinter.Tk, tkinter.Label]:
    root = tkinter.Tk()
    root.withdraw()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.0)
    label = tkinter.Label(root, font=("Segoe UI", 11, "bold"), fg="white", padx=16, pady=6)
    label.pack()
    root.update_idletasks()
    apply_overlay_window_style(root)
    root.deiconify()
    return root, label


def apply_overlay_window_style(root: tkinter.Tk) -> None:
    user32 = ctypes.windll.user32
    window_handle = user32.GetParent(root.winfo_id())
    current_style = user32.GetWindowLongW(window_handle, GWL_EXSTYLE)
    user32.SetWindowLongW(window_handle, GWL_EXSTYLE, current_style | OVERLAY_EX_STYLE)


def show_overlay(root: tkinter.Tk, label: tkinter.Label, text: str, color: str) -> None:
    label.config(text=text, bg=color)
    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_reqwidth()) // 2
    y = root.winfo_screenheight() - root.winfo_reqheight() - OVERLAY_BOTTOM_MARGIN_PX
    root.geometry(f"+{x}+{y}")
    root.attributes("-topmost", True)
    root.attributes("-alpha", OVERLAY_ALPHA)


def hide_overlay(root: tkinter.Tk) -> None:
    root.attributes("-alpha", 0.0)


def run_if_current(overlay: dict[str, int], generation: int, action: Callable[[], None]) -> None:
    if overlay["generation"] == generation:
        action()


def apply_ui_update(
    root: tkinter.Tk, label: tkinter.Label, update: UiUpdate, overlay: dict[str, int]
) -> None:
    kind, text, color = update
    overlay["generation"] += 1
    generation = overlay["generation"]
    show = lambda: show_overlay(root, label, text, color)

    if kind == "hide":
        hide_overlay(root)
    elif kind == "show":
        show()
    elif kind == "show_after_hold":
        root.after(int(MIN_HOLD_SECONDS * 1000), run_if_current, overlay, generation, show)
    elif kind == "flash":
        show()
        root.after(FLASH_MS, run_if_current, overlay, generation, lambda: hide_overlay(root))


def poll_ui_updates(
    root: tkinter.Tk,
    label: tkinter.Label,
    ui_updates: "queue.Queue[UiUpdate]",
    overlay: dict[str, int]
) -> None:
    while not ui_updates.empty():
        apply_ui_update(root, label, ui_updates.get_nowait(), overlay)
    root.after(UI_POLL_MS, poll_ui_updates, root, label, ui_updates, overlay)


def start_daemon_thread(target: Callable[..., None], *args: Any) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


def push_to_talk() -> None:
    if acquire_single_instance_mutex() is None:
        return
    logger.init_logger("push_to_talk")

    key_events: "queue.Queue[KeyEvent]" = queue.Queue()
    jobs: "queue.Queue[bytes]" = queue.Queue()
    ui_updates: "queue.Queue[UiUpdate]" = queue.Queue()
    start_daemon_thread(run_hotkey_controller, key_events, jobs, ui_updates)
    start_daemon_thread(run_transcription_worker, jobs, ui_updates, keyboard.Controller())
    build_key_listener(key_events).start()

    root, label = create_overlay()
    poll_ui_updates(root, label, ui_updates, {"generation": 0})
    logger.info("Push-to-talk ready: hold F8 to dictate")
    root.mainloop()


if __name__ == "__main__":
    push_to_talk()
