import json
import subprocess
import unittest
from typing import get_type_hints
from unittest.mock import patch

import kyanbasu.task_io as task_io
from kyanbasu.task_io import (
    _assign_unique_shorts,
    _build_export_command,
    _normalize_export_tasks,
    _normalize_task_row,
    _parse_task_export,
    fetch_tasks,
    run_quiet,
)
from kyanbasu.task_types import TaskRecord


class TestTaskIO(unittest.TestCase):
    def test_task_io_boundaries_have_explicit_contracts(self):
        self.assertEqual(get_type_hints(task_io.run_quiet)["return"], tuple[int, str, str])
        self.assertEqual(get_type_hints(task_io.fetch_tasks)["return"], list[TaskRecord])
        self.assertEqual(get_type_hints(task_io._split_filter)["return"], list[str])

    def test_export_command_builder_preserves_scope_and_runtime_flags(self):
        self.assertEqual(
            _build_export_command("project:Work", include_runtime_settings=True)[-2:],
            ["project:Work", "export"],
        )
        self.assertEqual(
            _build_export_command(None, include_runtime_settings=False),
            ["task", "status:pending", "export"],
        )

    def test_export_task_normalization_assigns_unique_short_ids(self):
        rows = [
            {"uuid": "aaaaaaaa-1111", "description": "One"},
            {"uuid": "aaaaaaaa-2222", "description": "Two"},
        ]

        tasks, widened = _normalize_export_tasks(rows)

        self.assertEqual(len({task["short"] for task in tasks}), 2)
        self.assertEqual(widened, 2)

    @patch("kyanbasu.task_io.subprocess.run")
    def test_run_quiet_returns_error_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["task"], timeout=30)

        rc, out, err = run_quiet(["task"], timeout=30)

        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertIn("timed out", err.lower())

    def test_assign_unique_shorts_handles_normalized_collisions(self):
        uuids = ["abc-def", "abcdef", "abc.def"]
        out = _assign_unique_shorts(uuids, min_len=6)
        shorts = [out[u] for u in uuids]
        self.assertEqual(len(set(shorts)), len(uuids))
        self.assertTrue(all(s.startswith("abcdef") for s in shorts))

    def test_assign_unique_shorts_handles_identical_normalized_values(self):
        self.assertEqual(
            _assign_unique_shorts(["same-id", "same.id"], min_len=4),
            {"same-id": "aed", "same.id": "aed1"},
        )

    def test_normalize_task_row_coerces_supported_shapes(self):
        row = {
            "id": 7,
            "description": "Task 1",
            "project": "Work",
            "tags": {"a", "b"},
            "dependencies": ("u1", "u2"),
            "due": 12345,
        }

        normalized = _normalize_task_row(row)

        self.assertEqual(normalized["uuid"], "7")
        self.assertEqual(normalized["desc"], "Task 1")
        self.assertEqual(normalized["project"], "Work")
        self.assertEqual(sorted(normalized["tags"]), ["a", "b"])
        self.assertEqual(normalized["depends"], ["u1", "u2"])
        self.assertEqual(normalized["due"], "12345")

    def test_parse_task_export_json_array(self):
        raw = (
            "Configuration override rc.verbose=off\n"
            + json.dumps([{"uuid": "u1", "description": "Task 1"}])
        )
        rows = _parse_task_export(raw)
        self.assertEqual(rows, [{"uuid": "u1", "description": "Task 1"}])

    def test_parse_task_export_ignores_non_object_array_members(self):
        raw = json.dumps(
            [
                {"uuid": "u1", "description": "Task 1"},
                None,
                "malformed row",
                17,
                ["nested", "array"],
            ]
        )

        rows = _parse_task_export(raw)

        self.assertEqual(rows, [{"uuid": "u1", "description": "Task 1"}])

    def test_parse_task_export_supports_data_and_rows_envelopes(self):
        expected = [{"uuid": "u1"}]
        self.assertEqual(_parse_task_export(json.dumps({"data": expected})), expected)
        self.assertEqual(_parse_task_export(json.dumps({"rows": expected})), expected)

    def test_normalize_task_row_coerces_string_and_scalar_collections(self):
        normalized = _normalize_task_row(
            {"uuid": "u1", "tags": "one, two three", "depends": 42}
        )

        self.assertEqual(normalized["tags"], ["one", "two", "three"])
        self.assertEqual(normalized["depends"], ["42"])

    def test_parse_task_export_line_json(self):
        raw = '{"uuid":"u1","description":"One"}\n{"uuid":"u2","description":"Two"}\nnoise'
        rows = _parse_task_export(raw)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["uuid"], "u1")
        self.assertEqual(rows[1]["uuid"], "u2")

    def test_parse_task_export_distinguishes_unrecognized_output(self):
        self.assertIsNone(_parse_task_export("Taskwarrior is unavailable"))

    def test_parse_task_export_keeps_empty_export_as_empty_rows(self):
        self.assertEqual(_parse_task_export(""), [])
        self.assertEqual(_parse_task_export("[]"), [])
        self.assertEqual(_parse_task_export('{"data":[]}'), [])

    def test_fetch_tasks_raises_on_invalid_filter_syntax(self):
        with self.assertRaisesRegex(ValueError, "Invalid --filter expression"):
            fetch_tasks('project:"broken')

    @patch("kyanbasu.task_io.run_quiet")
    def test_fetch_tasks_filter_and_log(self, mock_run_quiet):
        mock_run_quiet.return_value = (
            0,
            json.dumps(
                [
                    {
                        "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                        "description": "Beta",
                        "project": "Zeta",
                        "tags": "a,b",
                        "depends": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "due": "20260220T000000Z",
                    },
                    {
                        "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "description": "Alpha",
                        "project": "Alpha",
                        "tags": [],
                        "depends": [],
                    },
                ]
            ),
            "",
        )
        logs = []

        tasks = fetch_tasks("project:Work +P1", log_fn=logs.append)

        self.assertEqual(len(mock_run_quiet.call_args_list), 1)
        cmd = mock_run_quiet.call_args_list[0].args[0]
        self.assertIn("project:Work", cmd)
        self.assertIn("+P1", cmd)
        self.assertEqual(cmd[-1], "export")
        self.assertEqual(tasks[0]["desc"], "Alpha")
        self.assertEqual(tasks[1]["tags"], ["a", "b"])
        self.assertEqual(tasks[1]["depends"], ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"])
        self.assertTrue(any("Loaded tasks: 2" in line for line in logs))

    @patch("kyanbasu.task_io.run_quiet")
    def test_fetch_tasks_widens_short_ids_on_collision(self, mock_run_quiet):
        mock_run_quiet.return_value = (
            0,
            json.dumps(
                [
                    {
                        "uuid": "aaaaaaaa-1111-1111-1111-111111111111",
                        "description": "One",
                    },
                    {
                        "uuid": "aaaaaaaa-2222-2222-2222-222222222222",
                        "description": "Two",
                    },
                ]
            ),
            "",
        )
        logs = []
        tasks = fetch_tasks(None, log_fn=logs.append)
        shorts = [t["short"] for t in tasks]
        self.assertEqual(len(set(shorts)), 2)
        self.assertTrue(all(len(s) >= 9 for s in shorts))
        self.assertTrue(any("collision guard widened" in line.lower() for line in logs))

    @patch("kyanbasu.task_io.run_quiet")
    def test_fetch_tasks_fallback_preserves_pending_scope(self, mock_run_quiet):
        mock_run_quiet.side_effect = [
            (0, "", ""),
            (0, json.dumps([{"uuid": "u-1", "description": "Recovered"}]), ""),
        ]

        tasks = fetch_tasks(None)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(mock_run_quiet.call_args_list[0].args[0][-2:], ["status:pending", "export"])
        self.assertEqual(
            mock_run_quiet.call_args_list[1].args[0],
            ["task", "status:pending", "export"],
        )

    @patch("kyanbasu.task_io.run_quiet")
    def test_fetch_tasks_fallback_preserves_filter_scope(self, mock_run_quiet):
        mock_run_quiet.side_effect = [
            (1, "", "primary failed"),
            (
                0,
                json.dumps([{"uuid": "u-2", "description": "Recovered filtered"}]),
                "",
            ),
        ]

        tasks = fetch_tasks("project:Work +P1")

        self.assertEqual(len(tasks), 1)
        self.assertEqual(
            mock_run_quiet.call_args_list[1].args[0],
            ["task", "project:Work", "+P1", "export"],
        )

    @patch("kyanbasu.task_io.run_quiet")
    def test_fetch_tasks_logs_when_both_primary_and_fallback_fail(self, mock_run_quiet):
        mock_run_quiet.side_effect = [
            (1, "", "primary failed"),
            (1, "", "fallback failed"),
        ]
        logs = []

        with self.assertRaisesRegex(RuntimeError, "Taskwarrior export failed"):
            fetch_tasks("project:Work", log_fn=logs.append)

        self.assertTrue(any("task export failed" in m for m in logs))
        self.assertTrue(any("fallback task export failed" in m.lower() for m in logs))
        self.assertTrue(all("[Kyanbasu]" not in m for m in logs))

    @patch("kyanbasu.task_io.run_quiet")
    def test_fetch_tasks_returns_empty_for_successful_empty_exports(self, mock_run_quiet):
        mock_run_quiet.side_effect = [(0, "[]", ""), (0, '{"data":[]}', "")]

        self.assertEqual(fetch_tasks("project:Work"), [])
        self.assertEqual(mock_run_quiet.call_count, 2)

    @patch("kyanbasu.task_io.run_quiet")
    def test_fetch_tasks_preserves_primary_empty_when_fallback_is_unrecognized(
        self, mock_run_quiet
    ):
        mock_run_quiet.side_effect = [
            (0, "[]", ""),
            (0, "Taskwarrior emitted a warning instead of JSON", ""),
        ]

        self.assertEqual(fetch_tasks("project:Work"), [])

    @patch("kyanbasu.task_io.run_quiet")
    def test_fetch_tasks_rejects_unrecognized_output_after_fallback(self, mock_run_quiet):
        mock_run_quiet.side_effect = [
            (0, "Taskwarrior is unavailable", ""),
            (0, "still not JSON", ""),
        ]

        with self.assertRaisesRegex(
            RuntimeError, "(?i)unrecognized Taskwarrior export output.*primary.*fallback"
        ):
            fetch_tasks("project:Work")

    @patch("kyanbasu.task_io.run_quiet")
    def test_fetch_tasks_accepts_valid_empty_fallback_after_invalid_primary(
        self, mock_run_quiet
    ):
        mock_run_quiet.side_effect = [
            (0, "Taskwarrior emitted a warning instead of JSON", ""),
            (0, "[]", ""),
        ]

        self.assertEqual(fetch_tasks("project:Work"), [])

    @patch("kyanbasu.task_io.run_quiet")
    def test_fetch_tasks_default_error_preserves_both_bounded_failure_details(
        self, mock_run_quiet
    ):
        mock_run_quiet.side_effect = [
            (17, "", "primary failed" + "x" * 300),
            (23, "", "fallback failed"),
        ]

        with self.assertRaises(RuntimeError) as raised:
            fetch_tasks("project:Work")

        message = str(raised.exception)
        self.assertIn("primary", message)
        self.assertIn("rc=17", message)
        self.assertIn("primary failed", message)
        self.assertNotIn("x" * 221, message)
        self.assertIn("fallback", message)
        self.assertIn("rc=23", message)
        self.assertIn("fallback failed", message)


if __name__ == "__main__":
    unittest.main()
