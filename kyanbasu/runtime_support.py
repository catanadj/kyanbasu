from functools import lru_cache
from pathlib import Path

RUNTIME_ASSETS_DIR = Path(__file__).resolve().parent / "templates" / "runtime_assets"


@lru_cache(maxsize=None)
def load_runtime_asset(name: str) -> str:
    path = RUNTIME_ASSETS_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"Failed to load runtime asset: {path} ({e})") from e


def inject_before_close(html: str, closing_tag: str, snippet: str, *, fallback: str) -> str:
    lower_html = html.lower()
    lower_tag = closing_tag.lower()
    idx = lower_html.rfind(lower_tag)
    if idx == -1:
        if fallback == "prepend":
            return snippet + html
        return html + snippet
    return html[:idx] + snippet + html[idx:]


def inject_head(html: str, snippet: str) -> str:
    return inject_before_close(html, "</head>", snippet, fallback="prepend")


def inject_body(html: str, snippet: str) -> str:
    return inject_before_close(html, "</body>", snippet, fallback="append")


def inject_head_once(html: str, marker: str, snippet: str) -> str:
    if marker in html:
        return html
    return inject_head(html, snippet)


def inject_body_once(html: str, marker: str, snippet: str) -> str:
    if marker in html:
        return html
    return inject_body(html, snippet)
