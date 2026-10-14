#!/usr/bin/env python3
import ctypes
import functools
import itertools
import queue
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterator, Literal

from pynput import keyboard, mouse

import logger
from clean_transcript import clean_transcript
from next_dictation_draft import (
    EMPTY_DRAFT,
    DictationDraft,
    close_live_speech,
    next_dictation_draft,
    open_live_speech,
    polish_draft,
    render_draft,
)
from next_hotkey_state import IDLE_STATE, HotkeyEvent, HotkeyState, next_hotkey_state
from paste_text import paste_text
from play_sound_cue import SoundCue, build_cue_sounds, play_sound_cue
from read_screen_metrics import enable_dpi_awareness
from record_audio import start_recording, stop_recording
from render_bubble import HIDDEN_VIEW, BubbleView
from run_bubble_ui import run_bubble_ui
from stream_transcription import AudioItem, TranscriptEvent, stream_transcription

HOTKEY_VK_CODE = 0x77  # F8
CANCEL_VK_CODE = 0x1B  # Escape
KEY_DOWN_MESSAGES = (0x0100, 0x0104)  # WM_KEYDOWN, WM_SYSKEYDOWN
INJECTED_KEY_FLAGS = 0x10 | 0x02  # LLKHF_INJECTED | LLKHF_LOWER_IL_INJECTED
MIN_HOLD_SECONDS = 0.4
AUTO_STOP_SILENCE_SECONDS = 60
TICK_SECONDS = 1.0
# Long enough for the clicked app to take focus and place its caret before Ctrl+V arrives.
PASTE_DELAY_SECONDS = 0.15
# Toggled is hands-free: F8 is up, so a failure must not wait for a release that already happened.
KEY_HELD_PHASES = ("holding", "stopping", "cancelled")
SINGLE_INSTANCE_MUTEX = "Local\\espanso_push_to_talk"
ERROR_ALREADY_EXISTS = 183
ERROR_VIEW = BubbleView("error", "Dictation failed", "", "Details in logs/push_to_talk.log")

KeyAction = Literal["hotkey_down", "hotkey_up", "cancel", "swallow"]


@dataclass(frozen=True)
class KeyInput:
    kind: HotkeyEvent
    at: float


@dataclass(frozen=True)
class CancelPressed:
    pass


@dataclass(frozen=True)
class MouseReleased:
    pass


@dataclass(frozen=True)
class PasteDue:
    dictation_id: int


@dataclass(frozen=True)
class TranscriptUpdate:
    stream_id: int
    event: TranscriptEvent


@dataclass(frozen=True)
class StreamEnded:
    stream_id: int
    error: str | None


@dataclass(frozen=True)
class PolishReady:
    dictation_id: int
    source: str
    polished: str


@dataclass(frozen=True)
class Tick:
    pass


ControllerEvent = (
    KeyInput | CancelPressed | MouseReleased | PasteDue | TranscriptUpdate | StreamEnded | PolishReady | Tick
)


@dataclass(frozen=True)
class LiveStream:
    stream_id: int
    microphone: Any
    audio_items: "queue.Queue[AudioItem]"


@dataclass(frozen=True)
class Dictation:
    dictation_id: int
    draft: DictationDraft = EMPTY_DRAFT
    open_streams: frozenset[int] = frozenset()
    polishing: str | None = None
    polished: str = ""
    paste_requested: bool = False


@dataclass(frozen=True)
class ControllerState:
    hotkey: HotkeyState = IDLE_STATE
    dictation: Dictation | None = None
    live_stream: LiveStream | None = None
    last_speech_at: float = 0.0


def polish_safely(transcript: str, polish: Callable[[str], str]) -> str:
    try:
        return polish(transcript)
    except Exception as error:
        logger.error(f"Polish failed, keeping transcript: {error}")
        return transcript


def schedule_later(delay_seconds: float, action: Callable[[], None]) -> None:
    timer = threading.Timer(delay_seconds, action)
    timer.daemon = True
    timer.start()


@dataclass(frozen=True)
class Effects:
    events: "queue.Queue[ControllerEvent]"
    view_updates: "queue.Queue[BubbleView]"
    bubble_visible: threading.Event = field(default_factory=threading.Event)
    ids: Iterator[int] = field(default_factory=itertools.count)
    start_microphone: Callable[[Callable[[bytes], None]], Any] = start_recording
    stop_microphone: Callable[[Any], None] = stop_recording
    transcribe: Callable[..., None] = stream_transcription
    polish: Callable[[str], str] = clean_transcript
    paste: Callable[[str], None] = paste_text
    schedule: Callable[[float, Callable[[], None]], None] = schedule_later
    play_cue: Callable[[SoundCue], None] = lambda cue: None
    clock: Callable[[], float] = time.monotonic


def acquire_single_instance_mutex() -> int | None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return None
    return handle


def classify_key_message(message: int, vk_code: int, flags: int, bubble_visible: bool) -> KeyAction | None:
    if flags & INJECTED_KEY_FLAGS:
        return None
    is_down = message in KEY_DOWN_MESSAGES
    if vk_code == HOTKEY_VK_CODE:
        return "hotkey_down" if is_down else "hotkey_up"
    # Escape belongs to the bubble only while it is on screen; otherwise apps get it as usual.
    if vk_code == CANCEL_VK_CODE and bubble_visible:
        return "cancel" if is_down else "swallow"
    return None


def build_input_listeners(
    events: "queue.Queue[ControllerEvent]", bubble_visible: threading.Event
) -> tuple[keyboard.Listener, mouse.Listener]:
    # Hook callbacks must return fast or Windows silently drops the hook, so only enqueue here.
    def capture_key(message: int, data: Any) -> bool:
        action = classify_key_message(message, data.vkCode, data.flags, bubble_visible.is_set())
        if action is None:
            return True
        if action == "cancel":
            events.put(CancelPressed())
        elif action != "swallow":
            events.put(KeyInput(action, time.monotonic()))
        # Swallowed so apps never see F8 (Excel extend mode, debugger continue) or the bubble's Escape.
        key_listener.suppress_event()
        return False

    def on_click(x: int, y: int, button: Any, pressed: bool, injected: bool) -> None:
        if button == mouse.Button.left and not pressed and not injected:
            events.put(MouseReleased())

    key_listener = keyboard.Listener(win32_event_filter=capture_key)
    return key_listener, mouse.Listener(on_click=on_click)


def run_live_stream(stream_id: int, audio_items: "queue.Queue[AudioItem]", effects: Effects) -> None:
    try:
        effects.transcribe(audio_items, lambda event: effects.events.put(TranscriptUpdate(stream_id, event)))
        effects.events.put(StreamEnded(stream_id, None))
    except Exception as error:
        effects.events.put(StreamEnded(stream_id, str(error)))


def run_polish(dictation_id: int, source: str, effects: Effects) -> None:
    logger.info(f"Transcript: {source}")
    started = time.monotonic()
    polished = polish_safely(source, effects.polish)
    logger.info(f"Polished in {time.monotonic() - started:.1f}s: {polished}")
    effects.events.put(PolishReady(dictation_id, source, polished))


def start_daemon_thread(target: Callable[..., None], *args: Any) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


def stop_live_stream(live_stream: LiveStream | None, final_item: AudioItem, effects: Effects) -> None:
    if live_stream is None:
        return
    effects.stop_microphone(live_stream.microphone)
    live_stream.audio_items.put(final_item)


def cancel_hotkey(state: ControllerState, effects: Effects) -> HotkeyState:
    return next_hotkey_state(state.hotkey, "cancel", effects.clock(), MIN_HOLD_SECONDS)[0]


def abort_dictation(state: ControllerState, effects: Effects) -> ControllerState:
    stop_live_stream(state.live_stream, "abort", effects)
    return replace(state, dictation=None, live_stream=None, hotkey=cancel_hotkey(state, effects))


def start_live_stream(state: ControllerState, effects: Effects) -> ControllerState:
    # Pressing F8 again before pasting keeps adding to the same bubble.
    dictation = state.dictation or Dictation(next(effects.ids))
    stream_id = next(effects.ids)
    audio_items: "queue.Queue[AudioItem]" = queue.Queue()
    microphone = effects.start_microphone(audio_items.put)
    start_daemon_thread(run_live_stream, stream_id, audio_items, effects)
    dictation = replace(
        dictation,
        draft=open_live_speech(dictation.draft, stream_id),
        open_streams=dictation.open_streams | {stream_id},
    )
    return replace(state, dictation=dictation, live_stream=LiveStream(stream_id, microphone, audio_items))


def handle_key_input(state: ControllerState, key: KeyInput, effects: Effects) -> ControllerState:
    hotkey, action = next_hotkey_state(state.hotkey, key.kind, key.at, MIN_HOLD_SECONDS)
    state = replace(state, hotkey=hotkey)
    if action == "start":
        return start_live_stream(replace(state, last_speech_at=effects.clock()), effects)
    if action == "finish":
        stop_live_stream(state.live_stream, "done", effects)
        return replace(state, live_stream=None)
    return state


def handle_tick(state: ControllerState, effects: Effects) -> ControllerState:
    now = effects.clock()
    if state.hotkey.phase != "toggled" or now - state.last_speech_at < AUTO_STOP_SILENCE_SECONDS:
        return state
    # Hands-free mode is easy to forget, and a forgotten one keeps streaming the room to xAI.
    logger.info(f"No speech for {AUTO_STOP_SILENCE_SECONDS}s, stopping hands-free dictation")
    return handle_key_input(state, KeyInput("silence_timeout", now), effects)


def handle_mouse_released(state: ControllerState, effects: Effects) -> ControllerState:
    dictation = state.dictation
    # Clicks while listening are just the user working; only a click after stopping means "paste here".
    if dictation is None or state.live_stream is not None:
        return state
    due = PasteDue(dictation.dictation_id)
    effects.schedule(PASTE_DELAY_SECONDS, lambda: effects.events.put(due))
    return state


def handle_paste_due(state: ControllerState, due: PasteDue) -> ControllerState:
    dictation = state.dictation
    if dictation is None or dictation.dictation_id != due.dictation_id or state.live_stream is not None:
        return state
    return replace(state, dictation=replace(dictation, paste_requested=True))


def handle_transcript_update(state: ControllerState, update: TranscriptUpdate, effects: Effects) -> ControllerState:
    dictation = state.dictation
    if dictation is None or update.stream_id not in dictation.open_streams:
        return state
    if update.event.text:
        state = replace(state, last_speech_at=effects.clock())
    draft, _ = next_dictation_draft(dictation.draft, update.stream_id, update.event)
    return replace(state, dictation=replace(dictation, draft=draft))


def handle_stream_ended(state: ControllerState, ended: StreamEnded, effects: Effects) -> ControllerState:
    if state.live_stream is not None and state.live_stream.stream_id == ended.stream_id:
        effects.stop_microphone(state.live_stream.microphone)
        state = replace(state, live_stream=None, hotkey=cancel_hotkey(state, effects))
    dictation = state.dictation
    if dictation is None or ended.stream_id not in dictation.open_streams:
        return state
    draft, _ = close_live_speech(dictation.draft, ended.stream_id)
    dictation = replace(dictation, draft=draft, open_streams=dictation.open_streams - {ended.stream_id})
    return replace(state, dictation=dictation)


def handle_polish_ready(state: ControllerState, ready: PolishReady) -> ControllerState:
    dictation = state.dictation
    if dictation is None or dictation.dictation_id != ready.dictation_id:
        return state
    if render_draft(dictation.draft) != ready.source:
        # More speech arrived while Luna worked; the next stop polishes everything again.
        return replace(state, dictation=replace(dictation, polishing=None))
    draft = polish_draft(dictation.draft, ready.polished)
    polished = render_draft(draft)
    return replace(state, dictation=replace(dictation, draft=draft, polishing=None, polished=polished))


def is_settling(state: ControllerState) -> bool:
    dictation = state.dictation
    if state.live_stream is not None or dictation is None:
        return False
    return bool(dictation.open_streams) or dictation.polishing is not None


def is_ready(state: ControllerState) -> bool:
    return state.dictation is not None and state.live_stream is None and not is_settling(state)


def start_polish(state: ControllerState, text: str, effects: Effects) -> ControllerState:
    dictation = state.dictation
    start_daemon_thread(run_polish, dictation.dictation_id, text, effects)
    return replace(state, dictation=replace(dictation, polishing=text))


def settle_dictation(state: ControllerState, effects: Effects) -> ControllerState:
    if not is_ready(state):
        return state
    text = render_draft(state.dictation.draft)
    if not text:
        return replace(state, dictation=None)
    # Every stop gets one Luna pass over the whole text: a per-sentence gate skipped grammar and
    # context errors ("mon super application") because they read as fluent.
    if text != state.dictation.polished:
        return start_polish(state, text, effects)
    if not state.dictation.paste_requested:
        return state
    effects.paste(text)
    logger.info(f"Pasted {len(text)} characters")
    return replace(state, dictation=None)


def route_controller_event(state: ControllerState, event: ControllerEvent, effects: Effects) -> ControllerState:
    if isinstance(event, KeyInput):
        return handle_key_input(state, event, effects)
    if isinstance(event, CancelPressed):
        return abort_dictation(state, effects)
    if isinstance(event, MouseReleased):
        return handle_mouse_released(state, effects)
    if isinstance(event, PasteDue):
        return handle_paste_due(state, event)
    if isinstance(event, TranscriptUpdate):
        return handle_transcript_update(state, event, effects)
    if isinstance(event, StreamEnded):
        return handle_stream_ended(state, event, effects)
    if isinstance(event, Tick):
        return handle_tick(state, effects)
    return handle_polish_ready(state, event)


def handle_controller_event(state: ControllerState, event: ControllerEvent, effects: Effects) -> ControllerState:
    return settle_dictation(route_controller_event(state, event, effects), effects)


def describe_bubble(state: ControllerState) -> BubbleView:
    dictation = state.dictation
    if dictation is None:
        return HIDDEN_VIEW
    text = render_draft(dictation.draft)
    if state.live_stream is not None:
        hint = "tap F8 to stop" if state.hotkey.phase == "toggled" else "release F8 to stop"
        return BubbleView("listening", "Listening", hint, text)
    pending_hint = "pastes when done" if dictation.paste_requested else "Esc to cancel"
    if dictation.polishing is not None:
        return BubbleView("polishing", "Polishing", pending_hint, text)
    if is_settling(state):
        return BubbleView("finishing", "Finishing", pending_hint, text)
    return BubbleView("ready", "Ready", "click to paste · Esc to cancel", text)


def choose_sound_cue(before: ControllerState, after: ControllerState, event: ControllerEvent) -> SoundCue | None:
    previous, current = before.dictation, after.dictation
    # Cues only play once listening stops: the microphone is off and the user is waiting on the result.
    if previous is None or after.live_stream is not None or isinstance(event, CancelPressed):
        return None
    became_final = is_settling(before) and not is_settling(after)
    if became_final and render_draft(previous.draft):
        return "done"
    if current is not None and current.dictation_id == previous.dictation_id:
        if previous.polishing is None and current.polishing is not None:
            return "polish_started"
    return None


def publish_feedback(
    before: ControllerState, after: ControllerState, event: ControllerEvent, effects: Effects, failed: bool = False
) -> None:
    # A failure also empties the state, which would otherwise read as "finished" and ring the bell.
    cue = None if failed else choose_sound_cue(before, after, event)
    if cue is not None:
        effects.play_cue(cue)
    view = describe_bubble(after)
    if view != describe_bubble(before):
        effects.view_updates.put(view)
    if view.phase == "hidden":
        effects.bubble_visible.clear()
    else:
        effects.bubble_visible.set()


def describe_failure(state: ControllerState, event: ControllerEvent) -> str | None:
    if not isinstance(event, StreamEnded) or not event.error:
        return None
    # An aborted stream can still fail later; that is no longer the user's problem.
    if state.dictation is None or event.stream_id not in state.dictation.open_streams:
        return None
    return f"Transcription stream failed: {event.error}"


def recover_from_failure(state: ControllerState, event: ControllerEvent, effects: Effects) -> ControllerState:
    is_key = isinstance(event, KeyInput)
    still_holding = (is_key and event.kind == "hotkey_down") or (
        state.hotkey.phase in KEY_HELD_PHASES and not (is_key and event.kind == "hotkey_up")
    )
    # Cancelled ignores F8 key repeat until release, so a failing start is not retried 30 times a second.
    hotkey = HotkeyState("cancelled") if still_holding else IDLE_STATE
    try:
        stop_live_stream(state.live_stream, "abort", effects)
    except Exception as error:
        logger.error(f"Abort after failure also failed: {error}")
    return ControllerState(hotkey=hotkey)


def next_controller_event(events: "queue.Queue[ControllerEvent]") -> ControllerEvent:
    try:
        return events.get(timeout=TICK_SECONDS)
    except queue.Empty:
        return Tick()


def run_dictation_controller(effects: Effects) -> None:
    state = ControllerState()
    while True:
        event = next_controller_event(effects.events)
        before = state
        failure = describe_failure(state, event)
        try:
            state = handle_controller_event(state, event, effects)
        except Exception as error:
            failure = f"Dictation failed on {type(event).__name__}: {error}"
            state = recover_from_failure(state, event, effects)

        publish_feedback(before, state, event, effects, failed=failure is not None)
        if failure:
            logger.error(failure)
            effects.view_updates.put(ERROR_VIEW)


def push_to_talk() -> None:
    if acquire_single_instance_mutex() is None:
        return
    enable_dpi_awareness()
    logger.init_logger("push_to_talk")

    effects = Effects(
        events=queue.Queue(),
        view_updates=queue.Queue(),
        play_cue=functools.partial(play_sound_cue, build_cue_sounds()),
    )
    start_daemon_thread(run_dictation_controller, effects)
    for listener in build_input_listeners(effects.events, effects.bubble_visible):
        listener.start()

    logger.info("Push-to-talk ready: tap F8 for hands-free, or hold it to talk")
    run_bubble_ui(effects.view_updates)


if __name__ == "__main__":
    push_to_talk()
