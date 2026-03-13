def _unique_projects(tasks):
    """Return (projects_list, counts_dict). '(no project)' last."""
    counts = {}
    for task in tasks:
        project = task.get("project") or "(no project)"
        counts[project] = counts.get(project, 0) + 1
    names = sorted(project for project in counts if project != "(no project)")
    if "(no project)" in counts:
        names.append("(no project)")
    return names, counts


def _safe_addnstr(scr, y, x, text, max_cols, attr=0):
    """Write safely, avoiding curses ERR on small/resize terminals."""
    try:
        height, width = scr.getmaxyx()
        if y < 0 or y >= height or x < 0 or x >= width:
            return
        safe_width = max(0, min(max_cols, width - x))
        if safe_width <= 0:
            return
        scr.addnstr(y, x, text, safe_width, attr)
    except Exception:
        pass


def _run_selector_curses(projects, counts):
    """
    Curses TUI multi-select:
      ↑/↓ : move      PgUp/PgDn : page       Home/End : jump
      Space: toggle   a : select all (visible)    n : none (visible)
      / : filter      Esc : clear filter          q : cancel (return [])
      Enter: confirm
    """
    import curses

    selected = set()
    cursor = 0
    query = ""
    show_counts = True

    def filtered():
        if not query:
            return projects
        needle = query.lower()
        return [project for project in projects if needle in project.lower()]

    def clamp(index, size):
        return max(0, min(index, max(0, size - 1)))

    def draw(stdscr):
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        header = " Select projects (Enter=confirm, space=toggle, /=filter, a=all, n=none, q=cancel) "
        _safe_addnstr(stdscr, 0, 0, header.ljust(width), width, curses.A_REVERSE)

        if height >= 2:
            _safe_addnstr(stdscr, 1, 0, f"Filter: {query}", width)

        top = 2 if height >= 3 else (1 if height >= 2 else 0)
        footer_reserved = 1 if height >= 3 else 0
        rows = max(0, height - top - footer_reserved)
        visible = filtered()

        start = 0
        if rows > 0 and len(visible) > rows:
            start = min(max(cursor - rows // 2, 0), len(visible) - rows)

        for i in range(start, min(len(visible), start + rows)):
            project = visible[i]
            mark = "[x]" if project in selected else "[ ]"
            count = f"  ({counts.get(project, 0)})" if show_counts else ""
            line = f"{mark} {project}{count}"
            attr = curses.A_REVERSE if i == cursor else curses.A_NORMAL
            _safe_addnstr(stdscr, top + (i - start), 0, line.ljust(width), width, attr)

        if height >= 3:
            footer = f"{len(selected)} selected · {len(visible)} shown / {len(projects)} total"
            _safe_addnstr(stdscr, height - 1, 0, footer.ljust(width), width, curses.A_DIM)

        stdscr.refresh()

    def loop(stdscr):
        nonlocal cursor, query, show_counts, selected

        curses.curs_set(0)
        stdscr.keypad(True)
        try:
            curses.curs_set(0)
        except curses.error:
            pass

        while True:
            visible = filtered()
            cursor = clamp(cursor, len(visible))
            draw(stdscr)
            ch = stdscr.getch()

            if ch in (ord("q"), 27) and not query:
                return []

            if ch in (10, 13, curses.KEY_ENTER):
                return [project for project in projects if project in selected]

            if ch == ord("/"):
                while True:
                    draw(stdscr)
                    c = stdscr.getch()
                    if c in (10, 13, curses.KEY_ENTER):
                        break
                    if c == 27:
                        query = ""
                        break
                    if c in (curses.KEY_BACKSPACE, 127, 8):
                        query = query[:-1]
                    elif c != curses.KEY_RESIZE and 32 <= c <= 126:
                        query += chr(c)
                cursor = clamp(cursor, len(filtered()))
                continue

            if ch == ord("a"):
                for project in filtered():
                    selected.add(project)
                continue

            if ch == ord("n"):
                for project in filtered():
                    selected.discard(project)
                continue

            if ch == ord("c"):
                show_counts = not show_counts
                continue

            if ch in (curses.KEY_UP, ord("k")):
                cursor = clamp(cursor - 1, len(filtered()))
            elif ch in (curses.KEY_DOWN, ord("j")):
                cursor = clamp(cursor + 1, len(filtered()))
            elif ch == curses.KEY_PPAGE:
                cursor = clamp(cursor - max(5, curses.LINES - 4), len(filtered()))
            elif ch == curses.KEY_NPAGE:
                cursor = clamp(cursor + max(5, curses.LINES - 4), len(filtered()))
            elif ch == curses.KEY_HOME:
                cursor = 0
            elif ch == curses.KEY_RESIZE:
                continue
            elif ch == curses.KEY_END:
                cursor = max(0, len(filtered()) - 1)
            elif ch == ord(" ") and filtered():
                project = filtered()[cursor]
                if project in selected:
                    selected.remove(project)
                else:
                    selected.add(project)

    return curses.wrapper(loop)


def run_project_selector(tasks):
    """High-level entry: build list, launch curses UI, return chosen names."""
    projects, counts = _unique_projects(tasks)
    if not projects:
        print("[selector] No projects found.")
        return []
    try:
        return _run_selector_curses(projects, counts)
    except Exception:
        import traceback

        print("[selector] curses failed, falling back to simple prompt.")
        traceback.print_exc()
        width = max(len(project) for project in projects)
        for i, project in enumerate(projects, 1):
            print(f"{i:>3}. {project:<{width}} ({counts.get(project, 0)})")

        raw = input("Pick numbers (e.g. 1 2 5-7) or leave empty: ").strip()
        if not raw:
            return []

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
                for index in range(start_idx, end_idx + 1):
                    if 1 <= index <= len(projects):
                        picked.add(index - 1)
            else:
                try:
                    index = int(chunk)
                except ValueError:
                    continue
                if 1 <= index <= len(projects):
                    picked.add(index - 1)
        return [projects[i] for i in sorted(picked)]
