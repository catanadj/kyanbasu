import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kyanbasu.task_io import fetch_tasks
import tests.test_task_io_integration as integration_module


class TestIntegrationConfiguration(unittest.TestCase):
    def test_integration_skips_when_taskwarrior_is_unavailable(self):
        with patch.object(integration_module.shutil, "which", return_value=None):
            with self.assertRaisesRegex(unittest.SkipTest, "Taskwarrior binary"):
                integration_module.TestTaskIOIntegration.setUpClass()

    def test_integration_runs_when_taskwarrior_is_available(self):
        task_bin = "/usr/bin/task"
        with patch.dict(os.environ, {}, clear=True), patch.object(
            integration_module.shutil, "which", return_value=task_bin
        ):
            integration_module.TestTaskIOIntegration.setUpClass()

        self.assertEqual(integration_module.TestTaskIOIntegration.task_bin, task_bin)


class TestTaskIOIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task_bin = shutil.which("task")
        if not cls.task_bin:
            raise unittest.SkipTest("Taskwarrior binary ('task') not found.")

    def test_fetch_tasks_against_real_taskwarrior(self):
        with tempfile.TemporaryDirectory() as tmp:
            taskdata = Path(tmp) / "taskdata"
            taskdata.mkdir(parents=True, exist_ok=True)

            env = dict(os.environ)
            env["TASKDATA"] = str(taskdata)

            # Seed one task in an isolated TASKDATA.
            subprocess.run(
                [
                    self.task_bin,
                    "rc.confirmation=off",
                    "rc.verbose=nothing",
                    "add",
                    "Integration task",
                    "project:Work",
                    "+itest",
                ],
                check=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            with patch.dict(os.environ, {"TASKDATA": str(taskdata)}, clear=False):
                tasks_all = fetch_tasks(None)
                tasks_filtered = fetch_tasks("project:Work +itest")

            self.assertTrue(any(t["desc"] == "Integration task" for t in tasks_all))
            self.assertTrue(any(t["desc"] == "Integration task" for t in tasks_filtered))


if __name__ == "__main__":
    unittest.main()
