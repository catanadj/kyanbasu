#!/usr/bin/env bash
set -euo pipefail

echo "[release-check] Running compile checks..."
python3 -m compileall -q Kyanbasu.py TaskCanvas.py kyanbasu taskcanvas tests

echo "[release-check] Running unit tests..."
python3 -m unittest discover -s tests -v

if ! command -v task >/dev/null 2>&1; then
  echo "[release-check] ERROR: Taskwarrior binary ('task') is required for integration checks."
  echo "[release-check] Install Taskwarrior and re-run scripts/release_check.sh"
  exit 1
fi

echo "[release-check] Running Taskwarrior integration tests..."
TASKCANVAS_RUN_INTEGRATION=1 python3 -m unittest tests.test_task_io_integration -v

echo "[release-check] OK"
