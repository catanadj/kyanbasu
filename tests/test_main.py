import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import taskcanvas.app as TaskCanvas


def _task(uuid: str, desc: str, project: str = "Work", depends=None, due=None):
    depends = depends or []
    return {
        "uuid": uuid,
        "short": uuid.replace("-", "")[:8],
        "desc": desc,
        "project": project,
        "tags": [],
        "depends": depends,
        "due": due,
    }


class TestMainFlow(unittest.TestCase):
    def test_main_merges_selector_and_filter_placements(self):
        all_tasks = [
            _task("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "Alpha", project="Home"),
            _task("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "Beta"),
        ]
        filtered_tasks = [_task("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "Beta")]

        calls = []

        def fake_fetch(filter_str=None, timeout=30, log_fn=None, strict_errors=False):
            calls.append(filter_str)
            return filtered_tasks if filter_str else all_tasks

        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "TaskCanvas.html"
            with patch.object(TaskCanvas, "OUT_HTML", out_html), patch.object(
                TaskCanvas, "fetch_tasks", side_effect=fake_fetch
            ), patch.object(
                TaskCanvas, "build_payload", return_value={"tasks": [], "graph": {}}
            ), patch.object(
                TaskCanvas, "run_project_selector", return_value=["FromSelector"]
            ), patch.object(
                TaskCanvas,
                "_load_runtime_html",
                return_value="<html><head></head><body><!-- INLINE_PAYLOAD_HERE --></body></html>",
            ), patch.object(
                TaskCanvas, "_find_bg_file", return_value=None
            ), patch.object(
                TaskCanvas, "open_file"
            ) as mock_open, patch.object(
                TaskCanvas.sys,
                "argv",
                [
                    "TaskCanvas.py",
                    "--filter",
                    "project:Work +P1",
                    "--selector",
                    "Home",
                    "Home",
                ],
            ):
                rc = TaskCanvas.main()

            self.assertEqual(rc, 0)
            self.assertEqual(calls, [None, "project:Work +P1"])
            self.assertTrue(out_html.exists())
            mock_open.assert_called_once_with(out_html)

            html = out_html.read_text(encoding="utf-8")
            m = re.search(r"<script id='payload_data' type='application/json'>(.*?)</script>", html, flags=re.S)
            self.assertIsNotNone(m)
            payload = json.loads(m.group(1))
            self.assertEqual(payload["init_projects"], ["FromSelector", "Home"])
            self.assertEqual(payload["init_task_uuids"], ["bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"])

    def test_main_returns_error_on_invalid_filter(self):
        def fake_fetch(filter_str=None, timeout=30, log_fn=None, strict_errors=False):
            if filter_str is None:
                return []
            raise ValueError("Invalid --filter expression: No closing quotation")

        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "TaskCanvas.html"
            with patch.object(TaskCanvas, "OUT_HTML", out_html), patch.object(
                TaskCanvas, "fetch_tasks", side_effect=fake_fetch
            ), patch.object(
                TaskCanvas, "_load_runtime_html"
            ) as mock_html_loader, patch.object(
                TaskCanvas, "open_file"
            ) as mock_open, patch.object(
                TaskCanvas.sys, "argv", ["TaskCanvas.py", "--filter", "project:\"broken"]
            ):
                rc = TaskCanvas.main()

            self.assertEqual(rc, 2)
            self.assertFalse(out_html.exists())
            mock_html_loader.assert_not_called()
            mock_open.assert_not_called()

    def test_main_returns_error_on_missing_filter_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "TaskCanvas.html"
            with patch.object(TaskCanvas, "OUT_HTML", out_html), patch.object(
                TaskCanvas, "fetch_tasks"
            ) as mock_fetch, patch.object(
                TaskCanvas, "open_file"
            ) as mock_open, patch.object(
                TaskCanvas.sys, "argv", ["TaskCanvas.py", "--filter"]
            ):
                rc = TaskCanvas.main()

            self.assertEqual(rc, 2)
            self.assertFalse(out_html.exists())
            mock_fetch.assert_not_called()
            mock_open.assert_not_called()

    def test_main_returns_error_on_missing_bg_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "TaskCanvas.html"
            with patch.object(TaskCanvas, "OUT_HTML", out_html), patch.object(
                TaskCanvas, "fetch_tasks", return_value=[]
            ), patch.object(
                TaskCanvas, "_find_bg_file"
            ) as mock_find_bg, patch.object(
                TaskCanvas, "open_file"
            ) as mock_open, patch.object(
                TaskCanvas.sys, "argv", ["TaskCanvas.py", "--bg"]
            ):
                rc = TaskCanvas.main()

            self.assertEqual(rc, 2)
            self.assertFalse(out_html.exists())
            mock_find_bg.assert_not_called()
            mock_open.assert_not_called()

    def test_main_returns_error_on_template_load_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "TaskCanvas.html"
            with patch.object(TaskCanvas, "OUT_HTML", out_html), patch.object(
                TaskCanvas, "fetch_tasks", return_value=[]
            ), patch.object(
                TaskCanvas, "build_payload", return_value={"tasks": [], "graph": {}}
            ), patch.object(
                TaskCanvas,
                "_load_runtime_html",
                side_effect=RuntimeError("template load failed"),
            ), patch.object(
                TaskCanvas, "open_file"
            ) as mock_open, patch.object(
                TaskCanvas.sys, "argv", ["TaskCanvas.py"]
            ):
                rc = TaskCanvas.main()

            self.assertEqual(rc, 1)
            self.assertFalse(out_html.exists())
            mock_open.assert_not_called()

    def test_main_succeeds_even_if_auto_open_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "TaskCanvas.html"
            with patch.object(TaskCanvas, "OUT_HTML", out_html), patch.object(
                TaskCanvas, "fetch_tasks", return_value=[]
            ), patch.object(
                TaskCanvas, "_find_bg_file", return_value=None
            ), patch.object(
                TaskCanvas, "open_file", return_value=False
            ), patch.object(
                TaskCanvas.sys, "argv", ["TaskCanvas.py"]
            ):
                rc = TaskCanvas.main()

            self.assertEqual(rc, 0)
            self.assertTrue(out_html.exists())

    def test_main_smoke_generates_html_with_critical_blocks(self):
        tasks = [
            _task("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "Alpha"),
            _task(
                "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "Beta",
                depends=["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
                due="20260220T000000Z",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "TaskCanvas.html"
            with patch.object(TaskCanvas, "OUT_HTML", out_html), patch.object(
                TaskCanvas, "fetch_tasks", return_value=tasks
            ), patch.object(
                TaskCanvas, "_find_bg_file", return_value=None
            ), patch.object(
                TaskCanvas, "open_file"
            ), patch.object(
                TaskCanvas.sys, "argv", ["TaskCanvas.py"]
            ):
                rc = TaskCanvas.main()

            self.assertEqual(rc, 0)
            self.assertTrue(out_html.exists())
            html = out_html.read_text(encoding="utf-8")

            required_markers = [
                "id='payload_data'",
                'id="feature-hover-css"',
                'id="FEATURE_HOVERSTAGE"',
                'id="feature-due-css-v2"',
                'id="FEATURE_DUEBADGE2"',
                "__ENERGY_ARROW_CSS__",
                "__ONLY_DEPS_CONSOLE_CSS__",
                "__FIXPACK_V61__",
                "FEATURE_ACTIONABLE_BEACON_V7B_JS",
                "FEATURE_LAYOUT_PERSIST_V1",
                "FEATURE_COMMAND_PREFLIGHT_V1",
                "FEATURE_RUNTIME_DIAGNOSTICS_V1",
                "FEATURE_UNDO_REDO_V1",
            ]
            for marker in required_markers:
                self.assertIn(marker, html)

    def test_main_generates_distinct_reset_and_clear_canvas_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "TaskCanvas.html"
            with patch.object(TaskCanvas, "OUT_HTML", out_html), patch.object(
                TaskCanvas, "fetch_tasks", return_value=[]
            ), patch.object(
                TaskCanvas, "_find_bg_file", return_value=None
            ), patch.object(
                TaskCanvas, "open_file"
            ), patch.object(
                TaskCanvas.sys, "argv", ["TaskCanvas.py"]
            ):
                rc = TaskCanvas.main()

            self.assertEqual(rc, 0)
            html = out_html.read_text(encoding="utf-8")
            self.assertIn("function snapshotCanvasProjects()", html)
            self.assertIn("function rebuildCanvasProjects(projectStates)", html)
            self.assertIn("restoreCanvasSnapshot('reset-projects')", html)
            self.assertIn("restoreCanvasSnapshot('clear')", html)

    def test_main_generates_compact_task_cards_without_project_tag_caption(self):
        tasks = [_task("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "Alpha", project="Home")]

        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "TaskCanvas.html"
            with patch.object(TaskCanvas, "OUT_HTML", out_html), patch.object(
                TaskCanvas, "fetch_tasks", return_value=tasks
            ), patch.object(
                TaskCanvas, "_find_bg_file", return_value=None
            ), patch.object(
                TaskCanvas, "open_file"
            ), patch.object(
                TaskCanvas.sys, "argv", ["TaskCanvas.py"]
            ):
                rc = TaskCanvas.main()

            self.assertEqual(rc, 0)
            html = out_html.read_text(encoding="utf-8")
            self.assertNotIn('<div class="caption">', html)

    def test_main_places_dependency_lines_between_bubbles_and_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "TaskCanvas.html"
            with patch.object(TaskCanvas, "OUT_HTML", out_html), patch.object(
                TaskCanvas, "fetch_tasks", return_value=[]
            ), patch.object(
                TaskCanvas, "_find_bg_file", return_value=None
            ), patch.object(
                TaskCanvas, "open_file"
            ), patch.object(
                TaskCanvas.sys, "argv", ["TaskCanvas.py"]
            ):
                rc = TaskCanvas.main()

            self.assertEqual(rc, 0)
            html = out_html.read_text(encoding="utf-8")
            self.assertIn('id="chromeLayer" class="chromeLayer"', html)
            self.assertIn(".chromeLayer{", html)
            self.assertIn("z-index:9;", html)
            self.assertIn(".links{", html)
            self.assertIn("z-index:7;", html)

    def test_main_generates_dependency_details_for_task_inspector(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "TaskCanvas.html"
            with patch.object(TaskCanvas, "OUT_HTML", out_html), patch.object(
                TaskCanvas, "fetch_tasks", return_value=[]
            ), patch.object(
                TaskCanvas, "_find_bg_file", return_value=None
            ), patch.object(
                TaskCanvas, "open_file"
            ), patch.object(
                TaskCanvas.sys, "argv", ["TaskCanvas.py"]
            ):
                rc = TaskCanvas.main()

            self.assertEqual(rc, 0)
            html = out_html.read_text(encoding="utf-8")
            self.assertIn("function dependencyTaskSummary(shortId)", html)
            self.assertIn("function renderDependencyItems(ids, emptyText)", html)
            self.assertIn("This task has no current dependencies.", html)
            self.assertIn("No tasks currently depend on this task.", html)


if __name__ == "__main__":
    unittest.main()
