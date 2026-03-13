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

ENERGY_ARROW_CSS = r"""
<style id="__ENERGY_ARROW_CSS__">
  /* Flow animation down the staged edge */
  @keyframes energyFlow {
    from { stroke-dashoffset: 48; }
    to   { stroke-dashoffset: 0;  }
  }

  /* Generic staged edge look (we'll add this class via JS) */
  .staged-energy-edge {
    stroke: #60a5fa;
    stroke-width: 2.25px;
    fill: none;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-dasharray: 6 6;
    animation: energyFlow 900ms linear infinite;
    filter: drop-shadow(0 0 3px rgba(96,165,250,.7));
  }

  /* Optional on-hover emphasis (if your app enables hover on paths) */
  .staged-energy-edge:hover {
    stroke-width: 2.75px;
    filter: drop-shadow(0 0 5px rgba(96,165,250,.9));
  }

  /* Hide old dots inside the staging layer */
  #builderStage circle, #builderStage .energy-dot, #builderStage .pulse-dot {
    display: none !important;
  }
</style>
"""


ENERGY_ARROW_JS = r"""
<script id="__ENERGY_ARROW_JS__">
(function(){
  if (window.__ENERGY_ARROWS__) return; window.__ENERGY_ARROWS__ = true;

  // Apply animation to staged edges and hide dots (no arrowheads)
  function restyleStaging(){
    var svg = document.querySelector('#builderStage svg, svg');
    if (!svg) return;

    // Hide any dots that might have been recreated
    document.querySelectorAll('#builderStage circle, #builderStage .energy-dot, #builderStage .pulse-dot')
      .forEach(function(dot){ dot.style.display = 'none'; });

    // Heuristics: most builds draw staged links as <path> or <line> within #builderStage
    var stagedLines = document.querySelectorAll('#builderStage path, #builderStage line');
    stagedLines.forEach(function(el){
      // Only touch geometric edges (skip hidden/zero-length)
      // Also avoid re-marking same element
      if (!el.__energyArrowsApplied){
        // No arrowhead marker applied
        el.classList.add('staged-energy-edge');
        el.__energyArrowsApplied = true;
      }
    });
  }

  // Slow fallback sweep; primary updates are event-driven via observers/hooks below.
  var t = setInterval(function(){
    if (document.hidden) return;
    restyleStaging();
  }, 2800);

  // Also react to DOM changes inside the staging layer
  try{
    var root = document.getElementById('builderStage') || document.body;
    var mo = new MutationObserver(function(){
      if (document.hidden) return;
      restyleStaging();
    });
    mo.observe(root, {subtree:true, childList:true, attributes:true});
  }catch(_){}

  // First paints
  setTimeout(restyleStaging, 60);
  setTimeout(restyleStaging, 300);
  setTimeout(restyleStaging, 1200);
})();
</script>
"""


CSS_WIRE_DEPS_AS_MAIN = r"""
<!-- injected by generator: wire deps as main -->
<style id="__ONLY_DEPS_CONSOLE_CSS__">
  #consolePanel, .console-panel { display: none !important; visibility: hidden !important; pointer-events: none !important; }
  #depCmdOverlay {
    position: fixed !important;
    right: 80px !important;
    bottom: 20px !important;
    top: auto !important;
    max-width: 50vw; max-height: 44vh;
    z-index: 100000 !important;
  }
  #depCmdOverlay.hidden { display: none !important; }
  #depCmdOverlay .hdr{display:flex;align-items:center;gap:8px;padding:6px 8px;background:#0e1626;border-bottom:1px solid #243247}
  #depCmdOverlay pre{margin:0;padding:10px;white-space:pre;max-height:36vh;overflow:auto;font:12px ui-monospace,monospace}
</style>
"""


JS_WIRE_DEPS_AS_MAIN = r"""
<script id="__ONLY_DEPS_CONSOLE_JS__">
(function(){
  if (window.__ONLY_DEPS_CONSOLE__) return; window.__ONLY_DEPS_CONSOLE__ = true;

  function $(sel, root){ return (root||document).querySelector(sel); }
  function $all(sel, root){ return Array.prototype.slice.call((root||document).querySelectorAll(sel)); }

  // Guard: only allow programmatic console toggles right after pressing the Console button or 'D'
  var ALLOW_TOGGLE_UNTIL = 0;
  function allowToggleBriefly(){
    ALLOW_TOGGLE_UNTIL = Date.now() + 600; // 600ms window
  }
  function toggleAllowed(){
    return Date.now() <= ALLOW_TOGGLE_UNTIL;
  }

  function ensureOverlay(){
    var ol = document.getElementById('depCmdOverlay');
    if (!ol){
      var wrap = document.createElement('div');
      wrap.innerHTML =
        '<div id="depCmdOverlay" class="" style="position:fixed;right:18px;bottom:18px;z-index:100000;max-width:50vw;max-height:44vh;background:#0b1220;color:#e6eef9;border:1px solid #243247;border-radius:10px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,.35)">' +
        '  <div class="hdr" style="display:flex;align-items:center;gap:8px;padding:6px 8px;background:#0e1626;border-bottom:1px solid #243247">' +
        '    <b style="font:12px ui-monospace,monospace">Console</b><div style="flex:1"></div>' +
        '    <button id="depCmdHideBtn" style="all:unset;border:1px solid #2a3a54;padding:2px 6px;border-radius:6px;cursor:pointer;color:#9cc2ff">Hide</button>' +
        '  </div>' +
        '  <pre id="depCmdPre" style="margin:0;padding:10px;white-space:pre;max-height:36vh;overflow:auto;font:12px ui-monospace,monospace"></pre>' +
        '</div>';
      document.body.appendChild(wrap.firstChild);
      ol = document.getElementById('depCmdOverlay');
      var hideBtn = document.getElementById('depCmdHideBtn');
      if (hideBtn) hideBtn.addEventListener('click', function(e){ e.preventDefault(); e.stopPropagation(); hideOverlay(); }, true);
    }else{
      ol.classList.remove('hidden');
      ol.style.display = 'block';
    }
    return ol;
  }
  function overlayVisible(){
    var ol = $('#depCmdOverlay'); if (!ol) return false;
    return !(ol.classList.contains('hidden') || ol.style.display === 'none');
  }
  function showOverlay(){ var ol = ensureOverlay(); ol.classList.remove('hidden'); ol.style.display = 'block'; refreshOverlayText(); }
  function hideOverlay(){ var ol = ensureOverlay(); ol.classList.add('hidden'); ol.style.display = 'none'; }
  function toggleOverlay(){ if (overlayVisible()) hideOverlay(); else showOverlay(); }

  // Strict Console button matching: only specific selectors
  var CONSOLE_BTN_SELECTOR = '#consoleBtn, [data-action="toggle-console"], .toggle-console, .console-btn, button[aria-label="Console"]';

  // Intercept ONLY clicks on actual Console buttons (via closest on strict selector)
  document.addEventListener('click', function(e){
    var btn = (e.target && e.target.closest) ? e.target.closest(CONSOLE_BTN_SELECTOR) : null;
    if (!btn) return;
    try{ e.preventDefault(); e.stopImmediatePropagation(); e.stopPropagation(); }catch(_){}
    allowToggleBriefly();
    toggleOverlay();
  }, true); // capture

  // Redirect common global toggles, but obey the guard
  function overrideIfFunc(name){
    try{
      var f = window[name];
      if (typeof f === 'function'){
        window[name] = function(){
          if (!toggleAllowed()) return; // ignore stray programmatic toggles
          try{ return toggleOverlay(); }catch(_){}
        };
      }
    }catch(_){}
  }
  ['toggleConsole','toggleMainConsole','toggleCommands','showConsolePanel','hideConsolePanel'].forEach(overrideIfFunc);

  // 'D' key toggles deps overlay and opens guard window
  document.addEventListener('keydown', function(e){
    var k = (e.key||'').toLowerCase();
    if (k==='d' && !e.metaKey && !e.ctrlKey && !e.altKey){
      e.preventDefault(); e.stopPropagation();
      allowToggleBriefly();
      toggleOverlay();
    }
  }, true);

  // Keep overlay text in sync with buildCommands()
  function getAllCommands(){
    var txt = '';
    try{ if (typeof window.buildCommands==='function') txt = String(window.buildCommands()||''); }catch(_){}
    return shortenUUIDs(txt); // change this to return "txt" if you want the full UUID of the tasks in the commands.
  }
  function setText(el, text){
    if (!el) return;
    if ('value' in el) el.value = text;
    else if ('textContent' in el) el.textContent = text;
    else el.innerText = text;
  }
  function refreshOverlayText(){
    var pre = document.getElementById('depCmdPre');
    if (!pre) return;
    var txt = getAllCommands();
    if (txt!=null) setText(pre, txt);
  }
  (function hookUpdateConsole(){
    var _upd = window.updateConsole;
    window.updateConsole = function(){
      try{ if (typeof _upd==='function') _upd.apply(this, arguments); }catch(_){}
      try{ refreshOverlayText(); }catch(_){}
    };
  })();

  // Initial state
  ensureOverlay();
  showOverlay();
  setTimeout(refreshOverlayText, 60);
  setTimeout(refreshOverlayText, 300);
  setTimeout(refreshOverlayText, 1200);
})();
</script>
"""


REMOVE_MODE_JS = """(() => {
  const $  = (s,r=document)=>r.querySelector(s);
  const $$ = (s,r=document)=>Array.from(r.querySelectorAll(s));
  const getCB = ()=> $('#removeMode') || $('#remove-mode') || $('input[type="checkbox"][name="removeMode"]') || $('#depRemoveMode');
  const isOn  = ()=> !!(window.__forceRemoveMode || (getCB() && getCB().checked));

  // Clickable strokes only in Remove mode
  if (!document.getElementById('depRemovePE')){
    const s=document.createElement('style'); s.id='depRemovePE';
    s.textContent = `
      body.dep-remove-mode #builderLinks, body.dep-remove-mode #builderLinks * { pointer-events:auto !important; }
      body.dep-remove-mode #builderLinks path, body.dep-remove-mode #builderLinks line { pointer-events:stroke !important; }
      body.dep-remove-mode svg path:hover, body.dep-remove-mode svg line:hover { 
        filter: drop-shadow(0 0 6px rgba(181,58,58,.9)); 
        stroke-width: 3.8px; 
        cursor: pointer;
        stroke: #ff4444 !important;
        opacity: 0.9;
        transition: all 0.2s ease;
      }
      /* Also highlight removable lines even outside remove mode for better UX */
      svg path[data-from][data-to]:hover, svg line[data-from][data-to]:hover {
        stroke: #ff4444 !important;
        stroke-width: 2.5px;
        cursor: pointer;
        opacity: 0.8;
        filter: drop-shadow(0 0 4px rgba(255,68,68,0.6));
        transition: all 0.2s ease;
      }
    `;
    document.head.appendChild(s);
  }
  if (isOn()) document.body.classList.add('dep-remove-mode');

  // Command Console extender: append extra lines to buildCommands()
  if (!window.__depExtraCmds) window.__depExtraCmds = [];
  if (!window.__depWrapBuild && typeof window.buildCommands === 'function'){
    window.__depWrapBuild = true;
    const origBuild = window.buildCommands;
    window.buildCommands = function(){
      const base  = origBuild.call(this) || '';
      const extra = (window.__depExtraCmds||[]).join('\\n');
      return extra ? (base ? base+'\\n'+extra : extra) : base;
    };
  }

  // Keep removed SOLID edges hidden on redraw
  if (!window.__REMOVED_DEPS) window.__REMOVED_DEPS = Object.create(null);
  const markHidden = (f,t)=> (window.__REMOVED_DEPS[f+'>'+t]=true);
  ['gatherEdgesShort','gatherEdgesShorts'].forEach(name=>{
    const orig = window[name];
    if (typeof orig==='function' && !orig.__wrapped){
      const wrap=function(){
        const arr = orig.apply(this, arguments) || [];
        return arr.filter(e => !window.__REMOVED_DEPS[e.from+'>'+e.to]);
      };
      wrap.__wrapped=true; window[name]=wrap;
    }
  });

  // Helpers
  function uuidForShort(short){
    try{
      const el = window.nodeElByShort ? window.nodeElByShort(short) : null;
      const uuid = el && el.getAttribute && el.getAttribute('data-uuid');
      return uuid || short;
    }catch{ return short; }
  }

  // Core mutation for SOLID edges
  window.__removeEverywhere = function(from,to){
    let changed=false;
    try{
      const SA=window.stagedAdd||[];
      for (let i=SA.length-1;i>=0;i--){ const e=SA[i]; if(e&&String(e.from)===String(from)&&String(e.to)===String(to)){ SA.splice(i,1); changed=true; } }
    }catch{}
    try{
      const EX=window.EXIST_EDGES||[];
      for (let i=EX.length-1;i>=0;i--){ const e=EX[i]; if(e&&String(e.from)===String(from)&&String(e.to)===String(to)){ EX.splice(i,1); changed=true; } }
    }catch{}
    try{
      const T=window.TASK_BY_SHORT||{};
      const deps=T[from] && (T[from].depends||T[from].dependencies);
      if (Array.isArray(deps)){
        const idx=deps.findIndex(x=>String(x)===String(to)); if (idx>=0){ deps.splice(idx,1); changed=true; }
      } else if (typeof deps==='string'){
        const out = deps.split(/[\\s,]+/).filter(Boolean).filter(x=>String(x)!==String(to)).join(',');
        if (T[from]){ if (T[from].depends!=null) T[from].depends=out; if (T[from].dependencies!=null) T[from].dependencies=out; changed=true; }
      }
    }catch{}
    try{
      $$('#builderLinks path,#builderLinks line').forEach(n=>{
        if (n.getAttribute('data-from')===from && n.getAttribute('data-to')===to) n.remove();
      });
    }catch{}
    markHidden(from,to);
    try{ window.drawLinks && window.drawLinks(); }catch{}
    try{ window.refreshDepHandleLetters && window.refreshDepHandleLetters(); }catch{}
    return changed;
  };

  // Make previews deterministic: tag overlay paths with data-from/to + data-staged-index
  (function wrapRenderStagedOverlay(){
    const fn = window.renderStagedOverlay;
    if (typeof fn !== 'function' || fn.__wrappedV61) return;
    const wrap = function(){
      const out = fn.apply(this, arguments);
      try{
        const over = document.getElementById('depStagedOverlay');
        const SA = window.stagedAdd || [];
        if (over){
          const paths = Array.from(over.querySelectorAll('path.staged-energy-edge, line.staged-energy-edge'));
          for (let i=0; i<paths.length; i++){
            const p = paths[i], e = SA[i];
            if (!p) continue;
            if (e && e.from && e.to){
              p.setAttribute('data-from', e.from);
              p.setAttribute('data-to', e.to);
            }
            p.setAttribute('data-staged-index', i);
          }
        }
      }catch{}
      return out;
    };
    wrap.__wrappedV61 = true;
    window.renderStagedOverlay = wrap;
  })();

  // Click wiring (capture) with container-based detection
  const links = document.getElementById('builderLinks') || document.querySelector('svg');
  if (!links || links.__rmV61) { console.log('[FixPack V6.1] already bound'); return; }
  links.__rmV61 = true;

  function isPreviewNode(node){
    // A preview is anything inside #depStagedOverlay (group-based), regardless of classes
    try { return !!(node && node.closest && node.closest('#depStagedOverlay')); } catch { return false; }
  }

  function removePreviewNode(node){
    // Prefer data-from/to if present (after wrapper)
    const from = node.getAttribute && node.getAttribute('data-from');
    const to   = node.getAttribute && node.getAttribute('data-to');
    if (from && to){
      try{
        const SA = window.stagedAdd || [];
        for (let i=SA.length-1;i>=0;i--){
          const e = SA[i]; if (e && e.from===from && e.to===to){ SA.splice(i,1); break; }
        }
      }catch{}
    } else {
      // Fallback by index alignment
      try{
        const over = document.getElementById('depStagedOverlay');
        if (over){
          const paths = Array.from(over.querySelectorAll('path.staged-energy-edge, line.staged-energy-edge'));
          const idx = paths.indexOf(node);
          if (idx >= 0 && Array.isArray(window.stagedAdd) && idx < window.stagedAdd.length){
            window.stagedAdd.splice(idx,1);
          }
        }
      }catch{}
    }
    try{ node.remove(); }catch{}
    try{ window.renderStagedOverlay && window.renderStagedOverlay(); }catch{}
    try{ window.drawLinks && window.drawLinks(); }catch{}
    try{ window.updateConsole && window.updateConsole(); }catch{}
    console.log('[dep-preview-cancel] removed');
  }

  links.addEventListener('click', (e)=>{
    if (!(window.__forceRemoveMode || isOn())) return;
    const t = e.target;
    if (!(t && (t.tagName==='path' || t.tagName==='line'))) return;
    e.preventDefault(); e.stopPropagation();

    const fromShort = t.getAttribute('data-from');
    const toShort   = t.getAttribute('data-to');

    if (isPreviewNode(t)){
      // PREVIEW (staging) edge – always cancel it
      return removePreviewNode(t);
    }

    // SOLID (staged) edge – even if it has 'staged-energy-edge' class
    if (fromShort && toShort){
      window.__removeEverywhere(fromShort,toShort);

      const fromUUID = uuidForShort(fromShort);
      const toUUID   = uuidForShort(toShort);
      const cmd = "task "+fromUUID+" modify depends:-"+toUUID;

      window.__depExtraCmds.push(cmd);
      try{ window.updateConsole && window.updateConsole(); }catch{}
      console.log('[dep-remove]', cmd);
      if (typeof toastMsg==='function') toastMsg('Removed: '+fromShort+' !depends '+toShort);
      return;
    }
  }, true);

  // Re-tag previews when overlay mutates (safety net)
  try{
    const mo = new MutationObserver(() => {
      const over = document.getElementById('depStagedOverlay');
      const SA = window.stagedAdd || [];
      if (!over) return;
      const paths = Array.from(over.querySelectorAll('path.staged-energy-edge, line.staged-energy-edge'));
      for (let i=0; i<paths.length; i++){
        const p = paths[i], e = SA[i];
        if (!p) continue;
        if (e && e.from && e.to){
          p.setAttribute('data-from', e.from);
          p.setAttribute('data-to', e.to);
        }
        p.setAttribute('data-staged-index', i);
      }
    });
    mo.observe(document.body, {childList:true, subtree:true});
  }catch{}
})();
"""


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
    CSS = r"""
<style id="FEATURE_ACTIONABLE_BEACON_V7B_CSS">
@keyframes beaconPulseV7B {
  0%   { transform: scale(0.9);  opacity: .35; filter: drop-shadow(0 0 0px rgba(34,211,238,.00)); }
  45%  { transform: scale(1.05); opacity: .95; filter: drop-shadow(0 0 6px rgba(34,211,238,.50)); }
  100% { transform: scale(0.9);  opacity: .35; filter: drop-shadow(0 0 0px rgba(34,211,238,.00)); }
}
/* 6px beacon in top-right */
.node .act-beacon-wrap {
  position: absolute;
  top: 6px; right: 6px;
  width: 6px; height: 6px;
  pointer-events: none; z-index: 2;
}
.node .act-beacon {
  width: 100%; height: 100%;
  border-radius: 999px;
  /* lively cyan/teal core with soft falloff */
  background: radial-gradient(closest-side,
              rgba(224, 255, 255, .95),
              rgba(34, 211, 238, .70) 55%,
              rgba(34, 211, 238, 0) 100%);
  animation: beaconPulseV7B 2.2s ease-in-out infinite;
  will-change: transform, opacity, filter;
}
/* ambient halo (very soft) */
.node .act-beacon::after {
  content: "";
  position: absolute; inset: -3px;
  border-radius: 999px;
  background: radial-gradient(closest-side,
              rgba(34,211,238,.22),
              rgba(34,211,238,0) 70%);
}
@media (prefers-reduced-motion: reduce) {
  .node .act-beacon { animation: none; }
}
</style>
""".strip()

    JS = r"""
<script id="FEATURE_ACTIONABLE_BEACON_V7B_JS">
(function(){
  if (window.__ACT_BEACON_V7B__) return; window.__ACT_BEACON_V7B__ = true;

  function collectEdgeSets(){
    var havePrereq = Object.create(null), inChain = Object.create(null);
    function add(e){ if(!e) return; var f=e.from, t=e.to; if(f){havePrereq[f]=1; inChain[f]=1;} if(t){inChain[t]=1;} }
    try{ (window.EXIST_EDGES||[]).forEach(add); }catch(_){}
    try{ (window.stagedAdd  ||[]).forEach(add); }catch(_){}
    return {havePrereq,inChain};
  }
  function isCompletedOrDeleted(n){
    return !!(n && (n.classList.contains('completed') ||
                    n.classList.contains('stagedDel') ||
                    n.getAttribute('data-deleted')==='1'));
  }
  function ensureBeacon(node){
    var wrap = node.querySelector(':scope > .act-beacon-wrap');
    if (!wrap){
      wrap = document.createElement('div');
      wrap.className = 'act-beacon-wrap';
      var dot = document.createElement('div');
      dot.className = 'act-beacon';
      wrap.appendChild(dot);
      try{ var pos = getComputedStyle(node).position; if (pos==='static') node.style.position='relative'; }catch(_){}
      node.appendChild(wrap);
    }
  }
  function removeBeacon(node){
    var wrap = node.querySelector(':scope > .act-beacon-wrap');
    if (wrap) wrap.remove();
  }

  function recompute(){
    var {havePrereq,inChain} = collectEdgeSets();
    (document.querySelectorAll('#builderStage .node')||[]).forEach(function(nd){
      var short = nd.getAttribute('data-short')||'';
      var uuid  = nd.getAttribute('data-uuid') ||'';
      if (isCompletedOrDeleted(nd)){ removeBeacon(nd); return; }
      var hasReq   = !!(havePrereq[short] || havePrereq[uuid]);
      var involved = !!(inChain[short]    || inChain[uuid]);
      if (!hasReq && involved) ensureBeacon(nd); else removeBeacon(nd);
    });
  }
  function schedule(){ if (schedule._raf) cancelAnimationFrame(schedule._raf); schedule._raf = requestAnimationFrame(recompute); }

  ['drawLinks','renderStagedOverlay','renderDepsOverlay','__depsOverlayRender','renderList','updateConsole']
    .forEach(function(n){ var fn=window[n]; if(typeof fn==='function' && !fn.__actBeaconV7B){ var o=fn; window[n]=function(){var r=o.apply(this,arguments); schedule(); return r;}; window[n].__actBeaconV7B=true; }});

  try{ var root = document.getElementById('builderStage') || document.body;
       new MutationObserver(function(){ schedule(); })
       .observe(root, {subtree:true, childList:true, attributes:true, attributeFilter:['class','style']}); }catch(_){}
  document.addEventListener('twdata', schedule);

  schedule(); setTimeout(schedule,140); setTimeout(schedule,420);
})();
</script>
""".strip()

    if 'id="FEATURE_ACTIONABLE_BEACON_V7B_CSS"' not in html:
        html = re.sub(r'</head>', CSS + '\n</head>', html, count=1, flags=re.I)
    if 'id="FEATURE_ACTIONABLE_BEACON_V7B_JS"' not in html:
        html = re.sub(r'</body>', JS + '\n</body>', html, count=1, flags=re.I)
    return html


def inject_layout_persistence(html: str) -> str:
    js = _load_runtime_asset("injector_layout_persist_v1.js.html")

    if 'id="FEATURE_LAYOUT_PERSIST_V1"' in html:
        return html
    if re.search(r"</body\s*>", html, flags=re.I):
        return re.sub(r"</body\s*>", lambda m: js + "\n" + m.group(0), html, count=1, flags=re.I)
    return html + "\n" + js


def inject_undo_redo(html: str) -> str:
    js = r"""
<script id="FEATURE_UNDO_REDO_V1">
(function(){
  if (window.__UNDO_REDO_V1__) return; window.__UNDO_REDO_V1__ = true;

  var MAX_HISTORY = 80;
  var history = [];
  var index = -1;
  var suppress = false;
  var ready = false;
  var saveTimer = 0;

  function clone(v){
    try{ return JSON.parse(JSON.stringify(v)); }catch(_){ return v; }
  }
  function toInt(v, d){
    var n = parseInt(v, 10);
    return isFinite(n) ? n : d;
  }
  function escAttr(v){
    return String(v || "").replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  }
  function firstTag(t){
    return (t && Array.isArray(t.tags) && t.tags.length) ? t.tags[0] : "(no tag)";
  }
  function notify(msg){
    try{
      if (typeof window.showToast === "function") window.showToast(msg);
      else console.log("[undo]", msg);
    }catch(_){}
  }
  function isEditableTarget(t){
    if (!t) return false;
    var tag = String(t.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return true;
    if (t.isContentEditable) return true;
    return false;
  }
  function hasCanvasData(){
    try{
      if (window.TASKS && Array.isArray(TASKS) && TASKS.length) return true;
      if (window.DATA_READY && window.DATA && Array.isArray(window.DATA.tasks) && window.DATA.tasks.length) return true;
      var nodes = document.querySelectorAll("#builderStage .node");
      if (nodes && nodes.length) return true;
    }catch(_){}
    return false;
  }
  function armReady(reason){
    if (ready) return;
    ready = true;
    pushSnapshot("baseline:" + String(reason || "auto"), true);
    setTimeout(function(){ pushSnapshot("baseline-late:" + String(reason || "auto"), true); }, 260);
  }
  function maybeArmReady(reason){
    if (ready) return;
    if (hasCanvasData()) armReady(reason);
  }

  function captureAreas(){
    var out = {projects: [], tags: []};
    try{
      if (window.projectAreas && typeof projectAreas.forEach === "function"){
        projectAreas.forEach(function(pa, name){
          if (!pa) return;
          out.projects.push({
            name: String(name || "(no project)"),
            x: toInt(pa.x, 0), y: toInt(pa.y, 0),
            w: toInt(pa.w, 280), h: toInt(pa.h, 120),
            tagCols: Math.max(1, toInt(pa.tagCols, 3)),
            tagW0: Math.max(120, toInt(pa.tagW0, 600)),
            tagH0: Math.max(80, toInt(pa.tagH0, 220)),
            nextTagIndex: Math.max(0, toInt(pa.nextTagIndex, 0))
          });
        });
      }
    }catch(_){}
    try{
      if (window.tagAreas && typeof tagAreas.forEach === "function"){
        tagAreas.forEach(function(ta){
          if (!ta) return;
          out.tags.push({
            project: String(ta.project || "(no project)"),
            tag: String(ta.tag || "(no tag)"),
            x: toInt(ta.x, 0), y: toInt(ta.y, 0),
            w: Math.max(120, toInt(ta.w, 300)),
            h: Math.max(80, toInt(ta.h, 180))
          });
        });
      }
    }catch(_){}
    return out;
  }

  function captureNodes(){
    var out = [];
    try{
      var nodes = document.querySelectorAll("#builderStage .node");
      for (var i=0; i<nodes.length; i++){
        var n = nodes[i];
        out.push({
          id: n.getAttribute("data-uuid") || n.getAttribute("data-short") || "",
          uuid: n.getAttribute("data-uuid") || "",
          short: n.getAttribute("data-short") || "",
          x: toInt(n.style.left, 0),
          y: toInt(n.style.top, 0),
          proj: n.getAttribute("data-proj") || "",
          tag: n.getAttribute("data-tag") || "",
          done: n.classList.contains("stagedDone"),
          deleted: n.classList.contains("stagedDel")
        });
      }
    }catch(_){}
    return out;
  }

  function captureSnapshot(){
    var zoomValue = 100;
    try{
      var z = document.getElementById("zoom");
      zoomValue = z ? toInt(z.value, 100) : toInt((window.ZSCALE || 1) * 100, 100);
    }catch(_){}
    var areas = captureAreas();
    return {
      version: 1,
      tasks: clone(window.TASKS || []),
      init_main_tag: clone(window.INIT_MAIN_TAG || {}),
      init_project: clone(window.INIT_PROJECT || {}),
      fold: clone(window.FOLD || window.__FOLD_STATE__ || {}),
      ex_ops: clone(window.EX_OPS || window.__EXISTING_OPS__ || {}),
      staged_cmds: clone(window.STAGED_CMDS || []),
      staged_human: clone(window.STAGED_HUMAN || []),
      staged_add: clone(window.stagedAdd || []),
      exist_edges: clone(window.EXIST_EDGES || []),
      zoom: Math.max(50, Math.min(200, zoomValue)),
      projects: areas.projects,
      tags: areas.tags,
      nodes: captureNodes()
    };
  }

  function fingerprint(snapshot){
    try{ return JSON.stringify(snapshot); }catch(_){ return ""; }
  }

  function pushSnapshot(reason, force){
    if (suppress || !ready) return;
    var snap = captureSnapshot();
    var fp = fingerprint(snap);
    if (!fp) return;
    if (!force && index >= 0 && history[index] && history[index].fp === fp) return;

    history = history.slice(0, index + 1);
    history.push({fp: fp, snap: snap, reason: reason || "change"});
    if (history.length > MAX_HISTORY){
      history.shift();
    }
    index = history.length - 1;
  }

  function scheduleSnapshot(reason, delay){
    if (suppress) return;
    if (!ready) maybeArmReady("schedule:" + String(reason || ""));
    if (!ready) return;
    if ((delay|0) <= 0){
      pushSnapshot(reason || "scheduled-now", false);
      return;
    }
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(function(){
      saveTimer = 0;
      pushSnapshot(reason || "scheduled", false);
    }, Math.max(120, delay || 220));
  }
  function enqueueImmediateSnapshot(reason){
    if (suppress) return;
    if (!ready) maybeArmReady("immediate:" + String(reason || ""));
    if (!ready) return;
    // Run after current event loop so app handlers can finish mutating state.
    setTimeout(function(){
      pushSnapshot(reason || "immediate", false);
    }, 0);
  }
  function flushPendingSnapshot(reason){
    if (suppress || !ready) return;
    if (saveTimer){
      clearTimeout(saveTimer);
      saveTimer = 0;
    }
    pushSnapshot(reason || "flush", false);
  }

  function rebuildAreaMaps(snapshot){
    try{
      if (!snapshot || !Array.isArray(snapshot.projects) || !Array.isArray(snapshot.tags)) return;
      var projMap = new Map();
      for (var i=0; i<snapshot.projects.length; i++){
        var p = snapshot.projects[i] || {};
        projMap.set(String(p.name || "(no project)"), {
          x: toInt(p.x, 0), y: toInt(p.y, 0),
          w: Math.max(120, toInt(p.w, 280)),
          h: Math.max(80, toInt(p.h, 120)),
          tagCols: Math.max(1, toInt(p.tagCols, 3)),
          tagW0: Math.max(120, toInt(p.tagW0, 600)),
          tagH0: Math.max(80, toInt(p.tagH0, 220)),
          nextTagIndex: Math.max(0, toInt(p.nextTagIndex, 0)),
          el: null
        });
      }

      var cols = (window.LAYOUT && toInt(window.LAYOUT.COLS, 2)) || 2;
      var head = (window.LAYOUT && toInt(window.LAYOUT.TAG_HEAD, 40)) || 40;
      var pad = (window.LAYOUT && toInt(window.LAYOUT.TAG_PAD, 10)) || 10;
      var tagMap = new Map();
      for (var j=0; j<snapshot.tags.length; j++){
        var t = snapshot.tags[j] || {};
        var project = String(t.project || "(no project)");
        var tag = String(t.tag || "(no tag)");
        var y = toInt(t.y, 0);
        tagMap.set(project + "||" + tag, {
          x: toInt(t.x, 0), y: y,
          w: Math.max(120, toInt(t.w, 300)),
          h: Math.max(80, toInt(t.h, 180)),
          project: project,
          tag: tag,
          el: null,
          _cols: new Array(cols).fill(y + head + pad)
        });
      }
      window.projectAreas = projMap;
      window.tagAreas = tagMap;
    }catch(_){}
  }

  function taskById(id){
    var s = String(id || "");
    if (!s) return null;
    try{
      if (window.TASKS && Array.isArray(TASKS)){
        for (var i=0; i<TASKS.length; i++){
          var t = TASKS[i];
          if (!t) continue;
          if (String(t.uuid || "") === s || String(t.short || "") === s) return t;
        }
      }
    }catch(_){}
    return null;
  }

  function rebuildTaskByShort(){
    try{
      var map = Object.create(null);
      var arr = Array.isArray(window.TASKS) ? TASKS : [];
      for (var i=0; i<arr.length; i++){
        var t = arr[i];
        if (!t || !t.short) continue;
        map[t.short] = t;
      }
      window.TASK_BY_SHORT = map;
    }catch(_){}
  }

  function clearCanvasNodes(){
    try{
      var nodes = document.querySelectorAll("#builderStage .node");
      for (var i=0; i<nodes.length; i++) nodes[i].remove();
    }catch(_){}
  }

  function restoreNodes(snapshot){
    if (!snapshot || !Array.isArray(snapshot.nodes)) return;
    for (var i=0; i<snapshot.nodes.length; i++){
      var r = snapshot.nodes[i] || {};
      var id = r.uuid || r.id || r.short;
      var t = taskById(id);
      if (!t) continue;
      var proj = String(r.proj || t.project || "(no project)");
      var tag = String(r.tag || firstTag(t) || "(no tag)");
      t.project = proj;
      t.tags = (tag && tag !== "(no tag)") ? [tag] : [];
      try{
        if (typeof ensureTagArea === "function") ensureTagArea(proj, tag);
      }catch(_){}

      var n = null;
      try{
        if (typeof addNodeForTask === "function"){
          n = addNodeForTask(t, toInt(r.x, 0), toInt(r.y, 0), {deferLayout: true});
        }
      }catch(_){}
      if (!n){
        n = document.querySelector(
          '#builderStage .node[data-uuid="' + escAttr(String(r.uuid || "")) + '"], ' +
          '#builderStage .node[data-short="' + escAttr(String(r.short || "")) + '"]'
        );
      }
      if (!n) continue;
      n.style.left = toInt(r.x, 0) + "px";
      n.style.top = toInt(r.y, 0) + "px";
      if (r.uuid) n.setAttribute("data-uuid", String(r.uuid));
      if (r.short) n.setAttribute("data-short", String(r.short));
      n.setAttribute("data-proj", proj);
      n.setAttribute("data-tag", tag);
      n.classList.toggle("stagedDone", !!r.done);
      n.classList.toggle("stagedDel", !!r.deleted);
      var cap = n.querySelector(".caption");
      if (cap) cap.textContent = proj + " • " + tag;
    }
  }

  function applySnapshot(snapshot){
    if (!snapshot || typeof snapshot !== "object") return false;
    suppress = true;
    try{
      window.TASKS = clone(snapshot.tasks || []);
      window.INIT_MAIN_TAG = clone(snapshot.init_main_tag || {});
      window.INIT_PROJECT = clone(snapshot.init_project || {});
      window.FOLD = clone(snapshot.fold || {});
      window.__FOLD_STATE__ = window.FOLD;
      window.EX_OPS = clone(snapshot.ex_ops || {});
      window.__EXISTING_OPS__ = window.EX_OPS;
      window.STAGED_CMDS = clone(snapshot.staged_cmds || []);
      window.STAGED_HUMAN = clone(snapshot.staged_human || []);
      window.stagedAdd = clone(snapshot.staged_add || []);
      window.EXIST_EDGES = clone(snapshot.exist_edges || []);
      rebuildTaskByShort();

      rebuildAreaMaps(snapshot);
      clearCanvasNodes();
      try{
        if (typeof recomputeAreasAndTags === "function") recomputeAreasAndTags();
      }catch(_){}
      restoreNodes(snapshot);

      try{
        var z = document.getElementById("zoom");
        if (z) z.value = String(Math.max(50, Math.min(200, toInt(snapshot.zoom, 100))));
        if (typeof applyZoom === "function") applyZoom();
      }catch(_){}
      try{ if (typeof renderList === "function") renderList(); }catch(_){}
      try{ if (typeof drawLinks === "function") drawLinks(); }catch(_){}
      try{ if (typeof refreshDepHandleLetters === "function") refreshDepHandleLetters(); }catch(_){}
      try{ if (typeof updateConsole === "function") updateConsole(); }catch(_){}
      return true;
    }catch(_){
      return false;
    } finally {
      suppress = false;
    }
  }

  function undoCanvasChange(){
    flushPendingSnapshot("before-undo");
    if (index <= 0){
      notify("Nothing to undo");
      return false;
    }
    var target = index - 1;
    if (!history[target]) return false;
    if (!applySnapshot(history[target].snap)) return false;
    index = target;
    notify("Undo");
    return true;
  }

  function redoCanvasChange(){
    if (index >= history.length - 1){
      notify("Nothing to redo");
      return false;
    }
    var target = index + 1;
    if (!history[target]) return false;
    if (!applySnapshot(history[target].snap)) return false;
    index = target;
    notify("Redo");
    return true;
  }

  window.undoCanvasChange = undoCanvasChange;
  window.redoCanvasChange = redoCanvasChange;

  function wrapForCapture(name){
    var fn = window[name];
    if (typeof fn !== "function" || fn.__undoRedoWrap) return;
    var orig = fn;
    window[name] = function(){
      var rv = orig.apply(this, arguments);
      scheduleSnapshot("fn:" + name, 220);
      return rv;
    };
    window[name].__undoRedoWrap = true;
  }

  function install(){
    if (window.__undoRedoInstalled) return;
    window.__undoRedoInstalled = true;

    ["addNodeForTask", "addToBuilder", "recomputeAreasAndTags", "drawLinks", "updateConsole"]
      .forEach(wrapForCapture);

    try{
      var stage = document.getElementById("builderStage") || document.body;
      var mo = new MutationObserver(function(muts){
        if (suppress) return;
        if (!ready) maybeArmReady("mutation");
        if (!ready) return;
        for (var i=0; i<muts.length; i++){
          var m = muts[i];
          if (m.type === "attributes" || m.type === "childList"){
            scheduleSnapshot("mutation", 260);
            break;
          }
        }
      });
      mo.observe(stage, {
        subtree: true,
        childList: true,
        attributes: true,
        attributeFilter: ["style", "class", "data-proj", "data-tag"]
      });
    }catch(_){}

    document.addEventListener("mouseup", function(){
      enqueueImmediateSnapshot("mouseup-step");
      scheduleSnapshot("mouseup-fallback", 140);
    }, true);
    document.addEventListener("touchend", function(){
      enqueueImmediateSnapshot("touchend-step");
      scheduleSnapshot("touchend-fallback", 140);
    }, true);

    document.addEventListener("keydown", function(ev){
      if (isEditableTarget(ev.target)) return;
      var key = String(ev.key || "").toLowerCase();
      var ctrl = !!(ev.ctrlKey || ev.metaKey);
      if (!ctrl || ev.altKey) return;
      maybeArmReady("hotkey");

      if (key === "z"){
        ev.preventDefault(); ev.stopImmediatePropagation();
        if (ev.shiftKey) redoCanvasChange();
        else undoCanvasChange();
        return;
      }
      if (key === "y"){
        ev.preventDefault(); ev.stopImmediatePropagation();
        redoCanvasChange();
      }
    }, true);

    document.addEventListener("twdata", function(){
      setTimeout(function(){ maybeArmReady("twdata"); }, 40);
      setTimeout(function(){ maybeArmReady("twdata-late"); }, 320);
    });
    document.addEventListener("DOMContentLoaded", function(){ setTimeout(function(){ maybeArmReady("domcontentloaded"); }, 120); });
    window.addEventListener("load", function(){ setTimeout(function(){ maybeArmReady("load"); }, 140); });

    (function bootstrapProbe(){
      var tries = 0;
      var t = setInterval(function(){
        tries += 1;
        maybeArmReady("probe-" + tries);
        if (ready || tries >= 20) clearInterval(t);
      }, 150);
    })();

    setTimeout(function(){
      if (ready) pushSnapshot("boot", true);
    }, 2000);
  }

  install();
})();
</script>
""".strip()

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
    js = r"""
<script id="FEATURE_COMMAND_PREFLIGHT_V1">
(function(){
  if (window.__CMD_PREFLIGHT_V1__) return; window.__CMD_PREFLIGHT_V1__ = true;

  function shQuote(arg){
    var s = String(arg == null ? '' : arg);
    return "'" + s.replace(/'/g, "'\"'\"'") + "'";
  }

  function isModifierToken(tok){
    var t = String(tok || '').trim();
    if (!t) return false;
    if (/^[+-]\S+$/.test(t)) return true;
    if (/^[A-Za-z0-9_.-]+:.+$/.test(t)) return true;
    return false;
  }

  function shellQuoteTaskLine(line){
    var s = String(line || '').trim();
    if (!s) return '';

    var mTerm = /^task\s+(\S+)\s+(done|delete)\s*$/i.exec(s);
    if (mTerm){
      return 'task ' + shQuote(mTerm[1]) + ' ' + String(mTerm[2] || '').toLowerCase();
    }

    var mMod = /^task\s+(\S+)\s+modify(?:\s+(.*))?$/i.exec(s);
    if (mMod){
      var id = mMod[1];
      var rest = String(mMod[2] || '').trim();
      var toks = rest ? rest.split(/\s+/).filter(Boolean) : [];
      var qmods = toks.map(shQuote);
      return 'task ' + shQuote(id) + ' modify' + (qmods.length ? (' ' + qmods.join(' ')) : '');
    }

    var mAddLog = /^task\s+(add|log)\s+(.+)$/i.exec(s);
    if (mAddLog){
      var verb = String(mAddLog[1] || '').toLowerCase();
      var rest2 = String(mAddLog[2] || '').trim();
      if (!rest2){
        return 'task ' + verb + ' ' + shQuote('(no description)');
      }
      var parts = rest2.split(/\s+/).filter(Boolean);
      var mods = [];
      while (parts.length > 1 && isModifierToken(parts[parts.length - 1])){
        mods.unshift(parts.pop());
      }
      var desc = parts.join(' ').trim() || '(no description)';
      var tail = mods.map(shQuote).join(' ');
      return 'task ' + verb + ' ' + shQuote(desc) + (tail ? (' ' + tail) : '');
    }

    return s;
  }

  function parseAndNormalize(raw){
    var lines = String(raw||'').split(/\r?\n/).map(function(s){ return s.trim(); }).filter(Boolean);
    var seenExact = Object.create(null);
    var passthrough = [];
    var byTask = Object.create(null);
    var order = [];
    var warnings = [];

    function warn(msg){
      if (warnings.indexOf(msg) === -1) warnings.push(msg);
    }

    for (var i=0;i<lines.length;i++){
      var line = lines[i];
      if (seenExact[line]) continue;
      seenExact[line] = 1;

      var m = /^task\s+(\S+)\s+(modify|done|delete)\b(?:\s+(.*))?$/i.exec(line);
      if (!m){
        passthrough.push(line);
        continue;
      }

      var id = m[1];
      var verb = String(m[2]||'').toLowerCase();
      var rest = String(m[3]||'').trim();

      if (!byTask[id]){
        byTask[id] = { terminal:null, mods:[] };
        order.push(id);
      }
      var st = byTask[id];

      if (verb === 'modify'){
        if (st.terminal){
          warn('Dropped modify after terminal action for task ' + id);
          continue;
        }
        if (rest) st.mods.push(rest);
        continue;
      }

      // done/delete are terminal; last one wins.
      if (st.terminal && st.terminal !== verb){
        warn('Conflicting terminal actions for task ' + id + ' (kept last: ' + verb + ')');
      }
      st.terminal = verb;
    }

    var out = passthrough.slice();
    for (var j=0;j<order.length;j++){
      var id2 = order[j], s = byTask[id2];
      if (!s) continue;
      if (s.terminal){
        out.push('task ' + id2 + ' ' + s.terminal);
        continue;
      }
      if (s.mods && s.mods.length){
        var tokSeen = Object.create(null), toks = [];
        s.mods.join(' ').split(/\s+/).forEach(function(t){
          if (!t) return;
          if (tokSeen[t]) return;
          tokSeen[t] = 1;
          toks.push(t);
        });
        if (toks.length){
          out.push('task ' + id2 + ' modify ' + toks.join(' '));
        }
      }
    }
    var safe = out.map(shellQuoteTaskLine).filter(Boolean);
    return { text: safe.join('\n'), warnings: warnings };
  }

  function wrapBuildCommands(){
    var orig = window.buildCommands;
    if (typeof orig !== 'function' || orig.__cmdPreflightWrapped) return;
    window.buildCommands = function(){
      var raw = '';
      try{ raw = String(orig.apply(this, arguments) || ''); }catch(_){ return raw; }
      var res = parseAndNormalize(raw);
      window.__CMD_PREFLIGHT_WARNINGS__ = res.warnings || [];
      return res.text;
    };
    window.buildCommands.__cmdPreflightWrapped = true;
  }

  function wrapUpdateConsoleHint(){
    var _u = window.updateConsole;
    if (typeof _u !== 'function' || _u.__cmdPreflightHintWrap) return;
    window.updateConsole = function(){
      var rv = _u.apply(this, arguments);
      try{
        var w = window.__CMD_PREFLIGHT_WARNINGS__ || [];
        var box = document.getElementById('__cmdPreflightHint');
        if (!box){
          box = document.createElement('div');
          box.id = '__cmdPreflightHint';
          box.style.position = 'fixed';
          box.style.left = '12px';
          box.style.bottom = '12px';
          box.style.maxWidth = '40vw';
          box.style.padding = '6px 8px';
          box.style.borderRadius = '8px';
          box.style.background = '#2a1f12';
          box.style.border = '1px solid #8b5e34';
          box.style.color = '#fbd38d';
          box.style.font = '12px ui-monospace, monospace';
          box.style.zIndex = '99999';
          box.style.display = 'none';
          document.body.appendChild(box);
        }
        if (w.length){
          box.textContent = 'Preflight: ' + w.join(' | ');
          box.style.display = 'block';
        }else{
          box.style.display = 'none';
        }
      }catch(_){}
      return rv;
    };
    window.updateConsole.__cmdPreflightHintWrap = true;
  }

  wrapBuildCommands();
  wrapUpdateConsoleHint();
  setTimeout(function(){ try{ if (typeof updateConsole==='function') updateConsole(); }catch(_){} }, 0);
})();
</script>
""".strip()

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
    js = r"""
<script id="FEATURE_RUNTIME_DIAGNOSTICS_V1">
(function(){
  if (window.__RUNTIME_DIAGNOSTICS_V1__) return; window.__RUNTIME_DIAGNOSTICS_V1__ = true;

  var diag = window.__TASKCANVAS_DIAG__ || {
    errors: 0,
    rejections: 0,
    events: []
  };
  window.__TASKCANVAS_DIAG__ = diag;

  function push(kind, msg, extra){
    var entry = {
      ts: new Date().toISOString(),
      kind: String(kind || 'error'),
      msg: String(msg || '(no message)')
    };
    if (extra && typeof extra === 'object'){
      for (var k in extra){
        if (!Object.prototype.hasOwnProperty.call(extra, k)) continue;
        entry[k] = extra[k];
      }
    }
    diag.events.push(entry);
    if (diag.events.length > 50) diag.events.shift();
    try{ console.warn('[TaskCanvas][diag]', entry.kind + ':', entry.msg, entry); }catch(_){}
  }

  window.addEventListener('error', function(ev){
    try{
      diag.errors += 1;
      var msg = (ev && ev.message) ? ev.message : 'window error';
      push('error', msg, {
        file: ev && ev.filename ? ev.filename : '',
        line: ev && ev.lineno ? ev.lineno : 0,
        col: ev && ev.colno ? ev.colno : 0
      });
    }catch(_){}
  });

  window.addEventListener('unhandledrejection', function(ev){
    try{
      diag.rejections += 1;
      var reason = ev ? ev.reason : '';
      var msg = '';
      if (reason && typeof reason === 'object' && reason.message) msg = reason.message;
      else msg = String(reason || 'unhandled rejection');
      push('unhandledrejection', msg, {});
    }catch(_){}
  });

  window.TaskCanvasDiagnostics = function(){
    try{ return JSON.parse(JSON.stringify(diag)); }catch(_){ return diag; }
  };
})();
</script>
""".strip()

    if 'id="FEATURE_RUNTIME_DIAGNOSTICS_V1"' in html:
        return html
    if re.search(r"</body\s*>", html, flags=re.I):
        return re.sub(r"</body\s*>", lambda m: js + "\n" + m.group(0), html, count=1, flags=re.I)
    return html + "\n" + js
