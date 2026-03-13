import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Callable

RUNTIME_ASSETS_DIR = Path(__file__).resolve().parent.parent / "templates" / "runtime_assets"


@lru_cache(maxsize=None)
def _load_runtime_asset(name: str) -> str:
    path = RUNTIME_ASSETS_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"Failed to load runtime asset: {path} ({e})") from e

ENERGY_ARROW_CSS = _load_runtime_asset("injector_energy_arrows.css.html")


ENERGY_ARROW_JS = _load_runtime_asset("injector_energy_arrows.js.html")


CSS_WIRE_DEPS_AS_MAIN = _load_runtime_asset("injector_wire_deps_as_main.css.html")


JS_WIRE_DEPS_AS_MAIN = _load_runtime_asset("injector_wire_deps_as_main.js.html")


REMOVE_MODE_JS = _load_runtime_asset("injector_remove_mode_v61.js.txt")


def inject_hover_console_features(html: str, *, log=True) -> str:
    """
    Injects:
      - Modify injector (short IDs)
      - Toggle-aware Done/Delete observer
      - Shortify-at-render (textarea + deps overlay)
      - Merge wrapper (ensures STAGED_CMDS lines show in console & overlay)
    Prints generator-side logs.
    """
    def logp(*a):
        if log: print(*a, file=sys.stderr)

    def append_before_body(doc: str, snippet: str) -> str:
        low = doc.lower()
        idx = low.rfind("</body>")
        if idx == -1:
            return doc + snippet
        return doc[:idx] + snippet + doc[idx:]
    snip_obs = _load_runtime_asset("injector_hover_stage_observer.js.html")
    snip_shortify = _load_runtime_asset("injector_shortify_render.js.html")
    snip_merge = _load_runtime_asset("injector_console_merge_v3.js.html")
    snip_modify = _load_runtime_asset("injector_modify_stage_to_console.js.txt")

    modify_mark = "/* __PATCH_MODIFY_STAGE_TO_CONSOLE__ */"

    # Robust anchor for: ops.mods = merged;  (allows dot or ["mods"])
    pattern = r"(ops\s*(?:\.\s*|\[\s*['\"]\s*)mods(?:\s*['\"]\s*\])?\s*=\s*merged\s*;\s*)"

    if modify_mark in html:
        logp("[gen] modify injector: already present (marker).")
    else:
        hit_count = [0]

        def _repl(m):
            hit_count[0] += 1
            return m.group(1) + "\n" + snip_modify + "\n"

        new_html = re.sub(pattern, _repl, html)
        if hit_count[0] > 0:
            logp(f"[gen] modify injector: anchored ({hit_count[0]} site(s)).")
            html = new_html
        else:
            # Fallback: append at </body> so it still works if the anchor shifts/minifies away
            html = append_before_body(html, "<script>" + snip_modify + "</script>\n")
            logp("[gen] modify injector: fallback appended at </body>.")

    # Ensure observer present
    if "FEATURE_HOVER_STAGE_OBSERVER_V1" not in html:
        html = append_before_body(html, snip_obs + "\n")
        logp("[gen] observer: appended.")
    else:
        logp("[gen] observer: already present.")

    # Ensure shortify present
    if "FEATURE_SHORTIFY_RENDER_V1" not in html:
        html = append_before_body(html, snip_shortify + "\n")
        logp("[gen] shortify: appended.")
    else:
        logp("[gen] shortify: already present.")

    # Ensure merge wrapper present
    if "FEATURE_CONSOLE_MERGE_V3" not in html:
        html = append_before_body(html, snip_merge + "\n")
        logp("[gen] merge wrapper: appended.")
    else:
        logp("[gen] merge wrapper: already present.")

    return html


def inject_multiline_add(html: str) -> str:
    """
    Multiline task creation:
      - Intercepts per-tag '+' (.tagAddBtn) and FAB (#fabAddNew)
      - Shows textarea; each non-empty line -> one task
      - Generates UUID as 'new-<hex>' (so app emits 'task add …')
      - Generates independent 8-hex short for DnD acceptance
      - Uses app internals to render/place + refresh console
      - Rebinds interactions (twdata + per-node attachers)
    """
    JS_ID = "FEATURE_MULTILINE_ADD_V1"
    js = _load_runtime_asset("injector_multiline_add.js.html")

    if JS_ID not in html:
        html = html.replace("</body>", js + "\n</body>")
    return html


def inject_newtask_console_sync(html: str) -> str:
    """
    Ensures new tasks (uuid 'new-*' or short 'n-<6hex>') render as:
      - 'task add …' normally
      - 'task log …' when hover-done
      - removed when hover-delete
    Also merges +tag / project:/ due: changes into that one line.
    Idempotent via <script id="FEATURE_NEW_TASK_CONSOLE_SYNC_V2">.
    """
    JS_ID = "FEATURE_NEW_TASK_CONSOLE_SYNC_V2"
    js = _load_runtime_asset("injector_new_task_console_sync_v2.js.html")

    if JS_ID not in html:
        html = html.replace("</body>", js + "\n</body>")
    return html


def inject_console_hotkey_patch(html: str) -> str:
    JS_ID = "FEATURE_CONSOLE_HOTKEY_PATCH_V4"
    js = _load_runtime_asset("injector_console_hotkey_patch_v4.js.html")

    if JS_ID not in html:
        html = html.replace("</body>", js + "\n</body>")
    return html


def inject_staged_deps_color_split(html: str) -> str:
    css = _load_runtime_asset("injector_staged_line_anim.css.html")
    js = _load_runtime_asset("injector_staged_line_anim.js.html")

    if 'id="PATCH_STAGED_LINE_ANIM_V1"' not in html:
        html = re.sub(r'</head>', css + '\n</head>', html, count=1, flags=re.I)
    if 'id="PATCH_STAGED_LINE_ANIM_JS_V1"' not in html:
        html = re.sub(r'</body>', js + '\n</body>', html, count=1, flags=re.I)
    return html


def inject_follow_edges_on_move(html: str) -> str:
    js = _load_runtime_asset("injector_follow_edges_on_move_v1.js.html")

    if 'id="PATCH_FOLLOW_EDGES_ON_MOVE_V1"' not in html:
        html = re.sub(r'</body>', js + '\n</body>', html, count=1, flags=re.I)
    return html


def inject_actionable_beacon(html: str) -> str:
    css = _load_runtime_asset("injector_actionable_beacon.css.html")
    js = _load_runtime_asset("injector_actionable_beacon.js.html")

    if 'id="FEATURE_ACTIONABLE_BEACON_V7B_CSS"' not in html:
        html = re.sub(r'</head>', css + '\n</head>', html, count=1, flags=re.I)
    if 'id="FEATURE_ACTIONABLE_BEACON_V7B_JS"' not in html:
        html = re.sub(r'</body>', js + '\n</body>', html, count=1, flags=re.I)
    return html


def inject_layout_persistence(html: str) -> str:
    js = _load_runtime_asset("injector_layout_persist_v1.js.html")

    if 'id="FEATURE_LAYOUT_PERSIST_V1"' in html:
        return html
    if re.search(r"</body\s*>", html, flags=re.I):
        return re.sub(r"</body\s*>", lambda m: js + "\n" + m.group(0), html, count=1, flags=re.I)
    return html + "\n" + js


def inject_undo_redo(html: str) -> str:
    js = _load_runtime_asset("injector_undo_redo_v1.js.html")

    if 'id="FEATURE_UNDO_REDO_V1"' in html:
        return html
    if re.search(r"</body\s*>", html, flags=re.I):
        return re.sub(r"</body\s*>", lambda m: js + "\n" + m.group(0), html, count=1, flags=re.I)
    return html + "\n" + js


def _append_remove_mode(html):
    """Inject the working JavaScript directly into the HTML"""
    try:
        if not isinstance(html, str):
            return html
            
        low = html.lower()
        
        # Check if already injected
        if '__FIXPACK_V61__' in html:
            return html
        
        # Inject before closing body tag if it exists
        if '</body>' in low:
            idx = low.rfind('</body>')
            return (html[:idx] + 
                   '\n<script id="__FIXPACK_V61__">\n' + 
                   REMOVE_MODE_JS + 
                   '\n</script>\n' + 
                   html[idx:])
        else:
            # If no body tag, append at the end
            return html + '\n<script id="__FIXPACK_V61__">\n' + REMOVE_MODE_JS + '\n</script>\n'
            
    except Exception as e:
        # Log error but don't break the build
        print(f"Warning: Failed to inject working JS for remove mode: {e}")
        return html


def inject_wire_deps_as_main(html: str) -> str:
    # CSS into </head>
    if "__ONLY_DEPS_CONSOLE_CSS__" not in html:
        html = (re.sub(r'</head\s*>', lambda m: CSS_WIRE_DEPS_AS_MAIN + '\n' + m.group(0), html, count=1, flags=re.I)
                if re.search(r'</head\s*>', html, flags=re.I) else CSS_WIRE_DEPS_AS_MAIN + html)
    # JS into </body>
    if "__ONLY_DEPS_CONSOLE_JS__" not in html:
        html = (re.sub(r'</body\s*>', lambda m: JS_WIRE_DEPS_AS_MAIN + '\n' + m.group(0), html, count=1, flags=re.I)
                if re.search(r'</body\s*>', html, flags=re.I) else html + '\n' + JS_WIRE_DEPS_AS_MAIN)
    return html


def _find_bg_file(prefer: str | None, base_dir: Path | None = None):
    """Look for a background image either by explicit path or by common names in script dir / CWD."""
    exts = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")
    script_dir = (base_dir or Path(__file__).resolve().parent)
    cwd = Path.cwd()

    candidates = []
    if prefer:
        p = Path(prefer)
        candidates.append(p if p.is_absolute() else (cwd / p))
        candidates.append(script_dir / p.name)
    names = ["taskcanvas-bg", "TaskCanvas.bg", "canvas-bg", "background", "bg"]
    for root in (script_dir, cwd):
        for name in names:
            for ext in exts:
                candidates.append(root / f"{name}{ext}")

    for p in candidates:
        if p.is_file():
            return p
    return None


def inject_custom_background(
    html: str,
    img_path: Path,
    out_html: Path,
    log_fn: Callable[[str], None] | None = None,
    opacity: str | None = None,
) -> str:
    """
    Ensures the background image is next to out_html and injects a <style> overlay.
    Uses a body::before fixed cover layer with adjustable opacity.
    """
    import re, shutil
    try:
        out_dir = out_html.parent
        out_img = out_dir / img_path.name
        if img_path.resolve() != out_img.resolve():
            try:
                out_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(str(img_path), str(out_img))
                if log_fn:
                    log_fn(f"[TaskCanvas] Copied bg → {out_img.name}")
            except Exception as e:
                if log_fn:
                    log_fn(f"[TaskCanvas] Copy bg failed: {e}; will still reference original name.")
        op = opacity if (opacity and opacity.strip()) else "0.18"
        css = f"""
<style id="FEATURE_CUSTOM_BG_V1">
  html,body{{background:var(--bg);}}
  body{{position:relative;}}
  body::before{{
    content:"";
    position:fixed; inset:0;
    background:url('{out_img.name}') center/cover no-repeat fixed;
    opacity:{op};
    pointer-events:none; z-index:0;
  }}
  .app{{position:relative; z-index:1;}}
</style>""".strip()
        if re.search(r'</head\s*>', html, flags=re.I):
            return re.sub(r'</head\s*>', css + '\n</head>', html, count=1, flags=re.I)
        else:
            return css + html
    except Exception as e:
        if log_fn:
            log_fn(f"[TaskCanvas] custom bg inject failed: {e}")
        return html


def inject_energy_arrows(html: str) -> str:
    if "__ENERGY_ARROW_CSS__" not in html:
        html = (
            re.sub(r'</head\s*>', lambda m: ENERGY_ARROW_CSS + '\n' + m.group(0), html, count=1, flags=re.I)
            if re.search(r'</head\s*>', html, flags=re.I)
            else ENERGY_ARROW_CSS + html
        )
    if "__ENERGY_ARROW_JS__" not in html:
        html = (
            re.sub(r'</body\s*>', lambda m: ENERGY_ARROW_JS + '\n' + m.group(0), html, count=1, flags=re.I)
            if re.search(r'</body\s*>', html, flags=re.I)
            else html + '\n' + ENERGY_ARROW_JS
        )
    return html


def inject_command_preflight(html: str) -> str:
    """
    Final buildCommands guardrail:
      - de-duplicates exact duplicate command lines
      - prevents conflicting per-task done/delete/modify mixes
      - merges multiple modify commands for the same task into one line
      - shell-quotes generated task command args to avoid shell injection/splitting
    """
    js = _load_runtime_asset("injector_command_preflight_v1.js.html")

    if 'id="FEATURE_COMMAND_PREFLIGHT_V1"' in html:
        return html
    if re.search(r'</body\s*>', html, flags=re.I):
        return re.sub(r'</body\s*>', lambda m: js + '\n' + m.group(0), html, count=1, flags=re.I)
    return html + '\n' + js


def inject_runtime_diagnostics(html: str) -> str:
    """
    Lightweight browser diagnostics:
      - captures global error / unhandledrejection events
      - keeps a bounded in-memory ring buffer
      - exposes snapshot via window.TaskCanvasDiagnostics()
    """
    js = _load_runtime_asset("injector_runtime_diagnostics_v1.js.html")

    if 'id="FEATURE_RUNTIME_DIAGNOSTICS_V1"' in html:
        return html
    if re.search(r"</body\s*>", html, flags=re.I):
        return re.sub(r"</body\s*>", lambda m: js + "\n" + m.group(0), html, count=1, flags=re.I)
    return html + "\n" + js
