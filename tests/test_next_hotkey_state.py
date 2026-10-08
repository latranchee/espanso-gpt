import unittest

from next_hotkey_state import IDLE_STATE, HotkeyState, next_hotkey_state

MIN_HOLD = 0.4
HOLDING = HotkeyState("holding", 10.0)
CANCELLED = HotkeyState("cancelled", 10.0)


class NextHotkeyStateTest(unittest.TestCase):
    def test_hotkey_down_from_idle_starts_recording(self) -> None:
        self.assertEqual(next_hotkey_state(IDLE_STATE, "hotkey_down", 10.0, MIN_HOLD)[1], "start")

    def test_hotkey_down_from_idle_records_press_time(self) -> None:
        self.assertEqual(next_hotkey_state(IDLE_STATE, "hotkey_down", 10.0, MIN_HOLD)[0], HOLDING)

    def test_other_key_while_idle_is_ignored(self) -> None:
        self.assertEqual(next_hotkey_state(IDLE_STATE, "other_key_down", 10.0, MIN_HOLD), (IDLE_STATE, None))

    def test_hotkey_up_while_idle_is_ignored(self) -> None:
        self.assertEqual(next_hotkey_state(IDLE_STATE, "hotkey_up", 10.0, MIN_HOLD), (IDLE_STATE, None))

    def test_key_repeat_while_holding_keeps_original_press_time(self) -> None:
        self.assertEqual(next_hotkey_state(HOLDING, "hotkey_down", 10.3, MIN_HOLD), (HOLDING, None))

    def test_other_key_while_holding_discards_recording(self) -> None:
        self.assertEqual(next_hotkey_state(HOLDING, "other_key_down", 10.1, MIN_HOLD)[1], "discard")

    def test_other_key_while_holding_cancels(self) -> None:
        self.assertEqual(next_hotkey_state(HOLDING, "other_key_down", 10.1, MIN_HOLD)[0], CANCELLED)

    def test_release_after_min_hold_finishes(self) -> None:
        self.assertEqual(next_hotkey_state(HOLDING, "hotkey_up", 12.0, MIN_HOLD), (IDLE_STATE, "finish"))

    def test_release_exactly_at_min_hold_finishes(self) -> None:
        self.assertEqual(next_hotkey_state(HOLDING, "hotkey_up", 10.0 + MIN_HOLD, MIN_HOLD)[1], "finish")

    def test_quick_tap_discards_recording(self) -> None:
        self.assertEqual(next_hotkey_state(HOLDING, "hotkey_up", 10.1, MIN_HOLD), (IDLE_STATE, "discard"))

    def test_release_after_cancel_returns_to_idle_silently(self) -> None:
        self.assertEqual(next_hotkey_state(CANCELLED, "hotkey_up", 11.0, MIN_HOLD), (IDLE_STATE, None))

    def test_more_keys_after_cancel_stay_cancelled(self) -> None:
        self.assertEqual(next_hotkey_state(CANCELLED, "other_key_down", 11.0, MIN_HOLD), (CANCELLED, None))


if __name__ == "__main__":
    unittest.main()
