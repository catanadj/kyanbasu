import hashlib
import json
import logging
import os
import sys
from pathlib import Path

from taskcanvas.cli import parse_args
from taskcanvas.injectors import _find_bg_file, inject_custom_background
from taskcanvas.output import open_file
from taskcanvas.payload import build_payload
from taskcanvas.project_selector import run_project_selector
from taskcanvas.runtime_html import build_runtime_html
from taskcanvas.task_io import fetch_tasks

OUT_HTML = Path.cwd() / "TaskCanvas.html"


def _build_logger():
    level_name = os.environ.get("KYANBASU_LOG_LEVEL") or os.environ.get("TASKCANVAS_LOG_LEVEL", "INFO")
    level_name = level_name.upper()
    level = getattr(logging, level_name, logging.INFO)
    logger = logging.getLogger("Kyanbasu")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("[%(name)s][%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


LOGGER = _build_logger()


def eprint(*args):
    LOGGER.info(" ".join(str(arg) for arg in args))


def ewarn(*args):
    LOGGER.warning(" ".join(str(arg) for arg in args))


def eerror(*args):
    LOGGER.error(" ".join(str(arg) for arg in args))


def _fail(msg: str, *, tip: str | None = None, code: int = 1) -> int:
    eerror(msg)
    if tip:
        eerror(tip)
    return code


def _json_text(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"


def _load_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"Failed to load template: {path} ({e})") from e


def _load_runtime_html() -> str:
    html = _load_template("taskcanvas.base.html")
    return html.replace("</body>", _load_template("new_project_modal_v2_minimal.replace.html"))


def _load_pending_tasks() -> list[dict]:
    try:
        return fetch_tasks(None, log_fn=eprint, strict_errors=True)
    except RuntimeError as e:
        raise RuntimeError(f"Failed to load pending tasks: {e}") from e


def _resolve_initial_task_uuids(filter_str: str | None) -> list[str]:
    if not filter_str:
        return []
    try:
        filtered = fetch_tasks(filter_str, log_fn=eprint, strict_errors=True)
    except ValueError:
        raise
    except RuntimeError as e:
        raise RuntimeError(f"Failed to apply filter {filter_str!r}: {e}") from e
    return [task["uuid"] for task in filtered]


def _resolve_initial_projects(tasks_all: list[dict], project_args: list[str], selector: bool) -> list[str]:
    init_projects = []
    if selector:
        try:
            init_projects = run_project_selector(tasks_all)
        except Exception as e:
            print(f"[selector] error: {e}")

    seen = set(init_projects)
    for project in project_args:
        if project not in seen:
            init_projects.append(project)
            seen.add(project)
    return init_projects


def _apply_initial_placements(payload: dict, init_projects: list[str], init_task_uuids: list[str]) -> dict:
    if init_projects:
        payload["init_projects"] = init_projects
    if init_task_uuids:
        payload["init_task_uuids"] = init_task_uuids
    return payload


def _apply_workspace_identity(payload: dict) -> dict:
    path = str(OUT_HTML.expanduser().resolve())
    payload["workspace_id"] = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    return payload


def _render_html(tasks_all: list[dict], payload: dict) -> str:
    base_html = _load_runtime_html()
    return build_runtime_html(base_html, _json_text(payload), len(tasks_all), eprint)


def _apply_background(html: str, bg_arg: str | None, bg_opacity: str | None) -> str:
    bg_path = _find_bg_file(bg_arg, base_dir=BASE_DIR, include_demo=bool(bg_arg))
    if bg_path:
        eprint(f"Using background: {bg_path.name}")
        return inject_custom_background(html, bg_path, OUT_HTML, eprint, bg_opacity)

    eprint("No custom bg found. Put 'kyanbasu-bg.(jpg|png|webp|svg)' next to the script or pass --bg=FILE.")
    return html


def _write_output_html(html: str) -> None:
    try:
        OUT_HTML.write_text(html, encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"Failed to write {OUT_HTML}: {e}") from e


def main(argv: list[str] | None = None, *, prog: str = "kyanbasu") -> int:
    try:
        args = parse_args(argv, prog=prog)
    except ValueError as e:
        message = str(e)
        if message.startswith("--bg"):
            return _fail(
                message,
                tip="Tip: pass values as --bg=FILE and --bg-opacity=0.18 (or separated by a space).",
                code=2,
            )
        return _fail(
            message,
            tip="Tip: quote filter expressions, e.g. --filter 'project:Work +P1'",
            code=2,
        )

    try:
        tasks_all = _load_pending_tasks()
    except RuntimeError as e:
        return _fail(str(e), code=1)

    try:
        init_task_uuids = _resolve_initial_task_uuids(args.filter)
    except ValueError as e:
        return _fail(
            str(e),
            tip="Tip: quote filter expressions, e.g. --filter 'project:Work +P1'",
            code=2,
        )
    except RuntimeError as e:
        return _fail(str(e), code=1)

    payload = build_payload(tasks_all)
    payload = _apply_workspace_identity(payload)
    init_projects = _resolve_initial_projects(tasks_all, args.projects, args.selector)
    payload = _apply_initial_placements(payload, init_projects, init_task_uuids)

    try:
        html = _render_html(tasks_all, payload)
    except RuntimeError as e:
        return _fail(str(e), tip="Ensure package templates are installed.", code=1)

    html = _apply_background(html, args.bg, args.bg_opacity)

    try:
        _write_output_html(html)
    except RuntimeError as e:
        return _fail(str(e), code=1)

    print(f"Wrote {OUT_HTML}")
    if not open_file(OUT_HTML):
        ewarn(f"Could not auto-open {OUT_HTML}. Open it manually in your browser.")
    return 0


def kyanbasu_main(argv: list[str] | None = None) -> int:
    return main(argv, prog="kyanbasu")


def taskcanvas_main(argv: list[str] | None = None) -> int:
    return main(argv, prog="taskcanvas")
