#!/usr/bin/env python3
import queue
import time
import tkinter
from dataclasses import dataclass, replace
from typing import Any, Callable

import logger
from place_bubble import choose_tail_corner, place_bubble
from read_screen_metrics import ScreenMetrics, read_apps_use_light_theme, read_screen_metrics
from render_bubble import (
    DARK_THEME,
    HIDDEN_VIEW,
    LIGHT_THEME,
    BubbleTheme,
    BubbleView,
    animation_frame,
    layout_bubble,
    render_bubble,
    tail_tip,
)
from update_layered_window import (
    move_layered_window,
    prepare_layered_window,
    raise_layered_window,
    update_layered_window,
)

FRAME_MS = 16
FADE_STEP = 64
ERROR_SECONDS = 4.0


@dataclass(frozen=True)
class BubbleScreen:
    target: BubbleView = HIDDEN_VIEW
    shown: BubbleView = HIDDEN_VIEW
    opacity: int = 0
    position: tuple[int, int] = (0, 0)
    render_key: tuple[Any, ...] = ()
    error_until: float = 0.0


def drain_latest(view_updates: "queue.Queue[BubbleView]") -> BubbleView | None:
    latest = None
    while not view_updates.empty():
        latest = view_updates.get_nowait()
    return latest


def next_target(screen: BubbleScreen, latest: BubbleView | None, now: float) -> BubbleScreen:
    if latest is not None:
        error_until = now + ERROR_SECONDS if latest.phase == "error" else 0.0
        screen = replace(screen, target=latest, error_until=error_until)
    if screen.target.phase == "error" and now >= screen.error_until:
        screen = replace(screen, target=HIDDEN_VIEW)
    # Fading out keeps drawing the last visible content instead of an empty bubble.
    shown = screen.target if screen.target.phase != "hidden" else screen.shown
    return replace(screen, shown=shown)


def next_opacity(opacity: int, visible: bool) -> int:
    return min(255, opacity + FADE_STEP) if visible else max(0, opacity - FADE_STEP)


def draw_bubble_frame(
    screen: BubbleScreen, metrics: ScreenMetrics, theme: BubbleTheme, now: float, window_handle: int
) -> BubbleScreen:
    view = screen.shown
    layout = layout_bubble(view, metrics.scale)
    size = (layout.width, layout.height)
    corner = choose_tail_corner(metrics.cursor, size, metrics.work_area, metrics.scale)
    position = place_bubble(metrics.cursor, corner, tail_tip(layout, corner), size, metrics.work_area, metrics.scale)
    frame = animation_frame(view.phase, now)
    render_key = (view, layout, corner, frame, screen.opacity)
    if render_key != screen.render_key:
        update_layered_window(window_handle, render_bubble(view, layout, theme, corner, frame), position, screen.opacity)
    elif position != screen.position:
        move_layered_window(window_handle, position)
    return replace(screen, position=position, render_key=render_key)


def step_bubble_screen(
    screen: BubbleScreen,
    view_updates: "queue.Queue[BubbleView]",
    theme: BubbleTheme,
    window_handle: int,
    read_metrics: Callable[[], ScreenMetrics] = read_screen_metrics
) -> BubbleScreen:
    now = time.monotonic()
    screen = next_target(screen, drain_latest(view_updates), now)
    opacity = next_opacity(screen.opacity, screen.target.phase != "hidden")
    if opacity == 0 and screen.opacity == 0:
        return screen
    if screen.opacity == 0:
        # Re-asserted on every appearance: a topmost window opened since then would otherwise cover the bubble.
        raise_layered_window(window_handle)
    return draw_bubble_frame(replace(screen, opacity=opacity), read_metrics(), theme, now, window_handle)


def create_bubble_host() -> tuple[tkinter.Tk, int]:
    root = tkinter.Tk()
    root.withdraw()
    host = tkinter.Toplevel(root)
    host.withdraw()
    host.overrideredirect(True)
    host.update_idletasks()
    window_handle = prepare_layered_window(host.winfo_id())
    # A layered window shows nothing until UpdateLayeredWindow gives it pixels, so mapping it is invisible.
    host.deiconify()
    return root, window_handle


def run_bubble_ui(view_updates: "queue.Queue[BubbleView]") -> None:
    root, window_handle = create_bubble_host()
    theme = LIGHT_THEME if read_apps_use_light_theme() else DARK_THEME
    holder = {"screen": BubbleScreen()}

    def tick() -> None:
        try:
            holder["screen"] = step_bubble_screen(holder["screen"], view_updates, theme, window_handle)
        except Exception as error:
            logger.error(f"Bubble frame failed: {error}")
        finally:
            root.after(FRAME_MS, tick)

    root.after(FRAME_MS, tick)
    root.mainloop()
