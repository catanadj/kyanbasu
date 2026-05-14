import unittest
from unittest.mock import patch

import TaskCanvas


class TestEntrypoint(unittest.TestCase):
    def test_legacy_script_delegates_to_package_main(self):
        with patch("taskcanvas.app.main", return_value=0) as mock_main:
            self.assertEqual(TaskCanvas.main([]), 0)
        mock_main.assert_called_once_with([])


if __name__ == "__main__":
    unittest.main()
