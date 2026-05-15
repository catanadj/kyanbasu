import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from taskcanvas.runtime_html import build_runtime_html


class TestBrowserE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chromium = shutil.which("chromium")
        if not cls.chromium:
            raise unittest.SkipTest("Chromium not found; skipping browser E2E.")

        # Validate chromium is runnable in this environment.
        try:
            p = subprocess.run(
                [cls.chromium, "--headless", "--no-sandbox", "--dump-dom", "about:blank"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            raise unittest.SkipTest(f"Chromium probe failed in this environment ({type(e).__name__}).")
        if p.returncode != 0:
            raise unittest.SkipTest(
                f"Chromium unavailable in this environment (rc={p.returncode}); skipping browser E2E."
            )

    def _run_html_harness(self, html):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TaskCanvas.e2e.html"
            p.write_text(html, encoding="utf-8")
            try:
                out = subprocess.run(
                    [
                        self.chromium,
                        "--headless",
                        "--no-sandbox",
                        "--disable-gpu",
                        "--virtual-time-budget=7000",
                        "--dump-dom",
                        f"file://{p}",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=20,
                    check=False,
                )
            except (subprocess.TimeoutExpired, OSError) as e:
                self.skipTest(f"Chromium execution failed in this environment ({type(e).__name__}).")
            if out.returncode != 0:
                self.skipTest(f"Chromium failed in this environment (rc={out.returncode}).")
            m = re.search(r'<pre id="e2e-out">(.*?)</pre>', out.stdout, flags=re.S)
            self.assertIsNotNone(m, "Harness output element not found in dumped DOM.")
            return m.group(1)

    def test_build_commands_shell_quotes_new_task_description_and_modifiers(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps({"tasks": [], "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}}})
        html = build_runtime_html(base_html, payload, 0, lambda *_: None)

        harness = """
<script id="E2E_COMMAND_HARNESS">
window.addEventListener('load', function(){
  try{
    window.TASKS.push({
      uuid:'new-e2e',
      short:'n-e2e',
      desc:"hello; world $(id) O'Reilly",
      project:'Work',
      tags:['safe'],
      has_depends:false
    });
    if (typeof updateConsole==='function') updateConsole();
    var out = (typeof buildCommands==='function') ? String(buildCommands()||'') : '';
    var pre = document.createElement('pre');
    pre.id = 'e2e-out';
    pre.textContent = out;
    document.body.appendChild(pre);
  }catch(e){
    var pre2 = document.createElement('pre');
    pre2.id = 'e2e-out';
    pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
    document.body.appendChild(pre2);
  }
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")

        cmds = self._run_html_harness(html)
        self.assertNotIn("ERR:", cmds)
        self.assertIn("task add", cmds)
        self.assertIn("'project:Work' '+safe'", cmds)
        self.assertIn("'hello; world $(id) O'\"'\"'Reilly'", cmds)

    def test_taskcanvas_commands_core_normalizes_command_matrix(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps({"tasks": [], "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}}})
        html = build_runtime_html(base_html, payload, 0, lambda *_: None)

        harness = """
<script id="E2E_COMMAND_CORE_HARNESS">
window.addEventListener('load', function(){
  try{
    var raw = [
      "task abc modify +home",
      "task abc modify +home due:tomorrow",
      "task abc done",
      "task abc modify project:Later",
      "task def delete",
      "task def done",
      "task add Review O'Reilly $(id) project:Work +safe"
    ].join("\\n");
    var res = window.TaskCanvasCommands.normalize(raw);
    var pre = document.createElement('pre');
    pre.id = 'e2e-out';
    pre.textContent = JSON.stringify({text:res.text, warnings:res.warnings});
    document.body.appendChild(pre);
  }catch(e){
    var pre2 = document.createElement('pre');
    pre2.id = 'e2e-out';
    pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
    document.body.appendChild(pre2);
  }
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw_out = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw_out)
        result = json.loads(raw_out)
        text = result["text"]
        warnings = result["warnings"]

        self.assertIn("task 'abc' done", text)
        self.assertIn("task 'def' done", text)
        self.assertIn("task add 'Review O'\"'\"'Reilly $(id)' 'project:Work' '+safe'", text)
        self.assertNotIn("project:Later", text)
        self.assertTrue(any("Dropped modify after terminal action for task abc" in w for w in warnings))
        self.assertTrue(any("Conflicting terminal actions for task def" in w for w in warnings))

    def test_console_utility_runtimes_wire_toast_normalize_and_copy(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps({"tasks": [], "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}}})
        html = build_runtime_html(base_html, payload, 0, lambda *_: None)

        harness = """
<script id="E2E_CONSOLE_UTILITIES_HARNESS">
window.addEventListener('load', function(){
  setTimeout(function(){
    try{
      try{
        Object.defineProperty(navigator, 'clipboard', {
          configurable: true,
          value: { writeText: function(txt){ window.__copiedText = txt; return Promise.resolve(); } }
        });
      }catch(_){}
      var ct = document.getElementById('consoleText');
      ct.value = "task one\\ntask one\\\\ntask two";
      ct.dispatchEvent(new Event('input'));
      window.showToast("Ready");
      document.getElementById('copyBtn').click();
      setTimeout(function(){
        var out = {
          toast: (document.getElementById('devConsoleToast') || {}).textContent || "",
          console: ct.value,
          copied: window.__copiedText || "",
          flags: [
            !!window.__FEATURE_TOAST_UTIL_V1__,
            !!window.__FEATURE_CONSOLE_LINE_ENFORCER_V3__,
            !!window.__FEATURE_COPY_FULL_OVERRIDE_V1__,
            !!window.__FEATURE_SINGLE_CONSOLE_AUGMENT_V1__
          ]
        };
        var pre = document.createElement('pre');
        pre.id = 'e2e-out';
        pre.textContent = JSON.stringify(out);
        document.body.appendChild(pre);
      }, 0);
    }catch(e){
      var pre2 = document.createElement('pre');
      pre2.id = 'e2e-out';
      pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
      document.body.appendChild(pre2);
    }
  }, 600);
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        result = json.loads(raw)
        self.assertEqual(result["flags"], [True, True, True, True])
        self.assertIn(result["toast"], ["Ready", "Copied 2 line(s)."])
        self.assertEqual(result["console"], "task one\ntask two")
        self.assertEqual(result["copied"], "task one\ntask two")

    def test_focus_and_project_add_tag_runtimes_dedupe_and_add_multiple_tags(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps(
            {
                "tasks": [
                    {
                        "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "short": "aaaaaaaa",
                        "desc": "Alpha",
                        "project": "Work",
                        "tags": ["old"],
                        "has_depends": False,
                    }
                ],
                "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}},
                "init_projects": ["Work"],
            }
        )
        html = build_runtime_html(base_html, payload, 1, lambda *_: None)

        harness = """
<script id="E2E_FOCUS_ADD_TAG_HARNESS">
window.addEventListener('load', function(){
  setTimeout(function(){
    try{
      window.prompt = function(){ return "newtag extra old"; };
      var before = document.querySelectorAll('#builderStage .node[data-short="aaaaaaaa"]').length;
      if (typeof addToBuilder === 'function') addToBuilder(window.TASKS[0], 180, 180);
      var after = document.querySelectorAll('#builderStage .node[data-short="aaaaaaaa"]').length;
      var btn = document.querySelector('.projAreaLabel .projAddTagBtn');
      if (btn) btn.click();
      setTimeout(function(){
        var tags = Array.prototype.slice.call(document.querySelectorAll('.tagAreaLabel')).map(function(el){
          return (el.textContent || '').replace(/[+＋]\\s*$/, '').trim();
        }).sort();
        var out = {
          before: before,
          after: after,
          hasButton: !!btn,
          tags: tags,
          toast: (document.getElementById('devConsoleToast') || {}).textContent || "",
          flags: [
            !!window.__FEATURE_DEDUPE_FOCUS_V1__,
            !!window.__FEATURE_PROJECT_ADD_TAG_V4__
          ]
        };
        var pre = document.createElement('pre');
        pre.id = 'e2e-out';
        pre.textContent = JSON.stringify(out);
        document.body.appendChild(pre);
      }, 160);
    }catch(e){
      var pre2 = document.createElement('pre');
      pre2.id = 'e2e-out';
      pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
      document.body.appendChild(pre2);
    }
  }, 700);
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        result = json.loads(raw)
        self.assertEqual(result["flags"], [True, True])
        self.assertTrue(result["hasButton"])
        self.assertEqual(result["before"], 1)
        self.assertEqual(result["after"], 1)
        self.assertIn("newtag", result["tags"])
        self.assertIn("extra", result["tags"])
        self.assertIn("old", result["tags"])
        self.assertIn('Added tags "newtag", "extra" to Work.', result["toast"])
        self.assertIn("Skipped: old (already exists)", result["toast"])

    def test_review_changes_runtime_groups_staged_command_core_output(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps(
            {
                "tasks": [
                    {
                        "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "short": "aaaaaaaa",
                        "desc": "Alpha",
                        "project": "Work",
                        "tags": ["old"],
                        "has_depends": False,
                    },
                    {
                        "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                        "short": "bbbbbbbb",
                        "desc": "Beta",
                        "project": "Work",
                        "tags": [],
                        "has_depends": False,
                    },
                ],
                "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}},
                "init_projects": ["Work"],
            }
        )
        html = build_runtime_html(base_html, payload, 2, lambda *_: None)

        harness = """
<script id="E2E_REVIEW_CHANGES_HARNESS">
window.addEventListener('load', function(){
  setTimeout(function(){
    try{
      window.TASKS.push({
        uuid:"new-review",
        short:"new-rev",
        desc:"Review panel task",
        project:"Inbox",
        tags:["fresh"],
        has_depends:false
      });
      window.EX_OPS = window.__EXISTING_OPS__ = {
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa": {done:false, deleted:false, mods:["due:tomorrow"]},
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb": {done:true, deleted:false, mods:[]}
      };
      window.stagedAdd = [{from:"aaaaaaaa", to:"bbbbbbbb"}];
      if (typeof updateConsole === 'function') updateConsole();
      document.getElementById('reviewChangesBtn').click();
      setTimeout(function(){
        var current = window.TaskCanvasReview.current();
        var panel = document.getElementById('reviewChangesPanel');
        var out = {
          open: panel && panel.classList.contains('open'),
          button: !!document.getElementById('reviewChangesBtn'),
          groups: {
            newTasks: current.groups.newTasks.length,
            terminal: current.groups.terminal.length,
            fieldChanges: current.groups.fieldChanges.length,
            dependencies: current.groups.dependencies.length,
            other: current.groups.other.length
          },
          text: panel ? panel.textContent : "",
          raw: current.text
        };
        var pre = document.createElement('pre');
        pre.id = 'e2e-out';
        pre.textContent = JSON.stringify(out);
        document.body.appendChild(pre);
      }, 120);
    }catch(e){
      var pre2 = document.createElement('pre');
      pre2.id = 'e2e-out';
      pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
      document.body.appendChild(pre2);
    }
  }, 800);
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        result = json.loads(raw)
        self.assertTrue(result["button"])
        self.assertTrue(result["open"])
        self.assertEqual(result["groups"]["newTasks"], 1)
        self.assertEqual(result["groups"]["terminal"], 1)
        self.assertGreaterEqual(result["groups"]["fieldChanges"], 1)
        self.assertEqual(result["groups"]["dependencies"], 1)
        self.assertIn("Review Changes", result["text"])
        self.assertIn("New Tasks", result["text"])
        self.assertIn("Dependency Changes", result["text"])
        self.assertIn("task add 'Review panel task'", result["raw"])

    def test_done_delete_toggle_does_not_duplicate_console_commands(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps(
            {
                "tasks": [
                    {
                        "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "short": "aaaaaaaa",
                        "desc": "Alpha",
                        "project": "Work",
                        "tags": [],
                        "has_depends": False,
                    }
                ],
                "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}},
                "init_projects": ["Work"],
            }
        )
        html = build_runtime_html(base_html, payload, 1, lambda *_: None)

        harness = """
<script id="E2E_DONE_DELETE_DUP_HARNESS">
window.addEventListener('load', function(){
  setTimeout(function(){
    try{
      var btn = document.querySelector('#builderStage .node[data-short="aaaaaaaa"] .btnDone');
      if (!btn) throw new Error('done button missing');
      btn.click();
      var immediate = (document.getElementById('consoleText') || {}).value || "";
      setTimeout(function(){
        var early = (document.getElementById('consoleText') || {}).value || "";
        setTimeout(function(){
          var text = (document.getElementById('consoleText') || {}).value || "";
          var raw = (window.STAGED_CMDS || []).slice();
          var pre = document.createElement('pre');
          pre.id = 'e2e-out';
          pre.textContent = JSON.stringify({immediate:immediate, early:early, text:text, staged:raw});
          document.body.appendChild(pre);
        }, 260);
      }, 80);
    }catch(e){
      var pre2 = document.createElement('pre');
      pre2.id = 'e2e-out';
      pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
      document.body.appendChild(pre2);
    }
  }, 900);
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        result = json.loads(raw)
        self.assertEqual(result["staged"], [])
        immediate_lines = [line for line in result["immediate"].splitlines() if line.strip()]
        early_lines = [line for line in result["early"].splitlines() if line.strip()]
        final_lines = [line for line in result["text"].splitlines() if line.strip()]
        self.assertLessEqual(len(immediate_lines), 1)
        self.assertEqual(len(early_lines), 1)
        self.assertEqual(len(final_lines), 1)
        self.assertRegex(final_lines[0], r"^task '?[0-9a-f-]+'? done$")

    def test_canvas_notes_runtime_creates_links_and_stays_out_of_commands(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps({"tasks": [], "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}}})
        html = build_runtime_html(base_html, payload, 0, lambda *_: None)

        harness = """
<script id="E2E_CANVAS_NOTES_HARNESS">
window.addEventListener('load', function(){
  setTimeout(function(){
    try{
      var a = window.TaskCanvasNotes.createNote(260, 220, "Plan", "Break work down");
      var b = window.TaskCanvasNotes.createNote(560, 250, "Step 1", "Trace current flow");
      window.TaskCanvasNotes.linkNotes(a.id, b.id);
      window.TaskCanvasNotes.save();
      if (typeof updateConsole === 'function') updateConsole();
      setTimeout(function(){
        var out = {
          noteButton: !!document.getElementById('noteModeBtn'),
          linkButton: !!document.getElementById('noteLinkModeBtn'),
          notes: document.querySelectorAll('.tcNoteNode').length,
          textFields: document.querySelectorAll('.tcNoteNode .tcNoteText').length,
          titleFields: document.querySelectorAll('.tcNoteNode .tcNoteTitle').length,
          links: document.querySelectorAll('#tcNoteLinksLayer path.tcNoteLink').length,
          apiNotes: window.TaskCanvasNotes.notes().length,
          apiLinks: window.TaskCanvasNotes.links().length,
          firstContent: window.TaskCanvasNotes.notes()[0] && window.TaskCanvasNotes.notes()[0].content,
          hasTitleKey: window.TaskCanvasNotes.notes().some(function(n){ return Object.prototype.hasOwnProperty.call(n, 'title'); }),
          console: (document.getElementById('consoleText') || {}).value || "",
          savedKeys: Object.keys(localStorage).filter(function(k){ return k.indexOf('taskcanvas:notes:v1:') === 0; }).length
        };
        var pre = document.createElement('pre');
        pre.id = 'e2e-out';
        pre.textContent = JSON.stringify(out);
        document.body.appendChild(pre);
      }, 80);
    }catch(e){
      var pre2 = document.createElement('pre');
      pre2.id = 'e2e-out';
      pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
      document.body.appendChild(pre2);
    }
  }, 700);
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        result = json.loads(raw)
        self.assertTrue(result["noteButton"])
        self.assertTrue(result["linkButton"])
        self.assertEqual(result["notes"], 2)
        self.assertEqual(result["textFields"], 2)
        self.assertEqual(result["titleFields"], 0)
        self.assertEqual(result["links"], 1)
        self.assertEqual(result["apiNotes"], 2)
        self.assertEqual(result["apiLinks"], 1)
        self.assertEqual(result["firstContent"], "Plan\nBreak work down")
        self.assertFalse(result["hasTitleKey"])
        self.assertEqual(result["console"], "")
        self.assertGreaterEqual(result["savedKeys"], 1)

    def test_canvas_notes_runtime_creates_child_branches_and_reflows_map(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps({"tasks": [], "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}}})
        html = build_runtime_html(base_html, payload, 0, lambda *_: None)

        harness = """
<script id="E2E_CANVAS_NOTES_MINDMAP_HARNESS">
window.addEventListener('load', function(){
  setTimeout(function(){
    try{
      var root = window.TaskCanvasNotes.createNote(180, 240, "Launch plan", "");
      var a = window.TaskCanvasNotes.createChildNote(root.id, "Design", "");
      var b = window.TaskCanvasNotes.createChildNote(root.id, "Build", "");
      var c = window.TaskCanvasNotes.createChildNote(a.id, "Prototype", "");
      window.TaskCanvasNotes.reflowMindMap(root.id);
      window.TaskCanvasNotes.save();
      if (typeof updateConsole === 'function') updateConsole();
      setTimeout(function(){
        var notes = window.TaskCanvasNotes.notes();
        var links = window.TaskCanvasNotes.links();
        var byContent = {};
        notes.forEach(function(n){ byContent[n.content] = n; });
        var out = {
          reflowButton: !!document.getElementById('noteReflowBtn'),
          actionButtons: document.querySelectorAll('.tcNoteNode [data-note-child]').length,
          notes: notes.length,
          childLinks: links.filter(function(l){ return l.type === 'child'; }).length,
          childPaths: document.querySelectorAll('#tcNoteLinksLayer path.tcNoteLink[data-type="child"]').length,
          designRightOfRoot: byContent.Design.x > byContent["Launch plan"].x,
          prototypeRightOfDesign: byContent.Prototype.x > byContent.Design.x,
          console: (document.getElementById('consoleText') || {}).value || ""
        };
        var pre = document.createElement('pre');
        pre.id = 'e2e-out';
        pre.textContent = JSON.stringify(out);
        document.body.appendChild(pre);
      }, 80);
    }catch(e){
      var pre2 = document.createElement('pre');
      pre2.id = 'e2e-out';
      pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
      document.body.appendChild(pre2);
    }
  }, 700);
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        result = json.loads(raw)
        self.assertTrue(result["reflowButton"])
        self.assertEqual(result["actionButtons"], 4)
        self.assertEqual(result["notes"], 4)
        self.assertEqual(result["childLinks"], 3)
        self.assertEqual(result["childPaths"], 3)
        self.assertTrue(result["designRightOfRoot"])
        self.assertTrue(result["prototypeRightOfDesign"])
        self.assertEqual(result["console"], "")

    def test_canvas_notes_keyboard_creates_sibling_and_child_notes(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps({"tasks": [], "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}}})
        html = build_runtime_html(base_html, payload, 0, lambda *_: None)

        harness = """
<script id="E2E_CANVAS_NOTES_KEYBOARD_HARNESS">
window.addEventListener('load', function(){
  setTimeout(function(){
    try{
      var root = window.TaskCanvasNotes.createNote(180, 240, "Root", "");
      var first = window.TaskCanvasNotes.createChildNote(root.id, "First", "");
      window.TaskCanvasNotes.selectNote(first.id);
      document.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true, cancelable:true}));
      if (document.activeElement) document.activeElement.blur();
      window.TaskCanvasNotes.selectNote(first.id);
      document.dispatchEvent(new KeyboardEvent('keydown', {key:'Tab', bubbles:true, cancelable:true}));
      if (typeof updateConsole === 'function') updateConsole();
      setTimeout(function(){
        var notes = window.TaskCanvasNotes.notes();
        var links = window.TaskCanvasNotes.links();
        var rootChildren = links.filter(function(l){ return l.type === 'child' && l.from === root.id; });
        var firstChildren = links.filter(function(l){ return l.type === 'child' && l.from === first.id; });
        var selected = document.querySelectorAll('.tcNoteNode.selected').length;
        var out = {
          notes: notes.length,
          links: links.length,
          childLinks: links.filter(function(l){ return l.type === 'child'; }).length,
          rootChildren: rootChildren.length,
          firstChildren: firstChildren.length,
          selected: selected,
          focusedText: !!(document.activeElement && document.activeElement.classList && document.activeElement.classList.contains('tcNoteText')),
          console: (document.getElementById('consoleText') || {}).value || ""
        };
        var pre = document.createElement('pre');
        pre.id = 'e2e-out';
        pre.textContent = JSON.stringify(out);
        document.body.appendChild(pre);
      }, 120);
    }catch(e){
      var pre2 = document.createElement('pre');
      pre2.id = 'e2e-out';
      pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
      document.body.appendChild(pre2);
    }
  }, 700);
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        result = json.loads(raw)
        self.assertEqual(result["notes"], 4)
        self.assertEqual(result["links"], 3)
        self.assertEqual(result["childLinks"], 3)
        self.assertEqual(result["rootChildren"], 2)
        self.assertEqual(result["firstChildren"], 1)
        self.assertEqual(result["selected"], 1)
        self.assertTrue(result["focusedText"])
        self.assertEqual(result["console"], "")

    def test_taskcanvas_commands_core_includes_dependency_commands(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps({"tasks": [], "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}}})
        html = build_runtime_html(base_html, payload, 0, lambda *_: None)

        harness = """
<script id="E2E_DEP_COMMAND_CORE_HARNESS">
window.addEventListener('load', function(){
  try{
    var res = window.TaskCanvasCommands.build({
      raw: "task task-a modify +next",
      stagedAdd: [{from:"task-a", to:"task-b"}],
      depExtraCmds: ["task task-a modify depends:-task-c"],
      uuidForShort: function(short){ return ({ "task-a":"uuid-a", "task-b":"uuid-b", "task-c":"uuid-c" })[short] || short; }
    });
    var pre = document.createElement('pre');
    pre.id = 'e2e-out';
    pre.textContent = res.text;
    document.body.appendChild(pre);
  }catch(e){
    var pre2 = document.createElement('pre');
    pre2.id = 'e2e-out';
    pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
    document.body.appendChild(pre2);
  }
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        text = self._run_html_harness(html)
        self.assertNotIn("ERR:", text)
        self.assertIn("task 'task-a' modify '+next' 'depends:-task-c'", text)
        self.assertIn("task 'uuid-a' modify 'depends:uuid-b'", text)

    def test_taskcanvas_commands_core_handles_new_task_fold_states(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps({"tasks": [], "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}}})
        html = build_runtime_html(base_html, payload, 0, lambda *_: None)

        harness = """
<script id="E2E_NEW_TASK_CORE_HARNESS">
window.addEventListener('load', function(){
  try{
    var tasks = [
      {uuid:"new-add", short:"new-add", desc:"Add me", project:"Work", tags:["base"], due:"20260101T000000Z"},
      {uuid:"new-done", short:"new-done", desc:"Done me", project:"Home", tags:[]},
      {uuid:"new-del", short:"new-del", desc:"Delete me", project:"Home", tags:[]},
      {uuid:"new-mod", short:"new-mod", desc:"Mod me", project:"Inbox", tags:["old"]}
    ];
    var fold = {
      "new-done": {done:true, tags:{}, extra:[]},
      "new-del": {deleted:true, tags:{}, extra:[]},
      "new-mod": {project:"Later", due:"tomorrow", tags:{fresh:true}, extra:["priority:H"]}
    };
    var res = window.TaskCanvasCommands.build({
      raw: window.TaskCanvasCommands.rawTaskLines({tasks:tasks, fold:fold}).join("\\n")
    });
    var pre = document.createElement('pre');
    pre.id = 'e2e-out';
    pre.textContent = res.text;
    document.body.appendChild(pre);
  }catch(e){
    var pre2 = document.createElement('pre');
    pre2.id = 'e2e-out';
    pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
    document.body.appendChild(pre2);
  }
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        text = self._run_html_harness(html)
        self.assertNotIn("ERR:", text)
        self.assertIn("task add 'Add me' 'project:Work' '+base' 'due:20260101T000000Z'", text)
        self.assertIn("task log 'Done me' 'project:Home'", text)
        self.assertNotIn("Delete me", text)
        self.assertIn("task add 'Mod me' 'project:Later' '+old' '+fresh' 'due:tomorrow' 'priority:H'", text)

    def test_new_task_sync_reconciles_staged_new_task_modifiers_via_command_core(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps({"tasks": [], "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}}})
        html = build_runtime_html(base_html, payload, 0, lambda *_: None)

        harness = """
<script id="E2E_NEW_TASK_SYNC_HARNESS">
window.addEventListener('load', function(){
  try{
    window.TASKS.push({
      uuid:"new-sync",
      short:"new-sync",
      desc:"Sync me",
      project:"Inbox",
      tags:["old"],
      has_depends:false
    });
    window.STAGED_CMDS = [
      "task new-sync modify project:Work +fresh due:tomorrow",
      "task new-sync done"
    ];
    if (typeof updateConsole === 'function') updateConsole();
    var out = (document.getElementById('consoleText') || {}).value || "";
    var pre = document.createElement('pre');
    pre.id = 'e2e-out';
    pre.textContent = JSON.stringify({text:out, staged:window.STAGED_CMDS, fold:window.FOLD && window.FOLD["new-sync"]});
    document.body.appendChild(pre);
  }catch(e){
    var pre2 = document.createElement('pre');
    pre2.id = 'e2e-out';
    pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
    document.body.appendChild(pre2);
  }
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        result = json.loads(raw)
        self.assertEqual(result["staged"], [])
        self.assertTrue(result["fold"]["done"])
        self.assertIn("task log 'Sync me' 'project:Work' '+old' '+fresh' 'due:tomorrow'", result["text"])

    def test_taskcanvas_commands_core_handles_existing_task_ops(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps({"tasks": [], "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}}})
        html = build_runtime_html(base_html, payload, 0, lambda *_: None)

        harness = """
<script id="E2E_EXISTING_TASK_CORE_HARNESS">
window.addEventListener('load', function(){
  try{
    var tasks = [
      {uuid:"uuid-mod", short:"mod", desc:"Mod", project:"Later", tags:["next"]},
      {uuid:"uuid-done", short:"done", desc:"Done", project:"Work", tags:["old"]},
      {uuid:"uuid-del", short:"del", desc:"Delete", project:"Work", tags:["old"]}
    ];
    var res = window.TaskCanvasCommands.build({
      raw: window.TaskCanvasCommands.rawTaskLines({
        tasks: tasks,
        initMainTag: {mod:"old", done:"old", del:"old"},
        initProject: {mod:"Work", done:"Work", del:"Work"},
        existingOps: {
          "uuid-mod": {mods:["due:tomorrow", "+next", "priority:H"]},
          "uuid-done": {done:true, mods:["due:ignored"]},
          "uuid-del": {deleted:true, mods:["due:ignored"]}
        }
      }).join("\\n")
    });
    var pre = document.createElement('pre');
    pre.id = 'e2e-out';
    pre.textContent = res.text;
    document.body.appendChild(pre);
  }catch(e){
    var pre2 = document.createElement('pre');
    pre2.id = 'e2e-out';
    pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
    document.body.appendChild(pre2);
  }
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        text = self._run_html_harness(html)
        self.assertNotIn("ERR:", text)
        self.assertIn("task 'uuid-mod' modify 'project:Later' '-old' '+next' 'due:tomorrow' 'priority:H'", text)
        self.assertIn("task 'uuid-done' done", text)
        self.assertIn("task 'uuid-del' delete", text)
        self.assertNotIn("due:ignored", text)

    def test_runtime_existing_ops_flow_uses_command_core(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps(
            {
                "tasks": [
                    {
                        "uuid": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                        "short": "cccccccc",
                        "desc": "Existing",
                        "project": "Work",
                        "tags": ["old"],
                        "has_depends": False,
                    }
                ],
                "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}},
            }
        )
        html = build_runtime_html(base_html, payload, 1, lambda *_: None)

        harness = """
<script id="E2E_EXISTING_OPS_RUNTIME_HARNESS">
window.addEventListener('load', function(){
  try{
    window.__EXISTING_OPS__ = window.EX_OPS = {
      "cccccccc-cccc-cccc-cccc-cccccccccccc": {done:false, deleted:false, mods:["due:tomorrow", "+focus"]}
    };
    window.TASKS[0].project = "Later";
    window.TASKS[0].tags = ["next"];
    if (typeof updateConsole === 'function') updateConsole();
    var out = (document.getElementById('consoleText') || {}).value || "";
    var pre = document.createElement('pre');
    pre.id = 'e2e-out';
    pre.textContent = out;
    document.body.appendChild(pre);
  }catch(e){
    var pre2 = document.createElement('pre');
    pre2.id = 'e2e-out';
    pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
    document.body.appendChild(pre2);
  }
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        text = self._run_html_harness(html)
        self.assertNotIn("ERR:", text)
        self.assertIn("task 'cccccccc-cccc-cccc-cccc-cccccccccccc' modify 'project:Later' '-old' '+next' 'due:tomorrow' '+focus'", text)

    def test_build_commands_includes_staged_dependencies_without_base_monkey_patch(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps(
            {
                "tasks": [
                    {
                        "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "short": "aaaaaaaa",
                        "desc": "Parent",
                        "project": "Work",
                        "tags": [],
                        "has_depends": False,
                    },
                    {
                        "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                        "short": "bbbbbbbb",
                        "desc": "Child",
                        "project": "Work",
                        "tags": [],
                        "has_depends": False,
                    },
                ],
                "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}},
            }
        )
        html = build_runtime_html(base_html, payload, 2, lambda *_: None)
        self.assertNotIn("buildCommands monkey patch to include staged depends", html)
        self.assertNotIn("__buildCommandsPatched", html)

        harness = """
<script id="E2E_STAGED_DEP_COMMAND_HARNESS">
window.addEventListener('load', function(){
  try{
    window.stagedAdd = [{from:"aaaaaaaa", to:"bbbbbbbb"}];
    var out = (typeof buildCommands==='function') ? String(buildCommands()||'') : '';
    var pre = document.createElement('pre');
    pre.id = 'e2e-out';
    pre.textContent = out;
    document.body.appendChild(pre);
  }catch(e){
    var pre2 = document.createElement('pre');
    pre2.id = 'e2e-out';
    pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
    document.body.appendChild(pre2);
  }
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        self.assertIn("task 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' modify 'depends:bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'", raw)

    def test_dependency_overlay_matches_console_with_deduped_core_text(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps(
            {
                "tasks": [
                    {
                        "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "short": "aaaaaaaa",
                        "desc": "Parent",
                        "project": "Work",
                        "tags": [],
                        "has_depends": False,
                    },
                    {
                        "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                        "short": "bbbbbbbb",
                        "desc": "Child",
                        "project": "Work",
                        "tags": [],
                        "has_depends": False,
                    },
                    {
                        "uuid": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                        "short": "cccccccc",
                        "desc": "Old child",
                        "project": "Work",
                        "tags": [],
                        "has_depends": False,
                    },
                ],
                "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}},
            }
        )
        html = build_runtime_html(base_html, payload, 3, lambda *_: None)

        harness = """
<script id="E2E_DEP_OVERLAY_PARITY_HARNESS">
window.addEventListener('load', function(){
  try{
    window.stagedAdd = [
      {from:"aaaaaaaa", to:"bbbbbbbb"},
      {from:"aaaaaaaa", to:"bbbbbbbb"}
    ];
    window.__depExtraCmds = [
      "task aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa modify depends:-cccccccc-cccc-cccc-cccc-cccccccccccc"
    ];
    window.STAGED_CMDS = [
      "task aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa modify depends:bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    ];
    if (typeof updateConsole === 'function') updateConsole();
    setTimeout(function(){
      var out = {
        console: (document.getElementById('consoleText') || {}).value || "",
        overlay: (document.getElementById('depCmdPre') || {}).textContent || ""
      };
      var pre = document.createElement('pre');
      pre.id = 'e2e-out';
      pre.textContent = JSON.stringify(out);
      document.body.appendChild(pre);
    }, 350);
  }catch(e){
    var pre2 = document.createElement('pre');
    pre2.id = 'e2e-out';
    pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
    document.body.appendChild(pre2);
  }
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        result = json.loads(raw)
        self.assertEqual(result["console"], result["overlay"])
        self.assertEqual(result["console"].count("depends:bbbbbbbb"), 1)
        self.assertIn("task 'aaaaaaaa' modify 'depends:bbbbbbbb' 'depends:-cccccccc'", result["console"])

    def test_dependency_interactions_runtime_renders_single_handle_and_staged_path(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps(
            {
                "tasks": [
                    {
                        "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "short": "aaaaaaaa",
                        "desc": "Parent",
                        "project": "Work",
                        "tags": [],
                        "has_depends": False,
                    },
                    {
                        "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                        "short": "bbbbbbbb",
                        "desc": "Child",
                        "project": "Work",
                        "tags": [],
                        "has_depends": False,
                    },
                ],
                "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}},
            }
        )
        html = build_runtime_html(base_html, payload, 2, lambda *_: None)
        self.assertIn('id="FEATURE_DEPENDENCY_INTERACTIONS_V1"', html)
        self.assertNotIn("Minimal dep handle", html)
        self.assertNotIn("Dependency system (v0.7.7 strict)", html)
        self.assertNotIn("dep-handle counts (Chrome-optimized)", html)

        harness = """
<script id="E2E_DEP_INTERACTIONS_HARNESS">
window.addEventListener('load', function(){
  try{
    setTimeout(function(){
      var stage = document.getElementById('builderStage');
      function makeNode(uuid, shortId, left, top){
        var node = document.createElement('div');
        node.className = 'node';
        node.setAttribute('data-uuid', uuid);
        node.setAttribute('data-short', shortId);
        node.style.position = 'absolute';
        node.style.left = left + 'px';
        node.style.top = top + 'px';
        node.style.width = '140px';
        node.style.height = '70px';
        node.textContent = shortId;
        stage.appendChild(node);
        if (typeof attachDepHandleToNode === 'function') attachDepHandleToNode(node);
      }
      makeNode("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "aaaaaaaa", 120, 120);
      makeNode("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "bbbbbbbb", 320, 240);
      window.stagedAdd = [{from:"aaaaaaaa", to:"bbbbbbbb"}];
      if (typeof drawLinks === 'function') drawLinks();
      if (typeof updateConsole === 'function') updateConsole();
      setTimeout(function(){
        var out = {
          handles: document.querySelectorAll('#builderStage [data-short] > .depHandle').length,
          wiredHandles: Array.prototype.filter.call(document.querySelectorAll('#builderStage [data-short] > .depHandle'), function(h){ return !!h.__depInteractionWired; }).length,
          parentHandles: document.querySelectorAll('#builderStage [data-short="aaaaaaaa"] > .depHandle').length,
          childHandles: document.querySelectorAll('#builderStage [data-short="bbbbbbbb"] > .depHandle').length,
          stagedPaths: document.querySelectorAll('#depStagedOverlay path[data-from="aaaaaaaa"][data-to="bbbbbbbb"]').length,
          commandText: window.TaskCanvasCommands.runtimeCommandText(window, {short:true})
        };
        var pre = document.createElement('pre');
        pre.id = 'e2e-out';
        pre.textContent = JSON.stringify(out);
        document.body.appendChild(pre);
      }, 350);
    }, 500);
  }catch(e){
    var pre2 = document.createElement('pre');
    pre2.id = 'e2e-out';
    pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
    document.body.appendChild(pre2);
  }
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        result = json.loads(raw)
        self.assertEqual(result["handles"], 2)
        self.assertEqual(result["wiredHandles"], 2)
        self.assertEqual(result["parentHandles"], 1)
        self.assertEqual(result["childHandles"], 1)
        self.assertEqual(result["stagedPaths"], 1)
        self.assertIn("task 'aaaaaaaa' modify 'depends:bbbbbbbb'", result["commandText"])

    def test_dependency_edges_runtime_renders_existing_edges_and_pulses_once(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps(
            {
                "tasks": [
                    {
                        "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "short": "aaaaaaaa",
                        "desc": "Parent",
                        "project": "Work",
                        "tags": [],
                        "has_depends": False,
                    },
                    {
                        "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                        "short": "bbbbbbbb",
                        "desc": "Child",
                        "project": "Work",
                        "tags": [],
                        "has_depends": False,
                    },
                    {
                        "uuid": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                        "short": "cccccccc",
                        "desc": "Staged child",
                        "project": "Work",
                        "tags": [],
                        "has_depends": False,
                    },
                ],
                "graph": {
                    "edges": [{"from": "aaaaaaaa", "to": "bbbbbbbb"}],
                    "parent_current_deps": {},
                    "child_to_parents": {},
                },
            }
        )
        html = build_runtime_html(base_html, payload, 3, lambda *_: None)
        self.assertIn('id="FEATURE_DEPENDENCY_EDGES_V1"', html)
        self.assertNotIn("dep pulses: animate energy", html)
        self.assertNotIn("draw solid existing edges with robust anchors", html)

        harness = """
<script id="E2E_DEP_EDGES_HARNESS">
window.addEventListener('load', function(){
  try{
    setTimeout(function(){
      var stage = document.getElementById('builderStage');
      function makeNode(uuid, shortId, left, top){
        var node = document.createElement('div');
        node.className = 'node';
        node.setAttribute('data-uuid', uuid);
        node.setAttribute('data-short', shortId);
        node.style.position = 'absolute';
        node.style.left = left + 'px';
        node.style.top = top + 'px';
        node.style.width = '140px';
        node.style.height = '70px';
        node.textContent = shortId;
        stage.appendChild(node);
        if (typeof attachDepHandleToNode === 'function') attachDepHandleToNode(node);
      }
      makeNode("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "aaaaaaaa", 120, 120);
      makeNode("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "bbbbbbbb", 340, 230);
      makeNode("cccccccc-cccc-cccc-cccc-cccccccccccc", "cccccccc", 560, 330);
      window.EXIST_EDGES = [{from:"aaaaaaaa", to:"bbbbbbbb"}];
      window.stagedAdd = [{from:"bbbbbbbb", to:"cccccccc"}];
      if (typeof drawLinks === 'function') drawLinks();
      if (typeof drawLinks === 'function') drawLinks();
      setTimeout(function(){
        var out = {
          existingGroups: document.querySelectorAll('#depExistingEdges').length,
          existingPaths: document.querySelectorAll('#depExistingEdges path[data-from="aaaaaaaa"][data-to="bbbbbbbb"]').length,
          stagedGroups: document.querySelectorAll('#depStagedOverlay').length,
          stagedPaths: document.querySelectorAll('#depStagedOverlay path[data-from="bbbbbbbb"][data-to="cccccccc"]').length,
          pulseGroups: document.querySelectorAll('#depPulseOverlay').length,
          pulses: document.querySelectorAll('#depPulseOverlay .pulse-dot').length,
          api: !!window.TaskCanvasDependencyEdges
        };
        var pre = document.createElement('pre');
        pre.id = 'e2e-out';
        pre.textContent = JSON.stringify(out);
        document.body.appendChild(pre);
      }, 450);
    }, 500);
  }catch(e){
    var pre2 = document.createElement('pre');
    pre2.id = 'e2e-out';
    pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
    document.body.appendChild(pre2);
  }
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        result = json.loads(raw)
        self.assertTrue(result["api"])
        self.assertEqual(result["existingGroups"], 1)
        self.assertEqual(result["existingPaths"], 1)
        self.assertEqual(result["stagedGroups"], 1)
        self.assertEqual(result["stagedPaths"], 1)
        self.assertEqual(result["pulseGroups"], 1)
        self.assertGreaterEqual(result["pulses"], 2)

    def test_project_picker_runtime_opens_and_lists_projects(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps(
            {
                "tasks": [
                    {
                        "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "short": "aaaaaaaa",
                        "desc": "Alpha",
                        "project": "Work",
                        "tags": [],
                        "has_depends": False,
                    },
                    {
                        "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                        "short": "bbbbbbbb",
                        "desc": "Beta",
                        "project": "Home",
                        "tags": [],
                        "has_depends": False,
                    },
                ],
                "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}},
            }
        )
        html = build_runtime_html(base_html, payload, 2, lambda *_: None)
        self.assertIn('id="PROJECT_PICKER_V2_CSS"', html)
        self.assertIn('id="PROJECT_PICKER_V2_JS"', html)
        self.assertNotIn("<!-- PROJECT_PICKER_V2_CSS -->", html)
        self.assertNotIn("<!-- PROJECT_PICKER_V2_JS -->", html)
        self.assertNotIn("<!-- PROJECT_PICKER_V2_BIND -->", html)

        harness = """
<script id="E2E_PROJECT_PICKER_HARNESS">
window.addEventListener('load', function(){
  try{
    setTimeout(function(){
      window.showProjectPickerV2();
      setTimeout(function(){
        var out = {
          overlay: document.querySelectorAll('.projPickOverlay').length,
          items: Array.prototype.map.call(document.querySelectorAll('.projPickItem .name'), function(el){ return el.textContent; }),
          selectedText: (document.querySelector('.projPickFooter') || {}).textContent || ''
        };
        var pre = document.createElement('pre');
        pre.id = 'e2e-out';
        pre.textContent = JSON.stringify(out);
        document.body.appendChild(pre);
      }, 100);
    }, 250);
  }catch(e){
    var pre2 = document.createElement('pre');
    pre2.id = 'e2e-out';
    pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
    document.body.appendChild(pre2);
  }
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        result = json.loads(raw)
        self.assertEqual(result["overlay"], 1)
        self.assertEqual(result["items"], ["Home", "Work"])
        self.assertIn("0 selected", result["selectedText"])

    def test_quickfix_add_render_runtime_exposes_parser_and_optimistic_add(self):
        base_html = Path("taskcanvas/templates/taskcanvas.base.html").read_text(encoding="utf-8")
        payload = json.dumps({"tasks": [], "graph": {"edges": [], "parent_current_deps": {}, "child_to_parents": {}}})
        html = build_runtime_html(base_html, payload, 0, lambda *_: None)
        self.assertIn('id="FEATURE_QUICKFIX_ADD_RENDER_V1"', html)
        self.assertNotIn('<script id="FEATURE_QUICKFIX_ADD_RENDER_V1">(function(){\n  if (window.__FEATURE_QUICKFIX_ADD_RENDER_V1__)', base_html)

        harness = """
<script id="E2E_QUICKFIX_ADD_HARNESS">
window.addEventListener('load', function(){
  try{
    setTimeout(function(){
      var parsed = window.TaskCanvasQuickAdd.parseAdd("task add Review report project:Work +next due:tomorrow");
      var ok = window.TaskCanvasQuickAdd.optimisticAdd("task add Review report project:Work +next due:tomorrow");
      setTimeout(function(){
        var node = document.querySelector('#builderStage .node[data-uuid^="new-"]');
        var out = {
          parsed: parsed,
          ok: ok,
          hasNode: !!node,
          nodeProject: node && node.getAttribute('data-proj'),
          nodeText: node ? node.textContent : ''
        };
        var pre = document.createElement('pre');
        pre.id = 'e2e-out';
        pre.textContent = JSON.stringify(out);
        document.body.appendChild(pre);
      }, 250);
    }, 350);
  }catch(e){
    var pre2 = document.createElement('pre');
    pre2.id = 'e2e-out';
    pre2.textContent = 'ERR:' + (e && e.message ? e.message : String(e));
    document.body.appendChild(pre2);
  }
});
</script>
"""
        html = html.replace("</body>", harness + "\n</body>")
        raw = self._run_html_harness(html)
        self.assertNotIn("ERR:", raw)
        result = json.loads(raw)
        self.assertEqual(result["parsed"]["desc"], "Review report")
        self.assertEqual(result["parsed"]["project"], "Work")
        self.assertEqual(result["parsed"]["tags"], ["next"])
        self.assertTrue(result["ok"])
        self.assertTrue(result["hasNode"])
        self.assertIn("Review report", result["nodeText"])


if __name__ == "__main__":
    unittest.main()
