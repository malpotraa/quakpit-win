"""Secret storage backed by the Windows Credential Manager (DPAPI), via ctypes.

This is the Windows analogue of the macOS Keychain the original app used — the
vault is encrypted at rest and scoped to the logged-in user. We talk to
``advapi32`` (CredWriteW / CredReadW / CredDeleteW) directly so there's no
third-party dependency. Calendar events are never stored; only the OAuth refresh
token and the Google client credentials the user pastes.

Off Windows every call is a safe no-op (returns None), so the rest of the app
imports cleanly during development on other platforms.
"""

from __future__ import annotations

import sys

from . import APP_NAME

IS_WINDOWS = sys.platform == "win32"

_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2


def _target(key: str) -> str:
    return f"{APP_NAME}:{key}"


if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    class _CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    _PCREDENTIAL = ctypes.POINTER(_CREDENTIAL)

    _advapi32.CredWriteW.argtypes = [_PCREDENTIAL, wintypes.DWORD]
    _advapi32.CredWriteW.restype = wintypes.BOOL
    _advapi32.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_PCREDENTIAL),
    ]
    _advapi32.CredReadW.restype = wintypes.BOOL
    _advapi32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    _advapi32.CredDeleteW.restype = wintypes.BOOL
    _advapi32.CredFree.argtypes = [ctypes.c_void_p]
    _advapi32.CredFree.restype = None


def save_secret(key: str, value: str) -> None:
    if not IS_WINDOWS:
        return
    try:
        blob = value.encode("utf-16-le")
        buf = ctypes.create_string_buffer(blob, len(blob))  # exact length, no NUL
        cred = _CREDENTIAL()
        cred.Type = _CRED_TYPE_GENERIC
        cred.TargetName = _target(key)
        cred.CredentialBlobSize = len(blob)
        cred.CredentialBlob = ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))
        cred.Persist = _CRED_PERSIST_LOCAL_MACHINE
        cred.UserName = APP_NAME
        _advapi32.CredWriteW(ctypes.byref(cred), 0)
    except Exception:
        pass


def load_secret(key: str) -> str | None:
    if not IS_WINDOWS:
        return None
    pcred = _PCREDENTIAL()
    try:
        if not _advapi32.CredReadW(_target(key), _CRED_TYPE_GENERIC, 0, ctypes.byref(pcred)):
            return None
        cred = pcred.contents
        data = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
        return data.decode("utf-16-le")
    except Exception:
        return None
    finally:
        if pcred:
            try:
                _advapi32.CredFree(pcred)
            except Exception:
                pass


def clear_secret(key: str) -> None:
    if not IS_WINDOWS:
        return
    try:
        _advapi32.CredDeleteW(_target(key), _CRED_TYPE_GENERIC, 0)
    except Exception:
        pass  # not present is fine
