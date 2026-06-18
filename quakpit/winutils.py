"""Windows-only window tweaks, applied to a Qt window's native HWND.

Qt gives us frameless + translucent + always-on-top, but to (a) let clicks pass
straight through to the apps underneath and (b) float reliably above borderless
fullscreen windows, we need the native extended styles and an explicit
HWND_TOPMOST placement that we re-assert each flight.

All functions are safe no-ops off Windows so the rest of the app imports cleanly
during development on other platforms.
"""

from __future__ import annotations

import sys

IS_WINDOWS = sys.platform == "win32"

# Extended window styles.
WS_EX_TRANSPARENT = 0x00000020  # clicks fall through to windows below
WS_EX_LAYERED = 0x00080000  # required for per-pixel transparency / transparency
WS_EX_TOOLWINDOW = 0x00000080  # keep it out of Alt-Tab and the taskbar
WS_EX_NOACTIVATE = 0x08000000  # never steal focus
GWL_EXSTYLE = -20

# SetWindowPos placement + flags.
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


def make_overlay(hwnd: int) -> None:
    """Make the window click-through, non-activating, and hidden from Alt-Tab."""
    if not IS_WINDOWS or not hwnd:
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        get_long = user32.GetWindowLongW
        set_long = user32.SetWindowLongW
        get_long.restype = wintypes.LONG
        set_long.restype = wintypes.LONG

        ex = get_long(wintypes.HWND(hwnd), GWL_EXSTYLE)
        ex |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        set_long(wintypes.HWND(hwnd), GWL_EXSTYLE, ex)
    except Exception:
        pass


def assert_topmost(hwnd: int) -> None:
    """Re-pin the window above everything (incl. borderless-fullscreen apps)."""
    if not IS_WINDOWS or not hwnd:
        return
    try:
        import ctypes
        from ctypes import wintypes

        ctypes.windll.user32.SetWindowPos(
            wintypes.HWND(hwnd),
            wintypes.HWND(HWND_TOPMOST),
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
    except Exception:
        pass
