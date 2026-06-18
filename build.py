"""One-command Windows build: icon -> PyInstaller -> Inno Setup installer.

Run on Windows from the project root, inside your virtualenv:

    pip install -r requirements.txt
    python build.py

Steps (each best-effort, with a clear message if a tool is missing):
  1. Generate quakpit/assets/logo.ico from logo.png (needs Pillow).
  2. Build dist/Quakpit/ with PyInstaller (using quakpit.spec).
  3. Compile installer/quakpit.iss with Inno Setup's ISCC.exe -> dist/installer/.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "quakpit" / "assets"


def step(msg: str) -> None:
    print(f"\n=== {msg} ===")


def make_icon() -> None:
    step("1/3  Generating app icon (.ico)")
    png = ASSETS / "logo.png"
    ico = ASSETS / "logo.ico"
    if not png.exists():
        print("  ! logo.png not found — skipping icon.")
        return
    try:
        from PIL import Image
    except ImportError:
        print("  ! Pillow not installed (pip install pillow) — building without a custom icon.")
        return
    img = Image.open(png).convert("RGBA")
    sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    img.save(ico, format="ICO", sizes=sizes)
    print(f"  -> {ico}")


def build_exe() -> None:
    step("2/3  Building the .exe with PyInstaller")
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("  ! PyInstaller not installed. Run: pip install -r requirements.txt")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "quakpit.spec", "--noconfirm", "--clean"],
        cwd=ROOT,
        check=True,
    )
    print("  -> dist/Quakpit/Quakpit.exe")


def build_installer() -> None:
    step("3/3  Compiling the installer with Inno Setup")
    iscc = shutil.which("ISCC") or shutil.which("ISCC.exe")
    if not iscc:
        for guess in (
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe",
        ):
            if Path(guess).exists():
                iscc = guess
                break
    if not iscc:
        print(
            "  ! Inno Setup (ISCC.exe) not found. Install it from https://jrsoftware.org/isdl.php\n"
            "    then re-run, or compile installer/quakpit.iss by hand. The .exe in dist/Quakpit/ "
            "already works on its own."
        )
        return
    subprocess.run([iscc, "installer/quakpit.iss"], cwd=ROOT, check=True)
    print("  -> dist/installer/Quakpit-Setup.exe")


if __name__ == "__main__":
    if sys.platform != "win32":
        print("NOTE: a runnable Windows .exe/installer can only be produced on Windows.")
        print("This script will still generate the icon so you can commit it.\n")
        make_icon()
        sys.exit(0)
    make_icon()
    build_exe()
    build_installer()
    print("\nDone. \U0001f986")
