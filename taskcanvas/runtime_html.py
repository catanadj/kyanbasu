from collections.abc import Callable
from taskcanvas.injectors import (
    _append_remove_mode,
    inject_actionable_beacon,
    inject_command_preflight,
    inject_console_hotkey_patch,
    inject_energy_arrows,
    inject_follow_edges_on_move,
    inject_hover_console_features,
    inject_layout_persistence,
    inject_multiline_add,
    inject_newtask_console_sync,
    inject_runtime_diagnostics,
    inject_staged_deps_color_split,
    inject_undo_redo,
    inject_wire_deps_as_main,
)
from taskcanvas.runtime_support import inject_body, inject_head, load_runtime_asset


def build_runtime_html(
    base_html: str,
    json_text: str,
    tasks_count: int,
    log_fn: Callable[[str], None],
) -> str:
    html = base_html.replace("<!-- INLINE_PAYLOAD_HERE -->", "")
    # Escape '<' so embedded JSON cannot terminate the script tag (e.g. </SCRIPT>).
    safe_json = json_text.replace("<", "\\u003c")
    payload_tag = "<script id='payload_data' type='application/json'>" + safe_json + "</script>\n"
    runner = """<script>(function(){
      try{
        var el = document.getElementById('payload_data');
        var raw = el ? el.textContent : '';
        window.__RAW_LEN__ = raw.length;
        console.log('[payload] raw length (end) =', window.__RAW_LEN__);
        window.DATA = JSON.parse(raw);
        window.DATA_READY = true;
        var tlen = (window.DATA && Array.isArray(window.DATA.tasks)) ? window.DATA.tasks.length : 0;
        console.log('[payload] tasks =', tlen);
        try { document.dispatchEvent(new CustomEvent('twdata')); } catch(_) {}
    try {
      if (!window.__INIT_DONE__ && typeof initFromDATA==='function') {
        window.__INIT_DONE__ = true;
        console.log('[payload] calling initFromDATA directly');
        initFromDATA();
      }
    } catch(e) { console.log('[payload] initFromDATA error', e); }
      } catch(e){
        console.log('[payload] parse error', e);
        window.DATA = {tasks:[],graph:{}}; window.DATA_READY = false;
      }
    })();</script>
    """
    if 'id="COMMANDS_CORE_V1"' not in html:
        html = inject_body(html, load_runtime_asset("commands_core_v1.js.html") + "\n")
    html = inject_body(html, payload_tag + runner)

    head_snippets = [
        ("feature-hover-css", "feature_hover.css.html"),
        ("feature-due-css-v2", "feature_due.css.html"),
    ]
    body_snippets = [
        ("FEATURE_HOVERSTAGE", "feature_hover.js.html"),
        ("FEATURE_DUEBADGE2", "feature_due.js.html"),
        ("dep handle authoritative v6", "dep_handle_authoritative_v6.js.html"),
    ]

    for marker, asset_name in head_snippets:
        if marker not in html:
            html = inject_head(html, load_runtime_asset(asset_name))

    for marker, asset_name in body_snippets:
        if marker not in html:
            html = inject_body(html, load_runtime_asset(asset_name))

    if "__DEP_HANDLE_V6B_DEDUP__" not in html and "dep handle authoritative dedup v6b" not in html:
        html = inject_head(html, load_runtime_asset("dep_handle_authoritative_v6b.css.html"))
        html = inject_body(html, load_runtime_asset("dep_handle_authoritative_v6b.js.html"))

    html = inject_energy_arrows(html)

    if "<!-- INLINE_PAYLOAD_HERE -->" in html:
        log_fn("[TaskCanvas] ERROR: placeholder was not replaced in HTML")
    else:
        log_fn(f"[TaskCanvas] Embedded tasks: {tasks_count}")

    html = inject_wire_deps_as_main(html)
    html = _append_remove_mode(html)
    html = inject_hover_console_features(html)
    html = inject_multiline_add(html)
    html = inject_newtask_console_sync(html)
    html = inject_console_hotkey_patch(html)
    html = inject_staged_deps_color_split(html)
    html = inject_follow_edges_on_move(html)
    html = inject_actionable_beacon(html)
    html = inject_layout_persistence(html)
    html = inject_command_preflight(html)
    html = inject_runtime_diagnostics(html)
    html = inject_undo_redo(html)
    return html
