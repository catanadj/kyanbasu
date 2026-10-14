import contextlib
import io
import os
import unittest
from pathlib import Path
from typing import get_type_hints
from unittest.mock import patch

from kyanbasu.output import open_file


class TestOpenFile(unittest.TestCase):
    def test_open_file_public_type_contract(self):
        self.assertEqual(get_type_hints(open_file), {"path": Path, "return": bool})

    def setUp(self):
        self.path = Path("/tmp/Kyanbasu.html")

    def test_termux_uses_termux_open(self):
        with patch.dict(os.environ, {"TERMUX_VERSION": "1"}, clear=False), patch(
            "kyanbasu.output.subprocess.Popen"
        ) as popen:
            self.assertTrue(open_file(self.path))
        popen.assert_called_once_with(["termux-open", str(self.path)])

    def test_linux_uses_xdg_open(self):
        with patch.dict(os.environ, {}, clear=True), patch("kyanbasu.output.sys.platform", "linux"), patch(
            "kyanbasu.output.subprocess.Popen"
        ) as popen:
            self.assertTrue(open_file(self.path))
        popen.assert_called_once_with(["xdg-open", str(self.path)])

    def test_macos_uses_open(self):
        with patch.dict(os.environ, {}, clear=True), patch("kyanbasu.output.sys.platform", "darwin"), patch(
            "kyanbasu.output.subprocess.Popen"
        ) as popen:
            self.assertTrue(open_file(self.path))
        popen.assert_called_once_with(["open", str(self.path)])

    def test_windows_uses_startfile(self):
        with patch.dict(os.environ, {}, clear=True), patch("kyanbasu.output.sys.platform", "win32"), patch(
            "kyanbasu.output.os.startfile", create=True
        ) as startfile:
            self.assertTrue(open_file(self.path))
        startfile.assert_called_once_with(str(self.path))

    def test_unsupported_platform_prints_manual_instruction(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch("kyanbasu.output.sys.platform", "plan9"), contextlib.redirect_stdout(output):
            self.assertFalse(open_file(self.path))
        self.assertIn("Open /tmp/Kyanbasu.html in your browser.", output.getvalue())

    def test_launch_failure_prints_manual_instruction(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch("kyanbasu.output.sys.platform", "linux"), patch(
            "kyanbasu.output.subprocess.Popen", side_effect=OSError("no browser")
        ), contextlib.redirect_stdout(output):
            self.assertFalse(open_file(self.path))
        self.assertIn("Open /tmp/Kyanbasu.html in your browser.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
