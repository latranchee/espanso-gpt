#!/usr/bin/env python3
import ctypes
from ctypes import wintypes

from PIL import Image

GWL_EXSTYLE = -20
# LAYERED | TRANSPARENT | NOACTIVATE | TOOLWINDOW: drawn with per-pixel alpha, click-through,
# never focused (the paste must land in the user's window) and absent from the taskbar.
BUBBLE_EX_STYLE = 0x00080000 | 0x00000020 | 0x08000000 | 0x00000080
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
BI_RGB = 0
DIB_RGB_COLORS = 0

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


# Explicit signatures: ctypes defaults to 32-bit int, which truncates 64-bit handles.
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT
]
user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT), ctypes.POINTER(wintypes.SIZE),
    wintypes.HDC, ctypes.POINTER(wintypes.POINT), wintypes.COLORREF, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD,
]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE,
    wintypes.DWORD,
]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]


def to_premultiplied_bgra(image: Image.Image) -> bytes:
    red, green, blue, alpha = image.convert("RGBa").split()
    return Image.merge("RGBA", (blue, green, red, alpha)).tobytes()


def prepare_layered_window(tk_window_id: int) -> int:
    window_handle = user32.GetParent(tk_window_id)
    current_style = user32.GetWindowLongW(window_handle, GWL_EXSTYLE)
    user32.SetWindowLongW(window_handle, GWL_EXSTYLE, current_style | BUBBLE_EX_STYLE)
    return window_handle


def create_bitmap(memory_dc: int, image: Image.Image) -> int:
    width, height = image.size
    # Negative height makes the DIB top-down, matching PIL's row order.
    header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, BI_RGB)
    bits = ctypes.c_void_p()
    bitmap = gdi32.CreateDIBSection(memory_dc, ctypes.byref(BITMAPINFO(header)), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
    if not bitmap:
        raise OSError(f"CreateDIBSection failed (error {ctypes.get_last_error()})")
    pixels = to_premultiplied_bgra(image)
    ctypes.memmove(bits, pixels, len(pixels))
    return bitmap


def update_layered_window(window_handle: int, image: Image.Image, position: tuple[int, int], opacity: int) -> None:
    screen_dc = user32.GetDC(None)
    memory_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = create_bitmap(memory_dc, image)
    previous = gdi32.SelectObject(memory_dc, bitmap)
    try:
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, opacity, AC_SRC_ALPHA)
        updated = user32.UpdateLayeredWindow(
            window_handle, screen_dc, ctypes.byref(wintypes.POINT(*position)), ctypes.byref(wintypes.SIZE(*image.size)),
            memory_dc, ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(blend), ULW_ALPHA,
        )
    finally:
        gdi32.SelectObject(memory_dc, previous)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(None, screen_dc)
    if not updated:
        raise OSError(f"UpdateLayeredWindow failed (error {ctypes.get_last_error()})")


def move_layered_window(window_handle: int, position: tuple[int, int]) -> None:
    user32.SetWindowPos(window_handle, HWND_TOPMOST, position[0], position[1], 0, 0, SWP_NOSIZE | SWP_NOACTIVATE)


def raise_layered_window(window_handle: int) -> None:
    # WS_EX_TOPMOST cannot be set through SetWindowLong; only SetWindowPos puts a window above the others.
    user32.SetWindowPos(window_handle, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
