import json
import subprocess
import unittest
from unittest.mock import patch

from kyanbasu.task_io import (
    _assign_unique_shorts,
    _normalize_task_row,
    _parse_task_export,
    fetch_tasks,
    run_quiet,
)


class TestTaskIO(unittest.TestCase):
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

    def test_parse_task_export_line_json(self):
        raw = '{"uuid":"u1","description":"One"}\n{"uuid":"u2","description":"Two"}\nnoise'
        rows = _parse_task_export(raw)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["uuid"], "u1")
        self.assertEqual(rows[1]["uuid"], "u2")

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

        tasks = fetch_tasks("project:Work", log_fn=logs.append)

        self.assertEqual(tasks, [])
        self.assertTrue(any("task export failed" in m for m in logs))
        self.assertTrue(any("fallback task export failed" in m.lower() for m in logs))
        self.assertTrue(all("[Kyanbasu]" not in m for m in logs))

    @patch("kyanbasu.task_io.run_quiet")
    def test_fetch_tasks_raises_when_strict_and_both_exports_fail(self, mock_run_quiet):
        mock_run_quiet.side_effect = [
            (1, "", "primary failed"),
            (1, "", "fallback failed"),
        ]
        with self.assertRaisesRegex(RuntimeError, "Taskwarrior export failed"):
            fetch_tasks("project:Work", strict_errors=True)


if __name__ == "__main__":
    unittest.main()
