import json
import logging
import re
import tempfile
import unittest
from pathlib import Path
from typing import get_type_hints
from unittest.mock import patch

import kyanbasu.app as Kyanbasu
from kyanbasu.task_types import RuntimePayload, TaskRecord


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
    def test_app_boundaries_use_task_and_payload_contracts(self):
        self.assertEqual(get_type_hints(Kyanbasu._load_pending_tasks)["return"], list[TaskRecord])
        self.assertEqual(
            get_type_hints(Kyanbasu._resolve_initial_projects)["tasks_all"],
            list[TaskRecord],
        )
        self.assertEqual(
            get_type_hints(Kyanbasu._apply_initial_placements)["payload"],
            RuntimePayload,
        )
        self.assertEqual(get_type_hints(Kyanbasu._render_html)["payload"], RuntimePayload)
        self.assertEqual(get_type_hints(Kyanbasu._json_text)["data"], RuntimePayload)

    def test_runtime_payload_declares_optional_initial_placement_fields(self):
        self.assertEqual(get_type_hints(RuntimePayload).get("init_projects"), list[str])
        self.assertEqual(get_type_hints(RuntimePayload).get("init_task_uuids"), list[str])

    def test_runtime_config_resolves_output_and_log_level_per_invocation(self):
        with patch.dict(
            Kyanbasu.os.environ,
            {"KYANBASU_OUTPUT": "/tmp/first/Kyanbasu.html", "KYANBASU_LOG_LEVEL": "WARNING"},
            clear=True,
        ):
            first = Kyanbasu._resolve_runtime_config()
            first_level = first.logger.level
        with patch.dict(
            Kyanbasu.os.environ,
            {"KYANBASU_OUTPUT": "/tmp/second/Kyanbasu.html", "KYANBASU_LOG_LEVEL": "ERROR"},
            clear=True,
        ):
            second = Kyanbasu._resolve_runtime_config()

        self.assertEqual(first.out_html, Path("/tmp/first/Kyanbasu.html"))
        self.assertEqual(second.out_html, Path("/tmp/second/Kyanbasu.html"))
        self.assertEqual(first_level, logging.WARNING)
        self.assertEqual(second.logger.level, logging.ERROR)

    def test_output_replace_failure_preserves_existing_html_and_cleans_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "Kyanbasu.html"
            output.write_text("previous", encoding="utf-8")

            with patch.object(Kyanbasu.os, "replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(RuntimeError, "replace failed"):
                    Kyanbasu._write_output_html("new", output)

            self.assertEqual(output.read_text(encoding="utf-8"), "previous")
            self.assertEqual(list(Path(tmp).iterdir()), [output])

    def test_runtime_config_does_not_read_legacy_module_output_global(self):
        legacy_output = Path("/tmp/legacy-output.html")
        with patch.dict(Kyanbasu.__dict__, {"OUT_HTML": legacy_output}), patch.dict(
            Kyanbasu.os.environ, {}, clear=True
        ):
            config = Kyanbasu._resolve_runtime_config()

        self.assertNotEqual(config.out_html, legacy_output)

    def test_render_html_logs_embedded_task_count_at_application_boundary(self):
        with patch.object(Kyanbasu, "_load_runtime_html", return_value="base"), patch.object(
            Kyanbasu, "build_runtime_html", return_value="rendered"
        ), patch.object(Kyanbasu, "eprint") as mock_eprint:
            result = Kyanbasu._render_html([_task("a", "Alpha")], {"tasks": [], "graph": {}})

        self.assertEqual(result, "rendered")
        mock_eprint.assert_called_once_with("Embedded tasks: 1")

    def test_resolve_initial_projects_propagates_unexpected_selector_errors(self):
        with patch.object(Kyanbasu, "run_project_selector", side_effect=RuntimeError("selector bug")):
            with self.assertRaisesRegex(RuntimeError, "selector bug"):
                Kyanbasu._resolve_initial_projects([_task("a", "Alpha")], [], True)

    def test_logger_uses_kyanbasu_log_level(self):
        original_level = Kyanbasu.LOGGER.level
        try:
            with patch.dict(Kyanbasu.os.environ, {"KYANBASU_LOG_LEVEL": "ERROR"}, clear=True):
                logger = Kyanbasu._build_logger()
            self.assertEqual(logger.level, logging.ERROR)
        finally:
            Kyanbasu.LOGGER.setLevel(original_level)

    def test_main_merges_selector_and_filter_placements(self):
        all_tasks = [
            _task("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "Alpha", project="Home"),
            _task("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "Beta"),
        ]
        filtered_tasks = [
            _task("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "Beta"),
            _task("cccccccc-cccc-cccc-cccc-cccccccccccc", "Not in pending payload"),
        ]

        calls = []

        def fake_fetch(filter_str=None, timeout=30, log_fn=None, strict_errors=False):
            calls.append(filter_str)
            return filtered_tasks if filter_str else all_tasks

        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "Kyanbasu.html"
            with patch.dict(Kyanbasu.os.environ, {"KYANBASU_OUTPUT": str(out_html)}), patch.object(
                Kyanbasu, "fetch_tasks", side_effect=fake_fetch
            ), patch.object(
                Kyanbasu, "build_payload", return_value={"tasks": all_tasks, "graph": {}}
            ), patch.object(
                Kyanbasu, "run_project_selector", return_value=["FromSelector"]
            ), patch.object(
                Kyanbasu,
                "_load_runtime_html",
                return_value="<html><head></head><body><!-- INLINE_PAYLOAD_HERE --></body></html>",
            ), patch.object(
                Kyanbasu, "_find_bg_file", return_value=None
            ), patch.object(
                Kyanbasu, "open_file"
            ) as mock_open, patch.object(
                Kyanbasu.sys,
                "argv",
                [
                    "Kyanbasu.py",
                    "--filter",
                    "project:Work +P1",
                    "--selector",
                    "Home",
                    "Home",
                ],
            ):
                rc = Kyanbasu.main()

            self.assertEqual(rc, 0)
            self.assertEqual(calls, [None, "project:Work +P1"])
            self.assertTrue(out_html.exists())
            mock_open.assert_called_once_with(out_html)

            html = out_html.read_text(encoding="utf-8")
            m = re.search(r"<script id='payload_data' type='application/json'>(.*?)</script>", html, flags=re.S)
            self.assertIsNotNone(m)
            payload = json.loads(m.group(1))
            self.assertRegex(payload["workspace_id"], r"^[0-9a-f]{16}$")
            self.assertEqual(payload["init_projects"], ["FromSelector", "Home"])
            self.assertEqual(payload["init_task_uuids"], ["bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"])

    def test_apply_initial_placements_omits_filter_ids_missing_from_payload(self):
        payload = {"tasks": [_task("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "Beta")], "graph": {}}

        result = Kyanbasu._apply_initial_placements(
            payload,
            [],
            [
                "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "cccccccc-cccc-cccc-cccc-cccccccccccc",
            ],
        )

        self.assertEqual(result["init_task_uuids"], ["bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"])

    def test_main_returns_error_on_invalid_filter(self):
        def fake_fetch(filter_str=None, timeout=30, log_fn=None, strict_errors=False):
            if filter_str is None:
                return []
            raise ValueError("Invalid --filter expression: No closing quotation")

        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "Kyanbasu.html"
            with patch.dict(Kyanbasu.os.environ, {"KYANBASU_OUTPUT": str(out_html)}), patch.object(
                Kyanbasu, "fetch_tasks", side_effect=fake_fetch
            ), patch.object(
                Kyanbasu, "_load_runtime_html"
            ) as mock_html_loader, patch.object(
                Kyanbasu, "open_file"
            ) as mock_open, patch.object(
                Kyanbasu.sys, "argv", ["Kyanbasu.py", "--filter", "project:\"broken"]
            ):
                rc = Kyanbasu.main()

            self.assertEqual(rc, 2)
            self.assertFalse(out_html.exists())
            mock_html_loader.assert_not_called()
            mock_open.assert_not_called()

    def test_main_returns_error_on_missing_filter_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "Kyanbasu.html"
            with patch.dict(Kyanbasu.os.environ, {"KYANBASU_OUTPUT": str(out_html)}), patch.object(
                Kyanbasu, "fetch_tasks"
            ) as mock_fetch, patch.object(
                Kyanbasu, "open_file"
            ) as mock_open, patch.object(
                Kyanbasu.sys, "argv", ["Kyanbasu.py", "--filter"]
            ):
                rc = Kyanbasu.main()

            self.assertEqual(rc, 2)
            self.assertFalse(out_html.exists())
            mock_fetch.assert_not_called()
            mock_open.assert_not_called()

    def test_main_returns_error_on_missing_bg_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "Kyanbasu.html"
            with patch.dict(Kyanbasu.os.environ, {"KYANBASU_OUTPUT": str(out_html)}), patch.object(
                Kyanbasu, "fetch_tasks", return_value=[]
            ), patch.object(
                Kyanbasu, "_find_bg_file"
            ) as mock_find_bg, patch.object(
                Kyanbasu, "open_file"
            ) as mock_open, patch.object(
                Kyanbasu.sys, "argv", ["Kyanbasu.py", "--bg"]
            ):
                rc = Kyanbasu.main()

            self.assertEqual(rc, 2)
            self.assertFalse(out_html.exists())
            mock_find_bg.assert_not_called()
            mock_open.assert_not_called()

    def test_main_returns_error_on_template_load_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "Kyanbasu.html"
            with patch.dict(Kyanbasu.os.environ, {"KYANBASU_OUTPUT": str(out_html)}), patch.object(
                Kyanbasu, "fetch_tasks", return_value=[]
            ), patch.object(
                Kyanbasu, "build_payload", return_value={"tasks": [], "graph": {}}
            ), patch.object(
                Kyanbasu,
                "_load_runtime_html",
                side_effect=RuntimeError("template load failed"),
            ), patch.object(
                Kyanbasu, "open_file"
            ) as mock_open, patch.object(
                Kyanbasu.sys, "argv", ["Kyanbasu.py"]
            ):
                rc = Kyanbasu.main()

            self.assertEqual(rc, 1)
            self.assertFalse(out_html.exists())
            mock_open.assert_not_called()

    def test_main_succeeds_even_if_auto_open_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "Kyanbasu.html"
            with patch.dict(Kyanbasu.os.environ, {"KYANBASU_OUTPUT": str(out_html)}), patch.object(
                Kyanbasu, "fetch_tasks", return_value=[]
            ), patch.object(
                Kyanbasu, "_find_bg_file", return_value=None
            ), patch.object(
                Kyanbasu, "open_file", return_value=False
            ), patch.object(
                Kyanbasu.sys, "argv", ["Kyanbasu.py"]
            ):
                rc = Kyanbasu.main()

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
            out_html = Path(tmp) / "Kyanbasu.html"
            with patch.dict(Kyanbasu.os.environ, {"KYANBASU_OUTPUT": str(out_html)}), patch.object(
                Kyanbasu, "fetch_tasks", return_value=tasks
            ), patch.object(
                Kyanbasu, "_find_bg_file", return_value=None
            ), patch.object(
                Kyanbasu, "open_file"
            ), patch.object(
                Kyanbasu.sys, "argv", ["Kyanbasu.py"]
            ):
                rc = Kyanbasu.main()

            self.assertEqual(rc, 0)
            self.assertTrue(out_html.exists())
            html = out_html.read_text(encoding="utf-8")

            required_markers = [
                "id='payload_data'",
                'id="feature-hover-css"',
                'id="FEATURE_HOVERSTAGE"',
                'id="feature-due-css-v2"',
                'id="FEATURE_DUEBADGE2"',
                'id="FEATURE_DEPENDENCY_INTERACTIONS_V1"',
                'id="FEATURE_DEPENDENCY_EDGES_V1"',
                'id="FEATURE_QUICKFIX_ADD_RENDER_V1"',
                'id="PROJECT_PICKER_V2_CSS"',
                'id="PROJECT_PICKER_V2_JS"',
                'id="FEATURE_TOAST_UTIL_V1"',
                'id="FEATURE_CONSOLE_LINE_ENFORCER_V3"',
                'id="FEATURE_COPY_FULL_OVERRIDE_V1"',
                'id="FEATURE_SINGLE_CONSOLE_AUGMENT_V1"',
                'id="feature-dedupe-focus-v1-css"',
                'id="FEATURE_DEDUPE_FOCUS_V1"',
                'id="feature-project-addtag-v4-css"',
                'id="FEATURE_PROJECT_ADD_TAG_V4"',
                'id="FEATURE_REVIEW_CHANGES_V1_CSS"',
                'id="FEATURE_REVIEW_CHANGES_V1"',
                'id="FEATURE_CANVAS_STORAGE_V1"',
                'id="FEATURE_CANVAS_NAVIGATOR_V1_CSS"',
                'id="FEATURE_CANVAS_NAVIGATOR_V1"',
                'id="FEATURE_CANVAS_NOTES_V1_CSS"',
                'id="FEATURE_CANVAS_NOTES_CORE_V1"',
                'id="FEATURE_CANVAS_NOTES_V1"',
                'id="FEATURE_CONSOLE_EDITOR_V1_CSS"',
                'id="FEATURE_CONSOLE_EDITOR_V1"',
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
            out_html = Path(tmp) / "Kyanbasu.html"
            with patch.dict(Kyanbasu.os.environ, {"KYANBASU_OUTPUT": str(out_html)}), patch.object(
                Kyanbasu, "fetch_tasks", return_value=[]
            ), patch.object(
                Kyanbasu, "_find_bg_file", return_value=None
            ), patch.object(
                Kyanbasu, "open_file"
            ), patch.object(
                Kyanbasu.sys, "argv", ["Kyanbasu.py"]
            ):
                rc = Kyanbasu.main()

            self.assertEqual(rc, 0)
            html = out_html.read_text(encoding="utf-8")
            self.assertIn("function snapshotCanvasProjects()", html)
            self.assertIn("function rebuildCanvasProjects(projectStates)", html)
            self.assertIn("restoreCanvasSnapshot('reset-projects')", html)
            self.assertIn("restoreCanvasSnapshot('clear')", html)

    def test_main_generates_compact_task_cards_without_project_tag_caption(self):
        tasks = [_task("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "Alpha", project="Home")]

        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "Kyanbasu.html"
            with patch.dict(Kyanbasu.os.environ, {"KYANBASU_OUTPUT": str(out_html)}), patch.object(
                Kyanbasu, "fetch_tasks", return_value=tasks
            ), patch.object(
                Kyanbasu, "_find_bg_file", return_value=None
            ), patch.object(
                Kyanbasu, "open_file"
            ), patch.object(
                Kyanbasu.sys, "argv", ["Kyanbasu.py"]
            ):
                rc = Kyanbasu.main()

            self.assertEqual(rc, 0)
            html = out_html.read_text(encoding="utf-8")
            self.assertNotIn('<div class="caption">', html)

    def test_main_places_dependency_lines_between_bubbles_and_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "Kyanbasu.html"
            with patch.dict(Kyanbasu.os.environ, {"KYANBASU_OUTPUT": str(out_html)}), patch.object(
                Kyanbasu, "fetch_tasks", return_value=[]
            ), patch.object(
                Kyanbasu, "_find_bg_file", return_value=None
            ), patch.object(
                Kyanbasu, "open_file"
            ), patch.object(
                Kyanbasu.sys, "argv", ["Kyanbasu.py"]
            ):
                rc = Kyanbasu.main()

            self.assertEqual(rc, 0)
            html = out_html.read_text(encoding="utf-8")
            self.assertIn('id="chromeLayer" class="chromeLayer"', html)
            self.assertIn(".chromeLayer{", html)
            self.assertIn("z-index:9;", html)
            self.assertIn(".links{", html)
            self.assertIn("z-index:7;", html)

    def test_main_generates_dependency_details_for_task_inspector(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "Kyanbasu.html"
            with patch.dict(Kyanbasu.os.environ, {"KYANBASU_OUTPUT": str(out_html)}), patch.object(
                Kyanbasu, "fetch_tasks", return_value=[]
            ), patch.object(
                Kyanbasu, "_find_bg_file", return_value=None
            ), patch.object(
                Kyanbasu, "open_file"
            ), patch.object(
                Kyanbasu.sys, "argv", ["Kyanbasu.py"]
            ):
                rc = Kyanbasu.main()

            self.assertEqual(rc, 0)
            html = out_html.read_text(encoding="utf-8")
            self.assertIn("function dependencyTaskSummary(shortId)", html)
            self.assertIn("function renderDependencyItems(ids, emptyText)", html)
            self.assertIn("This task has no current dependencies.", html)
            self.assertIn("No tasks currently depend on this task.", html)


if __name__ == "__main__":
    unittest.main()
