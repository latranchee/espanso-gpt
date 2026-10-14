#!/usr/bin/env python3
import ctypes
import winreg
from ctypes import wintypes
from dataclasses import dataclass

MONITOR_DEFAULTTONEAREST = 2
MDT_EFFECTIVE_DPI = 0
BASE_DPI = 96
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"

user32 = ctypes.WinDLL("user32", use_last_error=True)
shcore = ctypes.WinDLL("shcore", use_last_error=True)


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
shcore.GetDpiForMonitor.argtypes = [
    wintypes.HMONITOR, ctypes.c_int, ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.UINT)
]


@dataclass(frozen=True)
class ScreenMetrics:
    cursor: tuple[int, int]
    work_area: tuple[int, int, int, int]
    scale: float


def enable_dpi_awareness() -> None:
    # Per-monitor aware: cursor, monitor and window coordinates are physical pixels, so the bubble is
    # rendered at the real resolution instead of being bitmap-stretched (blurry) at 150%.
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2))


def read_screen_metrics() -> ScreenMetrics:
    cursor = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(cursor))
    monitor = user32.MonitorFromPoint(cursor, MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    user32.GetMonitorInfoW(monitor, ctypes.byref(info))
    dpi_x, dpi_y = wintypes.UINT(BASE_DPI), wintypes.UINT(BASE_DPI)
    shcore.GetDpiForMonitor(monitor, MDT_EFFECTIVE_DPI, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
    work = info.rcWork
    return ScreenMetrics((cursor.x, cursor.y), (work.left, work.top, work.right, work.bottom), dpi_x.value / BASE_DPI)


def read_apps_use_light_theme() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY) as key:
            return bool(winreg.QueryValueEx(key, "AppsUseLightTheme")[0])
    except OSError:
        return False
