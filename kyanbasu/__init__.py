"""Public Kyanbasu package facade."""

from taskcanvas import __version__
from taskcanvas.app import kyanbasu_main as main

__all__ = ["__version__", "main"]
