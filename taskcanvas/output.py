import os
import subprocess
import sys
from pathlib import Path


def open_file(path: Path):
    try:
        if os.environ.get("TERMUX_VERSION"):
            subprocess.Popen(["termux-open", str(path)])
            return True
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(path)])
            return True
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
            return True
        elif sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
            return True
        else:
            print(f"Open {path} in your browser.")
            return False
    except (AttributeError, OSError, subprocess.SubprocessError):
        print(f"Open {path} in your browser.")
        return False
