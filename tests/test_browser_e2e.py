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


if __name__ == "__main__":
    unittest.main()
