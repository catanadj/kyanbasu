import json
import errno
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import get_type_hints
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / ".bridge"))
from watcher import Watcher, _read_pty_chunk, main


class TestBridgeWatcher(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base = Path(self.tempdir.name)
        self.watcher = Watcher(
            self.base,
            poll_interval=0.01,
            allow_pattern=None,
            require_confirm=False,
            default_timeout=5,
            use_pty=False,
        )

    def test_watcher_entry_points_declare_none_return_types(self):
        self.assertIs(get_type_hints(Watcher.run_forever)["return"], type(None))
        self.assertIs(get_type_hints(main)["return"], type(None))

    def run_request(self, payload):
        request_path = self.watcher.processing_dir / "request.json"
        request_path.write_text(json.dumps(payload))
        self.watcher._run_one(request_path)
        return json.loads((self.watcher.results_dir / "request.json").read_text())

    def write_queued_request(self, request_id):
        path = self.watcher.commands_dir / f"{request_id}.json"
        path.write_text(json.dumps({"cmd": [sys.executable, "-c", "print('ok')"]}))
        return path

    def run_one_poll(self):
        with patch("watcher.time.sleep", side_effect=KeyboardInterrupt):
            self.watcher.run_forever()

    def test_claim_io_failure_is_logged_and_polling_continues(self):
        failed = self.write_queued_request("a-claim-fail")
        good = self.write_queued_request("b-good")
        real_rename = os.rename

        def fail_first_claim(source, target):
            if Path(source) == failed:
                raise PermissionError("claim denied")
            return real_rename(source, target)

        output = StringIO()
        with patch("watcher.os.rename", side_effect=fail_first_claim):
            with patch.object(self.watcher, "_run_one"):
                with redirect_stdout(output):
                    self.run_one_poll()

        self.assertTrue(failed.exists())
        self.assertTrue((self.watcher.done_dir / good.name).exists())
        self.assertIn("claim", output.getvalue())
        self.assertIn("a-claim-fail", output.getvalue())

    def test_processing_io_failure_is_logged_and_later_request_runs(self):
        self.write_queued_request("a-process-fail")
        good = self.write_queued_request("b-good")
        def fail_first_processing(path):
            if path.stem == "a-process-fail":
                raise PermissionError("state write denied")

        output = StringIO()
        with patch.object(
            self.watcher, "_run_one", side_effect=fail_first_processing
        ):
            with redirect_stdout(output):
                self.run_one_poll()

        self.assertTrue((self.watcher.processing_dir / "a-process-fail.json").exists())
        self.assertTrue((self.watcher.done_dir / good.name).exists())
        self.assertIn("process", output.getvalue())
        self.assertIn("a-process-fail", output.getvalue())

    def test_done_move_io_failure_keeps_result_and_polling_continues(self):
        self.write_queued_request("a-move-fail")
        self.write_queued_request("b-good")
        real_rename = os.rename

        def fail_first_done_move(source, target):
            if Path(source).stem == "a-move-fail" and Path(target).parent == self.watcher.done_dir:
                raise PermissionError("done move denied")
            return real_rename(source, target)

        output = StringIO()
        with patch("watcher.os.rename", side_effect=fail_first_done_move):
            with patch.object(self.watcher, "_run_one"):
                with redirect_stdout(output):
                    self.run_one_poll()

        self.assertTrue((self.watcher.processing_dir / "a-move-fail.json").exists())
        self.assertTrue((self.watcher.done_dir / "b-good.json").exists())
        self.assertIn("done", output.getvalue())
        self.assertIn("a-move-fail", output.getvalue())

    def test_discovery_io_failure_recovers_on_next_poll(self):
        good = self.write_queued_request("good-after-scan-failure")
        real_glob = Path.glob
        calls = 0

        def fail_first_discovery(path, pattern):
            nonlocal calls
            if path == self.watcher.commands_dir and calls == 0:
                calls += 1
                raise PermissionError("directory unavailable")
            return real_glob(path, pattern)

        output = StringIO()
        with patch("watcher.Path.glob", autospec=True, side_effect=fail_first_discovery):
            with patch("watcher.time.sleep", side_effect=[None, KeyboardInterrupt]):
                with patch.object(self.watcher, "_run_one"):
                    with redirect_stdout(output):
                        self.watcher.run_forever()

        self.assertEqual(calls, 1)
        self.assertTrue((self.watcher.done_dir / good.name).exists())
        self.assertIn("could not read", output.getvalue())
        self.assertIn(str(self.watcher.commands_dir), output.getvalue())

    def test_stat_io_failure_skips_bad_file_and_runs_valid_request(self):
        bad = self.write_queued_request("a-unreadable")
        good = self.write_queued_request("b-readable")
        real_stat = Path.stat

        def fail_bad_stat(path, *args, **kwargs):
            if path == bad:
                raise PermissionError("metadata unavailable")
            return real_stat(path, *args, **kwargs)

        output = StringIO()
        with patch("watcher.Path.stat", autospec=True, side_effect=fail_bad_stat):
            with patch.object(self.watcher, "_run_one"):
                with redirect_stdout(output):
                    self.run_one_poll()

        self.assertTrue(bad.exists())
        self.assertTrue((self.watcher.done_dir / good.name).exists())
        self.assertIn("could not stat", output.getvalue())
        self.assertIn(str(bad), output.getvalue())

    def test_argv_command_preserves_shell_metacharacters_as_argument_data(self):
        result = self.run_request(
            {
                "cmd": [
                    sys.executable,
                    "-c",
                    "import sys; print(sys.argv[1])",
                    "literal; no shell",
                ]
            }
        )

        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"], "literal; no shell\n")
        self.assertIsNone(result["error"])

    def test_string_command_runs_in_explicit_trusted_shell_mode(self):
        command = "echo trusted-shell-mode" if os.name == "nt" else "printf trusted-shell-mode"
        result = self.run_request({"cmd": command})

        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"], "trusted-shell-mode")
        self.assertIsNone(result["error"])

    def _run_pipe_reader_failure(self, failing_channel):
        class Stream:
            def __init__(self, partial_output="", failure=None):
                self.partial_output = partial_output
                self.failure = failure
                self.read_once = False

            def readline(self):
                if not self.read_once and self.partial_output:
                    self.read_once = True
                    return self.partial_output
                if self.failure:
                    raise OSError(self.failure)
                return ""

            def close(self):
                pass

        class Process:
            returncode = 0

            def __init__(self, stdout, stderr):
                self.stdout = stdout
                self.stderr = stderr

            def wait(self, timeout):
                return self.returncode

        streams = {
            "stdout": Stream(
                "partial stdout\n",
                "stdout read failed" if failing_channel == "stdout" else None,
            ),
            "stderr": Stream(
                "partial stderr\n",
                "stderr read failed" if failing_channel == "stderr" else None,
            ),
        }
        process = Process(streams["stdout"], streams["stderr"])
        with patch("watcher.subprocess.Popen", return_value=process):
            result = self.run_request({"cmd": [sys.executable, "-c", "pass"]})
        return result

    def test_stdout_reader_failure_is_reported_and_preserves_collected_output(self):
        result = self._run_pipe_reader_failure("stdout")

        self.assertEqual(result["stdout"], "partial stdout\n")
        self.assertIn("stdout", result["error"])
        self.assertIn("stdout read failed", result["error"])

    def test_stderr_reader_failure_is_reported_and_preserves_collected_output(self):
        result = self._run_pipe_reader_failure("stderr")

        self.assertEqual(result["stderr"], "partial stderr\n")
        self.assertIn("stderr", result["error"])
        self.assertIn("stderr read failed", result["error"])

    def test_allowlist_rejects_trailing_shell_commands(self):
        self.watcher.allow_re = re.compile(r"printf allowed")

        self.assertTrue(self.watcher._is_allowed("printf allowed"))
        result = self.run_request({"cmd": "printf allowed; printf injected"})

        self.assertIsNone(result["returncode"])
        self.assertEqual(result["stdout"], "")
        self.assertIn("command blocked by allowlist", result["error"])

    def test_timed_out_argv_command_keeps_error_and_exit_status(self):
        result = self.run_request(
            {
                "cmd": [sys.executable, "-c", "import time; time.sleep(1)"],
                "timeout": 0.05,
            }
        )

        self.assertNotEqual(result["returncode"], 0)
        self.assertIn("timed out after 0.05s", result["error"])
        self.assertGreaterEqual(result["duration_s"], 0.0)

    def test_allowlist_blocked_result_has_numeric_duration(self):
        self.watcher.allow_re = re.compile(r"never-match")

        result = self.run_request({"cmd": ["printf", "blocked"]})

        self.assertEqual(result["duration_s"], 0.0)

    def test_operator_rejected_result_has_numeric_duration(self):
        self.watcher.require_confirm = True
        request_path = self.watcher.processing_dir / "request.json"
        request_path.write_text(json.dumps({"cmd": ["printf", "rejected"]}))
        with patch.object(self.watcher, "_confirm", return_value=False):
            self.watcher._run_one(request_path)

        result = json.loads((self.watcher.results_dir / "request.json").read_text())
        self.assertEqual(result["duration_s"], 0.0)

    @unittest.skipUnless(os.name == "posix", "PTY execution is Unix-only")
    def test_pty_and_pipe_modes_return_the_same_result_fields(self):
        self.watcher.use_pty = True

        result = self.run_request(
            {"cmd": [sys.executable, "-c", "print('pty-result')"]}
        )

        self.assertEqual(result["returncode"], 0)
        self.assertIn("pty-result", result["stdout"])
        self.assertEqual(
            set(result),
            {"id", "returncode", "stdout", "stderr", "duration_s", "error"},
        )

    @unittest.skipUnless(os.name == "posix", "PTY execution is Unix-only")
    def test_pty_execution_enforces_the_request_timeout(self):
        self.watcher.use_pty = True

        result = self.run_request(
            {
                "cmd": [sys.executable, "-c", "import time; time.sleep(1)"],
                "timeout": 0.05,
            }
        )

        self.assertIn("timed out after 0.05s", result["error"])
        self.assertNotEqual(result["returncode"], 0)

    @unittest.skipUnless(os.name == "posix", "PTY execution is Unix-only")
    def test_pty_timeout_waits_for_killed_child_before_returning(self):
        import pty

        class Process:
            returncode = None

            def __init__(self):
                self.wait_calls = 0

            def poll(self):
                return self.returncode

            def kill(self):
                pass

            def wait(self):
                self.wait_calls += 1
                self.returncode = -9
                return self.returncode

        process = Process()
        with patch("pty.openpty", return_value=(10, 11)):
            with patch("watcher.subprocess.Popen", return_value=process):
                with patch("watcher.os.close"):
                    with patch("watcher.time.time", side_effect=(1.0, 2.0)):
                        with patch("watcher._read_pty_chunk", return_value=None):
                            result = self.watcher._run_with_pty(
                                cmd=[sys.executable],
                                cmd_str="python child",
                                cwd=None,
                                env=None,
                                timeout=0.05,
                                live_file=StringIO(),
                                req_id="request-id",
                                buffers={"stdout": [], "stderr": []},
                            )

        self.assertEqual(process.wait_calls, 1)
        self.assertEqual(result["returncode"], -9)
        self.assertIn("timed out after 0.05s", result["error"])

    @unittest.skipUnless(os.name == "posix", "PTY execution is Unix-only")
    def test_pty_reader_treats_only_terminal_eio_as_eof(self):
        with patch("watcher.os.read", side_effect=OSError(errno.EIO, "closed pty")):
            self.assertIsNone(_read_pty_chunk(10))
        with patch("watcher.os.read", side_effect=OSError(errno.EBADF, "bad descriptor")):
            with self.assertRaises(OSError) as raised:
                _read_pty_chunk(10)
        self.assertEqual(raised.exception.errno, errno.EBADF)

    def test_malformed_request_returns_complete_result_record(self):
        request_path = self.watcher.processing_dir / "request.json"
        request_path.write_text("{")

        self.watcher._run_one(request_path)
        result = json.loads((self.watcher.results_dir / "request.json").read_text())

        self.assertEqual(
            set(result),
            {"id", "returncode", "stdout", "stderr", "duration_s", "error"},
        )
        self.assertIsNone(result["returncode"])
        self.assertTrue(result["error"].startswith("failed to parse command file:"))
        self.assertEqual(result["duration_s"], 0.0)

    def test_execution_io_errors_are_reported_but_unexpected_errors_propagate(self):
        request_path = self.watcher.processing_dir / "request.json"
        request_path.write_text(json.dumps({"cmd": ["does-not-matter"]}))

        with patch("watcher.subprocess.Popen", side_effect=OSError("spawn failed")):
            self.watcher._run_one(request_path)
        result = json.loads((self.watcher.results_dir / "request.json").read_text())
        self.assertIn("spawn failed", result["error"])

        with patch("watcher.subprocess.Popen", side_effect=RuntimeError("bug")):
            with self.assertRaisesRegex(RuntimeError, "bug"):
                self.watcher._run_one(request_path)


if __name__ == "__main__":
    unittest.main()
