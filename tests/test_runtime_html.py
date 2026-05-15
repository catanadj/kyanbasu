import json
import re
import unittest

from taskcanvas.runtime_html import build_runtime_html


class TestRuntimeHtml(unittest.TestCase):
    def test_build_runtime_html_injects_required_markers(self):
        base_html = "<html><head></head><body><!-- INLINE_PAYLOAD_HERE --></body></html>"
        payload = json.dumps({"tasks": [], "graph": {}}, separators=(",", ":"))
        logs = []

        out = build_runtime_html(base_html, payload, 0, logs.append)

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
        self.assertIn("rawRuntimeText: rawRuntimeText", out)
        self.assertIn("rawTaskLines", out)
        self.assertNotIn("var lines=[]", out)
        self.assertEqual(out.count('id="FEATURE_CONSOLE_MERGE_V3"'), 1)
        self.assertNotIn("<!-- INLINE_PAYLOAD_HERE -->", out)
        self.assertTrue(any("Embedded tasks: 0" in line for line in logs))

    def test_build_runtime_html_escapes_mixed_case_script_terminators_in_payload(self):
        base_html = "<html><head></head><body><!-- INLINE_PAYLOAD_HERE --></body></html>"
        payload = json.dumps(
            {"tasks": [{"desc": "x</SCRIPT><script>alert(1)</script>"}], "graph": {}},
            separators=(",", ":"),
        )
        out = build_runtime_html(base_html, payload, 1, lambda *_: None)

        m = re.search(r"<script id='payload_data' type='application/json'>(.*?)</script>", out, flags=re.S)
        self.assertIsNotNone(m)
        embedded = m.group(1)
        self.assertNotIn("</script", embedded.lower())
        self.assertIn("\\u003c/SCRIPT>", embedded)
        parsed = json.loads(embedded)
        self.assertEqual(parsed["tasks"][0]["desc"], "x</SCRIPT><script>alert(1)</script>")

if __name__ == "__main__":
    unittest.main()
