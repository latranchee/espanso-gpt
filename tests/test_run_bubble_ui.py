import queue
import unittest

from render_bubble import HIDDEN_VIEW, BubbleView
from run_bubble_ui import ERROR_SECONDS, FADE_STEP, BubbleScreen, drain_latest, next_opacity, next_target

LISTENING = BubbleView("listening", "Listening", "", "hi")
ERROR = BubbleView("error", "Dictation failed", "", "")


class DrainLatestTest(unittest.TestCase):
    def test_keeps_only_the_newest_view(self) -> None:
        updates: "queue.Queue[BubbleView]" = queue.Queue()
        updates.put(LISTENING)
        updates.put(HIDDEN_VIEW)
        self.assertEqual(drain_latest(updates), HIDDEN_VIEW)

    def test_empty_queue_has_no_update(self) -> None:
        self.assertIsNone(drain_latest(queue.Queue()))


class NextTargetTest(unittest.TestCase):
    def test_new_view_becomes_the_target(self) -> None:
        self.assertEqual(next_target(BubbleScreen(), LISTENING, 0.0).target, LISTENING)

    def test_hiding_keeps_drawing_the_last_view_while_fading(self) -> None:
        screen = next_target(BubbleScreen(), LISTENING, 0.0)
        self.assertEqual(next_target(screen, HIDDEN_VIEW, 0.1).shown, LISTENING)

    def test_error_hides_itself_after_a_while(self) -> None:
        screen = next_target(BubbleScreen(), ERROR, 0.0)
        self.assertEqual(next_target(screen, None, ERROR_SECONDS + 0.1).target, HIDDEN_VIEW)

    def test_error_stays_up_briefly(self) -> None:
        screen = next_target(BubbleScreen(), ERROR, 0.0)
        self.assertEqual(next_target(screen, None, 1.0).target, ERROR)


class NextOpacityTest(unittest.TestCase):
    def test_fades_in(self) -> None:
        self.assertEqual(next_opacity(0, True), FADE_STEP)

    def test_stops_at_fully_opaque(self) -> None:
        self.assertEqual(next_opacity(250, True), 255)

    def test_fades_out_to_zero(self) -> None:
        self.assertEqual(next_opacity(10, False), 0)


if __name__ == "__main__":
    unittest.main()
