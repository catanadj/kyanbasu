#!/usr/bin/env bash
set -euo pipefail

echo "[release-check] Running compile checks..."
python3 -m compileall -q Kyanbasu.py kyanbasu tests

echo "[release-check] Running unit tests..."
python3 -m unittest discover -s tests -v

wheel_dir="$(mktemp -d)"
install_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$wheel_dir" "$install_dir"
}
trap cleanup EXIT

echo "[release-check] Building wheel..."
python3 -m pip wheel --no-build-isolation --no-deps --wheel-dir "$wheel_dir" .

echo "[release-check] Smoke testing wheel..."
python3 -m pip install --no-deps --target "$install_dir" "$wheel_dir"/*.whl
primary_version="$(cd /tmp && PYTHONPATH="$install_dir" "$install_dir/bin/kyanbasu" --version)"
test "$primary_version" = "Kyanbasu 0.3.0"
(cd /tmp && PYTHONPATH="$install_dir" python3 -c "from kyanbasu.app import _load_runtime_html; assert 'Kyanbasu' in _load_runtime_html()")

if ! command -v task >/dev/null 2>&1; then
  echo "[release-check] ERROR: Taskwarrior binary ('task') is required for integration checks."
  echo "[release-check] Install Taskwarrior and re-run scripts/release_check.sh"
  exit 1
fi

echo "[release-check] Running Taskwarrior integration tests..."
KYANBASU_RUN_INTEGRATION=1 python3 -m unittest tests.test_task_io_integration -v

echo "[release-check] OK"
