import os
import subprocess
import sys
from pathlib import Path


def open_file(path: Path):
    try:
        if os.environ.get("TERMUX_VERSION"):
            subprocess.Popen(["termux-open", str(path)])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            print(f"Open {path} in your browser.")
    except Exception:
        print(f"Open {path} in your browser.")
