import queue
import unittest
from dataclasses import replace
from typing import Any, Callable

from next_hotkey_state import HotkeyState
from push_to_talk import (
    AUTO_STOP_SILENCE_SECONDS,
    HOTKEY_VK_CODE,
    CancelPressed,
    ControllerState,
    Dictation,
    Effects,
    KeyInput,
    MouseReleased,
    PolishReady,
    StreamEnded,
    Tick,
    TranscriptUpdate,
    classify_key_message,
    describe_bubble,
    describe_failure,
    handle_controller_event,
    publish_feedback,
    polish_safely,
    recover_from_failure,
)
from render_bubble import BubbleView
from stream_transcription import TranscriptEvent

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
VK_ESCAPE = 0x1B
VK_F9 = 0x78
LLKHF_INJECTED = 0x10


def failing_polish(transcript: str) -> str:
    raise RuntimeError("luna unavailable")


def polish_to(text: str) -> Callable[[str], str]:
    return lambda transcript: text


class FakeMicrophone:
    closed = False


class FakeDesktop:
    def __init__(self, polish: Callable[[str], str] = lambda text: text) -> None:
        self.now = 0.0
        self.pasted: list[str] = []
        self.cues: list[str] = []
        self.effects = Effects(
            events=queue.Queue(),
            view_updates=queue.Queue(),
            start_microphone=lambda on_chunk: FakeMicrophone(),
            stop_microphone=lambda microphone: None,
            transcribe=lambda audio_items, on_event: None,
            polish=polish,
            paste=self.pasted.append,
            schedule=lambda delay, action: action(),
            play_cue=self.cues.append,
            clock=lambda: self.now,
        )
        self.state = ControllerState()
        self.stream_id = -1

    def send(self, event: Any) -> "FakeDesktop":
        before = self.state
        self.state = handle_controller_event(self.state, event, self.effects)
        publish_feedback(before, self.state, event, self.effects)
        return self

    def press(self, at: float = 0.0) -> "FakeDesktop":
        self.send(KeyInput("hotkey_down", at))
        if self.state.live_stream is not None:
            self.stream_id = self.state.live_stream.stream_id
        return self

    def release(self, at: float = 1.0) -> "FakeDesktop":
        return self.send(KeyInput("hotkey_up", at))

    def tap(self, at: float = 0.0) -> "FakeDesktop":
        return self.press(at).release(at + 0.1)

    def wait(self, seconds: float) -> "FakeDesktop":
        self.now += seconds
        return self.send(Tick())

    def hear(self, kind: str, text: str) -> "FakeDesktop":
        return self.send(TranscriptUpdate(self.stream_id, TranscriptEvent(kind, text)))

    def end_stream(self) -> "FakeDesktop":
        return self.send(StreamEnded(self.stream_id, None))

    def click(self) -> "FakeDesktop":
        self.send(MouseReleased())
        return self.send_queued(lambda event: event.__class__.__name__ == "PasteDue")

    def apply_polish(self) -> "FakeDesktop":
        while True:
            event = self.effects.events.get(timeout=2)
            if isinstance(event, PolishReady):
                return self.send(event)

    def send_queued(self, wanted: Callable[[Any], bool]) -> "FakeDesktop":
        pending = []
        while not self.effects.events.empty():
            pending.append(self.effects.events.get_nowait())
        for event in pending:
            if wanted(event):
                self.send(event)
            else:
                self.effects.events.put(event)
        return self

    def dictate(self, utterance: str) -> "FakeDesktop":
        return self.stop_after(utterance).apply_polish()

    def stop_after(self, utterance: str) -> "FakeDesktop":
        return self.tap().hear("utterance_final", utterance).tap(at=5.0).end_stream()

    def bubble(self) -> BubbleView:
        return describe_bubble(self.state)


class ClassifyKeyMessageTest(unittest.TestCase):
    def test_f8_key_down_is_hotkey_down(self) -> None:
        self.assertEqual(classify_key_message(WM_KEYDOWN, HOTKEY_VK_CODE, 0, False), "hotkey_down")

    def test_f8_with_alt_held_is_hotkey_down(self) -> None:
        self.assertEqual(classify_key_message(WM_SYSKEYDOWN, HOTKEY_VK_CODE, 0, False), "hotkey_down")

    def test_f8_key_up_is_hotkey_up(self) -> None:
        self.assertEqual(classify_key_message(WM_KEYUP, HOTKEY_VK_CODE, 0, False), "hotkey_up")

    def test_f8_with_alt_released_is_hotkey_up(self) -> None:
        self.assertEqual(classify_key_message(WM_SYSKEYUP, HOTKEY_VK_CODE, 0, False), "hotkey_up")

    def test_neighbouring_function_key_is_ignored(self) -> None:
        self.assertIsNone(classify_key_message(WM_KEYDOWN, VK_F9, 0, True))

    def test_injected_f8_is_ignored(self) -> None:
        self.assertIsNone(classify_key_message(WM_KEYDOWN, HOTKEY_VK_CODE, LLKHF_INJECTED, False))

    def test_escape_cancels_while_bubble_is_visible(self) -> None:
        self.assertEqual(classify_key_message(WM_KEYDOWN, VK_ESCAPE, 0, True), "cancel")

    def test_escape_release_is_swallowed_while_bubble_is_visible(self) -> None:
        self.assertEqual(classify_key_message(WM_KEYUP, VK_ESCAPE, 0, True), "swallow")

    def test_escape_reaches_apps_without_bubble(self) -> None:
        self.assertIsNone(classify_key_message(WM_KEYDOWN, VK_ESCAPE, 0, False))


class PolishSafelyTest(unittest.TestCase):
    def test_returns_the_polished_text(self) -> None:
        self.assertEqual(polish_safely("um hi", polish=polish_to("Hi.")), "Hi.")

    def test_failed_polish_keeps_the_transcript(self) -> None:
        self.assertEqual(polish_safely("um hi", polish=failing_polish), "um hi")


class BubblePreviewTest(unittest.TestCase):
    def test_speech_shows_in_the_bubble(self) -> None:
        self.assertEqual(FakeDesktop().tap().hear("interim", "So I think").bubble().text, "So I think")

    def test_nothing_is_pasted_while_speaking(self) -> None:
        self.assertEqual(FakeDesktop().tap().hear("interim", "So I think").pasted, [])

    def test_hands_free_hint_says_how_to_stop(self) -> None:
        self.assertEqual(FakeDesktop().tap().bubble().hint, "tap F8 to stop")

    def test_held_key_hint_says_release(self) -> None:
        self.assertEqual(FakeDesktop().press().bubble().hint, "release F8 to stop")

    def test_preview_stays_raw_while_speaking(self) -> None:
        desktop = FakeDesktop(polish=polish_to("Hi.")).tap().hear("utterance_final", "um hi")
        self.assertEqual(desktop.bubble().text, "um hi")

    def test_stop_polishes_the_whole_text(self) -> None:
        desktop = FakeDesktop(polish=polish_to("Ceci est ma super application.")).tap()
        desktop.hear("utterance_final", "Ceci est mon super").hear("utterance_final", "application.")
        self.assertEqual(desktop.tap(at=5.0).end_stream().apply_polish().bubble().text, "Ceci est ma super application.")

    def test_stop_shows_polishing(self) -> None:
        self.assertEqual(FakeDesktop().stop_after("um hi").bubble().phase, "polishing")

    def test_fluent_text_is_still_polished(self) -> None:
        desktop = FakeDesktop(polish=polish_to("Ceci est ma super application."))
        self.assertEqual(desktop.dictate("Ceci est mon super application.").bubble().text, "Ceci est ma super application.")

    def test_speech_during_polish_waits_for_the_next_stop(self) -> None:
        desktop = FakeDesktop(polish=polish_to("Hi.")).stop_after("um hi")
        desktop.tap(at=10.0).hear("interim", "more")
        self.assertEqual(desktop.apply_polish().bubble().text, "um hi more")

    def test_appended_speech_is_polished_again(self) -> None:
        desktop = FakeDesktop(polish=lambda text: text.upper()).dictate("one.")
        desktop.tap(at=10.0).hear("utterance_final", "two.").tap(at=15.0).end_stream()
        self.assertEqual(desktop.apply_polish().bubble().text, "ONE. TWO.")

    def test_stopped_dictation_is_ready_to_paste(self) -> None:
        self.assertEqual(FakeDesktop().dictate("Hello there.").bubble().phase, "ready")

    def test_running_polish_shows_polishing(self) -> None:
        dictation = Dictation(0, polishing="um hi")
        self.assertEqual(describe_bubble(ControllerState(dictation=dictation)).phase, "polishing")

    def test_silent_dictation_hides_the_bubble(self) -> None:
        self.assertEqual(FakeDesktop().tap().tap(at=5.0).end_stream().bubble().phase, "hidden")

    def test_second_dictation_appends_to_the_bubble(self) -> None:
        desktop = FakeDesktop().dictate("One.")
        desktop.tap(at=10.0)
        self.assertEqual(desktop.hear("interim", "Two").bubble().text, "One. Two")


class PasteTest(unittest.TestCase):
    def test_click_after_stopping_pastes(self) -> None:
        self.assertEqual(FakeDesktop().dictate("Hello there.").click().pasted, ["Hello there."])

    def test_paste_closes_the_bubble(self) -> None:
        self.assertEqual(FakeDesktop().dictate("Hello there.").click().bubble().phase, "hidden")

    def test_click_while_listening_does_not_paste(self) -> None:
        self.assertEqual(FakeDesktop().tap().hear("interim", "Hello").click().pasted, [])

    def test_click_while_polishing_pastes_the_polished_text(self) -> None:
        desktop = FakeDesktop(polish=polish_to("Hi.")).stop_after("um hi").click().apply_polish()
        self.assertEqual(desktop.pasted, ["Hi."])

    def test_early_click_says_it_will_paste(self) -> None:
        self.assertEqual(FakeDesktop().stop_after("um hi").click().bubble().hint, "pastes when done")

    def test_failed_polish_still_pastes_the_transcript(self) -> None:
        desktop = FakeDesktop(polish=failing_polish).stop_after("um hi").click().apply_polish()
        self.assertEqual(desktop.pasted, ["um hi"])

    def test_click_without_dictation_does_nothing(self) -> None:
        self.assertEqual(FakeDesktop().click().pasted, [])


class CancelTest(unittest.TestCase):
    def test_escape_hides_the_bubble(self) -> None:
        self.assertEqual(FakeDesktop().dictate("Hello.").send(CancelPressed()).bubble().phase, "hidden")

    def test_escape_stops_listening(self) -> None:
        self.assertIsNone(FakeDesktop().tap().send(CancelPressed()).state.live_stream)

    def test_escape_while_holding_waits_for_release(self) -> None:
        self.assertEqual(FakeDesktop().press().send(CancelPressed()).state.hotkey.phase, "cancelled")

    def test_escape_drops_a_pending_paste(self) -> None:
        desktop = FakeDesktop(polish=polish_to("Hi.")).stop_after("um hi").click()
        self.assertEqual(desktop.send(CancelPressed()).apply_polish().pasted, [])


class HandsFreeTest(unittest.TestCase):
    def test_tap_keeps_listening_after_release(self) -> None:
        self.assertIsNotNone(FakeDesktop().tap().state.live_stream)

    def test_second_tap_stops_listening(self) -> None:
        self.assertIsNone(FakeDesktop().tap(at=0.0).tap(at=5.0).state.live_stream)

    def test_release_of_stopping_tap_does_not_restart(self) -> None:
        self.assertEqual(FakeDesktop().tap(at=0.0).tap(at=5.0).state.hotkey.phase, "idle")

    def test_long_silence_stops_listening(self) -> None:
        self.assertIsNone(FakeDesktop().tap().wait(AUTO_STOP_SILENCE_SECONDS).state.live_stream)

    def test_speech_resets_the_silence_timer(self) -> None:
        desktop = FakeDesktop().tap().wait(AUTO_STOP_SILENCE_SECONDS - 5).hear("interim", "still here")
        self.assertIsNotNone(desktop.wait(10).state.live_stream)

    def test_silence_never_stops_a_held_key(self) -> None:
        self.assertIsNotNone(FakeDesktop().press().wait(AUTO_STOP_SILENCE_SECONDS * 2).state.live_stream)

    def test_stream_failure_ends_hands_free_mode(self) -> None:
        desktop = FakeDesktop().tap()
        self.assertEqual(desktop.send(StreamEnded(desktop.stream_id, "timeout")).state.hotkey.phase, "idle")

    def test_next_press_after_auto_stop_starts_again(self) -> None:
        desktop = FakeDesktop().tap().wait(AUTO_STOP_SILENCE_SECONDS)
        self.assertIsNotNone(desktop.press(at=100.0).state.live_stream)


class SoundCueTest(unittest.TestCase):
    def test_stop_ticks_then_rings_when_polished(self) -> None:
        self.assertEqual(FakeDesktop().dictate("Hello.").cues, ["polish_started", "done"])

    def test_no_cue_while_listening(self) -> None:
        self.assertEqual(FakeDesktop().tap().hear("utterance_final", "um hi").cues, [])

    def test_cancel_never_rings(self) -> None:
        desktop = FakeDesktop(polish=polish_to("Hi.")).stop_after("um hi")
        self.assertEqual(desktop.send(CancelPressed()).apply_polish().cues, ["polish_started"])

    def test_silent_dictation_never_rings(self) -> None:
        self.assertEqual(FakeDesktop().tap().tap(at=5.0).end_stream().cues, [])

    def test_failure_never_rings(self) -> None:
        desktop = FakeDesktop().tap().hear("utterance_final", "Hello.").tap(at=5.0)
        publish_feedback(desktop.state, ControllerState(), Tick(), desktop.effects, failed=True)
        self.assertEqual(desktop.cues, [])


class BubbleVisibilityTest(unittest.TestCase):
    def test_visible_bubble_claims_escape(self) -> None:
        self.assertTrue(FakeDesktop().tap().effects.bubble_visible.is_set())

    def test_hidden_bubble_releases_escape(self) -> None:
        self.assertFalse(FakeDesktop().dictate("Hi.").click().effects.bubble_visible.is_set())


class DescribeFailureTest(unittest.TestCase):
    def test_open_stream_error_is_reported(self) -> None:
        state = ControllerState(dictation=Dictation(0, open_streams=frozenset({1})))
        self.assertIsNotNone(describe_failure(state, StreamEnded(1, "timeout")))

    def test_aborted_stream_error_is_silent(self) -> None:
        state = ControllerState(dictation=Dictation(0))
        self.assertIsNone(describe_failure(state, StreamEnded(1, "timeout")))


class RecoverFromFailureTest(unittest.TestCase):
    def test_failed_start_ignores_key_repeat_until_release(self) -> None:
        state = recover_from_failure(ControllerState(), KeyInput("hotkey_down", 0.0), FakeDesktop().effects)
        self.assertEqual(state.hotkey.phase, "cancelled")

    def test_failure_while_hands_free_returns_to_idle(self) -> None:
        toggled = replace(ControllerState(), hotkey=HotkeyState("toggled", 0.0))
        self.assertEqual(recover_from_failure(toggled, Tick(), FakeDesktop().effects).hotkey.phase, "idle")

    def test_failure_on_release_returns_to_idle(self) -> None:
        holding = replace(ControllerState(), hotkey=HotkeyState("holding", 0.0))
        state = recover_from_failure(holding, KeyInput("hotkey_up", 1.0), FakeDesktop().effects)
        self.assertEqual(state.hotkey.phase, "idle")


if __name__ == "__main__":
    unittest.main()
