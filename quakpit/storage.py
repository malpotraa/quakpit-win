"""Secret storage backed by the OS credential vault.

On Windows ``keyring`` uses the Credential Manager (DPAPI-protected), which is
the analogue of the macOS Keychain the original app relied on. Calendar events
are never stored — only the OAuth refresh token, the Google client credentials
the user pastes, and (optionally) a cached email for display.
"""

from __future__ import annotations

from . import APP_NAME

try:
    import keyring
except Exception:  # pragma: no cover - keyring missing in some dev shells
    keyring = None  # type: ignore[assignment]

SERVICE = APP_NAME


def save_secret(key: str, value: str) -> None:
    if keyring is None:
        return
    try:
        keyring.set_password(SERVICE, key, value)
    except Exception:
        pass


def load_secret(key: str) -> str | None:
    if keyring is None:
        return None
    try:
        return keyring.get_password(SERVICE, key)
    except Exception:
        return None


def clear_secret(key: str) -> None:
    if keyring is None:
        return
    try:
        keyring.delete_password(SERVICE, key)
    except Exception:
        pass  # not present is fine
