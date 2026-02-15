#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import json, logging, os, sys
from pathlib import Path

from taskcanvas.cli import _extract_bg_args, _extract_filter_arg
from taskcanvas.injectors import (
    _find_bg_file,
    inject_custom_background,
)
from taskcanvas.output import open_file
from taskcanvas.payload import build_payload
from taskcanvas.runtime_html import build_runtime_html
from taskcanvas.task_io import fetch_tasks

OUT_HTML = Path.cwd() / "TaskCanvas.html"

def _build_logger():
    level_name = os.environ.get("TASKCANVAS_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger = logging.getLogger("TaskCanvas")
    if not logger.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter("[%(name)s][%(levelname)s] %(message)s"))
        logger.addHandler(h)
    logger.setLevel(level)
    logger.propagate = False
    return logger

LOGGER = _build_logger()

def eprint(*args):
    LOGGER.info(" ".join(str(a) for a in args))

def ewarn(*args):
    LOGGER.warning(" ".join(str(a) for a in args))

def eerror(*args):
    LOGGER.error(" ".join(str(a) for a in args))

def _fail(msg: str, *, tip: str | None = None, code: int = 1) -> int:
    eerror(msg)
    if tip:
        eerror(tip)
    return code

# ======================= Better project selector (curses) =====================

def _unique_projects(tasks):
    """Return (projects_list, counts_dict). '(no project)' last."""
    counts = {}
    for t in tasks:
        p = t.get("project") or "(no project)"
        counts[p] = counts.get(p, 0) + 1
    names = sorted([p for p in counts if p != "(no project)"])
    if "(no project)" in counts:
        names.append("(no project)")
    return names, counts


def _run_selector_curses(projects, counts):
    """
    Curses TUI multi-select:
      ↑/↓ : move      PgUp/PgDn : page       Home/End : jump
      Space: toggle   a : select all (visible)    n : none (visible)
      / : filter      Esc : clear filter          q : cancel (return [])
      Enter: confirm
    """
    import curses
    sel = set()            # selected project names
    cursor = 0             # index in filtered list
    query = ""             # filter string (case-insensitive)
    show_counts = True

    def filtered():
        if not query:
            return projects
        q = query.lower()
        return [p for p in projects if q in p.lower()]

    def clamp(i, L):
        return max(0, min(i, max(0, L - 1)))

    def draw(stdscr):
        stdscr.erase()
        H, W = stdscr.getmaxyx()

        header = " Select projects (Enter=confirm, space=toggle, /=filter, a=all, n=none, q=cancel) "
        _safe_addnstr(stdscr, 0, 0, header.ljust(W), W, curses.A_REVERSE)

        # If we have at least 2 rows, show filter line
        if H >= 2:
            _safe_addnstr(stdscr, 1, 0, f"Filter: {query}", W)

        # Compute list window geometry
        # top row for list starts at 2 only if we have room for header+filter
        top = 2 if H >= 3 else (1 if H >= 2 else 0)
        # leave one footer row only if we have ≥3 rows total
        footer_reserved = 1 if H >= 3 else 0
        rows = max(0, H - top - footer_reserved)

        vis = filtered()

        # paginate: center cursor when possible; always keep visible
        start = 0
        if rows > 0 and len(vis) > rows:
            start = min(max(cursor - rows // 2, 0), len(vis) - rows)

        # Paint list
        for i in range(start, min(len(vis), start + rows)):
            p = vis[i]
            mark = "[x]" if p in sel else "[ ]"
            cnt = f"  ({counts.get(p, 0)})" if show_counts else ""
            line = f"{mark} {p}{cnt}"
            attr = curses.A_REVERSE if i == cursor else curses.A_NORMAL
            _safe_addnstr(stdscr, top + (i - start), 0, line.ljust(W), W, attr)

        # Footer (only if we have room)
        if H >= 3:
            foot = f"{len(sel)} selected · {len(vis)} shown / {len(projects)} total"
            _safe_addnstr(stdscr, H - 1, 0, foot.ljust(W), W, curses.A_DIM)

        stdscr.refresh()


    def loop(stdscr):
        nonlocal cursor, query, show_counts, sel
        curses.curs_set(0)
        stdscr.keypad(True)
        try:
            curses.curs_set(0)
        except curses.error:
            pass

        while True:
            vis = filtered()
            cursor = clamp(cursor, len(vis))
            draw(stdscr)
            ch = stdscr.getch()

            if ch in (ord('q'), 27) and not query:       # q or Esc (when not editing filter)
                if ch == 27 and query:  # handled below if we ever allow inline edit w/ Esc
                    pass
                return []               # cancel = start empty

            if ch in (10, 13, curses.KEY_ENTER):         # Enter
                return [p for p in projects if p in sel] # preserve original order

            if ch == ord('/'):                           # start/continue filter
                # simple in-line editing: typing appends; Backspace removes; Enter commits
                while True:
                    draw(stdscr)
                    c = stdscr.getch()
                    if c in (10, 13, curses.KEY_ENTER):  # finish filter
                        break
                    if c in (27,):                       # Esc clears filter
                        query = ""
                        break
                    if c in (curses.KEY_BACKSPACE, 127, 8):
                        query = query[:-1]
                    elif c == curses.KEY_RESIZE:
                        pass
                    elif 32 <= c <= 126:  # printable ASCII
                        query += chr(c)

                # clamp cursor after filter change
                cursor = clamp(cursor, len(filtered()))
                continue

            if ch == ord('a'):                           # select all (visible)
                for p in filtered():
                    sel.add(p)
                continue

            if ch == ord('n'):                           # clear all (visible)
                for p in filtered():
                    if p in sel:
                        sel.remove(p)
                continue


            if ch == ord('c'):                           # toggle counts display (optional)
                show_counts = not show_counts
                continue

            if ch in (curses.KEY_UP, ord('k')):
                cursor = clamp(cursor - 1, len(filtered()))
            elif ch in (curses.KEY_DOWN, ord('j')):
                cursor = clamp(cursor + 1, len(filtered()))
            elif ch == curses.KEY_PPAGE:  # PageUp
                cursor = clamp(cursor - max(5, curses.LINES - 4), len(filtered()))
            elif ch == curses.KEY_NPAGE:  # PageDown
                cursor = clamp(cursor + max(5, curses.LINES - 4), len(filtered()))
            elif ch == curses.KEY_HOME:
                cursor = 0
            elif ch == curses.KEY_RESIZE:
              # Let draw() re-read H,W and recalc layout on next iteration
              continue
            elif ch == curses.KEY_END:
                cursor = max(0, len(filtered()) - 1)
            elif ch in (ord(' '),):  # toggle selection
                if filtered():
                    p = filtered()[cursor]
                    if p in sel:
                        sel.remove(p)
                    else:
                        sel.add(p)

    import curses
    return curses.wrapper(loop)

def _safe_addnstr(scr, y, x, s, max_cols, attr=0):
    """Write safely, avoiding curses ERR on small/resize terminals."""
    try:
        H, W = scr.getmaxyx()
        if y < 0 or y >= H or x < 0 or x >= W:
            return
        width = max(0, min(max_cols, W - x))
        if width <= 0:
            return
        scr.addnstr(y, x, s, width, attr)
    except Exception:
        pass

def run_project_selector(tasks):
    """High-level entry: build list, launch curses UI, return chosen names."""
    projects, counts = _unique_projects(tasks)
    if not projects:
        print("[selector] No projects found.")
        return []
    try:
        return _run_selector_curses(projects, counts)
    except Exception as e:
        # Graceful fallback to a minimal prompt if curses fails
        import traceback
        print("[selector] curses failed, falling back to simple prompt.")
        traceback.print_exc()
        # Minimal fallback: show numbered list and accept space-separated indices
        width = max(len(p) for p in projects)
        for i, p in enumerate(projects, 1):
            print(f"{i:>3}. {p:<{width}} ({counts.get(p,0)})")
        raw = input("Pick numbers (e.g. 1 2 5-7) or leave empty: ").strip()
        if not raw:
            return []
        picked = set()
        for chunk in raw.replace(",", " ").split():
            if "-" in chunk:
                a, b = chunk.split("-", 1)
                try: a = int(a); b = int(b)
                except: continue
                if a > b: a, b = b, a
                for k in range(a, b+1):
                    if 1 <= k <= len(projects): picked.add(k-1)
            else:
                try:
                    k = int(chunk)
                    if 1 <= k <= len(projects): picked.add(k-1)
                except: pass
        return [projects[i] for i in sorted(picked)]





def _json_text(d:dict)->str: return json.dumps(d, ensure_ascii=False)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

def _load_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        raise RuntimeError(f"Failed to load template: {path} ({e})")

def _load_runtime_html() -> str:
    html = _load_template("taskcanvas.base.html")
    return html.replace("</body>", _load_template("new_project_modal_v2_minimal.replace.html"))








def main() -> int:
    raw_args = sys.argv[1:]
    filter_str, args_wo_filter = _extract_filter_arg(raw_args)

    # 1) Load ALL pending tasks for the payload (drawer/search, etc.)
    try:
        tasks_all = fetch_tasks(None, log_fn=eprint, strict_errors=True)
    except Exception as e:
        return _fail(f"Failed to load pending tasks: {e}", code=1)

    # 2) If filter is present, run it separately and capture just the UUIDs to auto-place
    init_task_uuids = []
    if filter_str:
        try:
            filtered = fetch_tasks(filter_str, log_fn=eprint, strict_errors=True)
        except ValueError as e:
            return _fail(
                str(e),
                tip="Tip: quote filter expressions, e.g. --filter 'project:Work +P1'",
                code=2,
            )
        except Exception as e:
            return _fail(f"Failed to apply filter {filter_str!r}: {e}", code=1)
        init_task_uuids = [t["uuid"] for t in filtered]

    # 3) Build payload using *all* tasks
    payload = build_payload(tasks_all)
    json_text = _json_text(payload)

    # 4) Merge selector/positional args (these are still supported)
    init_projects = []
    if any(a == "--selector" for a in args_wo_filter):
        try:
            init_projects = run_project_selector(tasks_all)
        except Exception as e:
            print(f"[selector] error: {e}")

    extra = [a for a in args_wo_filter if a and not a.startswith("-")]
    if extra:
        seen = set(init_projects)
        for p in extra:
            if p not in seen:
                init_projects.append(p); seen.add(p)

    # 5) Store initial placements into payload
    changed = False
    if init_projects:
        payload["init_projects"] = init_projects
        changed = True
    if init_task_uuids:
        payload["init_task_uuids"] = init_task_uuids 
        changed = True
    if changed:
        json_text = _json_text(payload)

    try:
        base_html = _load_runtime_html()
    except RuntimeError as e:
        return _fail(str(e), tip="Ensure templates/ exists next to TaskCanvas.py.", code=1)
    html = build_runtime_html(base_html, json_text, len(tasks_all), eprint)

    # Parse bg flags out of the leftover args:
    bg_arg, bg_opacity, args_wo_filter = _extract_bg_args(args_wo_filter)

    bg_path = _find_bg_file(bg_arg, base_dir=BASE_DIR)
    if bg_path:
        html = inject_custom_background(html, bg_path, OUT_HTML, eprint, bg_opacity)
        print(f"[TaskCanvas] Using background: {bg_path.name}")
    else:
        eprint("[TaskCanvas] No custom bg found. Put 'taskcanvas-bg.(jpg|png|webp|svg)' next to the script or pass --bg=FILE.")


    try:
        OUT_HTML.write_text(html, encoding="utf-8")
    except Exception as e:
        return _fail(f"Failed to write {OUT_HTML}: {e}", code=1)

    print(f"Wrote {OUT_HTML}")
    if not open_file(OUT_HTML):
        ewarn(f"Could not auto-open {OUT_HTML}. Open it manually in your browser.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
