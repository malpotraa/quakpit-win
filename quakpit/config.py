"""Non-personal preferences and on-disk paths.

No calendar data ever lives here — only UI preferences. Secrets (OAuth tokens,
client credentials) go through ``storage`` into the Windows Credential Manager.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from . import APP_NAME

DEFAULT_PREFS: dict[str, Any] = {
    "lead_minutes": 5,
    "message_template": "{title} in {minutes} minutes",
    "sound_enabled": True,
    "stay_signed_in": True,
    "launch_at_login": False,
    "target_display": "cursor",  # "cursor" | "primary"
    "fly_at_start": False,
    "duration_ms": 11000,
    "character": "duck",  # "duck" | "goat" | "custom"
    "sound_pack": "quack",  # see audio.SOUNDS
}


def data_dir() -> Path:
    """Per-user writable folder, e.g. ``%APPDATA%\\Quakpit`` on Windows."""
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    d = root / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def app_dir() -> Path:
    """Folder the app runs from (next to the frozen .exe, or the package root)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def assets_dir() -> Path:
    """Bundled assets. PyInstaller unpacks data files under ``sys._MEIPASS``."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "assets"
    return Path(__file__).resolve().parent / "assets"


def _prefs_path() -> Path:
    return data_dir() / "prefs.json"


def custom_character_path() -> Path:
    """The user's uploaded pilot image, kept locally (normalised to PNG)."""
    return data_dir() / "custom-character.png"


_cache: dict[str, Any] | None = None


def get_prefs() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    try:
        raw = json.loads(_prefs_path().read_text("utf-8"))
        _cache = {**DEFAULT_PREFS, **raw}
    except Exception:
        _cache = dict(DEFAULT_PREFS)
    return _cache


def set_prefs(patch: dict[str, Any]) -> dict[str, Any]:
    nxt = {**get_prefs(), **patch}
    global _cache
    _cache = nxt
    try:
        _prefs_path().write_text(json.dumps(nxt, indent=2), "utf-8")
    except Exception:
        pass  # preferences are best-effort
    return nxt
