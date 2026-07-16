import argparse

from kyanbasu import __version__


class _KyanbasuParser(argparse.ArgumentParser):
    def error(self, message):
        if "argument -f/--filter: expected one argument" in message:
            raise ValueError("--filter requires a value")
        if "argument --bg: expected one argument" in message:
            raise ValueError("--bg requires a value")
        if "argument --bg-opacity: expected one argument" in message:
            raise ValueError("--bg-opacity requires a value")
        raise ValueError(message)


def build_parser(*, prog: str = "kyanbasu") -> argparse.ArgumentParser:
    parser = _KyanbasuParser(
        prog=prog,
        description="Generate a Kyanbasu visual planning workspace for Taskwarrior.",
    )
    parser.add_argument(
        "projects",
        nargs="*",
        help="Project names to place on the initial canvas.",
    )
    parser.add_argument(
        "-f",
        "--filter",
        help="Taskwarrior filter expression used to place matching tasks initially.",
    )
    parser.add_argument(
        "--selector",
        action="store_true",
        help="Open the interactive project selector before generating the canvas.",
    )
    parser.add_argument(
        "--bg",
        help="Background image to copy next to the generated workspace and use behind the canvas.",
    )
    parser.add_argument(
        "--bg-opacity",
        help="Background overlay opacity, e.g. 0.18.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{'Kyanbasu' if prog == 'kyanbasu' else prog} {__version__}",
    )
    return parser


def parse_args(argv=None, *, prog: str = "kyanbasu"):
    return build_parser(prog=prog).parse_args(argv)


def _extract_filter_arg(argv):
    """
    Extract the filter option and return it with the remaining arguments.
    Supports:
      -f "project:Work +P1"
      --filter "due.before:2025-10-01 status:pending"
      --filter=project:Work
    """
    filt = None
    out = []
    skip_next = False
    for i, a in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if a == "-f" or a == "--filter":
            if i + 1 < len(argv):
                filt = argv[i + 1]
                skip_next = True
            else:
                raise ValueError("--filter requires a value")
        elif a.startswith("--filter="):
            filt = a.split("=", 1)[1]
        else:
            out.append(a)
    return filt, out


def _extract_bg_args(argv):
    """Extract background options and return them with remaining arguments."""
    bg = None
    opacity = None
    out = []
    skip = False
    for i, a in enumerate(argv):
        if skip:
            skip = False
            continue
        if a == "--bg":
            if i + 1 < len(argv):
                bg = argv[i + 1]
                skip = True
            else:
                raise ValueError("--bg requires a value")
        elif a == "--bg-opacity":
            if i + 1 < len(argv):
                opacity = argv[i + 1]
                skip = True
            else:
                raise ValueError("--bg-opacity requires a value")
        elif a.startswith("--bg="):
            bg = a.split("=", 1)[1]
        elif a.startswith("--bg-opacity="):
            opacity = a.split("=", 1)[1]
        else:
            out.append(a)
    return bg, opacity, out
