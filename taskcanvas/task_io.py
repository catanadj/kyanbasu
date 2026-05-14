import json
import re
import shlex
import subprocess
from json import JSONDecodeError
from typing import Any, Callable

from taskcanvas.task_types import TaskRecord


def run_quiet(cmd, timeout=30):
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


def _split_filter(filter_str: str):
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
        buckets = {}
        for uuid in uuids:
            raw = normalized[uuid] or str(uuid)
            pref_len = min(lengths[uuid], len(raw))
            short = raw[:pref_len]
            buckets.setdefault(short, []).append(uuid)

        collisions = [group for group in buckets.values() if len(group) > 1]
        if not collisions:
            break

        progressed = False
        for group in collisions:
            for uuid in group:
                raw = normalized[uuid] or str(uuid)
                if lengths[uuid] < len(raw):
                    lengths[uuid] += 1
                    progressed = True
        if not progressed:
            # Pathological case: identical normalized strings; fall back to full source token.
            break

    out = {}
    used = set()
    for uuid in uuids:
        raw = normalized[uuid] or str(uuid)
        base = raw[: min(lengths[uuid], len(raw))]
        cand = base
        if cand in used:
            n = 1
            while True:
                cand = f"{base}{n:x}"
                if cand not in used:
                    break
                n += 1
        out[uuid] = cand
        used.add(cand)
    return out


def _parse_task_export(raw: str):
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
            return obj
        if isinstance(obj, dict):
            if isinstance(obj.get("data"), list):
                return obj["data"]
            if isinstance(obj.get("rows"), list):
                return obj["rows"]
    except JSONDecodeError:
        pass
    rows = []
    for ln in txt.splitlines():
        s = ln.strip()
        if not s or not (s.startswith("{") and s.endswith("}")):
            continue
        try:
            rows.append(json.loads(s))
        except JSONDecodeError:
            pass
    return rows


def _normalize_task_row(row: dict[str, Any]) -> TaskRecord | None:
    uuid = row.get("uuid") or row.get("id") or ""
    if not uuid:
        return None

    desc = row.get("description") or row.get("desc") or "(no description)"
    project = row.get("project") or "(no project)"
    tags = row.get("tags") or []
    if isinstance(tags, str):
        tags = [tag for tag in re.split(r"[,\s]+", tags) if tag]
    elif isinstance(tags, (tuple, set)):
        tags = [str(tag) for tag in tags if str(tag)]
    elif not isinstance(tags, list):
        tags = [str(tags)] if str(tags) else []

    depends = row.get("depends") or row.get("dependencies") or []
    if isinstance(depends, str):
        depends = [dep for dep in re.split(r"[,\s]+", depends) if dep]
    elif isinstance(depends, (tuple, set)):
        depends = [str(dep) for dep in depends if str(dep)]
    elif not isinstance(depends, list):
        depends = [str(depends)] if str(depends) else []

    due = row.get("due")
    return {
        "uuid": str(uuid),
        "short": "",
        "desc": str(desc),
        "project": str(project),
        "tags": [str(tag) for tag in tags],
        "depends": [str(dep) for dep in depends],
        "due": None if due is None else str(due),
    }


def fetch_tasks(
    filter_str=None,
    timeout=30,
    log_fn: Callable[[str], None] | None = None,
    strict_errors: bool = False,
):
    """
    If filter_str is None → equivalent to 'task status:pending export'
    Else → runs 'task <filter_str> export'
    Returns list of dicts with fields: uuid, short, desc, project, tags, depends, due
    """
    base = [
        "task",
        "rc.confirmation=off",
        "rc.dependency.confirmation=off",
        "rc.verbose=nothing",
        "rc.json.array=on",
    ]

    if filter_str:
        base += _split_filter(filter_str)
    else:
        base += ["status:pending"]

    base += ["export"]

    rc, out, err = run_quiet(base, timeout)
    rc2 = 0
    err2 = ""
    rows = _parse_task_export(out)
    if not rows:
        # Fallback drops rc flags only, but preserves scope/filter semantics.
        fallback = ["task"]
        if filter_str:
            fallback += _split_filter(filter_str)
        else:
            fallback += ["status:pending"]
        fallback += ["export"]
        rc2, out2, err2 = run_quiet(fallback, timeout)
        rows = _parse_task_export(out2)

        if not rows and log_fn:
            if rc != 0:
                log_fn(f"[TaskCanvas] task export failed (rc={rc}): {(err or '').strip()[:220]}")
            if rc2 != 0:
                log_fn(f"[TaskCanvas] fallback task export failed (rc={rc2}): {(err2 or '').strip()[:220]}")
        if not rows and strict_errors and rc != 0 and rc2 != 0:
            raise RuntimeError("Taskwarrior export failed in both primary and fallback modes.")

    tasks_raw: list[TaskRecord] = []
    for r in rows or []:
        normalized = _normalize_task_row(r)
        if normalized is not None:
            tasks_raw.append(normalized)

    short_map = _assign_unique_shorts([t["uuid"] for t in tasks_raw], min_len=8)
    tasks: list[TaskRecord] = []
    widened = 0
    for t in tasks_raw:
        short = short_map.get(t["uuid"], re.sub(r"[^0-9a-fA-F]", "", t["uuid"]).lower()[:8])
        if len(short) > 8:
            widened += 1
        t2 = dict(t)
        t2["short"] = short
        tasks.append(t2)

    tasks.sort(key=lambda t: (t["project"], t["desc"]))

    msg = f"[TaskCanvas] Loaded tasks: {len(tasks)} (filter: {filter_str!r})"
    if log_fn:
        log_fn(msg)
        if widened:
            log_fn(f"[TaskCanvas] Short ID collision guard widened {widened} task id(s) beyond 8 chars.")

    return tasks
