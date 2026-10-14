import json
import sys
import tempfile
import threading
import time
import unittest
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import get_type_hints
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / ".bridge"))
import bridge_client


class TestBridgeClient(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base = Path(self.tempdir.name)

    def test_run_command_publishes_request_and_returns_matching_result(self):
        request_id = "fixed-request"
        result = {
            "id": request_id,
            "returncode": 0,
            "stdout": "done",
            "stderr": "",
            "duration_s": 0.1,
            "error": None,
        }
        self.assertEqual(
            set(result),
            {"id", "returncode", "stdout", "stderr", "duration_s", "error"},
        )
        results = self.base / "results"
        results.mkdir()

        def publish_result():
            request_path = self.base / "commands" / f"{request_id}.json"
            deadline = time.monotonic() + 1
            while not request_path.exists() and time.monotonic() < deadline:
                time.sleep(0.001)
            (results / f"{request_id}.json").write_text(json.dumps(result))

        producer = threading.Thread(target=publish_result, daemon=True)
        producer.start()

        with patch.object(bridge_client.uuid, "uuid4") as make_uuid:
            make_uuid.return_value.hex = request_id
            actual = bridge_client.run_command(
                ["printf", "hello"],
                options=bridge_client.BridgeOptions(
                    base_dir=str(self.base),
                    cwd="/tmp",
                    timeout=12,
                    env={"MODE": "test"},
                    poll_interval=0.001,
                    wait_timeout=1,
                ),
            )
        producer.join(timeout=1)

        request = json.loads((self.base / "commands" / f"{request_id}.json").read_text())
        self.assertEqual(request["cmd"], ["printf", "hello"])
        self.assertEqual(request["cwd"], "/tmp")
        self.assertEqual(request["timeout"], 12)
        self.assertEqual(request["env"], {"MODE": "test"})
        self.assertEqual(actual, result)

    def test_bridge_options_are_immutable_and_default_to_local_bridge_settings(self):
        options = bridge_client.BridgeOptions()

        self.assertEqual(options.base_dir, "./bridge")
        self.assertEqual(options.timeout, 60)
        self.assertEqual(options.poll_interval, 0.3)
        with self.assertRaises(FrozenInstanceError):
            options.timeout = 2

    def test_bridge_result_annotation_defines_the_shared_six_field_contract(self):
        result_type = bridge_client.BridgeResult
        expected = {"id", "returncode", "stdout", "stderr", "duration_s", "error"}

        self.assertEqual(set(result_type.__annotations__), expected)
        self.assertIs(get_type_hints(bridge_client.run_command)["return"], result_type)
        self.assertIs(
            get_type_hints(bridge_client.run_trusted_shell_command)["return"],
            result_type,
        )
        self.assertEqual(
            get_type_hints(bridge_client.BridgeOptions),
            {
                "base_dir": str | Path,
                "cwd": str | None,
                "timeout": float,
                "env": Mapping[str, str] | None,
                "poll_interval": float,
                "wait_timeout": float | None,
            },
        )
        self.assertEqual(
            get_type_hints(bridge_client._run_command),
            {
                "cmd": Sequence[str] | str,
                "options": bridge_client.BridgeOptions,
                "return": result_type,
            },
        )

    def test_tail_live_log_declares_its_iterator_api(self):
        self.assertEqual(
            get_type_hints(bridge_client.tail_live_log),
            {
                "req_id": str,
                "base_dir": str | Path,
                "poll_interval": float,
                "return": Iterator[str],
            },
        )

    def test_run_command_raises_after_client_wait_timeout(self):
        with self.assertRaises(bridge_client.BridgeTimeout):
            bridge_client.run_command(
                ["never-started"],
                options=bridge_client.BridgeOptions(
                    base_dir=str(self.base), poll_interval=0.001, wait_timeout=0.01
                ),
            )

    def test_request_directory_failure_has_path_request_and_chained_cause(self):
        with patch.object(bridge_client.uuid, "uuid4") as make_uuid:
            make_uuid.return_value.hex = "mkdir-request"
            with patch.object(Path, "mkdir", side_effect=OSError("permission denied")):
                with self.assertRaises(OSError) as caught:
                    bridge_client.run_command(
                        ["printf", "hello"],
                        options=bridge_client.BridgeOptions(base_dir=str(self.base)),
                    )

        error = caught.exception
        self.assertIn("mkdir-request", str(error))
        self.assertIn(str(self.base / "commands"), str(error))
        self.assertIsInstance(error.__cause__, OSError)

    def test_legacy_request_directory_failure_includes_request_context(self):
        with patch.object(bridge_client.uuid, "uuid4") as make_uuid:
            make_uuid.return_value.hex = "mkdir-request"
            with patch.object(Path, "mkdir", side_effect=OSError("permission denied")):
                with self.assertRaises(OSError) as caught:
                    bridge_client.run_command(["printf", "hello"], base_dir=self.base)

        self.assertIn("mkdir-request", str(caught.exception))
        self.assertIn(str(self.base / "commands"), str(caught.exception))
        self.assertIsInstance(caught.exception.__cause__, OSError)

    def test_legacy_request_publish_failure_includes_operation_and_request_context(self):
        with patch.object(bridge_client.uuid, "uuid4") as make_uuid:
            make_uuid.return_value.hex = "publish-request"
            with patch.object(bridge_client.os, "rename", side_effect=OSError("rename denied")):
                with self.assertRaises(OSError) as caught:
                    bridge_client.run_command(["printf", "hello"], base_dir=self.base)

        self.assertIn("publish", str(caught.exception).lower())
        self.assertIn("publish-request", str(caught.exception))
        self.assertIn(str(self.base / "commands" / "publish-request.json"), str(caught.exception))
        self.assertIsInstance(caught.exception.__cause__, OSError)

    def test_request_publish_failure_has_operation_path_and_chained_cause(self):
        with patch.object(bridge_client.uuid, "uuid4") as make_uuid:
            make_uuid.return_value.hex = "publish-request"
            with patch.object(bridge_client.os, "rename", side_effect=OSError("rename denied")):
                with self.assertRaises(OSError) as caught:
                    bridge_client.run_command(
                        ["printf", "hello"],
                        options=bridge_client.BridgeOptions(base_dir=str(self.base)),
                    )

        error = caught.exception
        self.assertIn("publish", str(error).lower())
        self.assertIn("publish-request", str(error))
        self.assertIn(str(self.base / "commands" / "publish-request.json"), str(error))
        self.assertIsInstance(error.__cause__, OSError)

    def test_malformed_result_timeout_includes_last_decode_error_and_request_id(self):
        request_id = "malformed-result"
        results = self.base / "results"
        results.mkdir()
        (results / f"{request_id}.json").write_text("{")

        with patch.object(bridge_client.uuid, "uuid4") as make_uuid:
            make_uuid.return_value.hex = request_id
            with self.assertRaises(bridge_client.BridgeTimeout) as caught:
                bridge_client.run_command(
                    ["printf", "hello"],
                    options=bridge_client.BridgeOptions(
                        base_dir=str(self.base), poll_interval=0.001, wait_timeout=0.01
                    ),
                )

        self.assertIn(request_id, str(caught.exception))
        self.assertIn("Expecting property name", str(caught.exception))
        self.assertIsInstance(caught.exception.__cause__, json.JSONDecodeError)

    def test_decoded_result_must_match_the_bridge_result_contract(self):
        request_id = "invalid-result"
        result_path = self.base / "results" / f"{request_id}.json"
        result_path.parent.mkdir()
        valid_result = {
            "id": request_id,
            "returncode": 0,
            "stdout": "done",
            "stderr": "",
            "duration_s": 0.1,
            "error": None,
        }
        malformed_results = [
            ([], "object"),
            ({**valid_result, "extra": "unsupported"}, "extra"),
            ({key: value for key, value in valid_result.items() if key != "error"}, "error"),
            ({**valid_result, "id": 7}, "id"),
            ({**valid_result, "returncode": True}, "returncode"),
            ({**valid_result, "stdout": 7}, "stdout"),
            ({**valid_result, "stderr": 7}, "stderr"),
            ({**valid_result, "duration_s": "fast"}, "duration_s"),
            ({**valid_result, "duration_s": True}, "duration_s"),
            ({**valid_result, "error": 7}, "error"),
        ]

        for index, (result, invalid_field) in enumerate(malformed_results):
            with self.subTest(invalid_field=invalid_field):
                case_id = f"{request_id}-{index}"
                case_path = result_path.with_name(f"{case_id}.json")
                case_path.write_text(json.dumps(result))
                with patch.object(bridge_client.uuid, "uuid4") as make_uuid:
                    make_uuid.return_value.hex = case_id
                    with self.assertRaisesRegex(ValueError, invalid_field) as caught:
                        bridge_client.run_command(
                            ["printf", "hello"],
                            options=bridge_client.BridgeOptions(
                                base_dir=str(self.base), poll_interval=0.001, wait_timeout=0.01
                            ),
                        )

                self.assertIn(case_id, str(caught.exception))
                self.assertIn(str(case_path), str(caught.exception))

    def test_run_command_rejects_string_commands_and_shell_mode_is_explicit(self):
        with self.assertRaisesRegex(TypeError, "argument sequence"):
            bridge_client.run_command(
                "printf unsafe",
                options=bridge_client.BridgeOptions(
                    base_dir=str(self.base), wait_timeout=0.01
                ),
            )

        with patch.object(bridge_client.uuid, "uuid4") as make_uuid:
            make_uuid.return_value.hex = "trusted-shell"
            results = self.base / "results"
            results.mkdir()
            result = {
                "id": "trusted-shell",
                "returncode": 0,
                "stdout": "trusted",
                "stderr": "",
                "duration_s": 0.1,
                "error": None,
            }
            (results / "trusted-shell.json").write_text(json.dumps(result))
            actual = bridge_client.run_trusted_shell_command(
                "printf trusted",
                options=bridge_client.BridgeOptions(base_dir=str(self.base)),
            )

        request = json.loads(
            (self.base / "commands" / "trusted-shell.json").read_text()
        )
        self.assertEqual(request["cmd"], "printf trusted")
        self.assertEqual(
            set(actual),
            {"id", "returncode", "stdout", "stderr", "duration_s", "error"},
        )
        self.assertEqual(actual, result)

    def test_tail_live_log_yields_remaining_log_then_stops_at_result(self):
        results = self.base / "results"
        results.mkdir()
        (results / "request.live.log").write_text("first\nsecond\n")
        (results / "request.json").write_text("{}")

        self.assertEqual(
            list(bridge_client.tail_live_log("request", base_dir=str(self.base))),
            ["first\nsecond\n"],
        )

    def test_tail_live_log_open_failure_has_path_request_and_chained_cause(self):
        results = self.base / "results"
        results.mkdir()
        (results / "read-request.live.log").write_text("output")

        with patch("builtins.open", side_effect=OSError("read denied")):
            with self.assertRaises(OSError) as caught:
                next(
                    bridge_client.tail_live_log(
                        "read-request", base_dir=str(self.base), poll_interval=0.001
                    )
                )

        error = caught.exception
        self.assertIn("read-request", str(error))
        self.assertIn(str(results / "read-request.live.log"), str(error))
        self.assertIsInstance(error.__cause__, OSError)

    def test_tail_live_log_yields_appended_chunks_until_result_arrives(self):
        results = self.base / "results"
        results.mkdir()
        live_path = results / "request.live.log"
        live_path.write_text("")

        def append_output_and_finish():
            time.sleep(0.01)
            with live_path.open("a") as stream:
                stream.write("first\n")
            time.sleep(0.01)
            with live_path.open("a") as stream:
                stream.write("second\n")
            (results / "request.json").write_text("{}")

        producer = threading.Thread(target=append_output_and_finish, daemon=True)
        producer.start()
        chunks = list(
            bridge_client.tail_live_log(
                "request", base_dir=str(self.base), poll_interval=0.001
            )
        )
        producer.join(timeout=1)

        self.assertEqual("".join(chunks), "first\nsecond\n")


if __name__ == "__main__":
    unittest.main()
