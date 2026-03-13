import unittest

from taskcanvas.runtime_support import inject_body, inject_body_once, inject_head, inject_head_once


class TestRuntimeSupport(unittest.TestCase):
    def test_inject_head_inserts_before_case_insensitive_closing_tag(self):
        html = "<html><HEAD></HEAD><body></body></html>"
        out = inject_head(html, "<style id='x'></style>\n")
        self.assertIn("<style id='x'></style>\n</HEAD>", out)

    def test_inject_body_appends_when_body_tag_missing(self):
        html = "<html><head></head><div>content</div></html>"
        out = inject_body(html, "<script id='x'></script>\n")
        self.assertTrue(out.endswith("<script id='x'></script>\n"))

    def test_inject_head_once_skips_when_marker_exists(self):
        html = "<html><head><style id='x'></style></head><body></body></html>"
        out = inject_head_once(html, "id='x'", "<style id='x'></style>\n")
        self.assertEqual(out, html)

    def test_inject_body_once_skips_when_marker_exists(self):
        html = "<html><head></head><body><script id='x'></script></body></html>"
        out = inject_body_once(html, "id='x'", "<script id='x'></script>\n")
        self.assertEqual(out, html)
