# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Quakpit (Windows).

Build:  pyinstaller quakpit.spec --noconfirm --clean
Output: dist/Quakpit/Quakpit.exe  (one-folder build; the installer wraps it)
"""

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

datas = [
    ("quakpit/assets", "assets"),
]

# google-auth-oauthlib / keyring pull in a few dynamically-imported backends.
hiddenimports = (
    collect_submodules("keyring.backends")
    + collect_submodules("google_auth_oauthlib")
    + ["win32timezone"]
)

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Quakpit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed app — no console
    icon=os.path.join("quakpit", "assets", "logo.ico")
    if os.path.exists(os.path.join("quakpit", "assets", "logo.ico"))
    else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Quakpit",
)
