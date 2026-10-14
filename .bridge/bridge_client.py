#!/usr/bin/env python3
"""
bridge_client.py — reference implementation for the AGENT side.

If your agent can execute Python, import run_command() directly.
If it can only write text files, use this as a spec for whatever
language/tool the agent has: it just needs to write a JSON file
(atomically) and then poll for the matching result file.
"""

import json
import os
import time
import uuid
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


class BridgeTimeout(Exception):
    pass


class BridgeResult(TypedDict):
    id: str
    returncode: int | None
    stdout: str
    stderr: str
    duration_s: float
    error: str | None


@dataclass(frozen=True)
class BridgeOptions:
    base_dir: str | Path = "./bridge"
    cwd: str | None = None
    timeout: float = 60
    env: Mapping[str, str] | None = None
    poll_interval: float = 0.3
    wait_timeout: float | None = None


def _filesystem_error(operation, path, req_id, error):
    raise OSError(
        f"Bridge {operation} failed for request {req_id} at {path}: {error}"
    ) from error


def _validate_result(data, req_id, result_path):
    fields = set(BridgeResult.__annotations__)
    if not isinstance(data, dict):
        raise ValueError(f"Bridge result for request {req_id} at {result_path} must be an object")
    missing, extra = fields - set(data), set(data) - fields
    if missing:
        raise ValueError(f"Bridge result for request {req_id} at {result_path} is missing field(s): {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"Bridge result for request {req_id} at {result_path} has unsupported field(s): {', '.join(sorted(extra))}")
    expected = {"id": str, "returncode": int, "stdout": str, "stderr": str, "duration_s": (int, float), "error": str}
    for field, kind in expected.items():
        value = data[field]
        valid = isinstance(value, kind) and not isinstance(value, bool)
        if field in ("returncode", "error") and value is None:
            valid = True
        if not valid:
            raise ValueError(f"Bridge result for request {req_id} at {result_path} has invalid {field}")
    if data["id"] != req_id:
        raise ValueError(f"Bridge result for request {req_id} at {result_path} has mismatched id")
    return data


def _run_command(cmd: Sequence[str] | str, options: BridgeOptions, allow_shell=False) -> BridgeResult:
    if isinstance(cmd, str) and not allow_shell:
        raise TypeError("cmd must be an argument sequence; use run_trusted_shell_command for shell commands")
    if not isinstance(cmd, str) and (not isinstance(cmd, Sequence) or not cmd or not all(isinstance(part, str) for part in cmd)):
        raise TypeError("cmd must be a non-empty argument sequence of strings")
    base_dir, cwd, timeout, env = options.base_dir, options.cwd, options.timeout, options.env
    poll_interval, wait_timeout = options.poll_interval, options.wait_timeout
    """
    Send a command to the watcher and block until the result is ready.

    cmd: list (preferred, e.g. ["ls", "-la"]) or string (runs via shell)
    wait_timeout: how long to wait for a result before giving up client-side
                  (defaults to `timeout` + 10s buffer)
    """
    base = Path(base_dir)
    commands_dir = base / "commands"
    results_dir = base / "results"
    req_id = uuid.uuid4().hex
    for operation, path in (("create commands directory", commands_dir),
                            ("create results directory", results_dir)):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            _filesystem_error(operation, path, req_id, error)

    payload = {"id": req_id, "cmd": cmd, "cwd": cwd, "timeout": timeout, "env": env or {}}

    # Atomic write: temp file + rename
    tmp_path = commands_dir / f".tmp-{req_id}.json"
    final_path = commands_dir / f"{req_id}.json"
    try:
        tmp_path.write_text(json.dumps(payload))
    except OSError as error:
        _filesystem_error("write request", tmp_path, req_id, error)
    try:
        os.rename(tmp_path, final_path)
    except OSError as error:
        _filesystem_error("publish request", final_path, req_id, error)

    result_path = results_dir / f"{req_id}.json"
    deadline = time.monotonic() + (wait_timeout if wait_timeout is not None else timeout + 10)
    last_decode_error = None
    while time.monotonic() < deadline:
        if result_path.exists():
            try:
                data = json.loads(result_path.read_text())
            except json.JSONDecodeError as error:
                last_decode_error = error
                time.sleep(poll_interval)
                continue  # watcher might still be writing; retry
            return _validate_result(data, req_id, result_path)
        time.sleep(poll_interval)

    error = BridgeTimeout(f"No result for command {req_id} after waiting" + (f"; last result decode error: {last_decode_error}" if last_decode_error else ""))
    if last_decode_error:
        raise error from last_decode_error
    raise error


def run_command(cmd: Sequence[str] | str, base_dir="./bridge", cwd=None, timeout=60,
                env=None, poll_interval=0.3, wait_timeout=None, *, options: BridgeOptions | None = None) -> BridgeResult:
    if options is not None and not isinstance(options, BridgeOptions):
        raise TypeError("options must be BridgeOptions")
    return _run_command(cmd, options or BridgeOptions(base_dir, cwd, timeout, env, poll_interval, wait_timeout))


def run_trusted_shell_command(cmd: str, base_dir="./bridge", cwd=None, timeout=60,
                              env=None, poll_interval=0.3, wait_timeout=None, *,
                              options: BridgeOptions | None = None) -> BridgeResult:
    if not isinstance(cmd, str):
        raise TypeError("shell command must be a string")
    return _run_command(cmd, options or BridgeOptions(base_dir, cwd, timeout, env, poll_interval, wait_timeout), allow_shell=True)


def tail_live_log(req_id: str, base_dir: str | Path = "./bridge", poll_interval: float = 0.2) -> Iterator[str]:
    """
    Generator that yields new output chunks as they're written to
    results/<id>.live.log, until the matching result file appears.
    Useful if the agent wants to show progress instead of just waiting.
    """
    base = Path(base_dir)
    live_path = base / "results" / f"{req_id}.live.log"
    result_path = base / "results" / f"{req_id}.json"

    pos = 0
    while True:
        if live_path.exists():
            try:
                with open(live_path) as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos += len(chunk)
            except OSError as error:
                _filesystem_error("read live log", live_path, req_id, error)
            if chunk:
                yield chunk
        if result_path.exists():
            # one final read in case output landed between the checks above
            if live_path.exists():
                try:
                    with open(live_path) as f:
                        f.seek(pos)
                        chunk = f.read()
                        pos += len(chunk)
                except OSError as error:
                    _filesystem_error("read live log", live_path, req_id, error)
                if chunk:
                    yield chunk
            return
        time.sleep(poll_interval)


def _cli():
    """
    CLI entry point so an agent can call this with a single clean shell
    command instead of nested python -c / quote escaping.

    Usage:
        # from a JSON file the agent already wrote:
        python3 bridge_client.py --json-file /tmp/req.json --base-dir ./bridge

        # or piped via stdin:
        echo '{"cmd": ["git","status"], "cwd": "/repo"}' | \\
            python3 bridge_client.py --base-dir ./bridge

    The JSON must contain at least "cmd". "cwd", "timeout", and "env" are
    optional and match the run_command() parameters.

    Prints the result as real JSON (json.dumps, not Python repr) to
    stdout, and exits with the inner command's returncode so normal
    shell "did it succeed" checks (`&&`, `$?`, etc.) work correctly.
    An inner timeout or bridge-level failure exits with code 1 and an
    {"error": ...} payload.
    """
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Run a command through the file bridge")
    ap.add_argument("--json-file", help="Path to a JSON file with the request (default: read stdin)")
    ap.add_argument("--base-dir", default="./bridge", help="Bridge base directory")
    ap.add_argument("--poll-interval", type=float, default=0.3)
    args = ap.parse_args()

    raw = Path(args.json_file).read_text() if args.json_file else sys.stdin.read()
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"invalid JSON request: {e}"}))
        sys.exit(1)

    if "cmd" not in spec:
        print(json.dumps({"error": "request JSON must include 'cmd'"}))
        sys.exit(1)

    try:
        result = run_command(
            spec["cmd"],
            base_dir=args.base_dir,
            cwd=spec.get("cwd"),
            timeout=spec.get("timeout", 60),
            env=spec.get("env"),
            poll_interval=args.poll_interval,
        )
    except BridgeTimeout as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    print(json.dumps(result))
    rc = result.get("returncode")
    sys.exit(rc if isinstance(rc, int) else 1)


if __name__ == "__main__":
    _cli()
