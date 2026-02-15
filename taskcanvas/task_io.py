import json
import re
import shlex
import subprocess
from typing import Callable


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
    except Exception as e:
        return 1, "", str(e)


def _split_filter(filter_str: str):
    try:
        return shlex.split(filter_str)
    except ValueError as e:
        raise ValueError(f"Invalid --filter expression: {e}") from e


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
    except Exception:
        pass
    rows = []
    for ln in txt.splitlines():
        s = ln.strip()
        if not s or not (s.startswith("{") and s.endswith("}")):
            continue
        try:
            rows.append(json.loads(s))
        except Exception:
            pass
    return rows


def fetch_tasks(filter_str=None, timeout=30, log_fn: Callable[[str], None] | None = None):
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

    tasks = []
    for r in rows or []:
        uuid = r.get("uuid") or r.get("id") or ""
        if not uuid:
            continue
        desc = r.get("description") or r.get("desc") or "(no description)"
        project = r.get("project") or "(no project)"
        tags = r.get("tags") or []
        if isinstance(tags, str):
            tags = [t for t in re.split(r"[,\s]+", tags) if t]
        depends = r.get("depends") or r.get("dependencies") or []
        if isinstance(depends, str):
            depends = [d for d in re.split(r"[,\s]+", depends) if d]
        due = r.get("due")
        tasks.append(
            {
                "uuid": uuid,
                "short": uuid.replace("-", "")[:8],
                "desc": desc,
                "project": project,
                "tags": tags,
                "depends": depends,
                "due": due,
            }
        )

    tasks.sort(key=lambda t: (t["project"], t["desc"]))

    msg = f"[TaskCanvas] Loaded tasks: {len(tasks)} (filter: {filter_str!r})"
    if log_fn:
        log_fn(msg)

    return tasks
