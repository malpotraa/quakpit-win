"""Flight audio: a synthesized propeller drone plus the quack at mid-screen.

We use ``QSoundEffect`` so the drone (looping) and the quack (one-shot) can play
at once. The engine drone is generated once at startup into a temp .wav with the
standard library — two slightly detuned saws through a soft low-pass, with a
tremolo wobble — so there's no binary engine asset to ship.
"""

from __future__ import annotations

import math
import struct
import tempfile
import wave
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

from . import config

_SAMPLE_RATE = 44_100
_engine_path: Path | None = None
_engine: QSoundEffect | None = None
_quack: QSoundEffect | None = None


def _synth_engine_wav() -> Path:
    """A ~2s seamlessly-loopable propeller drone, written to a temp file."""
    global _engine_path
    if _engine_path and _engine_path.exists():
        return _engine_path

    seconds = 2.0
    n = int(_SAMPLE_RATE * seconds)
    base = 92.0  # Hz, fundamental
    frames = bytearray()
    for i in range(n):
        t = i / _SAMPLE_RATE
        # Two detuned sawtooths.
        saw1 = 2.0 * (t * base % 1.0) - 1.0
        saw2 = 2.0 * (t * base * 1.012 % 1.0) - 1.0
        sample = (saw1 + saw2) * 0.5
        # Soft low-pass-ish shaping by mixing in the fundamental sine.
        sample = 0.6 * sample + 0.4 * math.sin(2 * math.pi * base * t)
        # Tremolo wobble (prop blades), 11 Hz.
        sample *= 0.85 + 0.15 * math.sin(2 * math.pi * 11.0 * t)
        sample *= 0.22  # headroom
        frames += struct.pack("<h", int(max(-1.0, min(1.0, sample)) * 32767))

    path = Path(tempfile.gettempdir()) / "quakpit-engine.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_SAMPLE_RATE)
        w.writeframes(bytes(frames))
    _engine_path = path
    return path


def _effect(path: Path, volume: float, loops: int = 1) -> QSoundEffect:
    fx = QSoundEffect()
    fx.setSource(QUrl.fromLocalFile(str(path)))
    fx.setVolume(volume)
    fx.setLoopCount(loops)
    return fx


def init() -> None:
    """Pre-load the sound effects (call once, on the GUI thread)."""
    global _engine, _quack
    try:
        _engine = _effect(_synth_engine_wav(), 0.16, QSoundEffect.Infinite)
    except Exception:
        _engine = None
    try:
        quack = config.assets_dir() / "quack.wav"
        if quack.exists():
            _quack = _effect(quack, 0.9)
    except Exception:
        _quack = None


def play_flight(duration_ms: int) -> None:
    """Start the drone for the flight and quack at the half-way point."""
    if _engine is not None:
        try:
            _engine.play()
        except Exception:
            pass

    from PySide6.QtCore import QTimer

    # Quack as the plane passes the middle of the screen.
    if _quack is not None:
        QTimer.singleShot(max(0, duration_ms // 2), _safe_quack)
    # Cut the engine when the crossing ends.
    QTimer.singleShot(max(0, duration_ms), _stop_engine)


def _safe_quack() -> None:
    try:
        if _quack is not None:
            _quack.play()
    except Exception:
        pass


def _stop_engine() -> None:
    try:
        if _engine is not None:
            _engine.stop()
    except Exception:
        pass
