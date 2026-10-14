import os
import subprocess
import sys
from pathlib import Path


def _launch_platform_open(path: Path) -> bool:
    # Fire-and-forget is intentional: opening a browser must not wait for it to exit.
    if os.environ.get("TERMUX_VERSION"):
        subprocess.Popen(["termux-open", str(path)])
        return True
    if sys.platform.startswith("linux"):
        subprocess.Popen(["xdg-open", str(path)])
        return True
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return True
    if sys.platform.startswith("win"):
        # `startfile` is Windows-only, so non-Windows type checkers do not expose it.
        os.startfile(str(path))  # type: ignore[attr-defined]
        return True
    return False


def open_file(path: Path) -> bool:
    try:
        if not _launch_platform_open(path):
            print(f"Open {path} in your browser.")
            return False
        return True
    except (AttributeError, OSError, subprocess.SubprocessError):
        print(f"Open {path} in your browser.")
        return False
