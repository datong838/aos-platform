#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/ddt/work/projects/ai_agent/aos-platform"
SRC="$ROOT/.evidence/qyh-successor-readonly-deployment-20261031/private/source-r3"
CFG="$ROOT/.evidence/qyh-successor-readonly-deployment-20261031/private/window-http-readonly-config-r1.json"
PY="$ROOT/services/aos-api/.venv/bin/python"
if lsof -iTCP:18468 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "18468 already listening"
  exit 0
fi
cd "$SRC"
exec env PYTHONPATH=services/aos-api "$PY" -B scripts/a0v_qyh_budget_policy_window.py --serve --config "$CFG"
