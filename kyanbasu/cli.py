import argparse
from collections.abc import Sequence

from kyanbasu.version import __version__


class _KyanbasuParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
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


def parse_args(
    argv: Sequence[str] | None = None,
    *,
    prog: str = "kyanbasu",
) -> argparse.Namespace:
    return build_parser(prog=prog).parse_args(argv)
