"""Launch-at-login via the per-user Run registry key (Windows).

We use ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`` rather than a
Startup-folder shortcut so the toggle in Settings can add/remove it cleanly with
no admin rights. Off Windows these are no-ops.
"""

from __future__ import annotations

import sys

from . import APP_NAME

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
IS_WINDOWS = sys.platform == "win32"


def _command() -> str:
    """The command Windows should run at login (quoted)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # Dev mode: launch the module with the windowed interpreter if available.
    exe = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{exe}" -m quakpit'


def set_enabled(enabled: bool) -> None:
    if not IS_WINDOWS:
        return
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
    except Exception:
        pass


def is_enabled() -> bool:
    if not IS_WINDOWS:
        return False
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_QUERY_VALUE
        ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except Exception:
        return False
