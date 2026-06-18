"""The control window: connect Google Calendar and tune the reminder."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import autostart, config, google_calendar
from .config import assets_dir


class _ConnectWorker(QObject):
    """Runs the blocking OAuth flow off the GUI thread."""

    done = Signal(bool, str)

    def run(self) -> None:
        try:
            google_calendar.connect()
            self.done.emit(True, "")
        except Exception as exc:  # surface a readable message
            self.done.emit(False, str(exc))


class SettingsWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Quakpit")
        self.setMinimumWidth(440)
        icon_path = assets_dir() / "logo.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._thread: QThread | None = None
        self._worker: _ConnectWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("Quakpit \U0001f986✈️")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        root.addWidget(title)
        root.addWidget(
            _muted("A duck flies across your screen before each meeting.")
        )

        # --- Google Calendar ---
        root.addWidget(_section("Google Calendar"))
        self._cal_status = _muted("Not connected.")
        root.addWidget(self._cal_status)

        creds_row = QFormLayout()
        self._client_id = QLineEdit()
        self._client_id.setPlaceholderText("OAuth Client ID")
        self._client_secret = QLineEdit()
        self._client_secret.setPlaceholderText("OAuth Client secret")
        self._client_secret.setEchoMode(QLineEdit.Password)
        creds_row.addRow("Client ID", self._client_id)
        creds_row.addRow("Client secret", self._client_secret)
        root.addLayout(creds_row)
        root.addWidget(
            _muted("Use your own Google OAuth desktop client — see the README. "
                   "Leave blank if you placed oauth-credentials.json next to the app.")
        )

        btn_row = QHBoxLayout()
        self._save_creds_btn = QPushButton("Save credentials")
        self._save_creds_btn.clicked.connect(self._save_creds)
        self._connect_btn = QPushButton("Connect")
        self._connect_btn.clicked.connect(self._connect)
        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.clicked.connect(self._disconnect)
        btn_row.addWidget(self._save_creds_btn)
        btn_row.addWidget(self._connect_btn)
        btn_row.addWidget(self._disconnect_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        # --- Reminder settings ---
        root.addWidget(_section("Reminder"))
        prefs = config.get_prefs()

        form = QFormLayout()
        self._lead = QSpinBox()
        self._lead.setRange(1, 120)
        self._lead.setValue(int(prefs["lead_minutes"]))
        self._lead.setSuffix(" min before")
        self._lead.valueChanged.connect(lambda v: config.set_prefs({"lead_minutes": int(v)}))
        form.addRow("Lead time", self._lead)

        self._template = QLineEdit(prefs["message_template"])
        self._template.editingFinished.connect(
            lambda: config.set_prefs({"message_template": self._template.text()})
        )
        form.addRow("Message", self._template)
        root.addLayout(form)
        root.addWidget(_muted("Use {title} and {minutes} as placeholders."))

        self._display = QComboBox()
        self._display.addItem("Screen under the cursor", "cursor")
        self._display.addItem("Primary screen", "primary")
        self._display.setCurrentIndex(0 if prefs["target_display"] == "cursor" else 1)
        self._display.currentIndexChanged.connect(
            lambda: config.set_prefs({"target_display": self._display.currentData()})
        )
        disp_form = QFormLayout()
        disp_form.addRow("Show on", self._display)
        root.addLayout(disp_form)

        self._sound = _toggle("Play the engine + quack", prefs["sound_enabled"],
                              lambda v: config.set_prefs({"sound_enabled": v}))
        self._fly_at_start = _toggle("Also fly by at the meeting's start", prefs["fly_at_start"],
                                     lambda v: config.set_prefs({"fly_at_start": v}))
        self._stay = _toggle("Stay signed in to Google", prefs["stay_signed_in"],
                             self._on_stay_signed_in)
        self._launch = _toggle("Launch Quakpit at startup", autostart.is_enabled(),
                               self._on_launch_at_login)
        for w in (self._sound, self._fly_at_start, self._stay, self._launch):
            root.addWidget(w)

        # --- Test ---
        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Send a test flight \U0001f6eb")
        self._test_btn.clicked.connect(self._on_test)
        test_row.addWidget(self._test_btn)
        test_row.addStretch(1)
        root.addLayout(test_row)

        self.on_test_flight = None  # set by the app

        self.refresh_status()

    # --- status ---
    def refresh_status(self) -> None:
        st = google_calendar.status()
        if st["connected"]:
            who = st["email"] or "your account"
            self._cal_status.setText(f"Connected as {who}.")
            self._connect_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(True)
        else:
            self._cal_status.setText(
                "Not connected." if st["configured"]
                else "Not connected — add your OAuth credentials first."
            )
            self._connect_btn.setEnabled(st["configured"])
            self._disconnect_btn.setEnabled(False)

    # --- handlers ---
    def _save_creds(self) -> None:
        try:
            google_calendar.set_creds(self._client_id.text(), self._client_secret.text())
            self._client_secret.clear()
            QMessageBox.information(self, "Quakpit", "Credentials saved.")
            self.refresh_status()
        except Exception as exc:
            QMessageBox.warning(self, "Quakpit", str(exc))

    def _connect(self) -> None:
        if not google_calendar.is_configured():
            QMessageBox.warning(self, "Quakpit", "Add your OAuth credentials first.")
            return
        self._connect_btn.setEnabled(False)
        self._cal_status.setText("Opening your browser to sign in…")

        self._thread = QThread(self)
        self._worker = _ConnectWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_connected)
        self._thread.start()

    def _on_connected(self, ok: bool, error: str) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
            self._worker = None
        if not ok:
            QMessageBox.warning(self, "Quakpit", error or "Sign-in failed.")
        self.refresh_status()
        if ok and callable(getattr(self, "on_connected", None)):
            self.on_connected()  # type: ignore[attr-defined]

    def _disconnect(self) -> None:
        google_calendar.disconnect()
        self.refresh_status()

    def _on_stay_signed_in(self, value: bool) -> None:
        config.set_prefs({"stay_signed_in": value})
        if value:
            google_calendar.persist_if_possible()
        else:
            google_calendar.forget_persisted()

    def _on_launch_at_login(self, value: bool) -> None:
        config.set_prefs({"launch_at_login": value})
        autostart.set_enabled(value)

    def _on_test(self) -> None:
        if callable(self.on_test_flight):
            self.on_test_flight()


# --- small UI helpers --------------------------------------------------------
def _section(text: str) -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 8, 0, 0)
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: #ddd;")
    label = QLabel(text)
    label.setStyleSheet("font-weight: 600; color: #444;")
    lay.addWidget(line)
    lay.addWidget(label)
    return box


def _muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: #777; font-size: 12px;")
    return label


def _toggle(text: str, checked: bool, on_change) -> QCheckBox:
    cb = QCheckBox(text)
    cb.setChecked(bool(checked))
    cb.toggled.connect(lambda v: on_change(bool(v)))
    return cb
