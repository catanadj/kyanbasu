import unittest
import curses
from collections.abc import Callable
from typing import get_type_hints
from unittest.mock import patch

import kyanbasu.project_selector as selector
from kyanbasu.project_selector import (
    _parse_selection,
    _safe_addnstr,
    _unique_projects,
    _move_selector_cursor,
    _apply_selector_action,
    _ProjectSelectorUI,
    run_project_selector,
)


class TestProjectSelector(unittest.TestCase):
    def test_selector_public_and_helper_type_contracts(self):
        from kyanbasu.task_types import TaskRecord

        expected = {
            selector._unique_projects: {"tasks": list[TaskRecord], "return": tuple[list[str], dict[str, int]]},
            selector._parse_selection: {"raw": str, "project_count": int, "return": list[int]},
            selector._safe_addnstr: {
                "scr": curses.window,
                "y": int,
                "x": int,
                "text": str,
                "max_cols": int,
                "attr": int,
                "return": type(None),
            },
            selector._edit_filter_query: {
                "stdscr": curses.window,
                "query": str,
                "redraw": Callable[[curses.window], None],
                "return": str,
            },
            selector._run_selector_curses: {
                "projects": list[str], "counts": dict[str, int], "return": list[str]
            },
            selector._run_selector_prompt: {
                "projects": list[str], "counts": dict[str, int], "return": list[str]
            },
            selector.run_project_selector: {"tasks": list[TaskRecord], "return": list[str]},
        }

        for function, annotations in expected.items():
            with self.subTest(function=function.__name__):
                self.assertEqual(get_type_hints(function), annotations)

    def test_safe_addnstr_suppresses_expected_curses_errors(self):
        class Screen:
            def getmaxyx(self):
                return (10, 20)

            def addnstr(self, *_args):
                raise curses.error("resized during draw")

        _safe_addnstr(Screen(), 0, 0, "text", 20)

    def test_safe_addnstr_propagates_unexpected_errors(self):
        class Screen:
            def getmaxyx(self):
                return (10, 20)

            def addnstr(self, *_args):
                raise RuntimeError("screen programming error")

        with self.assertRaisesRegex(RuntimeError, "screen programming error"):
            _safe_addnstr(Screen(), 0, 0, "text", 20)

    def test_filter_editor_updates_text_and_escape_clears_it(self):
        class Screen:
            def __init__(self, keys):
                self.keys = iter(keys)

            def getch(self):
                return next(self.keys)

        redraw_calls = []
        redraw = lambda _screen: redraw_calls.append(True)

        edited = selector._edit_filter_query(
            Screen([ord("w"), ord("o"), ord("r"), ord("k"), 10]),
            "",
            redraw,
        )
        cleared = selector._edit_filter_query(Screen([27]), "old query", redraw)

        self.assertEqual(edited, "work")
        self.assertEqual(cleared, "")
        self.assertEqual(len(redraw_calls), 6)

    def test_parse_selection_handles_indexes_ranges_reversals_duplicates_and_invalid_tokens(self):
        selected = _parse_selection("1 2-4 6-5 2 nope 99", 6)

        self.assertEqual(selected, [0, 1, 2, 3, 4, 5])

    def test_selector_key_helpers_preserve_navigation_and_visible_selection(self):
        self.assertEqual(_move_selector_cursor(curses.KEY_DOWN, 0, 4, 5), 1)
        self.assertEqual(_move_selector_cursor(curses.KEY_END, 0, 4, 5), 3)

        selected = set()
        projects = ["Home", "Work"]
        self.assertTrue(_apply_selector_action(ord("a"), projects, 0, selected))
        self.assertEqual(selected, {"Home", "Work"})
        self.assertTrue(_apply_selector_action(ord("n"), ["Home"], 0, selected))
        self.assertEqual(selected, {"Work"})
        self.assertTrue(_apply_selector_action(ord(" "), projects, 0, selected))
        self.assertEqual(selected, {"Home", "Work"})

    def test_selector_ui_methods_keep_key_flow_and_selection_order(self):
        class Screen:
            def __init__(self):
                self.keys = iter([curses.KEY_DOWN, ord(" "), 10])

            def getmaxyx(self):
                return (10, 50)

            def erase(self):
                pass

            def addnstr(self, *_args):
                pass

            def refresh(self):
                pass

            def keypad(self, _enabled):
                pass

            def getch(self):
                return next(self.keys)

        ui = _ProjectSelectorUI(["Home", "Work"], {"Home": 2, "Work": 1})
        with patch("kyanbasu.project_selector.curses.curs_set"), patch.object(
            curses, "LINES", 24, create=True
        ):
            selected = ui.run(Screen())

        self.assertEqual(selected, ["Work"])

    def test_unique_projects_sorts_and_keeps_no_project_last(self):
        tasks = [
            {"project": "Work"},
            {"project": None},
            {"project": "Home"},
            {"project": "Work"},
        ]

        names, counts = _unique_projects(tasks)

        self.assertEqual(names, ["Home", "Work", "(no project)"])
        self.assertEqual(counts, {"Work": 2, "(no project)": 1, "Home": 1})

    def test_run_project_selector_returns_empty_when_no_projects(self):
        with patch("builtins.print") as mock_print:
            out = run_project_selector([])

        self.assertEqual(out, [])
        mock_print.assert_called_once()

    def test_run_project_selector_propagates_unexpected_selector_errors(self):
        tasks = [{"project": "Work"}]

        with patch(
            "kyanbasu.project_selector._run_selector_curses",
            side_effect=RuntimeError("programming error"),
        ):
            with self.assertRaisesRegex(RuntimeError, "programming error"):
                run_project_selector(tasks)

    def test_run_project_selector_uses_fallback_for_terminal_errors(self):
        tasks = [{"project": "Work"}, {"project": "Home"}]

        with patch(
            "kyanbasu.project_selector._run_selector_curses",
            side_effect=curses.error("terminal unavailable"),
        ), patch("builtins.input", return_value="2"):
            out = run_project_selector(tasks)

        self.assertEqual(out, ["Work"])
