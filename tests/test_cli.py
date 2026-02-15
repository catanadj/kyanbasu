import unittest

from taskcanvas.cli import _extract_bg_args, _extract_filter_arg


class TestCliHelpers(unittest.TestCase):
    def test_extract_filter_arg_separate_token(self):
        filt, rest = _extract_filter_arg(["--filter", "project:Work +P1", "Home"])
        self.assertEqual(filt, "project:Work +P1")
        self.assertEqual(rest, ["Home"])

    def test_extract_filter_arg_equals_form(self):
        filt, rest = _extract_filter_arg(["--filter=due.before:today", "Home"])
        self.assertEqual(filt, "due.before:today")
        self.assertEqual(rest, ["Home"])

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


if __name__ == "__main__":
    unittest.main()
