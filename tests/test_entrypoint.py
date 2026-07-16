import unittest
from unittest.mock import patch

import Kyanbasu
import TaskCanvas
import kyanbasu


class TestEntrypoint(unittest.TestCase):
    def test_primary_script_delegates_with_kyanbasu_identity(self):
        with patch("taskcanvas.app.main", return_value=0) as mock_main:
            self.assertEqual(Kyanbasu.main([]), 0)
        mock_main.assert_called_once_with([], prog="kyanbasu")

    def test_primary_package_facade_delegates_with_kyanbasu_identity(self):
        with patch("taskcanvas.app.main", return_value=0) as mock_main:
            self.assertEqual(kyanbasu.main([]), 0)
        mock_main.assert_called_once_with([], prog="kyanbasu")

    def test_legacy_script_delegates_to_package_main(self):
        with patch("taskcanvas.app.main", return_value=0) as mock_main:
            self.assertEqual(TaskCanvas.main([]), 0)
        mock_main.assert_called_once_with([], prog="taskcanvas")

    def test_public_package_exposes_core_version(self):
        self.assertEqual(kyanbasu.__version__, "0.2.0")


if __name__ == "__main__":
    unittest.main()
