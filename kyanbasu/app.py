import hashlib
import json
import logging
import os
import sys
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from kyanbasu.cli import parse_args
from kyanbasu.injectors import _find_bg_file, inject_custom_background
from kyanbasu.output import open_file
from kyanbasu.payload import build_payload
from kyanbasu.project_selector import run_project_selector
from kyanbasu.runtime_html import build_runtime_html
from kyanbasu.task_io import fetch_tasks
from kyanbasu.task_types import RuntimePayload, TaskRecord

def _build_logger():
    level_name = os.environ.get("KYANBASU_LOG_LEVEL", "INFO")
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


LOGGER = logging.getLogger("Kyanbasu")


@dataclass(frozen=True)
class RuntimeConfig:
    out_html: Path
    base_dir: Path
    templates_dir: Path
    logger: logging.Logger


def _resolve_runtime_config() -> RuntimeConfig:
    output_value = os.environ.get("KYANBASU_OUTPUT")
    out_html = Path(output_value).expanduser() if output_value else Path.cwd() / "Kyanbasu.html"
    logger = _build_logger()
    return RuntimeConfig(
        out_html=out_html,
        base_dir=BASE_DIR,
        templates_dir=TEMPLATES_DIR,
        logger=logger,
    )


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


def _json_text(data: RuntimePayload) -> str:
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
    html = _load_template("kyanbasu.base.html")
    return html.replace("</body>", _load_template("new_project_modal_v2_minimal.replace.html"))


def _load_pending_tasks() -> list[TaskRecord]:
    try:
        return fetch_tasks(None, log_fn=eprint)
    except RuntimeError as e:
        raise RuntimeError(f"Failed to load pending tasks: {e}") from e


def _resolve_initial_task_uuids(filter_str: str | None) -> list[str]:
    if not filter_str:
        return []
    try:
        filtered = fetch_tasks(filter_str, log_fn=eprint)
    except ValueError:
        raise
    except RuntimeError as e:
        raise RuntimeError(f"Failed to apply filter {filter_str!r}: {e}") from e
    return [task["uuid"] for task in filtered]


def _resolve_initial_projects(tasks_all: list[TaskRecord], project_args: list[str], selector: bool) -> list[str]:
    init_projects = []
    if selector:
        init_projects = run_project_selector(tasks_all)

    seen = set(init_projects)
    for project in project_args:
        if project not in seen:
            init_projects.append(project)
            seen.add(project)
    return init_projects


def _apply_initial_placements(
    payload: RuntimePayload,
    init_projects: list[str],
    init_task_uuids: list[str],
) -> RuntimePayload:
    if init_projects:
        payload["init_projects"] = init_projects
    if init_task_uuids:
        payload_uuids = {task.get("uuid") for task in payload.get("tasks", [])}
        payload["init_task_uuids"] = [uuid for uuid in init_task_uuids if uuid in payload_uuids]
    return payload


def _apply_workspace_identity(payload: RuntimePayload, out_html: Path | None = None) -> RuntimePayload:
    out_html = out_html or _resolve_runtime_config().out_html
    path = str(out_html.expanduser().resolve())
    payload["workspace_id"] = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    return payload


def _render_html(tasks_all: list[TaskRecord], payload: RuntimePayload) -> str:
    base_html = _load_runtime_html()
    debug = os.environ.get("KYANBASU_DEBUG", "").lower() in {"1", "true", "yes", "on"}
    eprint(f"Embedded tasks: {len(tasks_all)}")
    return build_runtime_html(base_html, _json_text(payload), len(tasks_all), debug=debug)


def _apply_background(
    html: str,
    bg_arg: str | None,
    bg_opacity: str | None,
    config: RuntimeConfig | None = None,
) -> str:
    config = config or _resolve_runtime_config()
    bg_path = _find_bg_file(bg_arg, base_dir=config.base_dir, include_demo=bool(bg_arg))
    if bg_path:
        eprint(f"Using background: {bg_path.name}")
        return inject_custom_background(html, bg_path, config.out_html, eprint, bg_opacity)

    eprint("No custom bg found. Put 'kyanbasu-bg.(jpg|png|webp|svg)' next to the script or pass --bg=FILE.")
    return html


def _write_output_html(html: str, out_html: Path | None = None) -> None:
    out_html = out_html or _resolve_runtime_config().out_html
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=out_html.parent,
            prefix=f".{out_html.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(html)
        os.replace(temporary_path, out_html)
    except OSError as e:
        raise RuntimeError(f"Failed to write {out_html}: {e}") from e
    finally:
        if temporary_path is not None:
            with suppress(OSError):
                temporary_path.unlink()


def main(argv: list[str] | None = None, *, prog: str = "kyanbasu") -> int:
    config = _resolve_runtime_config()
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
    payload = _apply_workspace_identity(payload, config.out_html)
    init_projects = _resolve_initial_projects(tasks_all, args.projects, args.selector)
    payload = _apply_initial_placements(payload, init_projects, init_task_uuids)

    try:
        html = _render_html(tasks_all, payload)
    except RuntimeError as e:
        return _fail(str(e), tip="Ensure package templates are installed.", code=1)

    html = _apply_background(html, args.bg, args.bg_opacity, config)

    try:
        _write_output_html(html, config.out_html)
    except RuntimeError as e:
        return _fail(str(e), code=1)

    print(f"Wrote {config.out_html}")
    if not open_file(config.out_html):
        ewarn(f"Could not auto-open {config.out_html}. Open it manually in your browser.")
    return 0


def kyanbasu_main(argv: list[str] | None = None) -> int:
    return main(argv, prog="kyanbasu")
