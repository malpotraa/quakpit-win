"""Menu-bar / system-tray icon and the Ctrl+Shift+D global hotkey."""

from __future__ import annotations

import sys
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .config import assets_dir


def build_tray(
    parent: QObject,
    on_test: Callable[[], None],
    on_settings: Callable[[], None],
    on_quit: Callable[[], None],
) -> QSystemTrayIcon:
    icon_path = assets_dir() / "logo.png"
    icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
    tray = QSystemTrayIcon(icon, parent)
    tray.setToolTip("Quakpit")

    menu = QMenu()
    act_test = QAction("Send a test flight  (Ctrl+Shift+D)", menu)
    act_test.triggered.connect(on_test)
    act_settings = QAction("Settings…", menu)
    act_settings.triggered.connect(on_settings)
    act_quit = QAction("Quit Quakpit", menu)
    act_quit.triggered.connect(on_quit)
    menu.addAction(act_test)
    menu.addAction(act_settings)
    menu.addSeparator()
    menu.addAction(act_quit)

    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: on_settings() if reason == QSystemTrayIcon.Trigger else None
    )
    tray.show()
    return tray


# --- Global hotkey: Ctrl+Shift+D ---------------------------------------------
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_NOREPEAT = 0x4000
_VK_D = 0x44
_HOTKEY_ID = 0xB00B
_WM_HOTKEY = 0x0312


class HotkeyFilter(QObject, QAbstractNativeEventFilter):
    """Registers a thread-level hotkey and emits ``fired`` on WM_HOTKEY."""

    fired = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._registered = False

    def register(self) -> None:
        if sys.platform != "win32" or self._registered:
            return
        try:
            import ctypes

            ok = ctypes.windll.user32.RegisterHotKey(
                None, _HOTKEY_ID, _MOD_CONTROL | _MOD_SHIFT | _MOD_NOREPEAT, _VK_D
            )
            self._registered = bool(ok)
        except Exception:
            self._registered = False

    def unregister(self) -> None:
        if sys.platform != "win32" or not self._registered:
            return
        try:
            import ctypes

            ctypes.windll.user32.UnregisterHotKey(None, _HOTKEY_ID)
        except Exception:
            pass
        self._registered = False

    def nativeEventFilter(self, _event_type, message):  # noqa: N802 (Qt naming)
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
                if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                    self.fired.emit()
            except Exception:
                pass
        return False, 0
