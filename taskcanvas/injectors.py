import re
import sys
from pathlib import Path
from typing import Callable

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

  // Run periodically; skip work when tab is hidden to reduce background CPU churn.
  var t = setInterval(function(){
    if (document.hidden) return;
    restyleStaging();
  }, 650);

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

    # ============= OBSERVER (toggle-aware ✓/🗑) =============
    SNIP_OBS = r"""
<script id="FEATURE_HOVER_STAGE_OBSERVER_V1">(function(){
  if (window.__HOVER_STAGE_OBSERVER_V1__) return;
  window.__HOVER_STAGE_OBSERVER_V1__ = true;

  function resolveUUID(node){
    if (!node) return "";
    var uid = node.getAttribute && (node.getAttribute('data-uuid') || node.getAttribute('data-short')) || "";
    if (!uid){
      try{ var s = node.querySelector('.short'); if (s && s.textContent) uid = s.textContent.trim(); }catch(_){}
    }
    return uid || "";
  }
  function toShort(uid){
    if (!uid) return "";
    if (/^[0-9a-f]{6,8}$/i.test(uid)) return uid.slice(0,8);
    try{
      if (window.TASKS) for (var i=0;i<TASKS.length;i++) if (TASKS[i]?.uuid===uid) return TASKS[i].short || uid.slice(0,8);
      if (window.TASK_BY_SHORT){ for (var k in TASK_BY_SHORT) if (TASK_BY_SHORT[k]?.uuid===uid) return k; }
    }catch(_){}
    return uid.slice(0,8);
  }
  function ensureArray(){ return (window.STAGED_CMDS = Array.isArray(window.STAGED_CMDS) ? window.STAGED_CMDS : []); }
  function stage(kind, node){
    var uid = resolveUUID(node); if (!uid) return;
    var sid = toShort(uid);
    var cmd = 'task '+sid+' '+(kind==='modify'?'modify':kind);
    var A = ensureArray();
    var opp = cmd.replace(/\b(done|delete)\b/, kind==='done'?'delete':'done');
    for (var i=A.length-1;i>=0;i--){
      var s = String(A[i]||'');
      if (s === opp) A.splice(i,1);
      if (s === cmd) return;
    }
    A.push(cmd);
    try{ if (typeof updateConsole==='function') setTimeout(updateConsole,0); }catch(_){}
    try{ if (typeof __depsOverlayRender==='function') setTimeout(__depsOverlayRender,0); }catch(_){}
  }
  function unstage(kind, node){
    var uid = resolveUUID(node); if (!uid) return;
    var sid = toShort(uid);
    var cmd = 'task '+sid+' '+(kind==='modify'?'modify':kind);
    var A = ensureArray();
    for (var i=A.length-1;i>=0;i--){
      if (String(A[i]||'') === cmd) A.splice(i,1);
    }
    try{ if (typeof updateConsole==='function') setTimeout(updateConsole,0); }catch(_){}
    try{ if (typeof __depsOverlayRender==='function') setTimeout(__depsOverlayRender,0); }catch(_){}
  }
  function startObserver(){
    var root = document.getElementById('builderStage') || document.body;
    if (!root || root.__hoverObserver) return;
    var obs = new MutationObserver(function(records){
      for (var r of records){
        if (r.type === 'attributes' && r.attributeName === 'class'){
          var el = r.target; if (!el || !el.classList) continue;
          // additions
          if (el.classList.contains('stagedDone'))  stage('done',   el);
          if (el.classList.contains('stagedDel'))   stage('delete', el);
          // removals (using oldValue)
          var ov = r.oldValue || "";
          var hadDone = /\bstagedDone\b/.test(ov), hasDone = el.classList.contains('stagedDone');
          var hadDel  = /\bstagedDel\b/.test(ov),  hasDel  = el.classList.contains('stagedDel');
          if (hadDone && !hasDone) unstage('done', el);
          if (hadDel  && !hasDel ) unstage('delete', el);
        } else if (r.type === 'childList'){
          r.removedNodes && r.removedNodes.forEach(function(n){
            try{
              if (n.nodeType !== 1) return;
              if (n.classList && (n.classList.contains('stagedDone') || n.classList.contains('stagedDel'))){
                unstage(n.classList.contains('stagedDone') ? 'done' : 'delete', n);
              }
              var marked = n.querySelectorAll && n.querySelectorAll('.stagedDone, .stagedDel');
              if (marked && marked.length){ marked.forEach(function(m){
                unstage(m.classList.contains('stagedDone') ? 'done' : 'delete', m);
              });}
            }catch(_){}
          });
        }
      }
    });
    obs.observe(root, { subtree:true, attributes:true, attributeFilter:['class'], attributeOldValue:true, childList:true });
    root.__hoverObserver = obs;
  }
  startObserver();
  document.addEventListener('twdata', function(){ setTimeout(startObserver, 0); });
  window.addEventListener('load', function(){ setTimeout(startObserver, 60); });
  console.log('[observer] hover stage observer active (toggle-aware)');
})();</script>
""".strip("\n")

    # ============= SHORTIFY (render-time) =============
    SNIP_SHORTIFY = r"""
<script id="FEATURE_SHORTIFY_RENDER_V1">(function(){
  if (window.__SHORTIFY_RENDER__) return; window.__SHORTIFY_RENDER__=true;
  function uuidToShort(uuid){
    try{
      if (!uuid) return "";
      if (window.TASKS) for (var i=0;i<TASKS.length;i++) if (TASKS[i]?.uuid===uuid) return TASKS[i].short||uuid;
      if (window.TASK_BY_SHORT){ for (var k in TASK_BY_SHORT) if (TASK_BY_SHORT[k]?.uuid===uuid) return k; }
    }catch(_){}
    return uuid;
  }
  function shortifyText(txt){
    if (!txt) return txt;
    return String(txt).replace(/\b([0-9a-f]{8}-[0-9a-f-]{13,})\b/ig, function(m){ return uuidToShort(m) || m; });
  }
  if (typeof window.updateConsole === 'function' && !window.updateConsole.__shortifyWrap){
    var _u = window.updateConsole;
    window.updateConsole = function(){
      var rv = _u.apply(this, arguments);
      try{ var el = document.getElementById('consoleText'); if (el && typeof el.value === 'string') el.value = shortifyText(el.value); }catch(_){}
      return rv;
    };
    window.updateConsole.__shortifyWrap = true;
  }
  ['__depsOverlayRender','renderStagedOverlay'].forEach(function(fn){
    if (typeof window[fn] === 'function' && !window[fn].__shortifyWrap){
      var orig = window[fn];
      window[fn] = function(){
        var rv = orig.apply(this, arguments);
        try{ var pre = document.getElementById('depCmdPre'); if (pre && typeof pre.textContent === 'string') pre.textContent = shortifyText(pre.textContent); }catch(_){}
        return rv;
      };
      window[fn].__shortifyWrap = true;
    }
  });
  try{ if (typeof updateConsole==='function') updateConsole(); }catch(_){}
  try{ if (typeof __depsOverlayRender==='function') __depsOverlayRender(); }catch(_){}
})();</script>
""".strip("\n")

  # ============= MERGE (textarea + Deps overlay) — V3 silent/efficient =============
    SNIP_MERGE = r"""
  <script id="FEATURE_CONSOLE_MERGE_V3">(function(){
    if (window.__CONSOLE_MERGE_V3__) return; window.__CONSOLE_MERGE_V3__=true;

    // --- util ---
    function uuidToShort(uuid){
      try{
        if (!uuid) return "";
        if (window.TASKS) for (var i=0;i<TASKS.length;i++) if (TASKS[i] && TASKS[i].uuid===uuid) return TASKS[i].short||uuid;
        if (window.TASK_BY_SHORT) for (var k in TASK_BY_SHORT) if (TASK_BY_SHORT[k] && TASK_BY_SHORT[k].uuid===uuid) return k;
      }catch(_){}
      return uuid;
    }
    var UUID_RE = /\b([0-9a-f]{8}-[0-9a-f-]{13,})\b/ig;
    function shortifyText(txt){
      if (!txt || !UUID_RE.test(txt)) return txt||"";
      UUID_RE.lastIndex = 0;
      return String(txt).replace(UUID_RE, function(m){ return uuidToShort(m) || m; });
    }
    function lines(s){
      if (!s) return [];
      return String(s).replace(/\r\n/g,"\n").split("\n").map(function(x){return x.trim();}).filter(Boolean);
    }
    function uniqueMerge(baseText, stagedArr){
      var base = lines(baseText);
      var staged = Array.isArray(stagedArr) ? stagedArr : [];
      var out=[], seen=Object.create(null);
      for (var i=0;i<base.length;i++){ var s=base[i]; if (!s||seen[s]) continue; seen[s]=1; out.push(s); }
      for (var j=0;j<staged.length;j++){ var t=staged[j]; if (!t||seen[t]) continue; seen[t]=1; out.push(t); }
      return out.join("\n");
    }

    // --- writers with change detection ---
    var _lastTextarea = null, _lastPre = null;
    function mergeIntoTextarea(){
      var el = document.getElementById("consoleText");
      if (!el) return;
      var merged = shortifyText(uniqueMerge(el.value, window.STAGED_CMDS||[]));
      if (merged !== _lastTextarea){
        el.value = merged;
        _lastTextarea = merged;
      }
    }
    function mergeIntoDepsOverlay(){
      var pre = document.getElementById("depCmdPre");
      if (!pre) return;
      var merged = shortifyText(uniqueMerge(pre.textContent||"", window.STAGED_CMDS||[]));
      if (merged !== _lastPre){
        pre.textContent = merged;
        _lastPre = merged;
      }
    }

    // --- debounced runner ---
    var _t = null, _queued = false;
    function scheduleMerge(delay){
      if (_queued) return;
      _queued = true;
      if (_t) clearTimeout(_t);
      _t = setTimeout(function(){
        _queued = false;
        try{ mergeIntoTextarea(); mergeIntoDepsOverlay(); }catch(_){}
      }, Math.max(50, delay|0)); // ~20fps
    }

    // --- wrap updateConsole once (after any other wrappers) ---
    if (!window.updateConsole){
      window.updateConsole = function(){ scheduleMerge(50); };
    }else if (!window.updateConsole.__mergeV3){
      var orig = window.updateConsole;
      window.updateConsole = function(){ var rv = orig.apply(this, arguments); scheduleMerge(50); return rv; };
      window.updateConsole.__mergeV3 = true;
    }

    // initial paint
    scheduleMerge(0);
  })();</script>
  """.strip("\n")


    # ============= MODIFY injector (normalize + short IDs; robust anchor) =============
    MODIFY_MARK = "/* __PATCH_MODIFY_STAGE_TO_CONSOLE__ */"
    SNIP_MODIFY = r"""
          /* __PATCH_MODIFY_STAGE_TO_CONSOLE__ */
          try{
            (function(){
              console.log("[hover/console] modify injector active");
              function normalizeMods(arr){
                var out = [], lastIdx = Object.create(null);
                for (var i=0;i<arr.length;i++){
                  var tok = String(arr[i]||'').trim(); if (!tok) continue;
                  var m = tok.match(/^([^:\s]+):(.*)$/);
                  if (m){
                    var key = m[1].toLowerCase();
                    if (lastIdx[key] != null){ out[lastIdx[key]] = tok; }
                    else { lastIdx[key] = out.length; out.push(tok); }
                  }else{
                    out.push(tok);
                  }
                }
                return out;
              }
              function toShortId(x){
                try{
                  var n = document.querySelector('#builderStage [data-uuid="'+x+'"]');
                  if (n) return n.getAttribute('data-short') || String(x).slice(0,8);
                }catch(_){}
                var s = String(x||''); return s.length>8 ? s.slice(0,8) : s;
              }
              var sid = toShortId(id);
              var modsArr = (Array.isArray(merged) ? merged.slice() : []);
              if (!sid || !modsArr.length) return;
              modsArr = normalizeMods(modsArr);
              var line = 'task '+sid+' modify '+modsArr.join(' ');
              var A = (window.STAGED_CMDS = window.STAGED_CMDS || []);
              for (var i=A.length-1;i>=0;i--){
                var s = String(A[i]||'');
                if (s.indexOf('task '+sid+' modify ') === 0){ A.splice(i,1); }
              }
              A.push(line);
              try{ if (typeof window.updateConsole==='function') setTimeout(window.updateConsole, 0); }catch(_){}
              try{ if (typeof window.__depsOverlayRender==='function') setTimeout(window.__depsOverlayRender, 0); }catch(_){}
            })();
          }catch(_){}
""".strip("\n")

    # Robust anchor for: ops.mods = merged;  (allows dot or ["mods"])
    pattern = r"(ops\s*(?:\.\s*|\[\s*['\"]\s*)mods(?:\s*['\"]\s*\])?\s*=\s*merged\s*;\s*)"

    if MODIFY_MARK in html:
        logp("[gen] modify injector: already present (marker).")
    else:
        hit_count = [0]
        def _repl(m):
            hit_count[0] += 1
            return m.group(1) + "\n" + SNIP_MODIFY + "\n"
        new_html = re.sub(pattern, _repl, html)
        if hit_count[0] > 0:
            logp(f"[gen] modify injector: anchored ({hit_count[0]} site(s)).")
            html = new_html
        else:
            # Fallback: append at </body> so it still works if the anchor shifts/minifies away
            html = html.replace("</body>", "<script>"+SNIP_MODIFY+"</script>\n</body>")
            logp("[gen] modify injector: fallback appended at </body>.")

    # Ensure observer present
    if "FEATURE_HOVER_STAGE_OBSERVER_V1" not in html:
        html = html.replace("</body>", SNIP_OBS + "\n</body>")
        logp("[gen] observer: appended.")
    else:
        logp("[gen] observer: already present.")

    # Ensure shortify present
    if "FEATURE_SHORTIFY_RENDER_V1" not in html:
        html = html.replace("</body>", SNIP_SHORTIFY + "\n</body>")
        logp("[gen] shortify: appended.")
    else:
        logp("[gen] shortify: already present.")

    # Ensure merge wrapper present
    if "FEATURE_CONSOLE_MERGE_V2" not in html:
        html = html.replace("</body>", SNIP_MERGE + "\n</body>")
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

    js = r"""
<script id="FEATURE_MULTILINE_ADD_V1">(function(){
  if (window.__ML_ADD_V1__) return; window.__ML_ADD_V1__ = true;

  // -------- UI: multiline textarea modal --------
  function multilineDialog(title, placeholder){
    return new Promise((resolve)=>{
      const wrap = document.createElement('div');
      wrap.style.cssText = 'position:fixed;inset:0;display:flex;align-items:center;justify-content:center;z-index:999999;';
      wrap.innerHTML = `
        <div style="position:absolute;inset:0;background:rgba(0,0,0,.36)"></div>
        <div style="position:relative;max-width:720px;width:92%;background:#111;color:#eee;border-radius:12px;padding:16px;box-shadow:0 10px 30px rgba(0,0,0,.4)">
          <div style="font-weight:700;margin-bottom:8px">${title||'Add tasks (one per line)'}</div>
          <textarea id="mlAddTa" rows="8" autofocus
            style="width:100%;background:#0c0f16;color:#e7e7ee;border:1px solid #2a3344;border-radius:10px;padding:10px;resize:vertical;line-height:1.3;"
            placeholder="${placeholder||'One task per line…'}"></textarea>
          <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:10px">
            <button id="mlAddCancel" style="padding:6px 12px;border:1px solid #333;background:#1a1f2b;color:#bbb;border-radius:8px;cursor:pointer">Cancel</button>
            <button id="mlAddOk" style="padding:6px 12px;border:1px solid #3b82f6;background:#2563eb;color:#fff;border-radius:8px;cursor:pointer">Add</button>
          </div>
          <div style="font-size:12px;opacity:.7;margin-top:6px">Tip: Ctrl/⌘+Enter to submit</div>
        </div>`;
      document.body.appendChild(wrap);
      const ta = wrap.querySelector('#mlAddTa');
      const done = (ok)=>{ const v = ta.value; wrap.remove(); resolve(ok ? v : null); };
      wrap.querySelector('#mlAddOk').onclick = ()=>done(true);
      wrap.querySelector('#mlAddCancel').onclick = ()=>done(false);
      wrap.addEventListener('keydown', (ev)=>{
        if (ev.key==='Escape') { ev.preventDefault(); done(false); }
        if ((ev.ctrlKey||ev.metaKey) && ev.key==='Enter') { ev.preventDefault(); done(true); }
      });
      setTimeout(()=>ta.focus(),0);
    });
  }

  // -------- IDs: 'new-' UUID + independent 8-hex short --------
  function randHex(n){
    if (window.crypto && crypto.getRandomValues){
      const arr = new Uint8Array(n/2); crypto.getRandomValues(arr);
      return Array.from(arr, b=>b.toString(16).padStart(2,'0')).join('');
    }
    return Array.from({length:n},()=>Math.floor(Math.random()*16).toString(16)).join('');
  }
  function genNewIds(){
    // uuid prefix signals "new task" to your app's staging; short remains classic 8-hex for DnD
    const uuid = 'new-' + randHex(16);      // e.g., new-a1b2c3d4e5f67890
    const short = 'n-' + randHex(6);               // e.g., 7f9e02
    return { uuid, short };
  }
  function makeNewTask(desc, project, tagsArr){
    const ids = genNewIds();
    return { uuid: ids.uuid, short: ids.short, desc, project, tags: tagsArr, has_depends:false };
  }
  function firstTag(t){ return (t.tags && t.tags.length) ? t.tags[0] : "(no tag)"; }

  // -------- Rebinding: per-node + global --------
  function rebindForNode(nodeEl){
    try{
      if (typeof attachDepHandleToNode === 'function') attachDepHandleToNode(nodeEl);
      if (typeof __depHandleAuthorV6 === 'function') __depHandleAuthorV6(nodeEl);
      if (typeof __depHandleAuthorDedupV6b === 'function') __depHandleAuthorDedupV6b(nodeEl);
      nodeEl.setAttribute('draggable', 'true');    // harmless hint
      nodeEl.classList.add('draggable-node');      // benign class for delegated DnD
    }catch(_){}
  }
  function fireGlobalRebind(){
    try{ document.dispatchEvent(new Event('twdata')); }catch(_){}
  }

  // -------- Place one task using app internals --------
  function pushAndPlaceTask(t){
    // model
    window.TASKS.push(t);
    try{ window.TASK_BY_SHORT[t.short] = t; }catch(_){}
    // list
    try{ renderList(); }catch(_){}
    // builder + node enforcement
    try{
      const proj = t.project || "(no project)";
      const tag  = firstTag(t);
      if (typeof ensureTagArea==='function') ensureTagArea(proj, tag);
      let el = null;
      if (typeof addToBuilder==='function'){
        el = addToBuilder(t, null, null);
      }
      // ensure DOM carries correct identifiers (some paths may skip data-short)
      try{
        if (!el || el.nodeType !== 1){
          el = document.querySelector(`[data-uuid="${t.uuid}"]`) ||
               document.querySelector(`#builderStage .node[data-short="${t.short}"]`);
        }
        if (el && el.nodeType === 1){
          el.setAttribute('data-uuid', t.uuid);
          el.setAttribute('data-short', t.short);  // keep 8-hex for DnD logic
          rebindForNode(el);
        }
      }catch(_){}
    }catch(_){}
    try{ if (typeof updateConsole==='function') updateConsole(); }catch(_){}
  }

  // -------- 1) Intercept per-tag ＋ (.tagAddBtn) --------
  document.addEventListener('click', async function(ev){
    const btn = ev.target && ev.target.closest && ev.target.closest('.tagAddBtn');
    if (!btn) return;

    ev.preventDefault(); ev.stopImmediatePropagation();

    const area  = btn.closest('.tagArea');
    const project = area?.getAttribute('data-proj') || "(no project)";
    const tag     = area?.getAttribute('data-tag')  || "(no tag)";

    const val = await multilineDialog(`Add tasks to “${tag}” in ${project}`, 'One task per line…');
    if (val==null) return;
    const lines = String(val).split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
    if (!lines.length) return;

    const tagsArr = (tag && tag !== "(no tag)") ? [tag] : [];
    for (let i=0;i<lines.length;i++){
      pushAndPlaceTask(makeNewTask(lines[i], project, tagsArr));
      if (i && i%25===0) await new Promise(r=>setTimeout(r,0)); // yield on large batches
    }
    fireGlobalRebind(); // ensure DnD/hover binders include new nodes
    console.log('[ml-add] added', lines.length, 'tasks to', project, '/', tag);
  }, true);

  // -------- 2) Intercept FAB (#fabAddNew) --------
  (function(){
    const fabBtn = document.getElementById('fabAddNew');
    if (!fabBtn) return;
    fabBtn.addEventListener('click', async function(ev){
      ev.preventDefault(); ev.stopImmediatePropagation();

      const descs = await multilineDialog('Add new tasks (one per line)', 'One task per line…');
      if (descs==null) return;
      const lines = String(descs).split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
      if (!lines.length) return;

      // Ask once for project/tags (mirrors original flow)
      const projs = (function(){
        const set={}, arr=[];
        try{
          for (let i=0;i<(window.TASKS||[]).length;i++){
            const p=(window.TASKS[i].project||"(no project)");
            if(!set[p]){ set[p]=1; arr.push(p); }
          }
        }catch(_){}
        arr.sort(); return arr;
      })();

      const defProj = projs[0] || "(no project)";
      const project = prompt("Project (existing or new):", defProj) || "(no project)";
      const tagsIn  = prompt("Tags (comma-separated):", "") || "";
      const tagsArr = tagsIn.split(",").map(s=>s.trim()).filter(Boolean);

      const onCanvas = (function(){
        try{ return (window.projectAreas && typeof projectAreas.has==='function') ? projectAreas.has(project) : false; }catch(_){ return false; }
      })();

      for (let i=0;i<lines.length;i++){
        const t = makeNewTask(lines[i], project, tagsArr);
        window.TASKS.push(t);
        try{ window.TASK_BY_SHORT[t.short] = t; }catch(_){}
        try{ renderList(); }catch(_){}
        if (onCanvas){
          try{
            if (typeof ensureTagArea==='function') ensureTagArea(project, firstTag(t));
            if (typeof addToBuilder==='function'){
              let el = addToBuilder(t, null, null) || null;
              if (!el || el.nodeType !== 1){
                el = document.querySelector(`[data-uuid="${t.uuid}"]`) ||
                     document.querySelector(`#builderStage .node[data-short="${t.short}"]`);
              }
              if (el && el.nodeType === 1){
                el.setAttribute('data-uuid', t.uuid);
                el.setAttribute('data-short', t.short);
                rebindForNode(el);
              }
            }
          }catch(_){}
        }
        if (i && i%25===0) await new Promise(r=>setTimeout(r,0));
      }

      if (!onCanvas){
        try{ alert(`Created ${lines.length} task(s). Add the project (“${project}”) to the canvas to place them.`); }catch(_){}
      }
      try{ if (typeof updateConsole==='function') updateConsole(); }catch(_){}
      fireGlobalRebind();

      console.log('[ml-add] added', lines.length, 'new task(s) to project', project);
    }, true);
  })();

  console.log('[ml-add] multiline add enabled (new-uuid + 8hex short + rebind)');
})();</script>
""".strip("\n")

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
    js = r"""
<script id="FEATURE_NEW_TASK_CONSOLE_SYNC_V2">(function(){
  if (window.__NEW_TASK_SYNC_V2__) return; window.__NEW_TASK_SYNC_V2__ = true;

  // --- 1) New-ID detection: uuid 'new-*' or short 'n-<6hex>'
  window.isNewId = window.isNewId || function(x){
    if (!x) return false;
    var s = String(x);
    return /^new-/.test(s) || /^n-[0-9a-f]{6}$/i.test(s);
  };

  // --- 2) Fold holder for per-new-task state (mods, tags, done/deleted)
  function ensureFOLD(){ if (!window.FOLD) window.FOLD = Object.create(null); return window.FOLD; }
  function ensureFold(id){
    var F = ensureFOLD();
    var f = F[id] || (F[id]={});
    if (!f.tags) f.tags = Object.create(null);
    if (!Array.isArray(f.extra)) f.extra = [];
    return f;
  }
  function parseModsToFold(f, modsTokens){
    if (!Array.isArray(modsTokens)) return;
    var seenIdx = Object.create(null), extra = [];
    for (var i=0;i<modsTokens.length;i++){
      var tok = String(modsTokens[i]||'').trim(); if (!tok) continue;
      if (tok[0]==='+' && tok.length>1){ f.tags[tok.slice(1)] = true; continue; }
      if (tok[0]==='-' && tok.length>1){ delete f.tags[tok.slice(1)]; continue; }
      var m = tok.match(/^([^:\s]+):(.*)$/);
      if (m){
        var k = m[1].toLowerCase(), v = m[2];
        if (k==='project'){ f.project = v || "(no project)"; continue; }
        if (k==='due'){ f.due = v; continue; }
        if (seenIdx[k]!=null){ extra[seenIdx[k]] = tok; } else { seenIdx[k]=extra.length; extra.push(tok); }
      } else {
        extra.push(tok);
      }
    }
    f.extra = extra;
  }

  // --- 3) Pull staged lines that (accidentally) target new IDs into FOLD and remove them
  function reconcileNewStaged(){
    var A = Array.isArray(window.STAGED_CMDS) ? window.STAGED_CMDS : (window.STAGED_CMDS = []);
    for (var i=A.length-1;i>=0;i--){
      var s = String(A[i]||'').trim();
      var m = s.match(/^task\s+(\S+)\s+(done|delete|modify)\b(?:\s+(.*))?$/i);
      if (!m) continue;
      var id = m[1], verb = (m[2]||'').toLowerCase(), rest = (m[3]||'').trim();
      if (!window.isNewId(id)) continue;
      var f = ensureFold(id);
      if (verb==='done'){ f.done = true; }
      else if (verb==='delete'){ f.deleted = true; }
      else if (verb==='modify'){ parseModsToFold(f, rest ? rest.split(/\s+/) : []); }
      A.splice(i,1);
    }
  }

  // --- 4) Build canonical lines for all NEW tasks (one line each; add OR log)
  function newTaskConsoleLines(){
    var out = [];
    var T = Array.isArray(window.TASKS) ? window.TASKS : [];
    for (var i=0;i<T.length;i++){
      var t = T[i]; if (!t) continue;
      var id = t.uuid || t.short; if (!window.isNewId(id)) continue;

      // read current hover state from DOM
      var nd = document.querySelector('.node[data-uuid="'+id+'"], .node[data-short="'+id+'"]');
      var done = false, deleted = false;
      if (nd){
        done    = nd.classList.contains('stagedDone') || nd.classList.contains('completed') || nd.getAttribute('data-done')==='1';
        deleted = nd.classList.contains('stagedDel')  || nd.getAttribute('data-deleted')==='1';
      }

      // merge with FOLD (which also tracks staged ops we absorbed)
      var f = (ensureFOLD()[t.uuid] || ensureFOLD()[t.short] || {});
      if (f.done) done = true;
      if (f.deleted) deleted = true;
      if (deleted) continue; // delete removes any new-task line

      var parts = [ done ? "task log" : "task add", (t.desc||"(no description)") ];

      var proj = (typeof f.project!=='undefined') ? f.project : (t.project || "(no project)");
      if (proj && proj!=="(no project)") parts.push("project:"+proj);

      var tagset = Object.create(null);
      if (Array.isArray(t.tags)) for (var k=0;k<t.tags.length;k++){ var tg=t.tags[k]; if (tg && tg!=="(no tag)") tagset[tg]=true; }
      if (f.tags) for (var tg in f.tags){ if (f.tags[tg]) tagset[tg]=true; else delete tagset[tg]; }
      Object.keys(tagset).forEach(function(tg){ parts.push("+"+tg); });

      var due = (typeof f.due!=='undefined') ? f.due : t.due;
      if (due) parts.push("due:"+due);

      if (Array.isArray(f.extra)) for (var q=0;q<f.extra.length;q++){ parts.push(f.extra[q]); }

      out.push(parts.join(" "));
    }
    return out;
  }

  // --- 5) Helpers for merging & filtering
  function splitLines(s){
    if (!s) return [];
    return String(s).replace(/\r\n/g,"\n").split("\n").map(function(x){return x.trim();}).filter(Boolean);
  }
  function writeConsole(lines){
    try{
      var txt = (lines||[]).join("\n");
      var ta = document.getElementById('consoleText');
      if (ta && typeof ta.value==='string') ta.value = txt;
      var pre = document.getElementById('depCmdPre');
      if (pre) pre.textContent = txt;
    }catch(_){}
  }
  function newTaskDescriptors(){
    var set = Object.create(null);
    var T = Array.isArray(window.TASKS) ? window.TASKS : [];
    for (var i=0;i<T.length;i++){
      var t=T[i]; if (!t) continue;
      var id = t.uuid || t.short; if (!window.isNewId(id)) continue;
      var d = (t.desc||"").trim();
      if (d) set[d]=1;
    }
    return set;
  }
  // Remove any “task add …” or “task log …” lines that appear to belong to NEW tasks (by description match)
  function stripCurrentNewTaskLines(currentLines){
    var descs = newTaskDescriptors();
    return currentLines.filter(function(line){
      var m = line.match(/^(task\s+(?:add|log)\s+)(.*)$/i);
      if (!m) return true;
      var rest = m[2]||"";
      // basic containment check on the description token
      for (var d in descs){ if (descs[d] && rest.indexOf(d) !== -1) return false; }
      return true;
    });
  }
  // If both "task add X" and "task log X" exist, keep only log
  function preferLogOverAdd(lines){
    var bestByRest = Object.create(null), order=[];
    for (var i=0;i<lines.length;i++){
      var s = lines[i], m = s.match(/^(task\s+(add|log)\s+)(.*)$/i);
      if (!m){ if (!bestByRest["__misc__"]) { bestByRest["__misc__"]=[]; order.push("__misc__"); } bestByRest["__misc__"].push(s); continue; }
      var verb = (m[2]||"").toLowerCase();
      var rest = m[3]||"";
      var key = "REST::"+rest;
      if (!(key in bestByRest)){ bestByRest[key] = s; order.push(key); }
      else {
        var prev = bestByRest[key];
        if (/^task\s+add\s+/i.test(prev) && verb === "log"){ bestByRest[key] = s; } // upgrade to log
      }
    }
    var out=[];
    for (var j=0;j<order.length;j++){
      var k = order[j], v = bestByRest[k];
      if (Array.isArray(v)) out = out.concat(v);
      else out.push(v);
    }
    return out;
  }

  // --- 6) Wrap updateConsole: rebuild with strict new-task policy + dedupe
  (function(){
    var _u = window.updateConsole;
    window.updateConsole = function(){
      try{ reconcileNewStaged(); }catch(_){}
      var rv = (typeof _u==='function') ? _u.apply(this, arguments) : undefined;

      try{
        var ta = document.getElementById('consoleText');
        var currentText = (ta && typeof ta.value==='string') ? ta.value : '';
        var current = splitLines(currentText);

        // Strip any old add/log lines for NEW tasks first
        var currentSansNew = stripCurrentNewTaskLines(current);

        // Recompute canonical NEW lines + add any non-new staged lines (if any)
        var newLines = newTaskConsoleLines();
        var staged  = Array.isArray(window.STAGED_CMDS) ? window.STAGED_CMDS.slice() : [];

        // Merge: (current minus old new-lines) + new-lines + staged; then prefer log over add
        var merged = currentSansNew.concat(newLines).concat(staged);

        var finalLines = preferLogOverAdd(merged);
        var finalText  = finalLines.join("\n");
        if (finalText !== currentText){
          writeConsole(finalLines);
        }
      }catch(_){}

      return rv;
    };
    window.updateConsole.__newTaskSyncWrap = true;
  })();

  // --- 7) Track hover class flips to keep FOLD up to date → refresh console
  (function(){
    var root = document.getElementById('builderStage') || document.body;
    if (!root) return;
    var obs = new MutationObserver(function(recs){
      var touch = false;
      for (var r of recs){
        if (r.type!=='attributes' || r.attributeName!=='class') continue;
        var el = r.target; if (!el || !el.classList) continue;
        var id = el.getAttribute('data-uuid') || el.getAttribute('data-short'); if (!window.isNewId(id)) continue;
        var f = ensureFold(id);
        var hadDone = /\bstagedDone\b/.test(r.oldValue||''), hasDone = el.classList.contains('stagedDone');
        var hadDel  = /\bstagedDel\b/.test(r.oldValue||''),  hasDel  = el.classList.contains('stagedDel');
        if (hasDone) f.done = true;  if (hadDone && !hasDone) f.done = false;
        if (hasDel)  f.deleted = true; if (hadDel && !hasDel)  f.deleted = false;
        touch = true;
      }
      if (touch){ try{ setTimeout(updateConsole, 0); }catch(_){} }
    });
    obs.observe(root, {subtree:true, attributes:true, attributeFilter:['class'], attributeOldValue:true});
  })();

  // --- 8) First paint
  try{ reconcileNewStaged(); }catch(_){}
  try{ setTimeout(function(){ if (typeof updateConsole==='function') updateConsole(); }, 0); }catch(_){}
  console.log('[new-task-console-sync] v2.2 active');
})();</script>

""".strip("\n")

    if JS_ID not in html:
        html = html.replace("</body>", js + "\n</body>")
    return html


def inject_console_hotkey_patch(html: str) -> str:
    JS_ID = "FEATURE_CONSOLE_HOTKEY_PATCH_V4"
    js = r"""
<script id="FEATURE_CONSOLE_HOTKEY_PATCH_V4">(function(){
  if (window.__HOTKEY_PATCH_V4__) return; window.__HOTKEY_PATCH_V4__ = true;

  var BYPASS = false; // let our synthetic events through

  function isKeyD(ev){
    return (ev.key||'').toLowerCase() === 'd';
  }
  function isAllowedCombo(ev){
    // ONLY Ctrl+Shift+D (or Cmd+Shift+D); Alt must NOT be pressed
    return isKeyD(ev) && ev.shiftKey && (ev.ctrlKey || ev.metaKey) && !ev.altKey;
  }

  // Block any 'd' / 'D' that is NOT the allowed combo.
  function makeBlocker(){
    return function(ev){
      if (BYPASS) return;              // let our synthetic press pass
      if (!isKeyD(ev)) return;         // not D/d
      if (isAllowedCombo(ev)) return;  // allow the combo (we’ll remap below)
      // Stop reaching legacy handlers everywhere (capture), but don't preventDefault,
      // so typing still inserts the character in inputs/textareas.
      ev.stopImmediatePropagation();
    };
  }

  var blocker = makeBlocker();

  // Install capture blockers on all key roots and all phases
  var targets = [window, document];
  try { targets.push(document.documentElement); } catch(_) {}
  try { targets.push(document.body); } catch(_) {}
  ['keydown','keypress','keyup'].forEach(function(type){
    targets.forEach(function(t){
      try { t.addEventListener(type, blocker, true); } catch(_) {}
    });
  });

  // Remap Ctrl/Cmd+Shift+D → synthesize one 'd' sequence so the old toggle still works
  function onRemap(ev){
    if (!isAllowedCombo(ev)) return;
    ev.preventDefault();
    ev.stopImmediatePropagation();
    BYPASS = true;
    try{
      var opts = {bubbles:true};
      document.dispatchEvent(new KeyboardEvent('keydown',  Object.assign({key:'d', code:'KeyD'}, opts)));
      document.dispatchEvent(new KeyboardEvent('keypress', Object.assign({key:'d', code:'KeyD'}, opts)));
      document.dispatchEvent(new KeyboardEvent('keyup',    Object.assign({key:'d', code:'KeyD'}, opts)));
    } finally {
      setTimeout(function(){ BYPASS = false; }, 0);
    }
  }
  // Listen early so we own the combo
  window.addEventListener('keydown', onRemap, true);

  console.log('[hotkey] ONLY Ctrl+Shift+D toggles console; plain/Shift D suppressed');
})();</script>
""".strip("\n")

    if JS_ID not in html:
        html = html.replace("</body>", js + "\n</body>")
    return html


def inject_staged_deps_color_split(html: str) -> str:
    CSS = r"""
<style id="PATCH_STAGED_LINE_ANIM_V1">
/* Animate staged dependency lines in red and remove arrows */
@keyframes energyFlow {
  from { stroke-dashoffset: 48; }
  to   { stroke-dashoffset: 0; }
}

/* EXISTING/STAGED edges (completed dependencies) - RED */
#builderLinks path.dep-edge.existing,
#builderLinks line.dep-edge.existing,
#builderLinks path.link-existing,
#builderLinks line.link-existing,
#depExistingEdges path,
#depExistingEdges line,
path.dep-edge.staged,
line.dep-edge.staged,
path.existing[class*="dep"],
line.existing[class*="dep"] {
  stroke: #ec4899 !important;  /* Pink */
  filter: drop-shadow(0 0 3px rgba(236,72,153,.70)) !important;
  stroke-width: 2.25px !important;
  fill: none !important;
  stroke-linecap: round !important;
  stroke-linejoin: round !important;
  stroke-dasharray: 6 6 !important;
  animation: energyFlow 900ms linear infinite !important;
  marker-end: none !important;
  filter: drop-shadow(0 0 3px rgba(239,68,68,.70)) !important;
}

/* STAGING edges (preview while dragging) - BLUE - keep existing system */
#builderStage path.staged-energy-edge,
#builderStage line.staged-energy-edge {
  stroke: #60a5fa !important;
  stroke-width: 2.25px !important;
  fill: none !important;
  stroke-linecap: round !important;
  stroke-linejoin: round !important;
  stroke-dasharray: 6 6 !important;
  animation: energyFlow 900ms linear infinite !important;
  marker-end: none !important;
  filter: drop-shadow(0 0 3px rgba(96,165,250,.70)) !important;
}

/* Hide dots in staging area */
#builderStage circle,
#builderStage .energy-dot,
#builderStage .pulse-dot {
  display: none !important;
}
</style>
""".strip()

    JS = r"""
<script id="PATCH_STAGED_LINE_ANIM_JS_V1">(function(){
  if (window.__PATCH_STAGED_LINE_ANIM__) return; window.__PATCH_STAGED_LINE_ANIM__ = true;

  // Process EXISTING/STAGED edges (RED) - completed dependencies
  function restyleExistingEdges(root){
    var r = root || document;
    var existingSelectors = [
      '#builderLinks path.dep-edge.existing',
      '#builderLinks line.dep-edge.existing',
      '#builderLinks path.link-existing',
      '#builderLinks line.link-existing',
      '#depExistingEdges path',
      '#depExistingEdges line',
      'path.dep-edge.staged',
      'line.dep-edge.staged',
      'path.existing[class*="dep"]',
      'line.existing[class*="dep"]'
    ];
    
    existingSelectors.forEach(function(sel){
      r.querySelectorAll(sel).forEach(function(el){
        // Skip if this is in the staging area (preview)
        if (el.closest('#builderStage')) return;
        
        // Remove arrow marker
        if (el.getAttribute('marker-end')) el.removeAttribute('marker-end');
        
        // Ensure fill is none for proper stroke rendering
        if (el.getAttribute('fill') !== 'none') el.setAttribute('fill','none');
        
        // Force RED stroke-dasharray
        el.style.strokeDasharray = '6 6';
        el.style.animation = 'energyFlow 900ms linear infinite';
        
        // Mark as processed
        el.setAttribute('data-existing-animated', 'true');
      });
    });
  }

  // DON'T touch staging edges - let the existing __ENERGY_ARROW_JS__ handle them
  // Just ensure their marker-end is removed if present
  function ensureStagingNoArrows(root){
    var r = root || document;
    r.querySelectorAll('#builderStage path, #builderStage line').forEach(function(el){
      if (el.getAttribute('marker-end')) el.removeAttribute('marker-end');
    });
  }

  function restyleAll(){
    try{ 
      restyleExistingEdges(document);
      ensureStagingNoArrows(document);
    }catch(_){}
  }

  var __restyleScheduled = false;
  function scheduleRestyle(delay){
    if (__restyleScheduled) return;
    __restyleScheduled = true;
    setTimeout(function(){
      __restyleScheduled = false;
      if (document.hidden) return;
      restyleAll();
    }, delay || 10);
  }

  // Hook common renderers
  ['drawLinks','renderStagedOverlay','renderDepsOverlay','__depsOverlayRender','updateLinks','redrawLinks'].forEach(function(name){
    var fn = window[name];
    if (typeof fn === 'function' && !fn.__stagedAnimWrap){
      var orig = fn;
      window[name] = function(){
        var rv = orig.apply(this, arguments);
        scheduleRestyle(10);
        return rv;
      };
      window[name].__stagedAnimWrap = true;
    }
  });

  // Periodic sweep (low frequency; hidden tabs do no work)
  setInterval(function(){
    if (document.hidden) return;
    restyleAll();
  }, 900);

  // Watch for DOM changes
  try {
    var observer = new MutationObserver(function(mutations){
      var shouldRestyle = false;
      mutations.forEach(function(mut){
        if (mut.type === 'childList' && mut.addedNodes.length > 0) {
          shouldRestyle = true;
        }
      });
      if (shouldRestyle) {
        scheduleRestyle(10);
      }
    });
    observer.observe(document.body, {childList: true, subtree: true});
  } catch(_){}

  // Initial passes
  scheduleRestyle(10);
  scheduleRestyle(100);
  scheduleRestyle(500);
  scheduleRestyle(1000);
})();</script>
""".strip()

    if 'id="STAGED_DEPS_COLOR_SPLIT"' not in html:
        html = re.sub(r'</head>', CSS + '\n</head>', html, count=1, flags=re.I)
    if 'id="STAGED_DEPS_COLOR_SPLIT_JS"' not in html:
        html = re.sub(r'</body>', JS + '\n</body>', html, count=1, flags=re.I)
    return html


def inject_follow_edges_on_move(html: str) -> str:
    JS = r"""
<script id="PATCH_FOLLOW_EDGES_ON_MOVE_V1">(function(){
  if (window.__FOLLOW_EDGES_ON_MOVE_V1__) return; window.__FOLLOW_EDGES_ON_MOVE_V1__ = true;

  function stageRoot(){ return document.getElementById('builderStage') || document.body; }
  function linksRoot(){ return document.getElementById('builderLinks') || document; }
  function px(n){ return (typeof n==='number' && isFinite(n)) ? n : 0; }

  function nodeCenter(node){
    var st = stageRoot();
    var nb = node.getBoundingClientRect();
    var sb = st.getBoundingClientRect ? st.getBoundingClientRect() : {left:0,top:0};
    var x = nb.left - sb.left + nb.width/2;
    var y = nb.top  - sb.top  + nb.height/2;
    return {x: px(x), y: px(y)};
  }
  function findNodeById(id){
    if (!id) return null;
    var sel = `[data-short="${CSS.escape(id)}"], [data-uuid="${CSS.escape(id)}"]`;
    return stageRoot().querySelector(sel);
  }
  function cubicPath(p1, p2){
    var dx = Math.max(40, Math.abs(p2.x - p1.x) * 0.5);
    var c1 = {x: p1.x + dx, y: p1.y};
    var c2 = {x: p2.x - dx, y: p2.y};
    return `M ${p1.x} ${p1.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${p2.x} ${p2.y}`;
  }

  function recomputeEdge(el){
    try{
      var from = el.getAttribute('data-from');
      var to   = el.getAttribute('data-to');
      if (!from || !to) return;
      var n1 = findNodeById(from), n2 = findNodeById(to);
      if (!n1 || !n2) return;

      var p1 = nodeCenter(n1), p2 = nodeCenter(n2);

      if (el.tagName.toLowerCase() === 'line'){
        el.setAttribute('x1', p1.x); el.setAttribute('y1', p1.y);
        el.setAttribute('x2', p2.x); el.setAttribute('y2', p2.y);
      } else {
        el.setAttribute('d', cubicPath(p1,p2));
        el.setAttribute('fill','none');
      }
      // No arrows on staged/animated dashes
      el.removeAttribute('marker-end');
    }catch(_){}
  }

  function recomputeAll(){
    var root = linksRoot();
    var sel = [
      '#builderLinks path[data-from][data-to]',
      '#builderLinks line[data-from][data-to]',
      'svg path[data-from][data-to]',
      'svg line[data-from][data-to]'
    ].join(',');
    root.querySelectorAll(sel).forEach(recomputeEdge);
  }

  var raf = 0, queued = false;
  function scheduleRecompute(){
    if (queued) return;
    queued = true;
    if (raf) cancelAnimationFrame(raf);
    raf = requestAnimationFrame(function(){ queued = false; recomputeAll(); });
  }

  // Hook your common render/link functions
  ;['drawLinks','renderStagedOverlay','renderDepsOverlay','__depsOverlayRender',
    'updateLinks','redrawLinks'].forEach(function(name){
    var fn = window[name];
    if (typeof fn === 'function' && !fn.__followEdgesWrap){
      var orig = fn;
      window[name] = function(){ var rv = orig.apply(this, arguments); scheduleRecompute(); return rv; };
      window[name].__followEdgesWrap = true;
    }
  });

  // Observe node pos/cls changes
  try{
    var mo = new MutationObserver(function(list){
      for (var m of list){
        if (m.type === 'attributes' && m.target && m.target.classList && m.target.classList.contains('node')){
          scheduleRecompute(); break;
        }
      }
    });
    mo.observe(stageRoot(), {subtree:true, attributes:true, attributeFilter:['style','transform','class']});
  }catch(_){}

  // Drag feedback
  var dragging = false;
  document.addEventListener('mousedown', function(ev){
    if (ev.target && (ev.target.closest('.node') || ev.target.classList.contains('node'))){ dragging = true; }
  }, true);
  document.addEventListener('mouseup', function(){ dragging = false; scheduleRecompute(); }, true);
  document.addEventListener('mousemove', function(){ if (dragging) scheduleRecompute(); }, true);

  // App refresh signal
  document.addEventListener('twdata', function(){ scheduleRecompute(); });

  // Initial passes
  scheduleRecompute();
  setTimeout(scheduleRecompute, 80);
  setTimeout(scheduleRecompute, 300);
})();</script>
""".strip()

    if 'id="PATCH_FOLLOW_EDGES_ON_MOVE_V1"' not in html:
        html = re.sub(r'</body>', JS + '\n</body>', html, count=1, flags=re.I)
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
    js = r"""
<script id="FEATURE_LAYOUT_PERSIST_V1">
(function(){
  if (window.__LAYOUT_PERSIST_V1__) return; window.__LAYOUT_PERSIST_V1__ = true;

  var PREFIX = "taskcanvas:layout:v1:";
  var lastSerialized = null;
  var restored = false;
  var saveTimer = 0;

  function hasTasks(){
    return !!(window.TASKS && Array.isArray(window.TASKS) && window.TASKS.length);
  }
  function escAttr(v){
    return String(v || "").replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  }
  function toInt(v, d){
    var n = parseInt(v, 10);
    return isFinite(n) ? n : d;
  }
  function firstTag(t){
    return (t && Array.isArray(t.tags) && t.tags.length) ? t.tags[0] : "(no tag)";
  }
  function fnv1a(text){
    var h = 2166136261 >>> 0;
    for (var i=0; i<text.length; i++){
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return (h >>> 0).toString(16);
  }
  function boardKey(){
    try{
      if (!hasTasks()) return PREFIX + "empty";
      var ids = window.TASKS.map(function(t){
        if (!t) return "";
        return String(t.uuid || t.short || "");
      }).filter(Boolean).sort().join("|");
      return PREFIX + fnv1a(ids);
    }catch(_){
      return PREFIX + "fallback";
    }
  }

  function captureState(){
    var out = {
      version: 1,
      saved_at: Date.now(),
      zoom: 100,
      drawer_collapsed: !!(document.body && document.body.classList && document.body.classList.contains("drawer-collapsed")),
      nodes: {},
      projects: [],
      tags: []
    };

    try{
      var z = document.getElementById("zoom");
      var zv = z ? toInt(z.value, 100) : toInt((window.ZSCALE || 1) * 100, 100);
      out.zoom = Math.max(50, Math.min(200, zv));
    }catch(_){}

    try{
      var nodes = document.querySelectorAll("#builderStage .node");
      for (var i=0; i<nodes.length; i++){
        var n = nodes[i];
        var id = n.getAttribute("data-uuid") || n.getAttribute("data-short");
        if (!id) continue;
        out.nodes[id] = {
          x: toInt(n.style.left, 0),
          y: toInt(n.style.top, 0),
          proj: n.getAttribute("data-proj") || "",
          tag: n.getAttribute("data-tag") || ""
        };
      }
    }catch(_){}

    try{
      if (window.projectAreas && typeof projectAreas.forEach === "function"){
        projectAreas.forEach(function(pa, name){
          if (!pa) return;
          out.projects.push({
            name: String(name || "(no project)"),
            x: toInt(pa.x, 0), y: toInt(pa.y, 0),
            w: toInt(pa.w, 280), h: toInt(pa.h, 120),
            tagCols: toInt(pa.tagCols, 3),
            tagW0: toInt(pa.tagW0, 600),
            tagH0: toInt(pa.tagH0, 220),
            nextTagIndex: toInt(pa.nextTagIndex, 0)
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
            w: toInt(ta.w, 300), h: toInt(ta.h, 180)
          });
        });
      }
    }catch(_){}

    return out;
  }

  function writeState(force){
    try{
      if (!hasTasks()) return;
      var json = JSON.stringify(captureState());
      if (!force && json === lastSerialized) return;
      lastSerialized = json;
      localStorage.setItem(boardKey(), json);
    }catch(_){}
  }

  function scheduleSave(delay){
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(function(){
      saveTimer = 0;
      writeState(false);
    }, Math.max(140, delay || 220));
  }

  function applyAreaMaps(state){
    if (!state || !Array.isArray(state.projects) || !Array.isArray(state.tags)) return false;
    if (!state.projects.length) return false;
    try{
      var projMap = new Map();
      for (var i=0; i<state.projects.length; i++){
        var p = state.projects[i] || {};
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
      var tagMap = new Map();
      var cols = (window.LAYOUT && toInt(window.LAYOUT.COLS, 2)) || 2;
      var head = (window.LAYOUT && toInt(window.LAYOUT.TAG_HEAD, 40)) || 40;
      var pad = (window.LAYOUT && toInt(window.LAYOUT.TAG_PAD, 10)) || 10;
      for (var j=0; j<state.tags.length; j++){
        var t = state.tags[j] || {};
        var project = String(t.project || "(no project)");
        var tag = String(t.tag || "(no tag)");
        var x = toInt(t.x, 0), y = toInt(t.y, 0);
        tagMap.set(project + "||" + tag, {
          x: x, y: y,
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
      if (typeof recomputeAreasAndTags === "function") recomputeAreasAndTags();
      return true;
    }catch(_){
      return false;
    }
  }

  function applyNodePositions(state){
    if (!state || !state.nodes || typeof state.nodes !== "object") return false;
    var applied = false;
    var ids = Object.keys(state.nodes);
    for (var i=0; i<ids.length; i++){
      var id = ids[i];
      var n = document.querySelector(
        '#builderStage .node[data-uuid="' + escAttr(id) + '"], ' +
        '#builderStage .node[data-short="' + escAttr(id) + '"]'
      );
      if (!n) continue;
      var r = state.nodes[id] || {};
      var x = toInt(r.x, NaN), y = toInt(r.y, NaN);
      if (isFinite(x) && isFinite(y)){
        n.style.left = x + "px";
        n.style.top = y + "px";
        applied = true;
      }

      var proj = String(r.proj || n.getAttribute("data-proj") || "(no project)");
      var tag = String(r.tag || n.getAttribute("data-tag") || "(no tag)");
      n.setAttribute("data-proj", proj);
      n.setAttribute("data-tag", tag);

      var short = n.getAttribute("data-short");
      var t = (short && window.TASK_BY_SHORT && TASK_BY_SHORT[short]) || null;
      if (!t && window.TASKS && Array.isArray(TASKS)){
        for (var k=0; k<TASKS.length; k++){
          var it = TASKS[k];
          if (!it) continue;
          if (String(it.uuid || "") === String(id) || String(it.short || "") === String(id)){
            t = it; break;
          }
        }
      }
      if (t){
        t.project = proj;
        t.tags = (tag && tag !== "(no tag)") ? [tag] : [];
      }
      var cap = n.querySelector(".caption");
      if (cap) cap.textContent = proj + " • " + tag;
    }
    return applied;
  }

  function applyState(state){
    if (!state || typeof state !== "object") return false;
    var touched = false;

    try{
      var zv = toInt(state.zoom, 100);
      if (zv >= 50 && zv <= 200){
        var z = document.getElementById("zoom");
        if (z) z.value = String(zv);
        if (typeof applyZoom === "function") applyZoom();
      }
    }catch(_){}

    if (applyAreaMaps(state)) touched = true;
    if (applyNodePositions(state)) touched = true;

    try{
      if (state.drawer_collapsed && typeof collapseDrawer === "function"){
        collapseDrawer();
      }
    }catch(_){}

    try{ if (typeof drawLinks === "function") drawLinks(); }catch(_){}
    try{ if (typeof refreshDepHandleLetters === "function") refreshDepHandleLetters(); }catch(_){}
    try{ if (typeof updateConsole === "function") updateConsole(); }catch(_){}
    return touched;
  }

  function readState(){
    try{
      var raw = localStorage.getItem(boardKey());
      if (!raw) return null;
      return JSON.parse(raw);
    }catch(_){
      return null;
    }
  }

  function tryRestore(){
    if (restored || !hasTasks()) return;
    var state = readState();
    if (!state){
      restored = true;
      return;
    }
    if (applyState(state)) restored = true;
  }

  function wrapForAutosave(name){
    var fn = window[name];
    if (typeof fn !== "function" || fn.__layoutPersistWrap) return;
    var orig = fn;
    window[name] = function(){
      var rv = orig.apply(this, arguments);
      scheduleSave(260);
      return rv;
    };
    window[name].__layoutPersistWrap = true;
  }

  function install(){
    if (window.__layoutPersistInstalled) return;
    window.__layoutPersistInstalled = true;

    [
      "addNodeForTask",
      "recomputeAreasAndTags",
      "relayoutTag",
      "resolveTagOverlaps",
      "resolveProjectOverlaps",
      "drawLinks"
    ].forEach(wrapForAutosave);

    try{
      var zoom = document.getElementById("zoom");
      if (zoom && !zoom.__layoutPersistBound){
        zoom.__layoutPersistBound = true;
        zoom.addEventListener("input", function(){ scheduleSave(120); });
      }
    }catch(_){}

    document.addEventListener("mouseup", function(){ scheduleSave(260); }, true);
    document.addEventListener("touchend", function(){ scheduleSave(260); }, true);
    document.addEventListener("twdata", function(){
      setTimeout(tryRestore, 90);
      setTimeout(tryRestore, 420);
      setTimeout(function(){ scheduleSave(0); }, 800);
    });
    window.addEventListener("beforeunload", function(){ writeState(true); });
    document.addEventListener("visibilitychange", function(){
      if (document.hidden) writeState(true);
    });

    try{
      var stage = document.getElementById("builderStage") || document.body;
      var mo = new MutationObserver(function(muts){
        for (var i=0; i<muts.length; i++){
          var m = muts[i];
          if (m.type === "attributes" || m.type === "childList"){
            scheduleSave(320);
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

    setInterval(function(){
      if (!document.hidden) writeState(false);
    }, 3200);

    setTimeout(tryRestore, 120);
    setTimeout(tryRestore, 600);
  }

  install();
})();
</script>
""".strip()

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
    """
    js = r"""
<script id="FEATURE_COMMAND_PREFLIGHT_V1">
(function(){
  if (window.__CMD_PREFLIGHT_V1__) return; window.__CMD_PREFLIGHT_V1__ = true;

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
    return { text: out.join('\n'), warnings: warnings };
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
