import tempfile
import unittest
from pathlib import Path

from taskcanvas.injectors import (
    _append_remove_mode,
    _find_bg_file,
    inject_layout_persistence,
    inject_staged_deps_color_split,
    inject_command_preflight,
    inject_custom_background,
    inject_energy_arrows,
    inject_undo_redo,
    inject_wire_deps_as_main,
)


class TestInjectors(unittest.TestCase):
    def test_append_remove_mode_idempotent(self):
        html = "<html><body><main>ok</main></body></html>"
        once = _append_remove_mode(html)
        twice = _append_remove_mode(once)
        self.assertIn("__FIXPACK_V61__", once)
        self.assertEqual(twice.count("__FIXPACK_V61__"), 1)

    def test_inject_wire_deps_as_main_idempotent(self):
        html = "<html><head></head><body></body></html>"
        once = inject_wire_deps_as_main(html)
        twice = inject_wire_deps_as_main(once)
        self.assertEqual(twice.count("__ONLY_DEPS_CONSOLE_CSS__"), 1)
        self.assertEqual(twice.count("__ONLY_DEPS_CONSOLE_JS__"), 1)

    def test_inject_energy_arrows_idempotent(self):
        html = "<html><head></head><body></body></html>"
        once = inject_energy_arrows(html)
        twice = inject_energy_arrows(once)
        self.assertEqual(twice.count("__ENERGY_ARROW_CSS__"), 1)
        self.assertEqual(twice.count("__ENERGY_ARROW_JS__"), 1)
        self.assertIn("document.hidden", twice)

    def test_staged_deps_color_split_has_coalesced_scheduler(self):
        html = "<html><head></head><body></body></html>"
        out = inject_staged_deps_color_split(html)
        self.assertIn("scheduleRestyle", out)
        self.assertIn("document.hidden", out)
        self.assertIn("900", out)

    def test_inject_layout_persistence_idempotent(self):
        html = "<html><head></head><body></body></html>"
        once = inject_layout_persistence(html)
        twice = inject_layout_persistence(once)
        self.assertEqual(twice.count("FEATURE_LAYOUT_PERSIST_V1"), 1)
        self.assertIn("localStorage", twice)
        self.assertIn("boardKey", twice)

    def test_inject_undo_redo_idempotent(self):
        html = "<html><head></head><body></body></html>"
        once = inject_undo_redo(html)
        twice = inject_undo_redo(once)
        self.assertEqual(twice.count("FEATURE_UNDO_REDO_V1"), 1)
        self.assertIn("undoCanvasChange", twice)
        self.assertIn("redoCanvasChange", twice)
        self.assertIn("maybeArmReady", twice)
        self.assertIn("flushPendingSnapshot", twice)

    def test_inject_command_preflight_idempotent(self):
        html = "<html><head></head><body></body></html>"
        once = inject_command_preflight(html)
        twice = inject_command_preflight(once)
        self.assertEqual(twice.count("FEATURE_COMMAND_PREFLIGHT_V1"), 1)

    def test_find_bg_file_prefers_base_dir_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bg = base / "taskcanvas-bg.jpg"
            bg.write_bytes(b"img")
            found = _find_bg_file(None, base_dir=base)
            self.assertEqual(found, bg)

    def test_inject_custom_background_copies_and_injects_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src.jpg"
            src.write_bytes(b"fake-image")
            out_html = root / "dist" / "TaskCanvas.html"
            out_html.parent.mkdir(parents=True, exist_ok=True)

            logs = []
            html = "<html><head></head><body><div class='app'></div></body></html>"
            out = inject_custom_background(html, src, out_html, logs.append, "0.33")

            copied = out_html.parent / src.name
            self.assertTrue(copied.exists())
            self.assertIn("FEATURE_CUSTOM_BG_V1", out)
            self.assertIn("opacity:0.33", out)
            self.assertTrue(any("Copied bg" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
