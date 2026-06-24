"""Google Calendar over OAuth 2.0 (desktop / installed-app flow), stdlib only.

The sign-in is the standard loopback + PKCE flow, hand-rolled on the standard
library: open the user's browser, spin up a ``127.0.0.1`` callback server with
``http.server``, exchange the code, and keep an in-memory access token. Every
HTTP call uses ``urllib`` — no third-party dependencies. The refresh token is
persisted only if the user opted into "Stay signed in", in the OS credential
vault, never on disk in the clear.

Events are held in memory only and never written anywhere.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config, storage

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

_REFRESH_KEY = "google_refresh_token"
_CREDS_KEY = "google_creds"  # the user's OAuth client id/secret (JSON)

_SUCCESS_HTML = (
    b"<!doctype html><html><body style='font-family:-apple-system,Segoe UI,sans-serif;"
    b"text-align:center;padding-top:64px;background:#0b1b2b;color:#fff'>"
    b"<h2>\xf0\x9f\xa6\x86 Quakpit is connected!</h2>"
    b"<p>You can close this tab and return to the app.</p></body></html>"
)


@dataclass
class UpcomingEvent:
    id: str
    title: str
    start: float  # epoch milliseconds


# --- in-memory session -------------------------------------------------------
_access_token: str | None = None
_access_expiry: float = 0.0
_refresh_token: str | None = None
_user_email: str | None = None


# --- tiny HTTP helpers (stdlib) ----------------------------------------------
def _post_form(url: str, fields: dict[str, str]) -> dict[str, Any]:
    """POST application/x-www-form-urlencoded; return parsed JSON. Raises on HTTP error."""
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read().decode("utf-8")
    return json.loads(body) if body else {}


def _get_json(url: str, token: str) -> dict[str, Any]:
    """Authorized GET; return parsed JSON. Raises on HTTP error."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


# --- OAuth client credentials (id/secret) ------------------------------------
def _load_creds() -> dict[str, str] | None:
    """Resolve the OAuth client: pasted in-app → env → gitignored JSON file."""
    raw = storage.load_secret(_CREDS_KEY)
    if raw:
        try:
            j = json.loads(raw)
            if j.get("clientId") and j.get("clientSecret"):
                return {"clientId": j["clientId"], "clientSecret": j["clientSecret"]}
        except Exception:
            pass

    env_id = os.environ.get("GOOGLE_CLIENT_ID")
    env_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if env_id and env_secret:
        return {"clientId": env_id, "clientSecret": env_secret}

    # Org-distributed builds ship oauth-credentials.json with the installer.
    # Search: next to the .exe (installer drop) → user data dir → PyInstaller
    # bundle (sys._MEIPASS, if the file was added to the build instead).
    candidates = [config.app_dir(), config.data_dir()]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass))
    for candidate in candidates:
        path = candidate / "oauth-credentials.json"
        try:
            if path.exists():
                j = json.loads(path.read_text("utf-8"))
                cid = j.get("clientId") or j.get("installed", {}).get("client_id")
                sec = j.get("clientSecret") or j.get("installed", {}).get("client_secret")
                if cid and sec:
                    return {"clientId": cid, "clientSecret": sec}
        except Exception:
            pass
    return None


def set_creds(client_id: str, client_secret: str) -> None:
    cid, sec = client_id.strip(), client_secret.strip()
    if not cid or not sec:
        raise ValueError("Enter both the Client ID and the Client secret.")
    storage.save_secret(_CREDS_KEY, json.dumps({"clientId": cid, "clientSecret": sec}))


def is_configured() -> bool:
    return _load_creds() is not None


def status() -> dict[str, Any]:
    return {
        "connected": bool(_refresh_token or _access_token),
        "email": _user_email,
        "configured": is_configured(),
    }


# --- session lifecycle -------------------------------------------------------
def init() -> None:
    """Restore a previous session only if the user opted into 'Stay signed in'."""
    global _refresh_token
    if not config.get_prefs()["stay_signed_in"]:
        return
    _refresh_token = storage.load_secret(_REFRESH_KEY)
    if _refresh_token:
        try:
            _refresh_access()
        except Exception:
            _refresh_token = None


def connect() -> None:
    """Run the interactive OAuth loopback + PKCE flow. Blocking — call off the GUI thread.

    Opens the browser, captures the redirect on a random localhost port, and
    exchanges the code for tokens. PKCE (S256) protects the code in transit.
    """
    global _access_token, _access_expiry, _refresh_token

    creds = _load_creds()
    if not creds:
        raise RuntimeError("Google OAuth credentials are not configured (see README).")

    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())

    captured: dict[str, str] = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (stdlib naming)
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code = (qs.get("code") or [None])[0]
            err = (qs.get("error") or [None])[0]
            if code:
                captured["code"] = code
            elif err:
                captured["error"] = err
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_SUCCESS_HTML)

        def log_message(self, *_args):  # silence the default stderr logging
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    server.timeout = 2  # so handle_request() returns periodically to re-check the deadline
    redirect_uri = f"http://127.0.0.1:{server.server_address[1]}"

    params = urllib.parse.urlencode(
        {
            "client_id": creds["clientId"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    webbrowser.open(f"{AUTH_URL}?{params}")

    deadline = time.monotonic() + 300
    try:
        while not captured and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()

    if "error" in captured or "code" not in captured:
        raise RuntimeError(captured.get("error") or "Sign-in timed out or was cancelled.")

    tok = _post_form(
        TOKEN_URL,
        {
            "code": captured["code"],
            "client_id": creds["clientId"],
            "client_secret": creds["clientSecret"],
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        },
    )
    _access_token = tok["access_token"]
    _access_expiry = (time.time() + float(tok.get("expires_in", 3600))) * 1000.0
    if tok.get("refresh_token"):
        _refresh_token = tok["refresh_token"]
        if config.get_prefs()["stay_signed_in"]:
            storage.save_secret(_REFRESH_KEY, _refresh_token)
    _fetch_user_email()


def disconnect() -> None:
    global _access_token, _access_expiry, _refresh_token, _user_email
    # Revoke server-side first (best effort) so the grant is truly gone, not just
    # forgotten locally. Revoking the refresh token invalidates the whole grant.
    token = _refresh_token or storage.load_secret(_REFRESH_KEY) or _access_token
    if token:
        _revoke_token(token)
    _access_token = None
    _access_expiry = 0.0
    _refresh_token = None
    _user_email = None
    storage.clear_secret(_REFRESH_KEY)


def purge() -> None:
    """Revoke and erase all stored Google state.

    Run headless by the uninstaller via ``Quakpit.exe --purge-credentials`` so
    removing the app truly signs you out — both locally (Windows Credential
    Manager) and server-side at Google — instead of leaving a live token behind.
    """
    token = storage.load_secret(_REFRESH_KEY)
    if token:
        _revoke_token(token)
    storage.clear_secret(_REFRESH_KEY)
    storage.clear_secret(_CREDS_KEY)


def forget_persisted() -> None:
    """Stop persisting the token (toggle off) but keep the live session."""
    storage.clear_secret(_REFRESH_KEY)


def persist_if_possible() -> None:
    """Persist the current token (toggle on), if we have one."""
    if _refresh_token:
        storage.save_secret(_REFRESH_KEY, _refresh_token)


# --- events ------------------------------------------------------------------
def list_upcoming(within_minutes: int = 60) -> list[UpcomingEvent]:
    """Events starting within the next ``within_minutes``. In memory only."""
    if not _refresh_token and not _access_token:
        return []
    token = _get_access_token()

    now = time.time()
    params = {
        "timeMin": _iso(now),
        "timeMax": _iso(now + within_minutes * 60),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": "15",
    }
    data = _get_json(f"{EVENTS_URL}?{urllib.parse.urlencode(params)}", token)
    items = data.get("items", [])

    events: list[UpcomingEvent] = []
    for it in items:
        start = it.get("start", {})
        date_time = start.get("dateTime")
        if not date_time:
            continue  # skip all-day events
        declined = any(
            a.get("self") and a.get("responseStatus") == "declined"
            for a in it.get("attendees", []) or []
        )
        if declined:
            continue
        events.append(
            UpcomingEvent(
                id=it.get("id") or date_time,
                title=it.get("summary") or "Untitled event",
                start=_parse_rfc3339_ms(date_time),
            )
        )
    return events


# --- internals ---------------------------------------------------------------
def _revoke_token(token: str) -> None:
    """Tell Google to invalidate this token/grant. Best effort."""
    try:
        _post_form(REVOKE_URL, {"token": token})
    except Exception:
        pass  # offline, or the token is already invalid — nothing more to do


def _refresh_access() -> None:
    global _access_token, _access_expiry
    creds = _load_creds()
    if not creds or not _refresh_token:
        raise RuntimeError("Cannot refresh: not connected")
    j = _post_form(
        TOKEN_URL,
        {
            "client_id": creds["clientId"],
            "client_secret": creds["clientSecret"],
            "refresh_token": _refresh_token,
            "grant_type": "refresh_token",
        },
    )
    _access_token = j["access_token"]
    _access_expiry = (time.time() + float(j.get("expires_in", 3600))) * 1000.0
    if not _user_email:
        try:
            _fetch_user_email()
        except Exception:
            pass


def _get_access_token() -> str:
    if _access_token and time.time() * 1000.0 < _access_expiry - 60_000:
        return _access_token
    _refresh_access()
    if not _access_token:
        raise RuntimeError("No access token available")
    return _access_token


def _fetch_user_email() -> None:
    global _user_email
    try:
        _user_email = _get_json(USERINFO_URL, _get_access_token()).get("email")
    except Exception:
        pass  # email is cosmetic


def _iso(epoch_seconds: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_seconds))


def _parse_rfc3339_ms(value: str) -> float:
    """Parse a Google RFC3339 timestamp (with offset) to epoch milliseconds."""
    from datetime import datetime

    # Python <3.11 can't parse a trailing 'Z'; normalise it.
    v = value.replace("Z", "+00:00")
    return datetime.fromisoformat(v).timestamp() * 1000.0
