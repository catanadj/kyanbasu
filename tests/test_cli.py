import unittest

from taskcanvas.cli import _extract_bg_args, _extract_filter_arg, build_parser, parse_args


class TestCliHelpers(unittest.TestCase):
    def test_extract_filter_arg_separate_token(self):
        filt, rest = _extract_filter_arg(["--filter", "project:Work +P1", "Home"])
        self.assertEqual(filt, "project:Work +P1")
        self.assertEqual(rest, ["Home"])

    def test_extract_filter_arg_equals_form(self):
        filt, rest = _extract_filter_arg(["--filter=due.before:today", "Home"])
        self.assertEqual(filt, "due.before:today")
        self.assertEqual(rest, ["Home"])

    def test_extract_filter_arg_missing_value_raises(self):
        with self.assertRaisesRegex(ValueError, "--filter requires a value"):
            _extract_filter_arg(["--filter"])

    def test_extract_bg_args_mixed_forms(self):
        bg, opacity, rest = _extract_bg_args(["--bg", "wall.jpg", "--bg-opacity=0.22", "Home"])
        self.assertEqual(bg, "wall.jpg")
        self.assertEqual(opacity, "0.22")
        self.assertEqual(rest, ["Home"])

    def test_extract_bg_args_equals_form(self):
        bg, opacity, rest = _extract_bg_args(["--bg=wall.jpg", "Inbox"])
        self.assertEqual(bg, "wall.jpg")
        self.assertIsNone(opacity)
        self.assertEqual(rest, ["Inbox"])

    def test_extract_bg_args_missing_value_raises(self):
        with self.assertRaisesRegex(ValueError, "--bg requires a value"):
            _extract_bg_args(["--bg"])

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

    def test_help_uses_kyanbasu_identity_and_compatible_command(self):
        help_text = build_parser().format_help()
        self.assertIn("usage: taskcanvas", help_text)
        self.assertIn("Kyanbasu visual planning workspace", help_text)

    def test_parse_args_version_exits_zero(self):
        with self.assertRaises(SystemExit) as cm:
            parse_args(["--version"])
        self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
