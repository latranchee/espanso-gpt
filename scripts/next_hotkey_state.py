#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Literal

HotkeyPhase = Literal["idle", "holding", "cancelled"]
HotkeyEvent = Literal["hotkey_down", "hotkey_up", "other_key_down"]
HotkeyAction = Literal["start", "finish", "discard"] | None


@dataclass(frozen=True)
class HotkeyState:
    phase: HotkeyPhase = "idle"
    pressed_at: float = 0.0


IDLE_STATE = HotkeyState()


def next_hotkey_state(
    state: HotkeyState,
    event: HotkeyEvent,
    now: float,
    min_hold_seconds: float
) -> tuple[HotkeyState, HotkeyAction]:
    if state.phase == "idle":
        if event == "hotkey_down":
            return HotkeyState("holding", now), "start"
        return state, None

    if state.phase == "holding":
        # Any other key while the hotkey is held aborts, so a stray keypress never pastes a half dictation.
        if event == "other_key_down":
            return HotkeyState("cancelled", state.pressed_at), "discard"
        if event == "hotkey_up":
            held_long_enough = now - state.pressed_at >= min_hold_seconds
            return IDLE_STATE, "finish" if held_long_enough else "discard"
        return state, None

    if event == "hotkey_up":
        return IDLE_STATE, None
    return state, None
