#!/usr/bin/env bash
# W33 · 可演示冻结快检：API 可达 + demo smoke（含 l1-chain）+ Web 单测
# 用法：bash scripts/demo/run-freeze-check.sh
# 全量（含 pytest + 彩排）：bash scripts/demo/run-freeze-check.sh --full
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FULL="${1:-}"

echo "=== Freeze maintenance check (W33) ==="
bash "$ROOT/scripts/demo/ensure-api.sh"
bash "$ROOT/scripts/demo/run-demo-smoke.sh"

echo
echo "--- web unit tests ---"
(cd "$ROOT/apps/web" && npm test -- --run)

if [[ "$FULL" == "--full" ]]; then
  echo
  echo "--- api pytest ---"
  bash "$ROOT/scripts/ci/run-pytest.sh"
  echo
  echo "--- rehearsal (demo + Agnes) ---"
  bash "$ROOT/scripts/demo/run-rehearsal-smoke.sh"
fi

echo
echo "RESULT: FREEZE CHECK OK"
