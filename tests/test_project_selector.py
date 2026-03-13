import unittest
from unittest.mock import patch

from taskcanvas.project_selector import _unique_projects, run_project_selector


class TestProjectSelector(unittest.TestCase):
    def test_unique_projects_sorts_and_keeps_no_project_last(self):
        tasks = [
            {"project": "Work"},
            {"project": None},
            {"project": "Home"},
            {"project": "Work"},
        ]

        names, counts = _unique_projects(tasks)

        self.assertEqual(names, ["Home", "Work", "(no project)"])
        self.assertEqual(counts, {"Work": 2, "(no project)": 1, "Home": 1})

    def test_run_project_selector_returns_empty_when_no_projects(self):
        with patch("builtins.print") as mock_print:
            out = run_project_selector([])

        self.assertEqual(out, [])
        mock_print.assert_called_once()
