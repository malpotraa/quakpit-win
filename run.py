"""Launcher entry point (used by PyInstaller and for `python run.py` in dev)."""

import sys

from quakpit.app import main

if __name__ == "__main__":
    sys.exit(main())
