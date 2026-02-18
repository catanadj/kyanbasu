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
        p = subprocess.run(
            [cls.chromium, "--headless", "--no-sandbox", "about:blank"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
        )
        if p.returncode != 0:
            raise unittest.SkipTest(
                f"Chromium unavailable in this environment (rc={p.returncode}); skipping browser E2E."
            )

    def test_build_commands_shell_quotes_new_task_description_and_modifiers(self):
        base_html = Path("templates/taskcanvas.base.html").read_text(encoding="utf-8")
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

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "TaskCanvas.e2e.html"
            p.write_text(html, encoding="utf-8")
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
            if out.returncode != 0:
                self.skipTest(f"Chromium failed in this environment (rc={out.returncode}).")

            m = re.search(r'<pre id="e2e-out">(.*?)</pre>', out.stdout, flags=re.S)
            self.assertIsNotNone(m, "Harness output element not found in dumped DOM.")
            cmds = m.group(1)
            self.assertNotIn("ERR:", cmds)
            self.assertIn("task add", cmds)
            self.assertIn("'project:Work' '+safe'", cmds)
            self.assertIn("'hello; world $(id) O'\"'\"'Reilly'", cmds)


if __name__ == "__main__":
    unittest.main()
