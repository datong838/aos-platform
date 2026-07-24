#!/usr/bin/env bash
# W18 · TB.8 彩排前聚合冒烟：demo + Agnes（可选）
# 用法：bash scripts/demo/run-rehearsal-smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "=== Rehearsal smoke (TB.8 prep) ==="
bash "$ROOT/scripts/demo/ensure-api.sh"
bash "$ROOT/scripts/demo/run-demo-smoke.sh"

echo
echo "--- optional Agnes LLM ---"
bash "$ROOT/scripts/demo/run-agnes-smoke.sh"

echo
echo "RESULT: REHEARSAL SMOKE OK"
