import unittest

from place_bubble import GAP_BELOW_RIGHT, choose_tail_corner, cursor_gap, place_bubble

WORK_AREA = (0, 0, 1920, 1040)
SIZE = (400, 200)
TIP = (20, 10)


class CursorGapTest(unittest.TestCase):
    def test_below_right_clears_the_arrow(self) -> None:
        self.assertEqual(cursor_gap("top_left", 1.0), GAP_BELOW_RIGHT)

    def test_gap_scales_with_dpi(self) -> None:
        self.assertEqual(cursor_gap("top_left", 2.0), (GAP_BELOW_RIGHT[0] * 2, GAP_BELOW_RIGHT[1] * 2))

    def test_above_left_gap_is_negative(self) -> None:
        self.assertLess(cursor_gap("bottom_right", 1.0)[0], 0)


class ChooseTailCornerTest(unittest.TestCase):
    def test_prefers_below_right(self) -> None:
        self.assertEqual(choose_tail_corner((500, 300), SIZE, WORK_AREA, 1.0), "top_left")

    def test_flips_left_at_right_edge(self) -> None:
        self.assertEqual(choose_tail_corner((1800, 300), SIZE, WORK_AREA, 1.0), "top_right")

    def test_flips_up_at_bottom_edge(self) -> None:
        self.assertEqual(choose_tail_corner((500, 1000), SIZE, WORK_AREA, 1.0), "bottom_left")

    def test_flips_both_in_bottom_right_corner(self) -> None:
        self.assertEqual(choose_tail_corner((1800, 1000), SIZE, WORK_AREA, 1.0), "bottom_right")


class PlaceBubbleTest(unittest.TestCase):
    def test_tail_tip_lands_next_to_cursor(self) -> None:
        x, y = place_bubble((500, 300), "top_left", TIP, SIZE, WORK_AREA, 1.0)
        self.assertEqual((x + TIP[0], y + TIP[1]), (500 + GAP_BELOW_RIGHT[0], 300 + GAP_BELOW_RIGHT[1]))

    def test_stays_inside_the_work_area(self) -> None:
        self.assertEqual(place_bubble((5, 5), "bottom_right", (390, 190), SIZE, WORK_AREA, 1.0), (0, 0))

    def test_works_on_a_monitor_left_of_the_primary(self) -> None:
        x, _ = place_bubble((-1500, 300), "top_left", TIP, SIZE, (-1920, 0, 0, 1040), 1.0)
        self.assertEqual(x, -1500 + GAP_BELOW_RIGHT[0] - TIP[0])


if __name__ == "__main__":
    unittest.main()
