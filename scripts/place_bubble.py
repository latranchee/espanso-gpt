#!/usr/bin/env python3
from render_bubble import TailCorner

Point = tuple[int, int]
Rect = tuple[int, int, int, int]
# Logical pixels from the cursor hotspot to the tail tip; below-right clears the arrow cursor itself.
GAP_BELOW_RIGHT = (14, 22)
GAP_ABOVE_LEFT = (6, 6)


def cursor_gap(corner: TailCorner, scale: float) -> Point:
    gap_x = GAP_BELOW_RIGHT[0] if corner.endswith("left") else -GAP_ABOVE_LEFT[0]
    gap_y = GAP_BELOW_RIGHT[1] if corner.startswith("top") else -GAP_ABOVE_LEFT[1]
    return round(gap_x * scale), round(gap_y * scale)


def choose_tail_corner(cursor: Point, size: Point, work_area: Rect, scale: float) -> TailCorner:
    # The bubble prefers sitting below-right of the cursor, flipping only when it would leave the screen.
    below_right_gap_x, below_right_gap_y = cursor_gap("top_left", scale)
    fits_right = cursor[0] + below_right_gap_x + size[0] <= work_area[2]
    fits_below = cursor[1] + below_right_gap_y + size[1] <= work_area[3]
    vertical = "top" if fits_below else "bottom"
    horizontal = "left" if fits_right else "right"
    return f"{vertical}_{horizontal}"


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


def place_bubble(cursor: Point, corner: TailCorner, tip: Point, size: Point, work_area: Rect, scale: float) -> Point:
    gap_x, gap_y = cursor_gap(corner, scale)
    x = cursor[0] + gap_x - tip[0]
    y = cursor[1] + gap_y - tip[1]
    left, top, right, bottom = work_area
    return clamp(x, left, max(left, right - size[0])), clamp(y, top, max(top, bottom - size[1]))
