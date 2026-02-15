import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from taskcanvas.task_io import fetch_tasks


class TestTaskIOIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("TASKCANVAS_RUN_INTEGRATION") != "1":
            raise unittest.SkipTest("Set TASKCANVAS_RUN_INTEGRATION=1 to run integration tests.")
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
                tasks_all = fetch_tasks(None, strict_errors=True)
                tasks_filtered = fetch_tasks("project:Work +itest", strict_errors=True)

            self.assertTrue(any(t["desc"] == "Integration task" for t in tasks_all))
            self.assertTrue(any(t["desc"] == "Integration task" for t in tasks_filtered))


if __name__ == "__main__":
    unittest.main()
