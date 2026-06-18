"""The transparent, click-through, always-on-top overlay the duck flies across.

One window stays shown for the app's lifetime (fully transparent and
non-interactive); a flight just positions it over the chosen display and runs
the animation — the rig (banner + plane + spinning propeller) glides from
off-screen left to off-screen right, towing the banner behind it.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import QLabel, QWidget

from . import audio, config, winutils
from .config import assets_dir

PLANE_H = 116  # rendered plane height in px
HEAD_H = 70
PROP_H = 84
BANNER_H = 62
GAP = 18  # space between the towed banner and the tail
BANNER_FONTS = "Segoe Print, Comic Sans MS, Patrick Hand, Comic Sans, cursive"


class Banner(QWidget):
    """A rounded, solid-colour pennant with the reminder text."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._text = ""
        self._font = QFont()
        self._font.setFamilies([f.strip() for f in BANNER_FONTS.split(",")])
        self._font.setPixelSize(28)
        self._font.setBold(True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def set_text(self, text: str) -> None:
        self._text = text
        fm = QFontMetrics(self._font)
        width = fm.horizontalAdvance(text) + 52
        self.setFixedSize(max(140, width), BANNER_H)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)

        # Solid, high-visibility fill (brand yellow) with a dark outline.
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        p.setClipPath(path)
        p.fillRect(rect, QColor("#ffd34d"))
        p.setClipping(False)

        p.setPen(QPen(QColor("#1a1a1a"), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect, 12, 12)

        p.setFont(self._font)
        p.setPen(QColor("#1a1a1a"))
        p.drawText(rect, Qt.AlignCenter, self._text)
        p.end()


class Overlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # The moving rig and its parts.
        self._rig = QWidget(self)
        self._banner = Banner(self._rig)
        self._plane = QLabel(self._rig)
        self._head = QLabel(self._rig)
        self._prop = QLabel(self._rig)

        self._plane_pix = self._load("plane.png", PLANE_H)
        self._head_pix = self._load("head.png", HEAD_H)
        self._prop_src = self._load("blade.png", PROP_H)

        self._plane.setPixmap(self._plane_pix)
        self._head.setPixmap(self._head_pix)
        self._prop.setPixmap(self._prop_src)
        for lbl in (self._plane, self._head, self._prop):
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._prop_angle = 0
        self._prop_timer = QTimer(self)
        self._prop_timer.timeout.connect(self._spin)

        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._on_step)
        self._anim.finished.connect(self._on_finished)

        self._topmost_timer = QTimer(self)
        self._topmost_timer.timeout.connect(self._reassert_topmost)

        self._show_persistent()

    # --- public API ---
    def fly(self, message: str, duration_ms: int, sound: bool) -> None:
        screen = self._target_screen()
        geo = screen.geometry()
        self.setGeometry(geo)
        self._reassert_topmost()

        self._banner.set_text(message)
        self._layout_rig()

        rig_w = self._rig.width()
        y = int(geo.height() * 0.16)
        start_x = -rig_w - 40
        end_x = geo.width() + 40

        self._rig.move(start_x, y)
        self._rig.show()

        self._anim.stop()
        self._anim.setStartValue(start_x)
        self._anim.setEndValue(end_x)
        self._anim.setDuration(max(2000, duration_ms))
        self._anim.setEasingCurve(QEasingCurve.Linear)  # constant-speed cross
        self._fly_y = y

        self._prop_timer.start(30)
        self._anim.start()

        if sound:
            try:
                audio.play_flight(duration_ms)
            except Exception:
                pass

    # --- internals ---
    def _show_persistent(self) -> None:
        screen = QGuiApplication.primaryScreen()
        self.setGeometry(screen.geometry())
        self._rig.move(-9999, -9999)
        self.show()
        self._apply_native_styles()
        # Re-assert topmost a few times after show (mirrors the macOS dock fix).
        for delay in (200, 800, 2000):
            QTimer.singleShot(delay, self._reassert_topmost)

    def _apply_native_styles(self) -> None:
        winutils.make_overlay(int(self.winId()))
        winutils.assert_topmost(int(self.winId()))

    def _reassert_topmost(self) -> None:
        winutils.assert_topmost(int(self.winId()))

    def _target_screen(self):
        if config.get_prefs().get("target_display") == "primary":
            return QGuiApplication.primaryScreen()
        at = QGuiApplication.screenAt(QCursor.pos())
        return at or QGuiApplication.primaryScreen()

    def _layout_rig(self) -> None:
        """Place banner | gap | plane inside the rig and size the rig to fit."""
        bw, bh = self._banner.width(), self._banner.height()
        pw, ph = self._plane_pix.width(), self._plane_pix.height()
        rig_w = bw + GAP + pw
        rig_h = max(bh, ph, PROP_H)
        self._rig.resize(rig_w, rig_h)

        cy = rig_h // 2
        self._banner.move(0, cy - bh // 2)

        plane_x = bw + GAP
        plane_y = cy - ph // 2
        self._plane.move(plane_x, plane_y)

        # Head sits on the cockpit (upper-left of the plane body).
        self._head.move(plane_x + int(pw * 0.22), plane_y - int(self._head_pix.height() * 0.45))
        # Propeller spins at the nose (right edge of the plane).
        self._prop.move(plane_x + pw - int(self._prop_src.width() * 0.55), cy - PROP_H // 2)

    def _on_step(self, value: int) -> None:
        self._rig.move(int(value), self._fly_y)

    def _on_finished(self) -> None:
        self._prop_timer.stop()
        self._rig.move(-9999, -9999)  # rest off-screen so nothing lingers

    def _spin(self) -> None:
        self._prop_angle = (self._prop_angle + 42) % 360
        rotated = self._prop_src.transformed(
            QTransform().rotate(self._prop_angle), Qt.SmoothTransformation
        )
        # Keep it centered as it rotates.
        self._prop.setPixmap(rotated)
        self._prop.resize(rotated.size())

    def _load(self, name: str, height: int) -> QPixmap:
        path = assets_dir() / name
        pix = QPixmap(str(path))
        if pix.isNull():
            return QPixmap(height, height)  # transparent placeholder
        return pix.scaledToHeight(height, Qt.SmoothTransformation)
