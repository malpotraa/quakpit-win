"""Menu-bar / system-tray icon."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject
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
    act_test = QAction("Send a test flight", menu)
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
