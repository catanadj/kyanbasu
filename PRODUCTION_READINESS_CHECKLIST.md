# Production Readiness Checklist

Status key: `[ ]` pending, `[~]` in progress, `[x]` done

## P0 - Security / Correctness

- [x] Harden payload embedding against `</script>` termination in any case (e.g. `</SCRIPT>`).
  - Files: `taskcanvas/runtime_html.py`, tests in `tests/test_runtime_html.py`
- [x] Make generated Taskwarrior commands shell-safe and semantically stable for descriptions/modifiers.
  - Files: `templates/taskcanvas.base.html`, `taskcanvas/runtime_html.py`, `taskcanvas/injectors.py`
  - Add tests for quoting/escaping behavior.

## P1 - Reliability / Idempotency

- [x] Fix injector idempotency marker mismatches causing duplicate injections.
  - Files: `taskcanvas/injectors.py`, tests in `tests/test_injectors.py`
- [x] Guarantee short ID uniqueness even for pathological normalized-collision inputs.
  - Files: `taskcanvas/task_io.py`, tests in `tests/test_task_io.py`
- [x] Error on missing values for `--filter` and `--bg` instead of silently degrading behavior.
  - Files: `taskcanvas/cli.py`, `TaskCanvas.py`, tests in `tests/test_cli.py` + `tests/test_main.py`

## P2 - Observability / Performance

- [x] Add lightweight runtime diagnostics for swallowed browser-side exceptions.
- [x] Reduce polling where possible (prefer event-driven triggers over frequent intervals).
- [x] Add browser-level E2E checks for command generation correctness.

## Validation Gate

- [x] `python3 -m unittest discover -s tests -v`
- [x] `TASKCANVAS_RUN_INTEGRATION=1 python3 -m unittest tests.test_task_io_integration -v`
- [x] Automated hostile-payload + repeated rebuild smoke checks.
- [x] Interactive browser validation where Chromium can run without sandbox restrictions.
