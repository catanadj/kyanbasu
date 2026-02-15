from collections.abc import Callable

from taskcanvas.injectors import (
    _append_remove_mode,
    inject_actionable_beacon,
    inject_command_preflight,
    inject_console_hotkey_patch,
    inject_energy_arrows,
    inject_follow_edges_on_move,
    inject_hover_console_features,
    inject_multiline_add,
    inject_newtask_console_sync,
    inject_staged_deps_color_split,
    inject_wire_deps_as_main,
)


def build_runtime_html(
    base_html: str,
    json_text: str,
    tasks_count: int,
    log_fn: Callable[[str], None],
) -> str:
    html = base_html.replace("<!-- INLINE_PAYLOAD_HERE -->", "")
    safe_json = json_text.replace("</script", "<\/script")
    payload_tag = ("<script id='payload_data' type='application/json'>" + safe_json + "</script>\n")
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
    html = html.replace("</body>", payload_tag + runner + "</body>")
    
    # --- Feature: hover actions + staging & due badge (inline) ---
    CSS_HOVER = r'''<style id="feature-hover-css">
      .node:hover .nodeActions{opacity:1; pointer-events:auto}
      .nodeActions{position:absolute; right:6px; bottom:6px; display:flex; gap:6px; opacity:0; pointer-events:none;}
      .nodeActions button{border:1px solid #2a3344; background:#1b2230; color:var(--fg); border-radius:8px; padding:2px 6px; font-size:12px; cursor:pointer}
      .stagedDone{ outline:2px solid rgba(34,197,94,.95); box-shadow:0 0 0 5px rgba(34,197,94,.24) inset; background:linear-gradient(180deg, rgba(34,197,94,.10), rgba(34,197,94,.06)); }
      .stagedDel{ outline:4px solid #ef4444; box-shadow:0 0 0 7px rgba(239,68,68,.34) inset; background:linear-gradient(180deg, rgba(239,68,68,.28), rgba(239,68,68,.14)); }
      .stagedDone .title, .stagedDel .title{ text-decoration:line-through; opacity:.94 }
    </style>'''
    
    JS_HOVER = r'''<script id="FEATURE_HOVERSTAGE">(function(){
      if (window.__FEATURE_HOVERSTAGE__) return; window.__FEATURE_HOVERSTAGE__=true;
      function ensureArrays(){ if(!window.STAGED_CMDS) window.STAGED_CMDS=[]; if(!window.STAGED_HUMAN) window.STAGED_HUMAN=[]; }
      function removeFrom(arr, pred){ var out=[],removed=false; for(var i=0;i<arr.length;i++){ if(pred(arr[i],i)) removed=true; else out.push(arr[i]); } return {out:out, removed:removed}; }
      function stageAdd(cmd, human){ ensureArrays(); window.STAGED_CMDS.push(cmd); window.STAGED_HUMAN.push(human); try{updateConsole();}catch(_){}} 
      function stageToggle(node, task, kind){
        ensureArrays();
        var uid = (task && task.uuid) || (node && node.getAttribute('data-uuid')) || (node && node.getAttribute('data-short')) || '';
        var short = (task && task.short) || (node && node.getAttribute('data-short')) || 'task';
        var desc = (task && task.desc) || ((node && node.querySelector('.title'))? node.querySelector('.title').textContent : '');
        var cmd = 'task '+uid+' '+(kind==='done'?'done':'delete');
        var human = (kind==='done'?'DONE ':'DELETE ') + short + ' — ' + desc;
        var cls = (kind==='done'?'stagedDone':'stagedDel');
        if (!node) return;
        if (node.classList.contains(cls)){
          var res1 = removeFrom(window.STAGED_CMDS,  function(s){ return s===cmd; });
          var res2 = removeFrom(window.STAGED_HUMAN, function(s){ return s===human; });
          window.STAGED_CMDS = res1.out; window.STAGED_HUMAN = res2.out;
          node.classList.remove(cls);
        } else {
          window.STAGED_CMDS.push(cmd); window.STAGED_HUMAN.push(human); node.classList.add(cls);
          var other = (kind==='done'?'stagedDel':'stagedDone');
          if (node.classList.contains(other)){
            node.classList.remove(other);
            var cmdOther = 'task '+uid+' '+(kind==='done'?'delete':'done');
            var humanOther = (kind==='done'?'DELETE ':'DONE ') + short + ' — '+ desc;
            window.STAGED_CMDS = removeFrom(window.STAGED_CMDS,  function(s){ return s===cmdOther; }).out;
            window.STAGED_HUMAN = removeFrom(window.STAGED_HUMAN, function(s){ return s===humanOther; }).out;
          }
        }
        try{ updateConsole(); }catch(_){}
      }
      function findTaskByShort(short){
        try{ if (window.TASKS){ for(var i=0;i<TASKS.length;i++){ if(TASKS[i].short===short) return TASKS[i]; } } }catch(_){}
        return null;
      }
      function installHoverForNode(node, task){
        if (!node || node.querySelector('.nodeActions')) return;
        var bar = document.createElement('div'); bar.className='nodeActions';
        bar.innerHTML = '<button class="btnDone" title="Mark done">✓</button>'
                      + '<button class="btnDel" title="Delete">🗑</button>'
                      + '<button class="btnMod" title="Modify">✎</button>';
        node.appendChild(bar);
        var t = task;
        if (!t){
          var short = node.getAttribute('data-short');
          t = findTaskByShort(short) || { uuid: (node.getAttribute('data-uuid')||short), short: short||'task', desc: ((node.querySelector('.title')||{}).textContent||'') };
        }
        var b1 = bar.querySelector('.btnDone'); if(b1){ b1.addEventListener('click', function(e){ e.stopPropagation(); stageToggle(node, t, 'done'); }); }
        var b2 = bar.querySelector('.btnDel');  if(b2){ b2.addEventListener('click', function(e){ e.stopPropagation(); stageToggle(node, t, 'delete'); }); }
        var b3 = bar.querySelector('.btnMod');  if(b3){ b3.addEventListener('click', function(e){ e.stopPropagation(); var mods=prompt('Modifiers (e.g., pri:H due:2025-09-20 +tag -oldtag):',''); if(mods==null) return; mods=mods.trim(); if(!mods) return; stageAdd('task '+t.uuid+' modify '+mods, 'MODIFY '+t.short+' — '+mods); }); }
      }
      function attachDataAttributes(){
        try{
          var nodes = document.querySelectorAll('.node');
          for (var i=0;i<nodes.length;i++){
            var n=nodes[i];
            if (!n.getAttribute('data-short')){
              var guess = n.getAttribute('data-id') || n.getAttribute('data-key') || (n.querySelector('.short')||{}).textContent || '';
              if (guess) n.setAttribute('data-short', guess);
            }
            if (!n.getAttribute('data-uuid')){
              var srt = n.getAttribute('data-short');
              var t = srt && findTaskByShort(srt);
              if (t) n.setAttribute('data-uuid', t.uuid);
            }
          }
        }catch(_){}
      }
      (function(){
        if (!window.__HOVERSTAGE_NODE_WRAP__ && typeof window.addNodeForTask === 'function'){
          window.__HOVERSTAGE_NODE_WRAP__ = true;
          var old = window.addNodeForTask;
          window.addNodeForTask = function(task, cx, cy, opts){
            var n = old.apply(this, arguments);
            try{
              if (n && task){
                if (!n.getAttribute('data-uuid') && task.uuid) n.setAttribute('data-uuid', task.uuid);
                if (!n.getAttribute('data-short') && task.short) n.setAttribute('data-short', task.short);
              }
            }catch(_){}
            try{ installHoverForNode(n, task); }catch(_){}
            return n;
          };
        }
      })();
      function wrapUpdateConsoleLate(){
        try{
          if (window.__HOVERSTAGE_WRAP_UPDATE__) return;
          if (typeof window.updateConsole !== 'function') return;
          if (window.updateConsole && window.updateConsole.__hoverstageWrapped) return;
          var orig = window.updateConsole;
          function wrapper(){
            var rv = orig.apply(this, arguments);
            try{
              var ct = document.getElementById('consoleText');
              if (ct){
                var base = ct.value || '';
                var staged = (window.STAGED_CMDS||[]).join('\\n');
                if (staged){
                  if (base.indexOf(staged)!==0){
                    ct.value = staged + (base? '\\n'+base : '');
                  }
                }
              }
            }catch(_){}
            return rv;
          }
          wrapper.__hoverstageWrapped = true;
          window.updateConsole = wrapper;
          window.__HOVERSTAGE_WRAP_UPDATE__ = true;
          try{ window.updateConsole(); }catch(_){}
        }catch(_){}
      }
      function kick(){
        try{ attachDataAttributes(); }catch(_){}
        try{
          var nodes=document.querySelectorAll('.node');
          for (var i=0;i<nodes.length;i++){ installHoverForNode(nodes[i], null); }
        }catch(_){}
        try{ wrapUpdateConsoleLate(); }catch(_){}
      }
      document.addEventListener('twdata', function(){ setTimeout(kick, 0); });
      window.addEventListener('load', function(){ setTimeout(kick, 60); });
      var oldRe = window.recomputeAreasAndTags;
      if (typeof oldRe === 'function'){
        window.recomputeAreasAndTags = function(){
          var r = oldRe.apply(this, arguments);
          try{ kick(); }catch(_){}
          return r;
        };
      }
    })();</script>'''
    
    CSS_DUE = r'''<style id="feature-due-css-v2">
      .node.hasDue{ padding-top: 28px; }
      .dueBadge{
        position:absolute; left:6px !important; top:4px !important; bottom:auto !important;
        display:inline-flex; align-items:center; gap:6px;
        padding:2px 6px; border-radius:8px; font-size:12px;
        border:1px solid #3a4456; background:rgba(58,68,86,.18); color:#cfd8e3;
        pointer-events:none; user-select:none; z-index:2;
      }
      .dueBadge .clock{font-size:12px; opacity:.9}
      .dueOverdue{ border-color:#ef4444; background:rgba(239,68,68,.16); color:#fecaca; }
      .dueSoon{ border-color:#f59e0b; background:rgba(245,158,11,.14); color:#fde68a; }
      .dueFuture{ opacity:.9 }
    </style>'''
    
    JS_DUE = r'''<script id="FEATURE_DUEBADGE2">(function(){
      if (window.__FEATURE_DUEBADGE2__) return; window.__FEATURE_DUEBADGE2__=true;
      function tasksArray(){
        try{
          if (window.DATA && Array.isArray(window.DATA.tasks)) return window.DATA.tasks;
          if (Array.isArray(window.TASKS)) return window.TASKS;
        }catch(_){}
        return [];
      }
      function taskByShort(s){
        var arr = tasksArray();
        for (var i=0;i<arr.length;i++) if (arr[i].short===s) return arr[i];
        return null;
      }
      function parseTWDue(s){
        if (!s || typeof s!=='string') return null;
        try{
          var m;
          if ((m = s.match(/^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})Z)?$/))){
            var Y=+m[1], M=+m[2]-1, D=+m[3], h=+(m[4]||'0'), mi=+(m[5]||'0'), se=+(m[6]||'0');
            if (m[4]) return new Date(Date.UTC(Y,M,D,h,mi,se));
            return new Date(Y, M, D, 0, 0, 0);
          }
          if ((m = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2}))?Z)?$/))){
            var Y=+m[1], M=+m[2]-1, D=+m[3], h=+(m[4]||'0'), mi=+(m[5]||'0'), se=+(m[6]||'0');
            if (m[4]) return new Date(Date.UTC(Y,M,D,h,mi,se));
            return new Date(Y, M, D, 0, 0, 0);
          }
          var d = new Date(s);
          if (!isNaN(d.getTime())) return d;
        }catch(_){}
        return null;
      }
      function pad(n){ return (n<10?'0':'')+n; }
      function fmtLocal(dt){
        try{
          return dt.getFullYear()+'-'+pad(dt.getMonth()+1)+'-'+pad(dt.getDate())+' '+pad(dt.getHours())+':'+pad(dt.getMinutes());
        }catch(_){ return '—'; }
      }
      function deltaString(due){
        var now = new Date();
        var ms = now.getTime() - due.getTime(); // overdue -> positive
        var sign = ms>=0 ? '+' : '-';
        var abs = Math.abs(ms);
        var mins = Math.floor(abs/60000);
        var txt;
        if (mins >= 1440){
          txt = Math.round(mins/1440) + 'd';
        } else if (mins >= 60){
          txt = Math.round(mins/60) + 'h';
        } else {
          txt = mins + 'm';
        }
        return { sign: sign, text: sign+txt, ms: ms };
      }
      function classForDelta(ms){
        if (ms >= 0) return 'dueOverdue';
        if (Math.abs(ms) <= 72*3600*1000) return 'dueSoon';
        return 'dueFuture';
      }
      function ensureDueBadgeTop(node, task){
        try{
          if (!node) return;
          var t = task || (function(){ var s = node.getAttribute('data-short'); return taskByShort(s); })();
          if (!t || !t.due) { node.classList.remove('hasDue'); return; }
          var due = parseTWDue(String(t.due));
          if (!due) { node.classList.remove('hasDue'); return; }
          var info = deltaString(due);
          var existing = node.querySelector('.dueBadge');
          var cls = classForDelta(info.ms);
          var label = '⏰';
          if (!existing){
            var b = document.createElement('div');
            b.className = 'dueBadge '+cls;
            b.innerHTML = '<span class="clock">'+label+'</span>'
                        + '<span class="when">'+fmtLocal(due)+'</span>'
                        + '<span class="delta">· '+info.text+'</span>';
            node.insertBefore(b, node.firstChild);
          } else {
            existing.classList.remove('dueOverdue','dueSoon','dueFuture');
            existing.classList.add(cls);
            var w = existing.querySelector('.when'), d = existing.querySelector('.delta');
            if (w) w.textContent = fmtLocal(due);
            if (d) d.textContent = '· '+info.text;
            if (existing.previousSibling){ try{ node.insertBefore(existing, node.firstChild); }catch(_){} }
          }
          node.classList.add('hasDue');
        }catch(e){}
      }
      (function(){
        if (!window.__DUE_NODE_WRAP2__ && typeof window.addNodeForTask === 'function'){
          window.__DUE_NODE_WRAP2__ = true;
          var old = window.addNodeForTask;
          window.addNodeForTask = function(task, cx, cy, opts){
            var n = old.apply(this, arguments);
            try{ ensureDueBadgeTop(n, task); }catch(_){}
            return n;
          };
        }
      })();
      function runAll(){ try{ var nodes=document.querySelectorAll('.node'); for (var i=0;i<nodes.length;i++) ensureDueBadgeTop(nodes[i], null); }catch(_){}}  
      document.addEventListener('twdata', function(){ setTimeout(runAll, 0); });
      window.addEventListener('load', function(){ setTimeout(runAll, 60); });
      var oldRe = window.recomputeAreasAndTags;
      if (typeof oldRe === 'function'){
        window.recomputeAreasAndTags = function(){
          var r = oldRe.apply(this, arguments);
          try{ runAll(); }catch(_){}
          return r;
        };
      }
    })();</script><script id="FEATURE_UNIFIED_ACTIONS_V1">(function(){
      if (window.__FEATURE_UNIFIED_ACTIONS_V1__) return; window.__FEATURE_UNIFIED_ACTIONS_V1__=true;
    
      // ===== utils =====
      function isNewId(u){ u=String(u||''); return /^new-/.test(u) || /^n-/.test(u); }
      function uuidFromNode(nd){
    if (!nd) return null;
    var u = nd.getAttribute && nd.getAttribute('data-uuid'); if (u) return u;
    var s = nd.getAttribute && nd.getAttribute('data-short'); if (s) return s;
    return null;
      }
      function firstTag(t){
    if (!t || !Array.isArray(t.tags) || !t.tags.length) return "(no tag)";
    return t.tags[0] || "(no tag)";
      }
      function oldTagOf(t){ try{ return (window.INIT_MAIN_TAG && INIT_MAIN_TAG[t.short]) || "(no tag)"; }catch(_){ return "(no tag)"; } }
      function oldProjOf(t){ try{ return (window.INIT_PROJECT && INIT_PROJECT[t.short]) || "(no project)"; }catch(_){ return "(no project)"; } }
      function taskById(id){
    id = String(id||'');
    if (!Array.isArray(window.TASKS)) return null;
    for (var i=0;i<TASKS.length;i++){
      var t = TASKS[i]; if (!t) continue;
      if (String(t.uuid||'')===id) return t;
      if (String(t.short||'')===id) return t;
    }
    return null;
      }
      function genToken(){
    try{ return (Date.now().toString(36)+Math.random().toString(36).slice(2,8)).toLowerCase().replace(/[^a-z0-9]/g,''); }
    catch(_){ return String(Math.random()).slice(2,10); }
      }
      function newIdPair(){ var t=genToken(); return {uuid:'new-'+t, short:'n-'+t}; }
    
      // ===== ensure unique & synced ids for new tasks =====
      function rekeySync(){
    try{
      var dNew = Array.prototype.slice.call(document.querySelectorAll('.node'))
        .filter(function(nd){ return isNewId(uuidFromNode(nd)); });
      var tNew = Array.isArray(window.TASKS) ? TASKS.filter(function(t){ return isNewId(t && (t.uuid||t.short)); }) : [];
      if (!dNew.length && !tNew.length) return;
      var used = Object.create(null);
      function claim(id){ if (id) used[id]=1; }
      dNew.forEach(function(nd){ claim(uuidFromNode(nd)); });
      tNew.forEach(function(t){ claim(t.uuid); claim(t.short); });
      var n = Math.min(dNew.length, tNew.length);
      for (var i=0;i<n;i++){
        var nd = dNew[i], t = tNew[i];
        var nid = uuidFromNode(nd);
        var tid = String(t.uuid||t.short||'');
        var need = (!isNewId(nid) || !isNewId(tid) || nid!==tid || used[nid]>1 || used[tid]>1);
        if (need){
          var pair, tries=0;
          do{ pair = newIdPair(); tries++; } while((used[pair.uuid] || used[pair.short]) && tries<50);
          nd.setAttribute('data-uuid', pair.uuid);
          nd.setAttribute('data-short', pair.short);
          t.uuid = pair.uuid; t.short = pair.short;
          claim(pair.uuid); claim(pair.short);
        }
        if (!nd.hasAttribute('data-created-ts')) nd.setAttribute('data-created-ts', String(Date.now()-i));
      }
    }catch(_){}
      }
      setInterval(function(){
    if (document.hidden) return;
    rekeySync();
      }, 700);
      document.addEventListener('visibilitychange', function(){
    if (!document.hidden) setTimeout(rekeySync, 30);
      });
      window.addEventListener('load', function(){ setTimeout(rekeySync, 140); });
    
      // ===== state =====
      var FOLD = window.__FOLD_STATE__ || Object.create(null);  // for new tasks
      window.__FOLD_STATE__ = FOLD;
      var EX_OPS = window.__EXISTING_OPS__ || Object.create(null); // for existing tasks
      window.__EXISTING_OPS__ = EX_OPS;
    
      function ensureFold(id){
    var t = taskById(id); if (!t) return null;
    return FOLD[t.uuid] || (FOLD[t.uuid] = {extra:[]});
      }
      function ensureOps(id){
    return EX_OPS[id] || (EX_OPS[id] = {done:false, deleted:false, mods:[]});
      }
    
      // ===== apply modifiers to new tasks =====
      function applyModsToNew(id, modStr){
    var t = taskById(id); if (!t) return;
    var f = ensureFold(id); if (!f) return;
    var toks = String(modStr||'').trim().split(/\s+/);
    for (var i=0;i<toks.length;i++){
      var tk = toks[i]; if (!tk) continue;
      if (tk[0]==='+'){
        var tag = tk.slice(1);
        if (tag && tag!=='(no tag)'){
          t.tags = Array.isArray(t.tags) ? t.tags : [];
          if (t.tags.indexOf(tag)===-1) t.tags.push(tag);
        }
        continue;
      }
      if (tk[0]==='-'){
        var tag2 = tk.slice(1);
        if (Array.isArray(t.tags)){ t.tags = t.tags.filter(function(x){ return x!==tag2; }); }
        continue;
      }
      var kv = /^([a-z0-9_.-]+):(.*)$/i.exec(tk);
      if (kv){
        var k=kv[1].toLowerCase(), v=kv[2];
        if (k==='project'){ t.project = v || '(no project)'; f.project = t.project; }
        else if (k==='due'){ t.due = v; f.due = v; }
        else { f.extra.push(k+':'+v); }
      } else {
        f.extra.push(tk);
      }
    }
      }
    
      // ===== button detection =====
      function isModBtn(el){
    return !!(el && (el.closest('.btnMod')
      || el.closest('[data-action="modify"]')
      || el.closest('[title*="odif"]')
      || el.closest('[aria-label*="odif"]')));
      }
      function isDoneBtn(el){
    return !!(el && (el.closest('.btnDone')
      || el.closest('[data-action="done"]')
      || el.closest('[title*="omplet"]')
      || el.closest('[aria-label*="omplet"]')));
      }
      function isDelBtn(el){
    return !!(el && (el.closest('.btnDel')
      || el.closest('[data-action="delete"]')
      || el.closest('[title*="elete"]')
      || el.closest('[aria-label*="elete"]')));
      }
    
      // ===== unified click capture (new + existing) =====
      document.addEventListener('click', function(ev){
    var el = ev.target; if (!el) return;
    if (!(isModBtn(el) || isDoneBtn(el) || isDelBtn(el))) return;
    var nd = el.closest && el.closest('.node'); if (!nd) return;
    var id = uuidFromNode(nd); if (!id) return;
    
    // Only intercept staging; allow UI to also do its visuals
    ev.stopImmediatePropagation(); ev.preventDefault();
    
    if (isNewId(id)){
      // NEW TASKS
      if (isModBtn(el)){
        var val = window.prompt('Modifiers (e.g. due:3d +tag -old):','');
        if (typeof val === 'string' && val.trim()){
          applyModsToNew(id, val.trim());
        }
      } else if (isDoneBtn(el)){
        var nowDone = !nd.classList.contains('stagedDone');
        if (nowDone) nd.classList.add('stagedDone'); else nd.classList.remove('stagedDone');
        var f = ensureFold(id); if (f) f.done = nowDone;
      } else if (isDelBtn(el)){
        var nowDel = !nd.classList.contains('stagedDel');
        if (nowDel) nd.classList.add('stagedDel'); else nd.classList.remove('stagedDel');
        var f2 = ensureFold(id); if (f2) f2.deleted = nowDel;
      }
    } else {
      // EXISTING TASKS
      var ops = ensureOps(id);
      if (isModBtn(el)){
        var val2 = window.prompt('Modifiers (e.g., pri:H due:2025-09-20 +tag -oldtag):','');
        if (typeof val2 === 'string' && val2.trim()){
          var add = val2.trim().split(/\s+/).filter(Boolean);
          var seen = Object.create(null), merged = [];
          ops.mods.concat(add).forEach(function(tk){ if (!seen[tk]){ seen[tk]=1; merged.push(tk); } });
          ops.mods = merged;
        }
      } else if (isDoneBtn(el)){
        ops.done = !ops.done; ops.deleted = false;
        // reflect immediately in UI
        nd.classList.toggle('stagedDone', ops.done);
        nd.classList.remove('stagedDel');
      } else if (isDelBtn(el)){
        ops.deleted = !ops.deleted; ops.done = false;
        // reflect immediately in UI
        nd.classList.toggle('stagedDel', ops.deleted);
        nd.classList.remove('stagedDone');
      }
    
    }
    
    try{ if (typeof updateConsole==='function') setTimeout(updateConsole, 30); }catch(_){}
      }, true);
    
      // ===== console builder =====
      function buildConsole(){
    try{
      if (!Array.isArray(window.TASKS)) return "";
      var lines = [];
      for (var i=0;i<TASKS.length;i++){
        var t = TASKS[i]; if (!t) continue;
        var id = t.uuid || t.short;
    
        if (isNewId(id)){
          // fold new tasks
          var nd = document.querySelector('.node[data-uuid="'+id+'"], .node[data-short="'+id+'"]');
          var done=false, deleted=false;
          if (nd){
            done = nd.classList.contains('stagedDone') || nd.classList.contains('completed') || nd.getAttribute('data-done')==='1';
            deleted = nd.classList.contains('stagedDel') || nd.getAttribute('data-deleted')==='1';
          }
          var f = FOLD[t.uuid] || FOLD[t.short] || {};
          if (f.done) done=true;
          if (f.deleted) deleted=true;
          if (deleted) continue;
          var verb = done ? "task log" : "task add";
          var parts = [verb, (t.desc||"(no description)")];
          var proj = (typeof f.project!=='undefined') ? f.project : (t.project || "(no project)");
          if (proj && proj!=="(no project)") parts.push("project:"+proj);
          var tagset = Object.create(null);
          if (Array.isArray(t.tags)){ for (var k=0;k<t.tags.length;k++){ var tg=t.tags[k]; if (tg && tg!=="(no tag)") tagset[tg]=true; } }
          if (f.tags){ for (var tg in f.tags){ if (f.tags[tg]) tagset[tg]=true; else delete tagset[tg]; } }
          Object.keys(tagset).forEach(function(tg){ parts.push("+"+tg); });
          var due = (typeof f.due!=='undefined') ? f.due : t.due;
          if (due) parts.push("due:"+due);
          if (Array.isArray(f.extra)){ for (var q=0;q<f.extra.length;q++){ parts.push(f.extra[q]); } }
          lines.push(parts.join(" "));
        } else {
          // existing tasks — merge diffs + EX_OPS
          var ex = EX_OPS[id] || {};
          if (ex.deleted){ lines.push("task "+t.uuid+" delete"); continue; }
          if (ex.done){ lines.push("task "+t.uuid+" done"); continue; }
          var oT = oldTagOf(t), nT = firstTag(t);
          var oP = oldProjOf(t), nP = t.project || "(no project)";
          var ops = [];
          if (oT !== nT){
            if (oT !== "(no tag)") ops.push("-"+oT);
            if (nT !== "(no tag)") ops.push("+"+nT);
          }
          var projPart = null;
          if (oP !== nP){ projPart = (nP === "(no project)") ? "project:" : "project:"+nP; }
          var mods = [];
          if (projPart) mods.push(projPart);
          if (ops.length) Array.prototype.push.apply(mods, ops);
          if (ex.mods && ex.mods.length){
            var seen = Object.create(null);
            mods.forEach(function(m){ seen[m]=1; });
            ex.mods.forEach(function(m){ if (!seen[m]){ seen[m]=1; mods.push(m); } });
          }
          if (mods.length){ lines.push(("task "+t.uuid+" modify " + mods.join(" ")).trim()); }
        }
      }
      return lines.join("\\n");
    }catch(_){ return ""; }
      }
      function tick(){
    try{
      var ta = document.getElementById('consoleText');
      if (!ta) return;
      var v = buildConsole();
      if (ta.value !== v) ta.value = v;
    }catch(_){}
      }
      setInterval(function(){
    if (document.hidden) return;
    tick();
      }, 520);
      document.addEventListener('visibilitychange', function(){
    if (!document.hidden) setTimeout(tick, 30);
      });
      window.addEventListener('load', function(){ setTimeout(tick, 180); });
    
    })();</script></body>'''
    
    # --- Dep Handle: embedded authoritative writer (v6) + dedup (v6b) ---
    V6_JS = r'''
    <script>
    /* === dep handle authoritative v6 ========================================== */
    (function(){
      if (window.__depHandleAuthorV6) return;
    
      function qsa(sel, root){ return (root||document).querySelectorAll(sel); }
      function $(sel, root){ return (root||document).querySelector(sel); }
    
      // Map ids -> shorts using DOM (works with duplicates)
      function domMaps(){
    var els = qsa('#builderStage [data-short]');
    var shortSet = Object.create(null), uuid2short = Object.create(null);
    for (var i=0;i<els.length;i++){
      var el=els[i], s=el.getAttribute('data-short'), u=el.getAttribute('data-uuid');
      if (s) shortSet[s] = true;
      if (u && s) uuid2short[String(u).toLowerCase()] = s;
    }
    return { shortSet:shortSet, uuid2short:uuid2short };
      }
      function first8(x){ return String(x||'').replace(/[^0-9a-fA-F-]/g,'').slice(0,8); }
      function toShort(id, maps){
    if (!id) return null;
    var idstr = String(id);
    if (maps.shortSet[idstr]) return idstr;
    var low = idstr.toLowerCase();
    if (maps.uuid2short[low]) return maps.uuid2short[low];
    var f8 = first8(idstr);
    return maps.shortSet[f8] ? f8 : null;
      }
    
      // Build combined edge list in SHORT ids (existing + staged)
      function gatherEdgesShort(){
    var maps = domMaps(), out=[], i, e;
    var ex = window.EXIST_EDGES || [];
    for (i=0;i<ex.length;i++){
      e = ex[i]; if (!e) continue;
      var fs = toShort(e.from, maps), ts = toShort(e.to, maps);
      if (fs && ts) out.push({from:fs, to:ts});
    }
    var st = window.stagedAdd || [];
    for (i=0;i<st.length;i++){
      e = st[i]; if (!e) continue;
      var f2 = toShort(e.from, maps), t2 = toShort(e.to, maps);
      if (f2 && t2) out.push({from:f2, to:t2});
    }
    return out;
      }
    
      // Topo letters (A..Z wrap)
      function topoLetters(){
    var E = gatherEdgesShort();
    var nodes = Object.create(null), adj = Object.create(null), indeg = Object.create(null);
    var cards = qsa('#builderStage [data-short]'), i, n, u, v;
    for (i=0;i<cards.length;i++){ nodes[cards[i].getAttribute('data-short')] = 1; }
    for (i=0;i<E.length;i++){ nodes[E[i].from]=1; nodes[E[i].to]=1; }
    for (n in nodes){ adj[n]=[]; indeg[n]=0; }
    for (i=0;i<E.length;i++){ u=E[i].from; v=E[i].to; adj[u].push(v); indeg[v]++; }
    var q=[], level=Object.create(null);
    for (n in nodes){ if (!indeg[n]) q.push(n); level[n]=0; }
    while(q.length){
      u=q.shift(); var lu=level[u]||0, a=adj[u]||[];
      for (i=0;i<a.length;i++){
        v=a[i];
        if ((level[v]||0) < lu+1) level[v] = lu+1;
        indeg[v]--; if (!indeg[v]) q.push(v);
      }
    }
    var L=Object.create(null);
    for (n in nodes){ var lv=level[n]||0; L[n] = String.fromCharCode(65 + (lv % 26)); }
    return L;
      }
    
      // Degree counts per short
      function countsOutIn(){
    var E = gatherEdgesShort();
    var out = Object.create(null), inc = Object.create(null), i, e;
    for (i=0;i<E.length;i++){
      e = E[i];
      out[e.from] = (out[e.from]||0) + 1;
      inc[e.to]   = (inc[e.to]  ||0) + 1;
    }
    return {out:out, inc:inc};
      }
    
      // Ensure a handle exists inside the card (don’t duplicate if present)
      function ensureHandle(card){
    var h = card.querySelector('.depHandle');
    if (h) return h;
    try{
      h = document.createElement('div');
      h.className = 'depHandle';
      var s = card.getAttribute('data-short'); if (s) h.setAttribute('data-short', s);
      card.appendChild(h);
    }catch(_){}
    return h;
      }
    
      // Write authoritative text and visibility for all cards
      function writeHandles(){
    var L = topoLetters();
    var C = countsOutIn();
    var cards = qsa('#builderStage [data-short]');
    for (var i=0;i<cards.length;i++){
      var el = cards[i];
      var s  = el.getAttribute('data-short');
      var h  = ensureHandle(el);
      if (!h) continue;
    
      var base = L[s] || 'A';
      var o = C.out[s] || 0, d = C.inc[s] || 0;
      var next = base + String(o) + "/" + String(d);
    
      if (h.textContent !== next) h.textContent = next;
      // visible only if participates (has any degree)
      if (o>0 || d>0){ h.classList.add('dep-hasdeps'); }
      else{ h.classList.remove('dep-hasdeps'); }
    }
      }
    
      // Keep staged overlay paths tagged so pulses & tools can follow
      function tagStagedPaths(){
    var over = document.getElementById('depStagedOverlay');
    if (!over) return;
    var paths = over.querySelectorAll('path');
    var st = window.stagedAdd || [];
    for (var i=0;i<paths.length && i<st.length; i++){
      var p = paths[i], e = st[i]; if (!e) continue;
      if (!p.hasAttribute('data-from')) p.setAttribute('data-from', String(e.from||''));
      if (!p.hasAttribute('data-to'))   p.setAttribute('data-to',   String(e.to||''));
    }
      }
    
      // Wire up: after native refresh/draw, we write authoritative handles
      (function(){
    var _refresh = window.refreshDepHandleLetters;
    window.refreshDepHandleLetters = function(){
      if (typeof _refresh === 'function') try{ _refresh.apply(this, arguments); }catch(_){}
      setTimeout(function(){ try{ writeHandles(); }catch(_){ } }, 0);
    };
      })();
    
      (function(){
    var _draw = window.drawLinks;
    window.drawLinks = function(){
      if (typeof _draw === 'function') try{ _draw.apply(this, arguments); }catch(_){}
      try{ tagStagedPaths(); }catch(_){}
      // write after overlay settles
      setTimeout(function(){ try{ writeHandles(); }catch(_){ } }, 0);
    };
      })();
    
      // stagedAdd changes
      (function(){
    try{
      if (!('stagedAdd' in window)) window.stagedAdd = [];
      var a = window.stagedAdd;
      if (!a.__authorV6){
        var _p=a.push, _s=a.splice;
        a.push = function(e){ var r=_p.apply(this, arguments); setTimeout(function(){ try{ writeHandles(); }catch(_){ } }, 0); return r; };
        a.splice = function(){ var r=_s.apply(this, arguments); setTimeout(function(){ try{ writeHandles(); }catch(_){ } }, 0); return r; };
        a.__authorV6 = true;
      }
    }catch(_){}
      })();
    
      // mutations (style/class/childList) on stage
      (function(){
    var stage = $('#builderStage'); if (!stage) return;
    var t=null;
    var obs = new MutationObserver(function(){
      if (t) return;
      t = setTimeout(function(){ t=null; try{ writeHandles(); }catch(_){ } }, 40);
    });
    obs.observe(stage, {subtree:true, childList:true, attributes:true, attributeFilter:['style','class']});
    window.__depHandleAuthorV6Observer = obs;
      })();
    
      // resize
      window.addEventListener('resize', function(){ try{ writeHandles(); }catch(_){ } }, {passive:true});
    
      // initial paints
      setTimeout(function(){ try{ writeHandles(); }catch(_){ } }, 0);
      setTimeout(function(){ try{ writeHandles(); }catch(_){ } }, 120);
    
      window.__depHandleAuthorV6 = true;
    })();
    </script>
    '''
    V6B_CSS = r'''
    /* __DEP_HANDLE_V6B_DEDUP__ hide non-primary instantly (JS removes shortly) */
    #builderStage [data-short] .depHandle.__primary { display:inline-flex !important; }
    #builderStage [data-short] .depHandle:not(.__primary) { display:none !important; }
    '''
    V6B_JS  = r'''
    <script>
    /* === dep handle authoritative dedup v6b =================================== */
    (function(){
      if (window.__depHandleAuthorDedupV6b) return;
    
      function qsa(sel, root){ return (root||document).querySelectorAll(sel); }
      function $(sel, root){ return (root||document).querySelector(sel); }
    
      function choosePrimary(list){
    if (!list || !list.length) return null;
    if (list.length === 1) return list[0];
    // prefer one marked participating
    for (var i=0;i<list.length;i++){
      var h=list[i]; if (h.classList && h.classList.contains('dep-hasdeps')) return h;
    }
    // else longest text (usually includes full counts)
    var best=list[0], maxLen=(String(list[0].textContent||'').length|0);
    for (var j=1;j<list.length;j++){
      var len=(String(list[j].textContent||'').length|0);
      if (len>maxLen){ best=list[j]; maxLen=len; }
    }
    return best;
      }
    
      // Normalize to exactly one "A12/3"
      function sanitizeOne(txt){
    txt = String(txt||'').trim();
    // pick *first* leading letter (A..Z) if any
    var lead = (txt.match(/[A-Z]/) || [""])[0];
    // pick the *last* trailing counts pattern (d+ or d+/d+)
    var counts = (txt.match(/\d+(?:\/\d+)?(?!.*\d)/) || [""])[0];
    return (lead||"") + (counts ? counts : (lead ? "0/0" : ""));
      }
    
      function dedupOneCard(card){
    var hs = card.querySelectorAll('.depHandle');
    if (!hs || hs.length===0) return;
    // mark all non-primary for CSS hiding; set one primary
    var primary = choosePrimary(hs) || hs[0];
    for (var i=0;i<hs.length;i++){
      var h = hs[i];
      if (h === primary) h.classList.add('__primary');
      else h.classList.remove('__primary');
    }
    // sanitize text on primary
    var norm = sanitizeOne(primary.textContent);
    if (primary.textContent !== norm) primary.textContent = norm;
    // remove extras
    for (var j=0;j<hs.length;j++){
      var h2 = hs[j];
      if (h2 === primary) continue;
      try { h2.remove(); } catch(_){}
    }
      }
    
      function runDedup(){
    var cards = qsa('#builderStage [data-short]');
    for (var i=0;i<cards.length;i++) dedupOneCard(cards[i]);
      }
    
      // hook: if v6 writer exists, run dedup after it writes
      (function(){
    // detect v6 by presence of the observer symbol or writer wrapper
    var _refresh = window.refreshDepHandleLetters;
    window.refreshDepHandleLetters = function(){
      if (typeof _refresh === 'function') try{ _refresh.apply(this, arguments); }catch(_){}
      setTimeout(function(){ try{ runDedup(); }catch(_){ } }, 0);
    };
      })();
    
      // observe the stage for late insertions/mutations
      (function(){
    var stage = $('#builderStage'); if (!stage) return;
    var t=null;
    var obs = new MutationObserver(function(){
      if (t) return;
      t = setTimeout(function(){ t=null; try{ runDedup(); }catch(_){ } }, 30);
    });
    obs.observe(stage, {subtree:true, childList:true, attributes:true, attributeFilter:['class','style']});
    window.__depHandleAuthorDedupV6bObserver = obs;
      })();
    
      // resize can cause reinserts
      window.addEventListener('resize', function(){ try{ runDedup(); }catch(_){ } }, {passive:true});
    
      // first passes
      setTimeout(function(){ try{ runDedup(); }catch(_){ } }, 0);
      setTimeout(function(){ try{ runDedup(); }catch(_){ } }, 120);
    
      // manual helper
      window.depFix = window.depFix || {};
      window.depFix.dedup = runDedup;
    
      window.__depHandleAuthorDedupV6b = true;
    })();
    </script>
    '''
    
    
    
    # Inject the CSS/JS into the generated html
    if "feature-hover-css" not in html:
        html = html.replace("</head>", CSS_HOVER + "</head>")
    if "FEATURE_HOVERSTAGE" not in html:
        html = html.replace("</body>", JS_HOVER + "</body>")
    if "feature-due-css-v2" not in html:
        html = html.replace("</head>", CSS_DUE + "</head>")
    if "FEATURE_DUEBADGE2" not in html:
        html = html.replace("</body>", JS_DUE + "</body>")
    # --- Integrate dep-handle authoritative writer (v6) + dedup (v6b) ---
    if "dep handle authoritative v6" not in html:
        html = html.replace("</body>", V6_JS + "</body>")
    if "__DEP_HANDLE_V6B_DEDUP__" not in html and "dep handle authoritative dedup v6b" not in html:
        # CSS
        if "</head>" in html:
            html = html.replace("</head>", "<style>" + V6B_CSS + "</style></head>")
        else:
            html = "<style>" + V6B_CSS + "</style>" + html
        # JS
        html = html.replace("</body>", V6B_JS + "</body>")
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
    html = inject_command_preflight(html)
    
    return html
