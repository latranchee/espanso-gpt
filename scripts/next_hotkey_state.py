#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Literal

HotkeyPhase = Literal["idle", "holding", "toggled", "stopping", "cancelled"]
HotkeyEvent = Literal["hotkey_down", "hotkey_up", "silence_timeout", "cancel"]
HotkeyAction = Literal["start", "finish"] | None


@dataclass(frozen=True)
class HotkeyState:
    phase: HotkeyPhase = "idle"
    pressed_at: float = 0.0


IDLE_STATE = HotkeyState()


def next_holding_state(
    state: HotkeyState, event: HotkeyEvent, now: float, min_hold_seconds: float
) -> tuple[HotkeyState, HotkeyAction]:
    if event == "cancel":
        # F8 is still down: wait for its release so the release cannot be read as a new tap.
        return HotkeyState("cancelled", state.pressed_at), None
    if event == "hotkey_up":
        if now - state.pressed_at < min_hold_seconds:
            # A quick tap means hands-free: keep listening until the next press.
            return HotkeyState("toggled", state.pressed_at), None
        return IDLE_STATE, "finish"
    return state, None


def next_toggled_state(state: HotkeyState, event: HotkeyEvent) -> tuple[HotkeyState, HotkeyAction]:
    if event == "hotkey_down":
        # Stop on press, then swallow the matching release so it cannot start anything.
        return HotkeyState("stopping", state.pressed_at), "finish"
    if event == "silence_timeout":
        return IDLE_STATE, "finish"
    if event == "cancel":
        return IDLE_STATE, None
    return state, None


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
        return next_holding_state(state, event, now, min_hold_seconds)
    if state.phase == "toggled":
        return next_toggled_state(state, event)

    if event == "hotkey_up":
        return IDLE_STATE, None
    return state, None
