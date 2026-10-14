#!/usr/bin/env python3
"""
watcher.py — file-based command bridge (runs in YOUR environment)

Watches bridge/commands/ for JSON command requests, executes them,
streams output live, and writes JSON results to bridge/results/.

Protocol
--------
Command file: bridge/commands/<id>.json
    {
      "id": "abc123",
      "cmd": ["ls", "-la"],       // list = exec directly (safer), or string = shell
      "cwd": "optional/path",
      "timeout": 30,               // seconds, optional
      "env": {"KEY": "value"}      // optional extra env vars
    }

While running:
  bridge/running.json               index of all currently-running commands
  bridge/results/<id>.live.log      output as it's produced (tail -f this)

When finished:
  bridge/results/<id>.json          final result
    {
      "id": "abc123",
      "returncode": 0,
      "stdout": "...",
      "stderr": "...",
      "duration_s": 0.12,
      "error": null
    }

Agent-side write MUST be atomic: write to commands/.tmp-<id>.json then
os.rename() into commands/<id>.json. Same filesystem rename is atomic on
POSIX, so the watcher never sees a half-written file.
"""

import argparse
import errno
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Literal, TextIO

MAX_OUTPUT_CHARS = 200_000  # truncate huge output so result files stay sane


def atomic_write_json(path: Path, data: dict):
    tmp = path.with_name(f".tmp-{uuid.uuid4().hex}-{path.name}")
    tmp.write_text(json.dumps(data, indent=2))
    os.rename(tmp, path)  # atomic on same filesystem


def truncate(s: str) -> str:
    if s is None:
        return ""
    if len(s) > MAX_OUTPUT_CHARS:
        return s[:MAX_OUTPUT_CHARS] + f"\n... [truncated, {len(s)} chars total]"
    return s


def _read_pty_chunk(fd: int) -> str | None:
    try:
        return os.read(fd, 4096).decode(errors="replace")
    except OSError as error:
        if error.errno == errno.EIO:
            return None
        raise


def _empty_result(req_id: str, error: str | None = None) -> dict[str, object]:
    return {
        "id": req_id,
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "duration_s": 0.0,
        "error": error,
    }


class Watcher:
    def __init__(
        self,
        base_dir: Path,
        *,
        poll_interval: float,
        allow_pattern: str | None,
        require_confirm: bool,
        default_timeout: int,
        use_pty: bool,
    ):
        self.commands_dir = base_dir / "commands"
        self.processing_dir = base_dir / "processing"
        self.results_dir = base_dir / "results"
        self.done_dir = base_dir / "done"
        for d in (self.commands_dir, self.processing_dir, self.results_dir, self.done_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.running_path = base_dir / "running.json"
        atomic_write_json(self.running_path, {})

        self.poll_interval = poll_interval
        self.allow_re = re.compile(allow_pattern) if allow_pattern else None
        self.require_confirm = require_confirm
        self.default_timeout = default_timeout
        self.use_pty = use_pty
        self._running = {}  # id -> info dict, mirrors running.json
        self._lock = threading.Lock()

    def _claim(self, path: Path) -> Path | None:
        """Atomically move a command file into processing/ to avoid double-handling."""
        target = self.processing_dir / path.name
        try:
            os.rename(path, target)
            return target
        except FileNotFoundError:
            return None  # already claimed

    def _report_filesystem_error(self, operation: str, path: Path, error: OSError):
        print(
            f"[ERROR] Filesystem {operation} failed for request {path.stem} "
            f"at {path}: {error}"
        )

    def _handle_pending_request(self, path: Path):
        try:
            claimed = self._claim(path)
        except OSError as error:
            self._report_filesystem_error("claim", path, error)
            return
        if claimed is None:
            return

        try:
            self._run_one(claimed)
        except OSError as error:
            self._report_filesystem_error("process", claimed, error)
            return

        try:
            os.rename(claimed, self.done_dir / claimed.name)
        except OSError as error:
            self._report_filesystem_error("move to done", claimed, error)

    def _command_str(self, cmd) -> str:
        if isinstance(cmd, list):
            return " ".join(shlex.quote(str(c)) for c in cmd)
        return str(cmd)

    def _is_allowed(self, cmd_str: str) -> bool:
        return self.allow_re is None or bool(self.allow_re.fullmatch(cmd_str))

    def _confirm(self, cmd_str: str) -> bool:
        print(f"\n>>> Agent wants to run:\n    {cmd_str}")
        return input("    Allow? [y/N] ").strip().lower() == "y"

    def _mark_running(self, req_id, cmd_str, cwd):
        with self._lock:
            self._running[req_id] = {
                "cmd": cmd_str, "cwd": cwd, "started_at": time.time(),
            }
            atomic_write_json(self.running_path, dict(self._running))

    def _mark_done(self, req_id):
        with self._lock:
            self._running.pop(req_id, None)
            atomic_write_json(self.running_path, dict(self._running))

    def _stream_pipes(self, proc, live_file, req_id, buffers):
        """Read stdout/stderr concurrently, writing to live_file and console as it arrives."""
        reader_errors = []
        error_lock = threading.Lock()

        def record_error(message):
            with error_lock:
                reader_errors.append(message)

        def pump(
            stream: TextIO,
            key: Literal["stdout", "stderr"],
            prefix: Literal["OUT", "ERR"],
        ) -> None:
            try:
                for line in iter(stream.readline, ""):
                    buffers[key].append(line)
                    live_file.write(line)
                    live_file.flush()
                    sys.stdout.write(f"[{req_id[:8]} {prefix}] {line}")
                    sys.stdout.flush()
            except Exception as error:
                record_error(f"{key} reader failed: {error}")
            finally:
                try:
                    stream.close()
                except Exception as error:
                    record_error(f"{key} stream close failed: {error}")

        t_out = threading.Thread(target=pump, args=(proc.stdout, "stdout", "OUT"))
        t_err = threading.Thread(target=pump, args=(proc.stderr, "stderr", "ERR"))
        t_out.start()
        t_err.start()
        return t_out, t_err, reader_errors

    def _run_one(self, path: Path):
        req_id = path.stem
        try:
            payload = json.loads(path.read_text())
        except (OSError, UnicodeError, json.JSONDecodeError) as e:
            result = _empty_result(req_id, f"failed to parse command file: {e}")
            atomic_write_json(self.results_dir / f"{req_id}.json", result)
            return

        cmd = payload.get("cmd")
        cwd = payload.get("cwd")
        timeout = payload.get("timeout", self.default_timeout)
        extra_env = payload.get("env", {})
        cmd_str = self._command_str(cmd)

        if not self._is_allowed(cmd_str):
            result = _empty_result(req_id, f"command blocked by allowlist: {cmd_str}")
            print(f"[BLOCKED] {cmd_str}")
            atomic_write_json(self.results_dir / f"{req_id}.json", result)
            return

        if self.require_confirm and not self._confirm(cmd_str):
            result = _empty_result(req_id, "command rejected by operator")
            atomic_write_json(self.results_dir / f"{req_id}.json", result)
            return

        env = os.environ.copy()
        env.update({k: str(v) for k, v in extra_env.items()})

        live_path = self.results_dir / f"{req_id}.live.log"
        buffers = {"stdout": [], "stderr": []}
        print(f"[RUN {req_id[:8]}] {cmd_str}")
        self._mark_running(req_id, cmd_str, cwd)

        start = time.time()
        try:
            with open(live_path, "w") as live_file:
                if self.use_pty:
                    execution_result = self._run_with_pty(
                        cmd=cmd,
                        cmd_str=cmd_str,
                        cwd=cwd,
                        env=env,
                        timeout=timeout,
                        live_file=live_file,
                        req_id=req_id,
                        buffers=buffers,
                    )
                else:
                    # Popen has no timeout argument; proc.wait below enforces this request's deadline.
                    proc = subprocess.Popen(
                        cmd,
                        shell=isinstance(cmd, str),
                        cwd=cwd or None,
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                    )
                    t_out, t_err, reader_errors = self._stream_pipes(
                        proc, live_file, req_id, buffers
                    )
                    error = None
                    try:
                        proc.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                        error = f"timed out after {timeout}s"
                    t_out.join()
                    t_err.join()
                    if reader_errors:
                        reader_error = "; ".join(reader_errors)
                        error = f"{error}; {reader_error}" if error else reader_error
                    execution_result = {
                        "returncode": proc.returncode,
                        "stdout": truncate("".join(buffers["stdout"])),
                        "stderr": truncate("".join(buffers["stderr"])),
                        "error": error,
                    }
        except (OSError, subprocess.SubprocessError, TypeError, ValueError) as e:
            execution_result = {
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "error": f"{e}\n{traceback.format_exc()}",
            }
        result = {
            "id": req_id,
            **execution_result,
            "duration_s": round(time.time() - start, 3),
        }

        self._mark_done(req_id)
        atomic_write_json(self.results_dir / f"{req_id}.json", result)
        print(f"[DONE {req_id[:8]}] rc={result['returncode']} ({result['duration_s']}s)")

    def _run_with_pty(
        self, *, cmd, cmd_str, cwd, env, timeout, live_file, req_id, buffers
    ):
        """Run via a pseudo-terminal so buffered CLI tools behave as if interactive."""
        import pty
        import select

        master, slave = pty.openpty()
        # PTY mode enforces the timeout in the polling loop below, then kills overdue children.
        proc = subprocess.Popen(
            cmd,
            shell=isinstance(cmd, str),
            cwd=cwd or None,
            env=env,
            stdin=slave, stdout=slave, stderr=slave,
            close_fds=True,
        )
        os.close(slave)

        error = None
        start = time.time()
        try:
            while True:
                if proc.poll() is not None:
                    break
                if time.time() - start > timeout:
                    proc.kill()
                    proc.wait()
                    error = f"timed out after {timeout}s"
                    break
                r, _, _ = select.select([master], [], [], 0.2)
                if r:
                    chunk = _read_pty_chunk(master)
                    if chunk is None:
                        break
                    if chunk:
                        buffers["stdout"].append(chunk)
                        live_file.write(chunk)
                        live_file.flush()
                        sys.stdout.write(f"[{req_id[:8]} OUT] {chunk}")
                        sys.stdout.flush()
            # drain any remaining bytes
            while True:
                chunk = _read_pty_chunk(master)
                if not chunk:
                    break
                buffers["stdout"].append(chunk)
                live_file.write(chunk)
        finally:
            os.close(master)
        return {
            "returncode": proc.poll(),
            "stdout": truncate("".join(buffers["stdout"])),
            "stderr": "",  # PTY merges stderr into stdout.
            "error": error,
        }

    def run_forever(self) -> None:
        mode = "pty" if self.use_pty else "pipes"
        print(f"Watching {self.commands_dir} (poll every {self.poll_interval}s, mode={mode})... Ctrl+C to stop.")
        try:
            while True:
                try:
                    candidates = list(self.commands_dir.glob("*.json"))
                except OSError as e:
                    print(f"[ERROR] could not read {self.commands_dir}: {e}")
                    time.sleep(self.poll_interval)
                    continue

                pending = []
                for path in candidates:
                    try:
                        mtime = path.stat().st_mtime
                    except OSError as e:
                        print(f"[ERROR] could not stat {path}: {e}")
                        continue
                    pending.append((mtime, path))
                pending.sort(key=lambda item: item[0])

                for _, path in pending:
                    self._handle_pending_request(path)
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            print("\nStopped.")


def main() -> None:
    ap = argparse.ArgumentParser(description="File-based command bridge watcher")
    ap.add_argument("--dir", default="./bridge", help="Base bridge directory (default: ./bridge)")
    ap.add_argument("--poll-interval", type=float, default=0.5, help="Seconds between polls")
    ap.add_argument("--allow", default=None,
                     help="Regex the full command string must match to be allowed (recommended)")
    ap.add_argument("--confirm", action="store_true",
                     help="Ask for y/N confirmation before running each command")
    ap.add_argument("--timeout", type=int, default=60, help="Default timeout (s) per command")
    ap.add_argument("--pty", action="store_true",
                     help="Run commands through a pseudo-terminal for truer real-time output "
                          "(Unix only; merges stdout+stderr)")
    args = ap.parse_args()

    base = Path(args.dir).resolve()
    Watcher(
        base,
        poll_interval=args.poll_interval,
        allow_pattern=args.allow,
        require_confirm=args.confirm,
        default_timeout=args.timeout,
        use_pty=args.pty,
    ).run_forever()


if __name__ == "__main__":
    main()
