import curses
import logging
from collections.abc import Callable

from kyanbasu.task_types import TaskRecord


def _unique_projects(tasks: list[TaskRecord]) -> tuple[list[str], dict[str, int]]:
    """Return (projects_list, counts_dict). '(no project)' last."""
    counts = {}
    for task in tasks:
        project = task.get("project") or "(no project)"
        counts[project] = counts.get(project, 0) + 1
    names = sorted(project for project in counts if project != "(no project)")
    if "(no project)" in counts:
        names.append("(no project)")
    return names, counts


def _parse_selection(raw: str, project_count: int) -> list[int]:
    """Parse one-based project indexes and inclusive ranges into zero-based indexes."""
    # Ignore malformed tokens so one typo does not discard other valid selections.
    picked = set()
    for chunk in raw.replace(",", " ").split():
        if "-" in chunk:
            start, end = chunk.split("-", 1)
            try:
                start_idx = int(start)
                end_idx = int(end)
            except ValueError:
                continue
            if start_idx > end_idx:
                start_idx, end_idx = end_idx, start_idx
            indexes = range(start_idx, end_idx + 1)
        else:
            try:
                indexes = (int(chunk),)
            except ValueError:
                continue
        for index in indexes:
            if 1 <= index <= project_count:
                picked.add(index - 1)
    return sorted(picked)


def _safe_addnstr(
    scr: curses.window,
    y: int,
    x: int,
    text: str,
    max_cols: int,
    attr: int = 0,
) -> None:
    """Write safely, avoiding curses ERR on small/resize terminals."""
    try:
        height, width = scr.getmaxyx()
        if y < 0 or y >= height or x < 0 or x >= width:
            return
        safe_width = max(0, min(max_cols, width - x))
        if safe_width <= 0:
            return
        scr.addnstr(y, x, text, safe_width, attr)
    except curses.error:
        pass


def _edit_filter_query(
    stdscr: curses.window,
    query: str,
    redraw: Callable[[curses.window], None],
) -> str:
    """Read filter text until Enter accepts it or Escape clears it."""
    while True:
        redraw(stdscr)
        key = stdscr.getch()
        if key in (10, 13, curses.KEY_ENTER):
            return query
        if key == 27:
            return ""
        if key in (curses.KEY_BACKSPACE, 127, 8):
            query = query[:-1]
        elif key != curses.KEY_RESIZE and 32 <= key <= 126:
            query += chr(key)


def _clamp_index(index: int, size: int) -> int:
    return max(0, min(index, max(0, size - 1)))


def _move_selector_cursor(key: int, cursor: int, size: int, page_size: int) -> int:
    if key in (curses.KEY_UP, ord("k")):
        return _clamp_index(cursor - 1, size)
    if key in (curses.KEY_DOWN, ord("j")):
        return _clamp_index(cursor + 1, size)
    if key == curses.KEY_PPAGE:
        return _clamp_index(cursor - page_size, size)
    if key == curses.KEY_NPAGE:
        return _clamp_index(cursor + page_size, size)
    if key == curses.KEY_HOME:
        return 0
    if key == curses.KEY_END:
        return max(0, size - 1)
    return cursor


def _apply_selector_action(
    key: int, visible: list[str], cursor: int, selected: set[str]
) -> bool:
    if key == ord("a"):
        selected.update(visible)
        return True
    if key == ord("n"):
        selected.difference_update(visible)
        return True
    if key == ord(" ") and visible:
        project = visible[cursor]
        if project in selected:
            selected.remove(project)
        else:
            selected.add(project)
        return True
    return False


class _ProjectSelectorUI:
    """State and curses operations for the interactive project picker."""

    def __init__(self, projects: list[str], counts: dict[str, int]) -> None:
        self.projects = projects
        self.counts = counts
        self.selected: set[str] = set()
        self.cursor = 0
        self.query = ""
        self.show_counts = True

    def _filtered(self) -> list[str]:
        if not self.query:
            return self.projects
        needle = self.query.lower()
        return [project for project in self.projects if needle in project.lower()]

    def _draw(self, stdscr: curses.window) -> None:
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        header = " Select projects (Enter=confirm, space=toggle, /=filter, a=all, n=none, q=cancel) "
        _safe_addnstr(stdscr, 0, 0, header.ljust(width), width, curses.A_REVERSE)

        if height >= 2:
            _safe_addnstr(stdscr, 1, 0, f"Filter: {self.query}", width)

        top = 2 if height >= 3 else (1 if height >= 2 else 0)
        footer_reserved = 1 if height >= 3 else 0
        rows = max(0, height - top - footer_reserved)
        visible = self._filtered()

        start = 0
        if rows > 0 and len(visible) > rows:
            start = min(max(self.cursor - rows // 2, 0), len(visible) - rows)

        for i in range(start, min(len(visible), start + rows)):
            project = visible[i]
            mark = "[x]" if project in self.selected else "[ ]"
            count = f"  ({self.counts.get(project, 0)})" if self.show_counts else ""
            line = f"{mark} {project}{count}"
            attr = curses.A_REVERSE if i == self.cursor else curses.A_NORMAL
            _safe_addnstr(stdscr, top + (i - start), 0, line.ljust(width), width, attr)

        if height >= 3:
            footer = f"{len(self.selected)} selected · {len(visible)} shown / {len(self.projects)} total"
            _safe_addnstr(stdscr, height - 1, 0, footer.ljust(width), width, curses.A_DIM)

        stdscr.refresh()

    def run(self, stdscr: curses.window) -> list[str]:
        curses.curs_set(0)
        stdscr.keypad(True)

        while True:
            visible = self._filtered()
            self.cursor = _clamp_index(self.cursor, len(visible))
            self._draw(stdscr)
            key = stdscr.getch()

            if key in (ord("q"), 27) and not self.query:
                return []
            if key in (10, 13, curses.KEY_ENTER):
                return [project for project in self.projects if project in self.selected]
            if key == ord("/"):
                self.query = _edit_filter_query(stdscr, self.query, self._draw)
                self.cursor = _clamp_index(self.cursor, len(self._filtered()))
                continue
            if key == ord("c"):
                self.show_counts = not self.show_counts
                continue
            if _apply_selector_action(key, visible, self.cursor, self.selected):
                continue

            self.cursor = _move_selector_cursor(
                key, self.cursor, len(visible), max(5, curses.LINES - 4)
            )


def _run_selector_curses(projects: list[str], counts: dict[str, int]) -> list[str]:
    """Run the curses multi-select interface."""
    ui = _ProjectSelectorUI(projects, counts)
    return curses.wrapper(ui.run)


def _run_selector_prompt(projects: list[str], counts: dict[str, int]) -> list[str]:
    width = max(len(project) for project in projects)
    for i, project in enumerate(projects, 1):
        print(f"{i:>3}. {project:<{width}} ({counts.get(project, 0)})")

    try:
        raw = input("Pick numbers (e.g. 1 2 5-7) or leave empty: ").strip()
    except EOFError:
        return []
    if not raw:
        return []

    return [projects[i] for i in _parse_selection(raw, len(projects))]


def run_project_selector(tasks: list[TaskRecord]) -> list[str]:
    """High-level entry: build list, launch curses UI, return chosen names."""
    import curses

    projects, counts = _unique_projects(tasks)
    if not projects:
        print("[selector] No projects found.")
        return []
    try:
        return _run_selector_curses(projects, counts)
    except (curses.error, OSError) as exc:
        print("[selector] curses failed, falling back to simple prompt.")
        logging.getLogger("Kyanbasu").warning("[selector] curses failed: %s", exc)
        return _run_selector_prompt(projects, counts)
