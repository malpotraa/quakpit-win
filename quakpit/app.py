"""Application wiring: tray, overlay, scheduler, settings, single-instance lock."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from . import APP_NAME, audio, config, google_calendar
from .config import assets_dir
from .overlay import Overlay
from .scheduler import Scheduler
from .settings_window import SettingsWindow
from .tray import HotkeyFilter, build_tray

_LOCK_NAME = "QuakpitSingleInstance"


class QuakpitApp:
    def __init__(self, qapp: QApplication) -> None:
        self.qapp = qapp
        self.qapp.setApplicationName(APP_NAME)
        self.qapp.setQuitOnLastWindowClosed(False)  # live in the tray
        icon_path = assets_dir() / "logo.png"
        if icon_path.exists():
            self.qapp.setWindowIcon(QIcon(str(icon_path)))

        audio.init()

        self.overlay = Overlay()
        self.settings = SettingsWindow()
        self.settings.on_test_flight = self.test_flight
        self.settings.on_connected = self._on_connected

        self.scheduler = Scheduler(self._fly)

        self.tray = build_tray(
            self.qapp,
            on_test=self.test_flight,
            on_settings=self.open_settings,
            on_quit=self.quit,
        )

        self.hotkey = HotkeyFilter()
        self.qapp.installNativeEventFilter(self.hotkey)
        self.hotkey.fired.connect(self.test_flight)
        self.hotkey.register()

        # Honour saved launch-at-login (best effort).
        try:
            from . import autostart

            if config.get_prefs().get("launch_at_login"):
                autostart.set_enabled(True)
        except Exception:
            pass

        self.open_settings()

        # Restore any saved Google session, then start watching.
        QTimer.singleShot(0, self._boot_calendar)

    def _boot_calendar(self) -> None:
        try:
            google_calendar.init()
        except Exception:
            pass
        self.settings.refresh_status()
        self.scheduler.start()

    def _on_connected(self) -> None:
        self.scheduler.start()

    # --- actions ---
    def _fly(self, flight: dict) -> None:
        self.overlay.fly(
            flight["message"], int(flight["duration_ms"]), bool(flight.get("sound", True))
        )

    def test_flight(self) -> None:
        prefs = config.get_prefs()
        self._fly(
            {
                "message": "Call with Jack in 5 minutes",
                "duration_ms": int(prefs.get("duration_ms", 9000)),
                "sound": prefs["sound_enabled"],
            }
        )

    def open_settings(self) -> None:
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def quit(self) -> None:
        self.scheduler.stop()
        self.hotkey.unregister()
        self.tray.hide()
        self.qapp.quit()


def _take_single_instance_lock(qapp: QApplication) -> bool:
    """Returns True if this is the only instance; otherwise pings the running one."""
    probe = QLocalSocket()
    probe.connectToServer(_LOCK_NAME)
    if probe.waitForConnected(200):
        probe.write(b"show")
        probe.flush()
        probe.waitForBytesWritten(200)
        probe.disconnectFromServer()
        return False

    # Stale socket from a crash? Remove and (re)create the server.
    QLocalServer.removeServer(_LOCK_NAME)
    server = QLocalServer(qapp)
    server.listen(_LOCK_NAME)
    qapp._quakpit_lock_server = server  # type: ignore[attr-defined] (keep alive)
    return True


def main() -> int:
    qapp = QApplication(sys.argv)

    if not _take_single_instance_lock(qapp):
        return 0  # another instance is already running; it was brought forward

    app = QuakpitApp(qapp)

    # Bring the window forward when a second launch pings the lock server.
    server: QLocalServer = qapp._quakpit_lock_server  # type: ignore[attr-defined]
    server.newConnection.connect(lambda: (server.nextPendingConnection(), app.open_settings()))

    return qapp.exec()
