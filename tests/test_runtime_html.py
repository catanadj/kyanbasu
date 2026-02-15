import json
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
            "__ENERGY_ARROW_CSS__",
            "__ONLY_DEPS_CONSOLE_CSS__",
            "__FIXPACK_V61__",
            "FEATURE_ACTIONABLE_BEACON_V7B_JS",
            "FEATURE_LAYOUT_PERSIST_V1",
            "FEATURE_COMMAND_PREFLIGHT_V1",
        ]
        for marker in required_markers:
            self.assertIn(marker, out)
        self.assertNotIn("<!-- INLINE_PAYLOAD_HERE -->", out)
        self.assertTrue(any("Embedded tasks: 0" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
