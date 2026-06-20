# Quakpit for Windows 🦆✈️ (Python)

A little duck in a plane flies across your screen — above every app, even full-screen —
towing a banner that reminds you of your next meeting, with a propeller drone and a quack.
Fully automatic from your **Google Calendar**.

This is an independent **Windows / Python** port of [Quakpit by Ooble Studio](https://ooble.studio)
(originally an Electron app for macOS). Same idea, rebuilt in Python with PySide6.

- **Always on top** — floats above your apps, including borderless full-screen windows.
- **Click-through** — the overlay never intercepts your clicks.
- **Auto-start** — launches when you sign in to Windows.
- **Google Calendar via OAuth** — your own OAuth client; nothing routes through a server.
- **No server, no database, no telemetry.** Events are kept in memory only. The OAuth
  refresh token and your client secret live in the **Windows Credential Manager** (DPAPI).

---

## Quick start (run from source)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

The app opens its settings window and drops an icon in the system tray. Use the
tray menu's **Send a test flight** any time.

## Connect Google Calendar (one-time)

You bring your own Google OAuth client so nothing goes through anyone else:

1. <https://console.cloud.google.com/> → create a project.
2. **APIs & Services → Library** → enable **Google Calendar API**.
3. **OAuth consent screen** → External. Add the scope
   `.../auth/calendar.events.readonly`. Add your account under **Test users**.
4. **Credentials → Create credentials → OAuth client ID → Desktop app**.
5. Either:
   - paste the **Client ID / Client secret** into Quakpit’s settings and click
     **Save credentials**, **or**
   - copy `oauth-credentials.example.json` to **`oauth-credentials.json`** next to the
     app (or in `%APPDATA%\Quakpit`) and fill it in.

Then click **Connect** — your browser opens, you approve, and a `127.0.0.1` loopback
server captures the code. (For desktop apps the client secret is not confidential.)

## Build the Windows installer

> A runnable `.exe` and installer can only be produced **on Windows** (PyInstaller +
> Inno Setup target Windows). On macOS/Linux `build.py` only pre-generates the icon.

On a Windows machine:

```bat
pip install -r requirements.txt
pip install pillow            REM optional, for the .ico app icon
python build.py
```

`build.py` runs three steps:

1. **Icon** — `quakpit/assets/logo.png` → `logo.ico` (needs Pillow).
2. **Executable** — PyInstaller builds `dist\Quakpit\Quakpit.exe` (one-folder, windowed)
   from `quakpit.spec`.
3. **Installer** — [Inno Setup](https://jrsoftware.org/isdl.php)’s `ISCC.exe` compiles
   `installer\quakpit.iss` → `dist\installer\Quakpit-Setup.exe`.

If Inno Setup isn’t installed, the standalone `dist\Quakpit\Quakpit.exe` already works;
install Inno Setup and re-run to get the wrapped installer.

The installer is **per-user** (no admin rights), offers an **autostart** checkbox, and
adds a Start-menu (and optional desktop) shortcut. The app itself can also toggle
autostart from **Settings → “Launch Quakpit at startup”** (per-user `Run` registry key).

## Deploying to an organization (bundled sign-in)

For an internal rollout you ship **one** OAuth client so colleagues never enter keys
— they install, click **Connect**, approve, done. See `INSTALL.md` for the end-user
one-pager.

1. In Google Cloud Console, in your project, create an **OAuth client ID → Desktop
   app**. Confirm the consent screen lists the `calendar.events.readonly` scope.
   - Users not all on one Workspace domain → consent screen stays **External**.
     Set publishing status to **In production** (even unverified) so refresh tokens
     don’t expire every 7 days; users click through a one-time “unverified app”
     notice. Verification (the lighter, sensitive-scope review) removes that notice
     and the ~100-user cap when you scale.
2. Put the client’s id/secret in **`oauth-credentials.json`** in the project root
   (copy `oauth-credentials.example.json`). This file is **gitignored — never commit
   it.**
3. `python build.py`. The installer auto-detects that file and ships it next to the
   `.exe`; the app finds it on first launch, hides the credential fields, and shows
   “Connect.” A Desktop client’s secret is non-confidential by design, so bundling it
   is expected.
4. Share `dist\installer\Quakpit-Setup.exe` (per-user, no admin) and `INSTALL.md`.

## How it works

| Concern | Implementation |
| --- | --- |
| Always-on-top, click-through overlay | Frameless translucent `QWidget` + native `WS_EX_LAYERED \| WS_EX_TRANSPARENT \| WS_EX_TOOLWINDOW \| WS_EX_NOACTIVATE`, re-pinned `HWND_TOPMOST` each flight (`quakpit/winutils.py`, `overlay.py`) |
| Above full-screen apps | Topmost tool window floats over **borderless** full-screen apps. **Exclusive** full-screen DirectX games take the whole GPU surface and can’t be reliably overlaid by any normal window — same limitation as the original. |
| Google OAuth | `google-auth-oauthlib` loopback flow + `requests` for the Calendar API (`google_calendar.py`) |
| Scheduling | `QTimer` poll (60 s) + tick (15 s), fires at `start − lead`, dedup per event (`scheduler.py`) |
| Secrets | `keyring` → Windows Credential Manager (`storage.py`) |
| Auto-start | per-user `Run` key, toggled in Settings or by the installer (`autostart.py`) |
| Sound | synthesized propeller drone (stdlib `wave`) + `quack.wav`, via `QSoundEffect` (`audio.py`) |

## Project layout

```
run.py                  launcher (PyInstaller entry)
build.py                icon → PyInstaller → Inno Setup
quakpit.spec            PyInstaller spec
installer/quakpit.iss   Inno Setup installer script
quakpit/
  app.py                wiring: tray, overlay, scheduler, settings, single-instance
  overlay.py            the flying duck window
  google_calendar.py    OAuth + event fetching
  scheduler.py          poll / tick / fire
  settings_window.py    the control window
  tray.py               tray icon
  audio.py              engine drone + quack
  storage.py            credential-vault secrets
  config.py             prefs + paths
  autostart.py          launch-at-login
  winutils.py           native window styles
  assets/               duck / plane / propeller / quack / logo
```

## License

[MIT](LICENSE). Independent port; artwork & quack reused from the upstream
MIT-licensed Quakpit by **[Ooble Studio](https://ooble.studio)**.
