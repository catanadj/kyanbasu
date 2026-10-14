from dataclasses import dataclass
from typing import Callable, TypeAlias

from kyanbasu.injectors import (
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
from kyanbasu.runtime_support import inject_body, inject_head, load_runtime_asset


@dataclass(frozen=True)
class _AssetStep:
    target: str
    marker: str
    asset_name: str


@dataclass(frozen=True)
class _PayloadStep:
    pass


@dataclass(frozen=True)
class _DiagnosticsStep:
    pass


@dataclass(frozen=True)
class _InjectorStep:
    injector: Callable[[str], str]


_RuntimeStep: TypeAlias = _AssetStep | _PayloadStep | _DiagnosticsStep | _InjectorStep


_RUNTIME_PIPELINE: tuple[_RuntimeStep, ...] = (
    _DiagnosticsStep(),
    _AssetStep("body", "COMMANDS_CORE_V1", "commands_core_v1.js.html"),
    _AssetStep("body", "FEATURE_DEDUPE_FOCUS_V1", "dedupe_focus_v1.js.html"),
    _AssetStep("body", "FEATURE_PROJECT_ADD_TAG_V4", "project_add_tag_v4.js.html"),
    _PayloadStep(),
    _AssetStep("head", "feature-hover-css", "feature_hover.css.html"),
    _AssetStep("head", "feature-due-css-v2", "feature_due.css.html"),
    _AssetStep("head", "PROJECT_PICKER_V2_CSS", "project_picker_v2.css.html"),
    _AssetStep("head", "feature-dedupe-focus-v1-css", "dedupe_focus_v1.css.html"),
    _AssetStep("head", "feature-project-addtag-v4-css", "project_add_tag_v4.css.html"),
    _AssetStep("head", "FEATURE_REVIEW_CHANGES_V1_CSS", "review_changes_v1.css.html"),
    _AssetStep("head", "FEATURE_CANVAS_NAVIGATOR_V1_CSS", "canvas_navigator_v1.css.html"),
    _AssetStep("head", "FEATURE_CANVAS_WORKBENCHES_V1_CSS", "canvas_workbenches_v1.css.html"),
    _AssetStep("head", "FEATURE_CANVAS_NOTES_V1_CSS", "canvas_notes_v1.css.html"),
    _AssetStep("head", "FEATURE_CANVAS_DECISION_TRIAGE_V1_CSS", "canvas_decision_triage_v1.css.html"),
    _AssetStep("head", "FEATURE_CANVAS_NOTE_ACTIONS_V1_CSS", "canvas_note_actions_v1.css.html"),
    _AssetStep("head", "FEATURE_CANVAS_DECISION_SKIP_GATE_V1_CSS", "canvas_decision_skip_gate_v1.css.html"),
    _AssetStep("head", "FEATURE_CANVAS_DECISION_REVIEW_V1_CSS", "canvas_decision_review_v1.css.html"),
    _AssetStep("head", "FEATURE_CONSOLE_EDITOR_V1_CSS", "console_editor_v1.css.html"),
    _AssetStep("body", "FEATURE_HOVERSTAGE", "feature_hover.js.html"),
    _AssetStep("body", "FEATURE_DUEBADGE2", "feature_due.js.html"),
    _AssetStep("body", "FEATURE_DEPENDENCY_INTERACTIONS_V1", "dependency_interactions_v1.js.html"),
    _AssetStep("body", "FEATURE_DEPENDENCY_EDGES_V1", "dependency_edges_v1.js.html"),
    _AssetStep("body", "dep handle authoritative v6", "dep_handle_authoritative_v6.js.html"),
    _AssetStep("body", "FEATURE_QUICKFIX_ADD_RENDER_V1", "quickfix_add_render_v1.js.html"),
    _AssetStep("body", "PROJECT_PICKER_V2_JS", "project_picker_v2.js.html"),
    _AssetStep("body", "FEATURE_TOAST_UTIL_V1", "toast_util_v1.js.html"),
    _AssetStep("body", "FEATURE_CONSOLE_LINE_ENFORCER_V3", "console_line_enforcer_v3.js.html"),
    _AssetStep("body", "FEATURE_COPY_FULL_OVERRIDE_V1", "copy_full_override_v1.js.html"),
    _AssetStep("body", "FEATURE_SINGLE_CONSOLE_AUGMENT_V1", "single_console_augment_v1.js.html"),
    _AssetStep("body", "__FEATURE_REVIEW_CHANGES_V1__", "review_changes_v1.js.html"),
    _AssetStep("body", "FEATURE_CANVAS_STORAGE_V1", "canvas_storage_v1.js.html"),
    _AssetStep("body", "__FEATURE_CANVAS_NAVIGATOR_V1__", "canvas_navigator_v1.js.html"),
    _AssetStep("body", "FEATURE_CANVAS_NOTES_CORE_V1", "canvas_notes_core_v1.js.html"),
    _AssetStep("body", '<script id="FEATURE_CANVAS_DECISION_TRIAGE_V1"', "canvas_decision_triage_v1.js.html"),
    _AssetStep("body", "FEATURE_CANVAS_DECISION_GUIDANCE_V1", "canvas_decision_guidance_v1.js.html"),
    _AssetStep("body", "__FEATURE_CANVAS_NOTES_V1__", "canvas_notes_v1.js.html"),
    _AssetStep("body", "FEATURE_CANVAS_NOTES_WORKFLOW_V1", "canvas_notes_workflow_v1.js.html"),
    _AssetStep("body", "FEATURE_CANVAS_DECISION_TRIAGE_UI_V1", "canvas_decision_triage_ui_v1.js.html"),
    _AssetStep("body", '<script id="FEATURE_CANVAS_NOTE_ACTIONS_V1"', "canvas_note_actions_v1.js.html"),
    _AssetStep("body", '<script id="FEATURE_CANVAS_DECISION_SKIP_GATE_V1"', "canvas_decision_skip_gate_v1.js.html"),
    _AssetStep("body", '<script id="FEATURE_CANVAS_DECISION_REVIEW_V1"', "canvas_decision_review_v1.js.html"),
    _AssetStep("body", "__CANVAS_WORKBENCHES_V1__", "canvas_workbenches_v1.js.html"),
    _AssetStep("body", "__FEATURE_CONSOLE_EDITOR_V1__", "console_editor_v1.js.html"),
    _AssetStep("head", "__DEP_HANDLE_V6B_DEDUP__", "dep_handle_authoritative_v6b.css.html"),
    _AssetStep("body", "dep handle authoritative dedup v6b", "dep_handle_authoritative_v6b.js.html"),
    _InjectorStep(inject_energy_arrows),
    _InjectorStep(inject_wire_deps_as_main),
    _InjectorStep(_append_remove_mode),
    _InjectorStep(inject_hover_console_features),
    _InjectorStep(inject_multiline_add),
    _InjectorStep(inject_newtask_console_sync),
    _InjectorStep(inject_console_hotkey_patch),
    _InjectorStep(inject_staged_deps_color_split),
    _InjectorStep(inject_follow_edges_on_move),
    _InjectorStep(inject_actionable_beacon),
    _InjectorStep(inject_layout_persistence),
    _InjectorStep(inject_command_preflight),
    _InjectorStep(inject_undo_redo),
)


def _inject_declared_asset(html: str, target: str, marker: str, asset_name: str) -> str:
    if marker in html:
        return html
    asset = load_runtime_asset(asset_name)
    return inject_head(html, asset) if target == "head" else inject_body(html, asset)


def _assemble_runtime_features(html: str, payload_tag: str, *, debug: bool) -> str:
    """Apply runtime assets and transformations in their declared order."""
    for step in _RUNTIME_PIPELINE:
        if isinstance(step, _DiagnosticsStep):
            html = inject_runtime_diagnostics(html, debug=debug)
        elif isinstance(step, _PayloadStep):
            html = inject_body(html, payload_tag)
        elif isinstance(step, _AssetStep):
            html = _inject_declared_asset(html, step.target, step.marker, step.asset_name)
        else:
            html = step.injector(html)
    return html


def build_runtime_html(
    base_html: str,
    json_text: str,
    tasks_count: int,
    *,
    debug: bool = False,
) -> str:
    html = base_html.replace("<!-- INLINE_PAYLOAD_HERE -->", "")
    # Escape '<' so embedded JSON cannot terminate the script tag (e.g. </SCRIPT>).
    safe_json = json_text.replace("<", "\\u003c")
    payload_tag = "<script id='payload_data' type='application/json'>" + safe_json + "</script>\n"
    runner = """<script>(function(){
      window.KYANBASU_DEBUG = __KYANBASU_DEBUG__;
      try{
        var el = document.getElementById('payload_data');
        if (!el) {
          if (window.KYANBASU_DEBUG) console.warn('[payload] missing payload element');
          return;
        }
        var raw = el.textContent;
        window.__RAW_LEN__ = raw.length;
        if (window.KYANBASU_DEBUG) console.log('[payload] raw length (end) =', window.__RAW_LEN__);
        window.DATA = JSON.parse(raw);
        window.DATA_READY = true;
        var tlen = (window.DATA && Array.isArray(window.DATA.tasks)) ? window.DATA.tasks.length : 0;
        if (window.KYANBASU_DEBUG) console.log('[payload] tasks =', tlen);
        try { document.dispatchEvent(new CustomEvent('twdata')); }
        catch(e) {
          if (window.KYANBASU_DEBUG) console.warn('[payload] twdata dispatch failed', e);
        }
    try {
      if (!window.__INIT_DONE__ && typeof initFromDATA==='function') {
        window.__INIT_DONE__ = true;
        if (window.KYANBASU_DEBUG) console.log('[payload] calling initFromDATA directly');
        initFromDATA();
      }
    } catch(e) { console.error('[payload] initFromDATA error', e); }
      } catch(e){
        console.error('[payload] parse error', e);
        window.DATA = {tasks:[],graph:{}}; window.DATA_READY = false;
      }
    })();</script>
    """
    runner = runner.replace("__KYANBASU_DEBUG__", str(debug).lower())
    return _assemble_runtime_features(html, payload_tag + runner, debug=debug)
