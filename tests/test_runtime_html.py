import json
import re
import unittest
from pathlib import Path

from kyanbasu.runtime_html import build_runtime_html


class TestRuntimeHtml(unittest.TestCase):
    def test_build_runtime_html_suppresses_routine_browser_logs_by_default(self):
        base_html = "<html><head></head><body><!-- INLINE_PAYLOAD_HERE --></body></html>"
        payload = json.dumps({"tasks": [], "graph": {}}, separators=(",", ":"))

        out = build_runtime_html(base_html, payload, 0)

        self.assertIn("window.KYANBASU_DEBUG = false", out)
        for message in (
            "[observer] hover stage observer active (toggle-aware)",
            "[hover/console] modify injector active",
            "[hotkey] ONLY Ctrl+Shift+D toggles console; plain/Shift D suppressed",
            "[FixPack V6.1] already bound",
            "[dep-preview-cancel] removed",
            "[dep-remove]",
        ):
            self.assertIn(f"if (window.KYANBASU_DEBUG) console.log('{message}", out)
        self.assertIn("if (!el) {", out)
        self.assertIn("if (window.KYANBASU_DEBUG) console.warn('[payload] missing payload element');", out)
        self.assertIn("if (window.KYANBASU_DEBUG) console.warn('[payload] twdata dispatch failed', e);", out)
        self.assertIn("console.error('[payload] initFromDATA error'", out)
        self.assertIn("console.error('[payload] parse error'", out)

    def test_build_runtime_html_can_enable_browser_debug_logs(self):
        base_html = "<html><head></head><body><!-- INLINE_PAYLOAD_HERE --></body></html>"
        payload = json.dumps({"tasks": [], "graph": {}}, separators=(",", ":"))

        out = build_runtime_html(base_html, payload, 0, debug=True)

        self.assertIn("console.log('[payload]", out)
        self.assertIn("window.KYANBASU_DEBUG = true", out)
        self.assertIn("if (window.KYANBASU_DEBUG) console.warn('[payload] missing payload element');", out)
        self.assertIn("if (window.KYANBASU_DEBUG) console.warn('[payload] twdata dispatch failed', e);", out)

    def test_runtime_diagnostics_and_toast_fallback_logs_are_debug_only(self):
        base_html = Path("kyanbasu/templates/kyanbasu.base.html").read_text(encoding="utf-8")
        payload = json.dumps({"tasks": [], "graph": {}}, separators=(",", ":"))

        out = build_runtime_html(base_html, payload, 0)

        self.assertIn("if (window.KYANBASU_DEBUG) console.warn('[Kyanbasu][diag]'", out)
        self.assertIn("if (window.KYANBASU_DEBUG) console.log(msg);", out)
        self.assertLess(
            out.index("window.KYANBASU_DEBUG = false"),
            out.index("id=\"FEATURE_RUNTIME_DIAGNOSTICS_V1\""),
        )
        self.assertIn("if (window.KYANBASU_DEBUG && !originals.setTimeout", out)
        self.assertIn("if (window.KYANBASU_DEBUG && !originals.MutationObserver", out)
        self.assertIn("console.error('[boot] init error'", out)
        self.assertIn("console.error('[Kyanbasu] initFromDATA error'", out)

    def test_build_runtime_html_injects_required_markers(self):
        base_html = "<html><head></head><body><!-- INLINE_PAYLOAD_HERE --></body></html>"
        payload = json.dumps({"tasks": [], "graph": {}}, separators=(",", ":"))
        out = build_runtime_html(base_html, payload, 0)

        required_markers = [
            "id='payload_data'",
            'id="feature-hover-css"',
            'id="FEATURE_HOVERSTAGE"',
            'id="feature-due-css-v2"',
            'id="FEATURE_DUEBADGE2"',
            'id="FEATURE_DEPENDENCY_INTERACTIONS_V1"',
            'id="FEATURE_DEPENDENCY_EDGES_V1"',
            'id="FEATURE_QUICKFIX_ADD_RENDER_V1"',
            'id="PROJECT_PICKER_V2_CSS"',
            'id="PROJECT_PICKER_V2_JS"',
            'id="FEATURE_TOAST_UTIL_V1"',
            'id="FEATURE_CONSOLE_LINE_ENFORCER_V3"',
            'id="FEATURE_COPY_FULL_OVERRIDE_V1"',
            'id="FEATURE_SINGLE_CONSOLE_AUGMENT_V1"',
            'id="feature-dedupe-focus-v1-css"',
            'id="FEATURE_DEDUPE_FOCUS_V1"',
            'id="feature-project-addtag-v4-css"',
            'id="FEATURE_PROJECT_ADD_TAG_V4"',
            'id="FEATURE_REVIEW_CHANGES_V1_CSS"',
            'id="FEATURE_REVIEW_CHANGES_V1"',
            'id="FEATURE_CANVAS_STORAGE_V1"',
            'id="FEATURE_CANVAS_NAVIGATOR_V1_CSS"',
            'id="FEATURE_CANVAS_NAVIGATOR_V1"',
            'id="FEATURE_CANVAS_NOTES_V1_CSS"',
            'id="FEATURE_CANVAS_DECISION_TRIAGE_V1_CSS"',
            'id="FEATURE_CANVAS_NOTE_ACTIONS_V1_CSS"',
            'id="FEATURE_CANVAS_DECISION_SKIP_GATE_V1_CSS"',
            'id="FEATURE_CANVAS_DECISION_REVIEW_V1_CSS"',
            'id="FEATURE_CANVAS_NOTES_CORE_V1"',
            'id="FEATURE_CANVAS_DECISION_TRIAGE_V1"',
            'id="FEATURE_CANVAS_DECISION_GUIDANCE_V1"',
            'id="FEATURE_CANVAS_NOTES_V1"',
            'id="FEATURE_CANVAS_NOTES_WORKFLOW_V1"',
            'id="FEATURE_CANVAS_DECISION_TRIAGE_UI_V1"',
            'id="FEATURE_CANVAS_NOTE_ACTIONS_V1"',
            'id="FEATURE_CANVAS_DECISION_SKIP_GATE_V1"',
            'id="FEATURE_CANVAS_DECISION_REVIEW_V1"',
            'id="FEATURE_CONSOLE_EDITOR_V1_CSS"',
            'id="FEATURE_CONSOLE_EDITOR_V1"',
            "__ENERGY_ARROW_CSS__",
            "__ONLY_DEPS_CONSOLE_CSS__",
            "__FIXPACK_V61__",
            "FEATURE_ACTIONABLE_BEACON_V7B_JS",
            "FEATURE_LAYOUT_PERSIST_V1",
            "COMMANDS_CORE_V1",
            "FEATURE_COMMAND_PREFLIGHT_V1",
            "FEATURE_RUNTIME_DIAGNOSTICS_V1",
            "FEATURE_UNDO_REDO_V1",
        ]
        for marker in required_markers:
            self.assertIn(marker, out)
        self.assertLess(out.index('id="FEATURE_RUNTIME_DIAGNOSTICS_V1"'), out.index('id="FEATURE_HOVERSTAGE"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_STORAGE_V1"'), out.index('id="FEATURE_CANVAS_NOTES_CORE_V1"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_NOTES_CORE_V1"'), out.index('id="FEATURE_CANVAS_DECISION_TRIAGE_V1"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_DECISION_TRIAGE_V1"'), out.index('id="FEATURE_CANVAS_DECISION_GUIDANCE_V1"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_NOTES_CORE_V1"'), out.index('id="FEATURE_CANVAS_DECISION_GUIDANCE_V1"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_DECISION_GUIDANCE_V1"'), out.index('id="FEATURE_CANVAS_NOTES_V1"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_NOTES_V1_CSS"'), out.index('id="FEATURE_CANVAS_DECISION_TRIAGE_V1_CSS"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_DECISION_TRIAGE_V1_CSS"'), out.index('id="FEATURE_CANVAS_NOTE_ACTIONS_V1_CSS"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_NOTES_V1_CSS"'), out.index('id="FEATURE_CANVAS_NOTE_ACTIONS_V1_CSS"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_NOTES_V1"'), out.index('id="FEATURE_CANVAS_DECISION_TRIAGE_UI_V1"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_DECISION_TRIAGE_UI_V1"'), out.index('id="FEATURE_CANVAS_NOTE_ACTIONS_V1"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_NOTES_V1"'), out.index('id="FEATURE_CANVAS_NOTE_ACTIONS_V1"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_NOTES_V1"'), out.index('id="FEATURE_CANVAS_NOTES_WORKFLOW_V1"'))
        self.assertEqual(out.count('id="FEATURE_CANVAS_NOTES_WORKFLOW_V1"'), 1)
        self.assertLess(out.index('id="FEATURE_CANVAS_NOTE_ACTIONS_V1_CSS"'), out.index('id="FEATURE_CANVAS_DECISION_REVIEW_V1_CSS"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_NOTE_ACTIONS_V1_CSS"'), out.index('id="FEATURE_CANVAS_DECISION_SKIP_GATE_V1_CSS"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_DECISION_SKIP_GATE_V1_CSS"'), out.index('id="FEATURE_CANVAS_DECISION_REVIEW_V1_CSS"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_NOTE_ACTIONS_V1"'), out.index('id="FEATURE_CANVAS_DECISION_REVIEW_V1"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_NOTE_ACTIONS_V1"'), out.index('id="FEATURE_CANVAS_DECISION_SKIP_GATE_V1"'))
        self.assertLess(out.index('id="FEATURE_CANVAS_DECISION_SKIP_GATE_V1"'), out.index('id="FEATURE_CANVAS_DECISION_REVIEW_V1"'))
        self.assertEqual(out.count('id="FEATURE_CANVAS_DECISION_GUIDANCE_V1"'), 1)
        self.assertEqual(out.count('id="FEATURE_CANVAS_DECISION_TRIAGE_V1"'), 1)
        self.assertEqual(out.count('id="FEATURE_CANVAS_DECISION_TRIAGE_V1_CSS"'), 1)
        self.assertEqual(out.count('id="FEATURE_CANVAS_DECISION_TRIAGE_UI_V1"'), 1)
        self.assertEqual(out.count('id="FEATURE_CANVAS_NOTE_ACTIONS_V1_CSS"'), 1)
        self.assertEqual(out.count('id="FEATURE_CANVAS_NOTE_ACTIONS_V1"'), 1)
        self.assertEqual(out.count('id="FEATURE_CANVAS_DECISION_SKIP_GATE_V1_CSS"'), 1)
        self.assertEqual(out.count('id="FEATURE_CANVAS_DECISION_SKIP_GATE_V1"'), 1)
        self.assertEqual(out.count('id="FEATURE_CANVAS_DECISION_REVIEW_V1_CSS"'), 1)
        self.assertEqual(out.count('id="FEATURE_CANVAS_DECISION_REVIEW_V1"'), 1)
        self.assertIn("rawRuntimeText: rawRuntimeText", out)
        self.assertIn("rawTaskLines", out)
        self.assertNotIn("var lines=[]", out)
        self.assertNotIn("infinite", out)
        self.assertNotIn("energyFlow", out)
        self.assertIn("var anim = { enabled:false", out)
        self.assertEqual(out.count('id="FEATURE_CONSOLE_MERGE_V3"'), 1)
        self.assertNotIn("<!-- INLINE_PAYLOAD_HERE -->", out)
        self.assertIn("[Kyanbasu][diag]", out)
        self.assertIn("# Generated by Kyanbasu review.", out)
        self.assertIn("kyanbasu-notes.json", out)
        self.assertIn("kyanbasu-workbenches.json", out)
        self.assertIn("kyanbasu-reviewed-commands.sh", out)

    def test_build_runtime_html_preserves_the_ordered_assembly_stages(self):
        base_html = "<html><head></head><body><!-- INLINE_PAYLOAD_HERE --></body></html>"
        payload = json.dumps({"tasks": [], "graph": {}}, separators=(",", ":"))

        out = build_runtime_html(base_html, payload, 0)

        ordered_markers = (
            'id="FEATURE_RUNTIME_DIAGNOSTICS_V1"',
            'id="COMMANDS_CORE_V1"',
            "id='payload_data'",
            'id="FEATURE_HOVERSTAGE"',
            'id="FEATURE_COMMAND_PREFLIGHT_V1"',
            'id="FEATURE_UNDO_REDO_V1"',
        )
        positions = [out.index(marker) for marker in ordered_markers]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(
            out.index('id="FEATURE_RUNTIME_DIAGNOSTICS_V1"'),
            out.index('id="FEATURE_HOVERSTAGE"'),
        )
        self.assertIsNotNone(
            re.search(r"id='payload_data'[^>]*>.*?</script>\s*<script>\(function\(\)", out, re.S)
        )

    def test_build_runtime_html_escapes_mixed_case_script_terminators_in_payload(self):
        base_html = "<html><head></head><body><!-- INLINE_PAYLOAD_HERE --></body></html>"
        payload = json.dumps(
            {"tasks": [{"desc": "x</SCRIPT><script>alert(1)</script>"}], "graph": {}},
            separators=(",", ":"),
        )
        out = build_runtime_html(base_html, payload, 1)

        m = re.search(r"<script id='payload_data' type='application/json'>(.*?)</script>", out, flags=re.S)
        self.assertIsNotNone(m)
        embedded = m.group(1)
        self.assertNotIn("</script", embedded.lower())
        self.assertIn("\\u003c/SCRIPT>", embedded)
        parsed = json.loads(embedded)
        self.assertEqual(parsed["tasks"][0]["desc"], "x</SCRIPT><script>alert(1)</script>")
        self.assertIsNotNone(
            re.search(r"</script>\s*<script>\(function\(\).*?window\.KYANBASU_DEBUG = false", out, re.S)
        )

if __name__ == "__main__":
    unittest.main()
