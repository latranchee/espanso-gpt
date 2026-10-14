import unittest

from next_hotkey_state import IDLE_STATE, HotkeyState, next_hotkey_state

MIN_HOLD = 0.4
HOLDING = HotkeyState("holding", 10.0)
TOGGLED = HotkeyState("toggled", 10.0)
STOPPING = HotkeyState("stopping", 10.0)
CANCELLED = HotkeyState("cancelled", 10.0)


class IdleTest(unittest.TestCase):
    def test_hotkey_down_starts_recording(self) -> None:
        self.assertEqual(next_hotkey_state(IDLE_STATE, "hotkey_down", 10.0, MIN_HOLD)[1], "start")

    def test_hotkey_down_records_press_time(self) -> None:
        self.assertEqual(next_hotkey_state(IDLE_STATE, "hotkey_down", 10.0, MIN_HOLD)[0], HOLDING)

    def test_hotkey_up_is_ignored(self) -> None:
        self.assertEqual(next_hotkey_state(IDLE_STATE, "hotkey_up", 10.0, MIN_HOLD), (IDLE_STATE, None))

    def test_silence_timeout_is_ignored(self) -> None:
        self.assertEqual(next_hotkey_state(IDLE_STATE, "silence_timeout", 10.0, MIN_HOLD), (IDLE_STATE, None))

    def test_cancel_is_ignored(self) -> None:
        self.assertEqual(next_hotkey_state(IDLE_STATE, "cancel", 10.0, MIN_HOLD), (IDLE_STATE, None))


class HoldingTest(unittest.TestCase):
    def test_key_repeat_keeps_original_press_time(self) -> None:
        self.assertEqual(next_hotkey_state(HOLDING, "hotkey_down", 10.3, MIN_HOLD), (HOLDING, None))

    def test_release_after_min_hold_finishes(self) -> None:
        self.assertEqual(next_hotkey_state(HOLDING, "hotkey_up", 12.0, MIN_HOLD), (IDLE_STATE, "finish"))

    def test_release_exactly_at_min_hold_finishes(self) -> None:
        self.assertEqual(next_hotkey_state(HOLDING, "hotkey_up", 10.0 + MIN_HOLD, MIN_HOLD)[1], "finish")

    def test_quick_tap_switches_to_hands_free(self) -> None:
        self.assertEqual(next_hotkey_state(HOLDING, "hotkey_up", 10.1, MIN_HOLD), (TOGGLED, None))

    def test_silence_timeout_does_not_stop_a_held_key(self) -> None:
        self.assertEqual(next_hotkey_state(HOLDING, "silence_timeout", 80.0, MIN_HOLD), (HOLDING, None))

    def test_cancel_waits_for_the_release(self) -> None:
        self.assertEqual(next_hotkey_state(HOLDING, "cancel", 10.2, MIN_HOLD), (CANCELLED, None))


class ToggledTest(unittest.TestCase):
    def test_second_press_finishes(self) -> None:
        self.assertEqual(next_hotkey_state(TOGGLED, "hotkey_down", 20.0, MIN_HOLD), (STOPPING, "finish"))

    def test_silence_timeout_finishes(self) -> None:
        self.assertEqual(next_hotkey_state(TOGGLED, "silence_timeout", 80.0, MIN_HOLD), (IDLE_STATE, "finish"))

    def test_cancel_returns_to_idle(self) -> None:
        self.assertEqual(next_hotkey_state(TOGGLED, "cancel", 20.0, MIN_HOLD), (IDLE_STATE, None))

    def test_stray_release_keeps_listening(self) -> None:
        self.assertEqual(next_hotkey_state(TOGGLED, "hotkey_up", 20.0, MIN_HOLD), (TOGGLED, None))


class WaitingForReleaseTest(unittest.TestCase):
    def test_release_after_stop_returns_to_idle_silently(self) -> None:
        self.assertEqual(next_hotkey_state(STOPPING, "hotkey_up", 20.1, MIN_HOLD), (IDLE_STATE, None))

    def test_key_repeat_after_stop_does_not_restart(self) -> None:
        self.assertEqual(next_hotkey_state(STOPPING, "hotkey_down", 20.3, MIN_HOLD), (STOPPING, None))

    def test_release_after_cancel_returns_to_idle_silently(self) -> None:
        self.assertEqual(next_hotkey_state(CANCELLED, "hotkey_up", 11.0, MIN_HOLD), (IDLE_STATE, None))

    def test_key_repeat_after_cancel_stays_cancelled(self) -> None:
        self.assertEqual(next_hotkey_state(CANCELLED, "hotkey_down", 11.0, MIN_HOLD), (CANCELLED, None))


if __name__ == "__main__":
    unittest.main()
