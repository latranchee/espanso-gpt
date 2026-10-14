import unittest

from render_bubble import (
    DARK_THEME,
    LIGHT_THEME,
    MAX_BODY_LINES,
    BubbleView,
    accent_color,
    animation_frame,
    layout_bubble,
    render_bubble,
    split_long_word,
    tail_tip,
    visible_lines,
    wrap_text,
)

LISTENING = BubbleView("listening", "Listening", "tap F8 to stop", "")
READY = BubbleView("ready", "Ready", "click to paste", "Hello there, this is a test.")
LONG_TEXT = " ".join(["word"] * 400)


def character_count(text: str) -> float:
    return float(len(text))


class WrapTextTest(unittest.TestCase):
    def test_short_text_stays_on_one_line(self) -> None:
        self.assertEqual(wrap_text("hi there", character_count, 20), ["hi there"])

    def test_breaks_between_words(self) -> None:
        self.assertEqual(wrap_text("aaa bbb ccc", character_count, 7), ["aaa bbb", "ccc"])

    def test_empty_text_has_no_lines(self) -> None:
        self.assertEqual(wrap_text("   ", character_count, 10), [])

    def test_overlong_word_is_split(self) -> None:
        self.assertEqual(wrap_text("abcdefgh", character_count, 3), ["abc", "def", "gh"])


class SplitLongWordTest(unittest.TestCase):
    def test_fitting_word_is_kept_whole(self) -> None:
        self.assertEqual(split_long_word("abc", character_count, 5), ["abc"])

    def test_empty_word_has_no_pieces(self) -> None:
        self.assertEqual(split_long_word("", character_count, 5), [])


class VisibleLinesTest(unittest.TestCase):
    def test_short_text_is_unchanged(self) -> None:
        self.assertEqual(visible_lines(["a", "b"], 3), ["a", "b"])

    def test_long_text_keeps_the_newest_lines(self) -> None:
        self.assertEqual(visible_lines(["a", "b", "c", "d"], 2), ["… c", "d"])


class LayoutBubbleTest(unittest.TestCase):
    def test_empty_listening_shows_placeholder(self) -> None:
        self.assertEqual(layout_bubble(LISTENING, 1.0).lines, ("Speak now…",))

    def test_placeholder_is_flagged(self) -> None:
        self.assertTrue(layout_bubble(LISTENING, 1.0).is_placeholder)

    def test_text_is_not_a_placeholder(self) -> None:
        self.assertFalse(layout_bubble(READY, 1.0).is_placeholder)

    def test_long_text_is_capped(self) -> None:
        self.assertEqual(len(layout_bubble(BubbleView("ready", "Ready", "", LONG_TEXT), 1.0).lines), MAX_BODY_LINES)

    def test_higher_scale_is_bigger(self) -> None:
        self.assertGreater(layout_bubble(READY, 1.5).width, layout_bubble(READY, 1.0).width)


class TailTipTest(unittest.TestCase):
    def test_top_tail_points_above_the_body(self) -> None:
        layout = layout_bubble(READY, 1.0)
        self.assertLess(tail_tip(layout, "top_left")[1], layout.margin)

    def test_bottom_tail_points_below_the_body(self) -> None:
        layout = layout_bubble(READY, 1.0)
        self.assertGreater(tail_tip(layout, "bottom_left")[1], layout.margin + layout.body_height)

    def test_right_tail_is_on_the_right(self) -> None:
        layout = layout_bubble(READY, 1.0)
        self.assertGreater(tail_tip(layout, "top_right")[0], layout.width / 2)


class RenderBubbleTest(unittest.TestCase):
    def test_matches_layout_size(self) -> None:
        layout = layout_bubble(READY, 1.5)
        self.assertEqual(render_bubble(READY, layout, DARK_THEME, "top_left", 0).size, (layout.width, layout.height))

    def test_outer_corner_is_transparent(self) -> None:
        layout = layout_bubble(READY, 1.0)
        self.assertEqual(render_bubble(READY, layout, DARK_THEME, "top_left", 0).getpixel((0, 0))[3], 0)

    def test_body_is_nearly_opaque(self) -> None:
        layout = layout_bubble(READY, 1.0)
        image = render_bubble(READY, layout, LIGHT_THEME, "top_left", 0)
        self.assertGreater(image.getpixel((layout.width // 2, layout.margin + layout.body_height - 4))[3], 240)

    def test_animation_frames_differ(self) -> None:
        layout = layout_bubble(LISTENING, 1.0)
        first = render_bubble(LISTENING, layout, DARK_THEME, "top_left", 0)
        self.assertNotEqual(first.tobytes(), render_bubble(LISTENING, layout, DARK_THEME, "top_left", 15).tobytes())


class AnimationFrameTest(unittest.TestCase):
    def test_listening_animates(self) -> None:
        self.assertEqual(animation_frame("listening", 2.0), 60)

    def test_ready_is_still(self) -> None:
        self.assertEqual(animation_frame("ready", 2.0), 0)


class AccentColorTest(unittest.TestCase):
    def test_known_phase_has_its_accent(self) -> None:
        self.assertNotEqual(accent_color(DARK_THEME, "ready"), DARK_THEME.muted)

    def test_unknown_phase_falls_back_to_muted(self) -> None:
        self.assertEqual(accent_color(DARK_THEME, "hidden"), DARK_THEME.muted)


if __name__ == "__main__":
    unittest.main()
