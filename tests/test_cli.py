import contextlib
import io
import unittest
import argparse
from collections.abc import Sequence
from typing import get_type_hints

import kyanbasu.cli as cli
from kyanbasu.cli import build_parser, parse_args


class TestCliHelpers(unittest.TestCase):
    def test_parse_args_and_parser_error_have_precise_api_types(self):
        self.assertEqual(
            get_type_hints(cli.parse_args),
            {
                "argv": Sequence[str] | None,
                "prog": str,
                "return": argparse.Namespace,
            },
        )
        self.assertEqual(
            get_type_hints(cli._KyanbasuParser.error),
            {"message": str, "return": type(None)},
        )

    def test_parse_args_accepts_current_cli_shape(self):
        args = parse_args([
            "--filter",
            "project:Work +P1",
            "--selector",
            "--bg",
            "wall.jpg",
            "--bg-opacity=0.22",
            "Home",
        ])
        self.assertEqual(args.filter, "project:Work +P1")
        self.assertTrue(args.selector)
        self.assertEqual(args.bg, "wall.jpg")
        self.assertEqual(args.bg_opacity, "0.22")
        self.assertEqual(args.projects, ["Home"])

    def test_parse_args_missing_filter_value_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "--filter requires a value"):
            parse_args(["--filter"])

    def test_parse_args_help_exits_zero(self):
        with self.assertRaises(SystemExit) as cm:
            parse_args(["--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_help_uses_kyanbasu_identity_and_primary_command(self):
        help_text = build_parser().format_help()
        self.assertIn("usage: kyanbasu", help_text)
        self.assertIn("Kyanbasu visual planning workspace", help_text)

    def test_parse_args_version_exits_zero(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as cm:
            parse_args(["--version"])
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), "Kyanbasu 0.3.0")


if __name__ == "__main__":
    unittest.main()
