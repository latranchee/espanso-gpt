#!/usr/bin/env python3
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Literal

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

BubblePhase = Literal["hidden", "listening", "finishing", "polishing", "ready", "error"]
TailCorner = Literal["top_left", "top_right", "bottom_left", "bottom_right"]
Color = tuple[int, int, int, int]
Point = tuple[int, int]

ANIMATED_PHASES = ("listening", "finishing", "polishing")
ANIMATION_FPS = 30
BODY_FONT = "segoeui.ttf"
HEADER_FONT = "seguisb.ttf"
# Layout values are logical pixels, multiplied by the monitor scale (1.5 at 150%).
PADDING_X = 15
PADDING_Y = 12
CORNER_RADIUS = 16
TAIL_SIZE = 9
SHADOW_MARGIN = 16
SHADOW_BLUR = 7
SHADOW_OFFSET_Y = 3
ICON_SIZE = 14
ICON_GAP = 7
HINT_GAP = 9
HEADER_FONT_PX = 12
HEADER_HEIGHT = 16
HEADER_GAP = 7
BODY_FONT_PX = 15
LINE_HEIGHT = 21
MIN_BODY_WIDTH = 150
MAX_BODY_WIDTH = 360
MAX_BODY_LINES = 8
# Shapes are drawn this many times larger and shrunk, which is how PIL gets smooth edges.
SUPERSAMPLE = 4


@dataclass(frozen=True)
class BubbleView:
    phase: BubblePhase = "hidden"
    title: str = ""
    hint: str = ""
    text: str = ""


HIDDEN_VIEW = BubbleView()


@dataclass(frozen=True)
class BubbleTheme:
    background: Color
    border: Color
    text: Color
    muted: Color
    shadow: Color
    icon_ink: Color
    accents: tuple[tuple[str, Color], ...]


DARK_THEME = BubbleTheme(
    background=(36, 36, 44, 245),
    border=(255, 255, 255, 34),
    text=(242, 242, 247, 255),
    muted=(158, 158, 175, 255),
    shadow=(0, 0, 0, 150),
    icon_ink=(36, 36, 44, 255),
    accents=(
        ("listening", (255, 92, 108, 255)),
        ("finishing", (150, 170, 190, 255)),
        ("polishing", (171, 140, 255, 255)),
        ("ready", (92, 204, 140, 255)),
        ("error", (255, 170, 60, 255)),
    ),
)
# Pastel accents vanish on white, so the light theme uses deeper shades of the same hues.
LIGHT_THEME = BubbleTheme(
    background=(255, 255, 255, 250),
    border=(0, 0, 0, 26),
    text=(30, 30, 38, 255),
    muted=(108, 108, 122, 255),
    shadow=(20, 20, 40, 80),
    icon_ink=(255, 255, 255, 255),
    accents=(
        ("listening", (220, 38, 72, 255)),
        ("finishing", (96, 112, 132, 255)),
        ("polishing", (112, 72, 220, 255)),
        ("ready", (22, 150, 82, 255)),
        ("error", (214, 110, 0, 255)),
    ),
)
PLACEHOLDERS = {"listening": "Speak now…", "error": ""}


def accent_color(theme: BubbleTheme, phase: str) -> Color:
    return dict(theme.accents).get(phase, theme.muted)


@dataclass(frozen=True)
class BubbleLayout:
    scale: float
    lines: tuple[str, ...]
    is_placeholder: bool
    width: int
    height: int
    margin: int
    body_width: int
    body_height: int


def scaled(value: float, scale: float) -> int:
    return max(1, round(value * scale))


@lru_cache(maxsize=16)
def load_font(name: str, size_px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(name, size_px)


def split_long_word(word: str, measure: Callable[[str], float], max_width: float) -> list[str]:
    pieces, current = [], ""
    for character in word:
        if current and measure(current + character) > max_width:
            pieces.append(current)
            current = character
        else:
            current += character
    return [*pieces, current] if current else pieces


def wrap_text(text: str, measure: Callable[[str], float], max_width: float) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if measure(candidate) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        *full_pieces, current = split_long_word(word, measure, max_width)
        lines.extend(full_pieces)
    return [*lines, current] if current else lines


def visible_lines(lines: list[str], max_lines: int) -> list[str]:
    # Long dictations show their tail: the newest words are the ones being checked.
    if len(lines) <= max_lines:
        return lines
    tail = lines[-max_lines:]
    return [f"… {tail[0]}", *tail[1:]]


def measure_header(view: BubbleView, font: ImageFont.FreeTypeFont, scale: float) -> float:
    title_width = scaled(ICON_SIZE + ICON_GAP, scale) + font.getlength(view.title)
    return title_width + (scaled(HINT_GAP, scale) + font.getlength(view.hint) if view.hint else 0)


def layout_bubble(view: BubbleView, scale: float) -> BubbleLayout:
    body_font = load_font(BODY_FONT, scaled(BODY_FONT_PX, scale))
    header_font = load_font(HEADER_FONT, scaled(HEADER_FONT_PX, scale))
    wrapped = visible_lines(wrap_text(view.text, body_font.getlength, scaled(MAX_BODY_WIDTH, scale)), MAX_BODY_LINES)
    placeholder = PLACEHOLDERS.get(view.phase, "…")
    lines = tuple(wrapped) or ((placeholder,) if placeholder else ())
    content_width = max(
        scaled(MIN_BODY_WIDTH, scale),
        measure_header(view, header_font, scale),
        *(body_font.getlength(line) for line in lines),
    )
    body_lines_height = scaled(HEADER_GAP + LINE_HEIGHT * len(lines), scale) if lines else 0
    body_width = math.ceil(content_width) + 2 * scaled(PADDING_X, scale)
    body_height = 2 * scaled(PADDING_Y, scale) + scaled(HEADER_HEIGHT, scale) + body_lines_height
    margin = scaled(SHADOW_MARGIN + TAIL_SIZE, scale)
    return BubbleLayout(
        scale, lines, not wrapped, body_width + 2 * margin, body_height + 2 * margin, margin, body_width, body_height
    )


def body_box(layout: BubbleLayout) -> tuple[int, int, int, int]:
    return layout.margin, layout.margin, layout.margin + layout.body_width, layout.margin + layout.body_height


def tail_points(layout: BubbleLayout, corner: TailCorner) -> list[tuple[float, float]]:
    left, top, right, bottom = body_box(layout)
    radius, size = scaled(CORNER_RADIUS, layout.scale), scaled(TAIL_SIZE, layout.scale)
    base_start, overlap = left + radius * 0.45, size * 0.6
    # A short, wide nub reads as a speech bubble; a long thin one reads as a warning flag.
    points = [(base_start, top + overlap), (left + radius * 0.2, top - size * 0.85), (base_start + size * 2.3, top + overlap)]
    mirror_x = corner.endswith("right")
    mirror_y = corner.startswith("bottom")
    return [(left + right - x if mirror_x else x, top + bottom - y if mirror_y else y) for x, y in points]


def tail_tip(layout: BubbleLayout, corner: TailCorner) -> Point:
    tip_x, tip_y = tail_points(layout, corner)[1]
    return round(tip_x), round(tip_y)


def bubble_mask(layout: BubbleLayout, corner: TailCorner) -> Image.Image:
    big = Image.new("L", (layout.width * SUPERSAMPLE, layout.height * SUPERSAMPLE), 0)
    draw = ImageDraw.Draw(big)
    left, top, right, bottom = (value * SUPERSAMPLE for value in body_box(layout))
    draw.rounded_rectangle((left, top, right, bottom), scaled(CORNER_RADIUS, layout.scale) * SUPERSAMPLE, fill=255)
    draw.polygon([(x * SUPERSAMPLE, y * SUPERSAMPLE) for x, y in tail_points(layout, corner)], fill=255)
    return big.resize((layout.width, layout.height), Image.LANCZOS)


def tinted_layer(size: Point, color: Color, mask: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", size, color[:3] + (0,))
    layer.putalpha(mask.point(lambda value: value * color[3] // 255))
    return layer


def draw_header_text(image: Image.Image, view: BubbleView, layout: BubbleLayout, theme: BubbleTheme) -> None:
    font = load_font(HEADER_FONT, scaled(HEADER_FONT_PX, layout.scale))
    draw = ImageDraw.Draw(image)
    x = layout.margin + scaled(PADDING_X + ICON_SIZE + ICON_GAP, layout.scale)
    y = layout.margin + scaled(PADDING_Y + HEADER_HEIGHT / 2, layout.scale)
    draw.text((x, y), view.title, font=font, fill=accent_color(theme, view.phase), anchor="lm")
    if view.hint:
        hint_x = x + font.getlength(view.title) + scaled(HINT_GAP, layout.scale)
        draw.text((hint_x, y), view.hint, font=font, fill=theme.muted, anchor="lm")


def draw_body_text(image: Image.Image, layout: BubbleLayout, theme: BubbleTheme) -> None:
    font = load_font(BODY_FONT, scaled(BODY_FONT_PX, layout.scale))
    draw = ImageDraw.Draw(image)
    x = layout.margin + scaled(PADDING_X, layout.scale)
    top = layout.margin + scaled(PADDING_Y + HEADER_HEIGHT + HEADER_GAP, layout.scale)
    color = theme.muted if layout.is_placeholder else theme.text
    for index, line in enumerate(layout.lines):
        y = top + scaled(LINE_HEIGHT * index + LINE_HEIGHT / 2, layout.scale)
        draw.text((x, y), line, font=font, fill=color, anchor="lm")


@lru_cache(maxsize=8)
def render_bubble_base(view: BubbleView, layout: BubbleLayout, theme: BubbleTheme, corner: TailCorner) -> Image.Image:
    size = (layout.width, layout.height)
    mask = bubble_mask(layout, corner)
    shadow_mask = ImageChops.offset(mask, 0, scaled(SHADOW_OFFSET_Y, layout.scale))
    shadow = tinted_layer(size, theme.shadow, shadow_mask.filter(ImageFilter.GaussianBlur(SHADOW_BLUR * layout.scale)))
    border_mask = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
    image = Image.alpha_composite(shadow, tinted_layer(size, theme.background, mask))
    image = Image.alpha_composite(image, tinted_layer(size, theme.border, border_mask))
    draw_header_text(image, view, layout, theme)
    draw_body_text(image, layout, theme)
    return image


def draw_icon_shape(draw: ImageDraw.ImageDraw, phase: BubblePhase, size: int, seconds: float, theme: BubbleTheme) -> None:
    accent, center = accent_color(theme, phase), size / 2
    if phase == "listening":
        pulse = (math.sin(seconds * 2 * math.pi / 1.3) + 1) / 2
        halo = center * (0.75 + 0.25 * pulse)
        draw.ellipse((center - halo,) * 2 + (center + halo,) * 2, fill=accent[:3] + (int(70 + 60 * pulse),))
        dot = center * 0.52
        draw.ellipse((center - dot,) * 2 + (center + dot,) * 2, fill=accent)
    elif phase in ("finishing", "polishing"):
        width, start = max(2, round(size * 0.15)), (seconds * 400) % 360
        inset = width / 2 + 1
        draw.arc((inset, inset, size - inset, size - inset), start, start + 270, fill=accent, width=width)
    elif phase == "ready":
        draw.ellipse((0, 0, size - 1, size - 1), fill=accent)
        check = [(size * 0.28, size * 0.52), (size * 0.44, size * 0.68), (size * 0.73, size * 0.35)]
        draw.line(check, fill=theme.icon_ink, width=max(2, round(size * 0.12)), joint="curve")
    elif phase == "error":
        draw.ellipse((0, 0, size - 1, size - 1), fill=accent)
        draw.line([(center, size * 0.25), (center, size * 0.58)], fill=theme.icon_ink, width=max(2, round(size * 0.12)))
        dot = size * 0.07
        draw.ellipse((center - dot, size * 0.72 - dot, center + dot, size * 0.72 + dot), fill=theme.icon_ink)


def render_status_icon(phase: BubblePhase, size: int, seconds: float, theme: BubbleTheme) -> Image.Image:
    big = Image.new("RGBA", (size * SUPERSAMPLE, size * SUPERSAMPLE), (0, 0, 0, 0))
    draw_icon_shape(ImageDraw.Draw(big), phase, size * SUPERSAMPLE, seconds, theme)
    return big.resize((size, size), Image.LANCZOS)


def animation_frame(phase: BubblePhase, seconds: float) -> int:
    return int(seconds * ANIMATION_FPS) if phase in ANIMATED_PHASES else 0


def render_bubble(
    view: BubbleView, layout: BubbleLayout, theme: BubbleTheme, corner: TailCorner, frame: int
) -> Image.Image:
    image = render_bubble_base(view, layout, theme, corner).copy()
    icon_size = scaled(ICON_SIZE, layout.scale)
    icon = render_status_icon(view.phase, icon_size, frame / ANIMATION_FPS, theme)
    x = layout.margin + scaled(PADDING_X, layout.scale)
    y = layout.margin + scaled(PADDING_Y + HEADER_HEIGHT / 2, layout.scale) - icon_size // 2
    image.alpha_composite(icon, (x, y))
    return image
