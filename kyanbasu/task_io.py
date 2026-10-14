import json
import re
import shlex
import subprocess
from collections.abc import Mapping, Sequence
from json import JSONDecodeError
from typing import Any, Callable

from kyanbasu.task_types import TaskRecord

SubprocessResult = tuple[int, str, str]
TaskExportRow = dict[str, Any]


def _uuid_token(uuid: str, normalized: Mapping[str, str]) -> str:
    return normalized[uuid] or str(uuid)


def _short_id_buckets(
    uuids: list[str], lengths: Mapping[str, int], normalized: Mapping[str, str]
) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for uuid in uuids:
        raw = _uuid_token(uuid, normalized)
        short = raw[: min(lengths[uuid], len(raw))]
        buckets.setdefault(short, []).append(uuid)
    return buckets


def _grow_colliding_ids(
    collisions: list[list[str]], lengths: dict[str, int], normalized: Mapping[str, str]
) -> bool:
    progressed = False
    for group in collisions:
        for uuid in group:
            if lengths[uuid] < len(_uuid_token(uuid, normalized)):
                lengths[uuid] += 1
                progressed = True
    return progressed


def _unique_collision_suffix(base: str, used: set[str]) -> str:
    suffix = 1
    while f"{base}{suffix:x}" in used:
        suffix += 1
    return f"{base}{suffix:x}"


def run_quiet(cmd: Sequence[str], timeout: int = 30) -> SubprocessResult:
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            text=True,
        )
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"Command timed out after {timeout}s"
    except OSError as e:
        return 1, "", str(e)


def _split_filter(filter_str: str) -> list[str]:
    try:
        return shlex.split(filter_str)
    except ValueError as e:
        raise ValueError(f"Invalid --filter expression: {e}") from e


def _assign_unique_shorts(uuids: list[str], min_len: int = 8) -> dict[str, str]:
    """
    Build collision-safe short IDs from UUIDs.
    Starts at min_len and grows only where needed.
    """
    normalized = {}
    for uuid in uuids:
        normalized[uuid] = re.sub(r"[^0-9a-fA-F]", "", str(uuid)).lower()

    lengths = {uuid: min_len for uuid in uuids}
    max_len = max((len(v) for v in normalized.values()), default=min_len)
    if max_len < min_len:
        max_len = min_len

    while True:
        collisions = [
            group for group in _short_id_buckets(uuids, lengths, normalized).values()
            if len(group) > 1
        ]
        if not collisions:
            break
        if not _grow_colliding_ids(collisions, lengths, normalized):
            # Pathological case: identical normalized strings; fall back to full source token.
            break

    out = {}
    used = set()
    for uuid in uuids:
        raw = _uuid_token(uuid, normalized)
        base = raw[: min(lengths[uuid], len(raw))]
        cand = base
        if cand in used:
            cand = _unique_collision_suffix(base, used)
        out[uuid] = cand
        used.add(cand)
    return out


def _object_rows(value: list[Any]) -> list[TaskExportRow]:
    return [row for row in value if isinstance(row, dict)]


def _rows_from_json_object(value: dict[str, Any]) -> list[TaskExportRow] | None:
    for key in ("data", "rows"):
        rows = value.get(key)
        if isinstance(rows, list):
            return _object_rows(rows)
    return None


def _parse_line_json_rows(text: str) -> list[TaskExportRow]:
    rows = []
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate.startswith("{") or not candidate.endswith("}"):
            continue
        try:
            value = json.loads(candidate)
        except JSONDecodeError:
            # A malformed object-shaped line is not a task row; keep scanning other lines.
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _parse_task_export(raw: str) -> list[TaskExportRow] | None:
    """Return parsed rows, with None reserved for non-empty unrecognized output."""
    if not raw:
        return []
    lines = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s or s.startswith("Configuration override "):
            continue
        lines.append(ln)
    txt = "\n".join(lines).strip()
    if not txt:
        return []
    try:
        obj = json.loads(txt)
        if isinstance(obj, list):
            return _object_rows(obj)
        if isinstance(obj, dict):
            rows = _rows_from_json_object(obj)
            if rows is not None:
                return rows
    except JSONDecodeError:
        # Taskwarrior may emit newline-delimited JSON instead of one JSON document.
        pass
    rows = _parse_line_json_rows(txt)
    return rows if rows else None


def _normalize_string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part for part in re.split(r"[,\s]+", value) if part]
    if isinstance(value, (tuple, set)):
        return [str(item) for item in value if str(item)]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)] if str(value) else []


def _normalize_task_row(row: Mapping[str, Any]) -> TaskRecord | None:
    uuid = row.get("uuid") or row.get("id") or ""
    if not uuid:
        return None

    desc = row.get("description") or row.get("desc") or "(no description)"
    project = row.get("project") or "(no project)"
    tags = _normalize_string_values(row.get("tags") or [])
    depends = _normalize_string_values(row.get("depends") or row.get("dependencies") or [])

    due = row.get("due")
    return {
        "uuid": str(uuid),
        "short": "",
        "desc": str(desc),
        "project": str(project),
        "tags": tags,
        "depends": depends,
        "due": None if due is None else str(due),
    }


def _build_export_command(
    filter_str: str | None, *, include_runtime_settings: bool
) -> list[str]:
    command = ["task"]
    if include_runtime_settings:
        command += [
            "rc.confirmation=off",
            "rc.dependency.confirmation=off",
            "rc.verbose=nothing",
            "rc.json.array=on",
        ]
    command += _split_filter(filter_str) if filter_str else ["status:pending"]
    return [*command, "export"]


def _log_export_failures(
    log_fn: Callable[[str], None] | None,
    rc: int,
    error: str,
    fallback_rc: int,
    fallback_error: str,
) -> None:
    if log_fn is None:
        return
    if rc != 0:
        log_fn(f"Task export failed (rc={rc}): {(error or '').strip()[:220]}")
    if fallback_rc != 0:
        log_fn(
            f"Fallback task export failed (rc={fallback_rc}): "
            f"{(fallback_error or '').strip()[:220]}"
        )


def _export_failure_detail(label: str, rc: int, error: str) -> str:
    detail = (error or "").strip()[:220]
    suffix = f": {detail}" if detail else ""
    return f"{label} rc={rc}{suffix}"


def _unrecognized_export_outputs(
    rc: int,
    output: str,
    rows: list[TaskExportRow] | None,
    fallback_rc: int,
    fallback_output: str,
    fallback_rows: list[TaskExportRow] | None,
) -> list[str]:
    unrecognized = []
    if rc == 0 and rows is None:
        unrecognized.append(f"primary: {output.strip()[:160]!r}")
    if fallback_rc == 0 and fallback_rows is None:
        unrecognized.append(f"fallback: {fallback_output.strip()[:160]!r}")
    return unrecognized


def _load_export_rows(
    filter_str: str | None,
    timeout: int,
    log_fn: Callable[[str], None] | None,
) -> list[TaskExportRow]:
    rc, output, error = run_quiet(
        _build_export_command(filter_str, include_runtime_settings=True), timeout
    )
    primary_rows = _parse_task_export(output)
    if primary_rows:
        return primary_rows
    primary_valid_empty = rc == 0 and primary_rows == []

    fallback_rc, fallback_output, fallback_error = run_quiet(
        _build_export_command(filter_str, include_runtime_settings=False), timeout
    )
    fallback_rows = _parse_task_export(fallback_output)
    if fallback_rows:
        return fallback_rows

    _log_export_failures(log_fn, rc, error, fallback_rc, fallback_error)
    if rc != 0 and fallback_rc != 0:
        primary_detail = _export_failure_detail("primary", rc, error)
        fallback_detail = _export_failure_detail("fallback", fallback_rc, fallback_error)
        raise RuntimeError(
            "Taskwarrior export failed in both primary and fallback modes "
            f"({primary_detail}; {fallback_detail})."
        )
    if primary_valid_empty:
        return []
    if fallback_rc == 0 and fallback_rows is not None:
        return fallback_rows
    unrecognized = _unrecognized_export_outputs(
        rc, output, primary_rows, fallback_rc, fallback_output, fallback_rows
    )
    if unrecognized:
        raise RuntimeError(
            "Unrecognized Taskwarrior export output (" + "; ".join(unrecognized) + ")."
        )
    return []


def _normalize_export_tasks(
    rows: list[TaskExportRow],
) -> tuple[list[TaskRecord], int]:
    tasks_raw = [
        normalized
        for row in rows
        if (normalized := _normalize_task_row(row)) is not None
    ]
    short_map = _assign_unique_shorts([task["uuid"] for task in tasks_raw], min_len=8)
    widened = 0
    tasks = []
    for task in tasks_raw:
        short = short_map.get(
            task["uuid"], re.sub(r"[^0-9a-fA-F]", "", task["uuid"]).lower()[:8]
        )
        widened += len(short) > 8
        tasks.append({**task, "short": short})
    return tasks, widened


def fetch_tasks(
    filter_str: str | None = None,
    timeout: int = 30,
    log_fn: Callable[[str], None] | None = None,
) -> list[TaskRecord]:
    """
    If filter_str is None → equivalent to 'task status:pending export'
    Else → runs 'task <filter_str> export'
    Returns list of dicts with fields: uuid, short, desc, project, tags, depends, due
    """
    rows = _load_export_rows(filter_str, timeout, log_fn)
    tasks, widened = _normalize_export_tasks(rows)
    tasks.sort(key=lambda t: (t["project"], t["desc"]))

    msg = f"Loaded tasks: {len(tasks)} (filter: {filter_str!r})"
    if log_fn:
        log_fn(msg)
        if widened:
            log_fn(f"Short ID collision guard widened {widened} task id(s) beyond 8 chars.")

    return tasks
