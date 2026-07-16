import unittest
from unittest.mock import patch

import Kyanbasu
import kyanbasu


class TestEntrypoint(unittest.TestCase):
    def test_primary_script_delegates_with_kyanbasu_identity(self):
        with patch("kyanbasu.app.main", return_value=0) as mock_main:
            self.assertEqual(Kyanbasu.main([]), 0)
        mock_main.assert_called_once_with([], prog="kyanbasu")

    def test_primary_package_facade_delegates_with_kyanbasu_identity(self):
        with patch("kyanbasu.app.main", return_value=0) as mock_main:
            self.assertEqual(kyanbasu.main([]), 0)
        mock_main.assert_called_once_with([], prog="kyanbasu")

    def test_public_package_exposes_core_version(self):
        self.assertEqual(kyanbasu.__version__, "0.3.0")


if __name__ == "__main__":
    unittest.main()
