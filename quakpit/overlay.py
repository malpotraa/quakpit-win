"""The transparent, click-through, always-on-top overlay the duck flies across.

One window stays shown for the app's lifetime (fully transparent and
non-interactive); a flight just positions it over the chosen display and runs
the animation — the rig (banner + plane + spinning propeller) glides from
off-screen left to off-screen right, towing the banner behind it.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QRect,
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
)
from PySide6.QtWidgets import QLabel, QWidget

from . import audio, config, winutils
from .config import assets_dir

# The aircraft is ONE square sprite box. plane / head / blade are the same
# 1088x1088 aligned canvas, so they're rendered at the same size and stacked at
# the same origin — each sprite's content already sits where it belongs (head in
# the cockpit, blade at the nose). Never scale or position them independently.
AIRCRAFT_S = 150
# Propeller hub within that shared canvas (from the original art), as fractions.
PROP_HUB = (0.945, 0.562)
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

        # The moving rig: a banner towed behind the aircraft.
        self._rig = QWidget(self)
        self._banner = Banner(self._rig)

        # The aircraft: plane + head + blade stacked on one shared square canvas.
        self._aircraft = QWidget(self._rig)
        self._aircraft.setFixedSize(AIRCRAFT_S, AIRCRAFT_S)
        self._plane = QLabel(self._aircraft)
        self._head = QLabel(self._aircraft)
        self._prop = QLabel(self._aircraft)

        self._plane_pix = self._load("plane.png", AIRCRAFT_S)
        self._head_pix = self._load("head.png", AIRCRAFT_S)
        self._prop_src = self._load("blade.png", AIRCRAFT_S)
        self._plane.setPixmap(self._plane_pix)
        self._head.setPixmap(self._head_pix)
        self._prop.setPixmap(self._prop_src)
        for lbl in (self._plane, self._head, self._prop):
            lbl.setGeometry(0, 0, AIRCRAFT_S, AIRCRAFT_S)  # same size, same origin
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._plane.lower()
        self._prop.raise_()  # z-order: plane < head < prop

        self._prop_angle = 0
        self._prop_timer = QTimer(self)
        self._prop_timer.timeout.connect(self._spin)

        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._on_step)
        self._anim.finished.connect(self._on_finished)

        self._prepare_window()

    # --- public API ---
    def fly(self, message: str, duration_ms: int, sound: bool) -> None:
        screen = self._target_screen()
        geo = self._flight_geometry(screen)
        self.setGeometry(geo)
        # Show only for the duration of a flight (Option 2): a persistent
        # full-screen topmost window makes Windows demote the taskbar.
        self.show()
        self._apply_native_styles()

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
    def _prepare_window(self) -> None:
        # Realize the native window (hidden) so click-through styles can be set,
        # but DON'T show it. We only show during a flight — see fly()/_on_finished.
        self.setGeometry(self._flight_geometry(QGuiApplication.primaryScreen()))
        self._rig.move(-9999, -9999)
        self.winId()  # force native handle creation
        self._apply_native_styles()

    def _flight_geometry(self, screen) -> QRect:
        # One pixel shorter than the monitor (Option 1): an *exact* monitor-sized
        # topmost window makes the Windows shell treat us as a fullscreen app and
        # demote the taskbar. The 1px gap is invisible (overlay is transparent and
        # the duck flies near the top).
        g = screen.geometry()
        return QRect(g.x(), g.y(), g.width(), max(1, g.height() - 1))

    def _apply_native_styles(self) -> None:
        winutils.make_overlay(int(self.winId()))
        winutils.assert_topmost(int(self.winId()))

    def _target_screen(self):
        if config.get_prefs().get("target_display") == "primary":
            return QGuiApplication.primaryScreen()
        at = QGuiApplication.screenAt(QCursor.pos())
        return at or QGuiApplication.primaryScreen()

    def _layout_rig(self) -> None:
        """Place banner | gap | aircraft and size the rig to fit."""
        bw, bh = self._banner.width(), self._banner.height()
        s = AIRCRAFT_S
        rig_h = max(bh, s)
        self._rig.resize(bw + GAP + s, rig_h)

        cy = rig_h // 2
        self._banner.move(0, cy - bh // 2)
        self._aircraft.move(bw + GAP, cy - s // 2)

    def _on_step(self, value: int) -> None:
        self._rig.move(int(value), self._fly_y)

    def _on_finished(self) -> None:
        self._prop_timer.stop()
        self._rig.move(-9999, -9999)  # rest off-screen so nothing lingers
        self.hide()  # Option 2: don't leave a full-screen topmost window around

    def _spin(self) -> None:
        # Rotate the blade about its hub (not the image centre) onto a fixed
        # canvas, so the prop stays pinned at the nose as it spins.
        self._prop_angle = (self._prop_angle + 42) % 360
        canvas = QPixmap(self._prop_src.size())
        canvas.fill(Qt.transparent)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        hx = self._prop_src.width() * PROP_HUB[0]
        hy = self._prop_src.height() * PROP_HUB[1]
        p.translate(hx, hy)
        p.rotate(self._prop_angle)
        p.translate(-hx, -hy)
        p.drawPixmap(0, 0, self._prop_src)
        p.end()
        self._prop.setPixmap(canvas)

    def _load(self, name: str, size: int) -> QPixmap:
        path = assets_dir() / name
        pix = QPixmap(str(path))
        if pix.isNull():
            placeholder = QPixmap(size, size)
            placeholder.fill(Qt.transparent)  # transparent placeholder
            return placeholder
        return pix.scaledToHeight(size, Qt.SmoothTransformation)
