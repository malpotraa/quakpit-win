"""Flight audio: a synthesized propeller drone plus a selectable signature sound.

Each sound is either **synthesized** with the standard library (no asset to ship,
e.g. the engine and "pew pew") or a bundled **.wav clip** (e.g. the quack, or a
CC0 goat scream). The set offered to the user is whatever is actually available
at runtime — synth sounds always, clips only when their file is present — so a
sound whose asset hasn't been added yet simply doesn't appear in the picker.
"""

from __future__ import annotations

import math
import struct
import tempfile
import wave
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtMultimedia import QSoundEffect

from . import config

_SAMPLE_RATE = 44_100

# id -> spec.  kind 'clip' => assets/<file>;  kind 'synth' => generated once.
# offsets_ms: trigger times (relative to the base moment) for each repeat.
SOUNDS: dict[str, dict] = {
    "quack": {
        "name": "Duck quack",
        "kind": "clip",
        "file": "quack.wav",
        "offsets_ms": [0, 380],
        "volume": 0.9,
    },
    "pewpew": {
        "name": "Pew pew (laser)",
        "kind": "synth",
        "synth": "pew",
        "offsets_ms": [0, 170],
        "volume": 0.7,
    },
    "goat": {
        "name": "Goat scream",
        "kind": "clip",
        "file": "sounds/goat-scream.wav",
        "offsets_ms": [0],
        "volume": 1.0,
    },
}
DEFAULT_SOUND = "quack"

_engine: QSoundEffect | None = None
_effects: dict[str, QSoundEffect] = {}
_engine_path: Path | None = None
_synth_paths: dict[str, Path] = {}


# --- synthesis ---------------------------------------------------------------
def _write_wav(path: Path, samples: list[float]) -> None:
    frames = bytearray()
    for s in samples:
        frames += struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_SAMPLE_RATE)
        w.writeframes(bytes(frames))


def _synth_engine() -> Path:
    """A ~2s seamlessly-loopable propeller drone."""
    global _engine_path
    if _engine_path and _engine_path.exists():
        return _engine_path
    n = int(_SAMPLE_RATE * 2.0)
    base = 92.0
    out: list[float] = []
    for i in range(n):
        t = i / _SAMPLE_RATE
        saw1 = 2.0 * (t * base % 1.0) - 1.0
        saw2 = 2.0 * (t * base * 1.012 % 1.0) - 1.0
        s = 0.6 * ((saw1 + saw2) * 0.5) + 0.4 * math.sin(2 * math.pi * base * t)
        s *= 0.85 + 0.15 * math.sin(2 * math.pi * 11.0 * t)  # prop wobble
        out.append(s * 0.22)
    p = Path(tempfile.gettempdir()) / "quakpit-engine.wav"
    _write_wav(p, out)
    _engine_path = p
    return p


def _synth_pew() -> Path:
    """A short descending laser 'pew' — pitch 1200→300 Hz with a fast decay."""
    n = int(_SAMPLE_RATE * 0.18)
    out: list[float] = []
    for i in range(n):
        frac = i / n
        t = i / _SAMPLE_RATE
        freq = 1200.0 * (300.0 / 1200.0) ** frac
        env = math.exp(-5.0 * frac)
        sine = math.sin(2 * math.pi * freq * t)
        square = 1.0 if sine >= 0 else -1.0
        out.append((0.7 * sine + 0.3 * square) * env * 0.5)
    p = Path(tempfile.gettempdir()) / "quakpit-pew.wav"
    _write_wav(p, out)
    return p


_SYNTHS = {"pew": _synth_pew}


# --- effects -----------------------------------------------------------------
def _effect(path: Path, volume: float, loops: int = 1) -> QSoundEffect:
    fx = QSoundEffect()
    fx.setSource(QUrl.fromLocalFile(str(path)))
    fx.setVolume(volume)
    fx.setLoopCount(loops)
    return fx


def _source_path(meta: dict) -> Path | None:
    """Resolve a sound's wav path, generating synth wavs on first use."""
    if meta["kind"] == "clip":
        p = config.assets_dir() / meta["file"]
        return p if p.exists() else None
    sid = meta["synth"]
    if sid not in _synth_paths:
        try:
            _synth_paths[sid] = _SYNTHS[sid]()
        except Exception:
            return None
    return _synth_paths[sid]


def available_sounds() -> list[tuple[str, str]]:
    """(id, name) for every sound whose source exists right now."""
    return [
        (sid, meta["name"])
        for sid, meta in SOUNDS.items()
        if _source_path(meta) is not None
    ]


def init() -> None:
    """Pre-load the engine and every available sound (call once, on the GUI thread)."""
    global _engine
    try:
        _engine = _effect(_synth_engine(), 0.16, QSoundEffect.Infinite)
    except Exception:
        _engine = None
    for sid, meta in SOUNDS.items():
        path = _source_path(meta)
        if path is None:
            continue
        try:
            _effects[sid] = _effect(path, meta.get("volume", 0.9))
        except Exception:
            pass


def _play_effect(sid: str) -> None:
    fx = _effects.get(sid)
    if fx is not None:
        try:
            fx.play()
        except Exception:
            pass


def preview(sound_id: str) -> None:
    """Play a sound once (no engine) — for the Settings preview button."""
    meta = SOUNDS.get(sound_id) or SOUNDS[DEFAULT_SOUND]
    if sound_id not in _effects:
        return
    for off in meta["offsets_ms"]:
        QTimer.singleShot(max(0, off), lambda s=sound_id: _play_effect(s))


def play_flight(duration_ms: int, sound_id: str = DEFAULT_SOUND) -> None:
    """Start the drone for the flight and play the chosen sound at mid-screen."""
    if _engine is not None:
        try:
            _engine.play()
        except Exception:
            pass

    meta = SOUNDS.get(sound_id) or SOUNDS[DEFAULT_SOUND]
    mid = max(0, duration_ms // 2)
    if sound_id in _effects:
        for off in meta["offsets_ms"]:
            QTimer.singleShot(mid + off, lambda s=sound_id: _play_effect(s))

    QTimer.singleShot(max(0, duration_ms), _stop_engine)


def _stop_engine() -> None:
    if _engine is not None:
        try:
            _engine.stop()
        except Exception:
            pass
