import re
import sys
from pathlib import Path
from typing import Callable

from taskcanvas.runtime_support import (
    inject_body,
    inject_body_once,
    inject_head,
    inject_head_once,
    load_runtime_asset,
)

ENERGY_ARROW_CSS = load_runtime_asset("injector_energy_arrows.css.html")


ENERGY_ARROW_JS = load_runtime_asset("injector_energy_arrows.js.html")


CSS_WIRE_DEPS_AS_MAIN = load_runtime_asset("injector_wire_deps_as_main.css.html")


JS_WIRE_DEPS_AS_MAIN = load_runtime_asset("injector_wire_deps_as_main.js.html")


REMOVE_MODE_JS = load_runtime_asset("injector_remove_mode_v61.js.txt")


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
        return inject_body(doc, snippet)

    snip_obs = load_runtime_asset("injector_hover_stage_observer.js.html")
    snip_shortify = load_runtime_asset("injector_shortify_render.js.html")
    snip_merge = load_runtime_asset("injector_console_merge_v3.js.html")
    snip_modify = load_runtime_asset("injector_modify_stage_to_console.js.txt")

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
    js = load_runtime_asset("injector_multiline_add.js.html")
    return inject_body_once(html, JS_ID, js + "\n")


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
    js = load_runtime_asset("injector_new_task_console_sync_v2.js.html")
    return inject_body_once(html, JS_ID, js + "\n")


def inject_console_hotkey_patch(html: str) -> str:
    JS_ID = "FEATURE_CONSOLE_HOTKEY_PATCH_V4"
    js = load_runtime_asset("injector_console_hotkey_patch_v4.js.html")
    return inject_body_once(html, JS_ID, js + "\n")


def inject_staged_deps_color_split(html: str) -> str:
    css = load_runtime_asset("injector_staged_line_anim.css.html")
    js = load_runtime_asset("injector_staged_line_anim.js.html")

    html = inject_head_once(html, 'id="PATCH_STAGED_LINE_ANIM_V1"', css + "\n")
    html = inject_body_once(html, 'id="PATCH_STAGED_LINE_ANIM_JS_V1"', js + "\n")
    return html


def inject_follow_edges_on_move(html: str) -> str:
    js = load_runtime_asset("injector_follow_edges_on_move_v1.js.html")
    return inject_body_once(html, 'id="PATCH_FOLLOW_EDGES_ON_MOVE_V1"', js + "\n")


def inject_actionable_beacon(html: str) -> str:
    css = load_runtime_asset("injector_actionable_beacon.css.html")
    js = load_runtime_asset("injector_actionable_beacon.js.html")

    html = inject_head_once(html, 'id="FEATURE_ACTIONABLE_BEACON_V7B_CSS"', css + "\n")
    html = inject_body_once(html, 'id="FEATURE_ACTIONABLE_BEACON_V7B_JS"', js + "\n")
    return html


def inject_layout_persistence(html: str) -> str:
    js = load_runtime_asset("injector_layout_persist_v1.js.html")
    return inject_body_once(html, 'id="FEATURE_LAYOUT_PERSIST_V1"', js + "\n")


def inject_undo_redo(html: str) -> str:
    js = load_runtime_asset("injector_undo_redo_v1.js.html")
    return inject_body_once(html, 'id="FEATURE_UNDO_REDO_V1"', js + "\n")


def _append_remove_mode(html):
    """Inject the working JavaScript directly into the HTML"""
    try:
        if not isinstance(html, str):
            return html

        # Check if already injected
        if '__FIXPACK_V61__' in html:
            return html

        return inject_body(
            html,
            '\n<script id="__FIXPACK_V61__">\n' + REMOVE_MODE_JS + '\n</script>\n',
        )

    except Exception as e:
        # Log error but don't break the build
        print(f"Warning: Failed to inject working JS for remove mode: {e}")
        return html


def inject_wire_deps_as_main(html: str) -> str:
    html = inject_head_once(html, "__ONLY_DEPS_CONSOLE_CSS__", CSS_WIRE_DEPS_AS_MAIN + "\n")
    html = inject_body_once(html, "__ONLY_DEPS_CONSOLE_JS__", JS_WIRE_DEPS_AS_MAIN + "\n")
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
        return inject_head(html, css + "\n")
    except Exception as e:
        if log_fn:
            log_fn(f"[TaskCanvas] custom bg inject failed: {e}")
        return html


def inject_energy_arrows(html: str) -> str:
    html = inject_head_once(html, "__ENERGY_ARROW_CSS__", ENERGY_ARROW_CSS + "\n")
    html = inject_body_once(html, "__ENERGY_ARROW_JS__", ENERGY_ARROW_JS + "\n")
    return html


def inject_command_preflight(html: str) -> str:
    """
    Final buildCommands guardrail:
      - de-duplicates exact duplicate command lines
      - prevents conflicting per-task done/delete/modify mixes
      - merges multiple modify commands for the same task into one line
      - shell-quotes generated task command args to avoid shell injection/splitting
    """
    js = load_runtime_asset("injector_command_preflight_v1.js.html")
    return inject_body_once(html, 'id="FEATURE_COMMAND_PREFLIGHT_V1"', js + "\n")


def inject_runtime_diagnostics(html: str) -> str:
    """
    Lightweight browser diagnostics:
      - captures global error / unhandledrejection events
      - keeps a bounded in-memory ring buffer
      - exposes snapshot via window.TaskCanvasDiagnostics()
    """
    js = load_runtime_asset("injector_runtime_diagnostics_v1.js.html")
    return inject_body_once(html, 'id="FEATURE_RUNTIME_DIAGNOSTICS_V1"', js + "\n")
