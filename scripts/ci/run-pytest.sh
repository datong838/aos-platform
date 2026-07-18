#!/usr/bin/env bash
# W13 · aos-api pytest 回归（对齐 89 · macOS/Linux）
# 用法：bash scripts/ci/run-pytest.sh
# 可选：AOS_PYTEST_ARGS="-k align" 过滤子集
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API_DIR="$ROOT/services/aos-api"

export PATH="${HOME}/tools/micromamba-root/envs/aos/bin:${HOME}/tools/bin:${PATH}"

if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL no python"
  exit 1
fi
PY="$(command -v python || true)"
if [ -z "$PY" ]; then PY="$(command -v python3)"; fi

cd "$API_DIR"

if ! "$PY" -c "import pytest" 2>/dev/null; then
  echo "WARN pytest missing — pip install -e '.[dev]'"
  "$PY" -m pip install -e ".[dev]" -q
fi

# JWKS tests need cryptography (listed in [dev]; ensure present)
if ! "$PY" -c "import cryptography" 2>/dev/null; then
  "$PY" -m pip install "cryptography>=42" -q
fi

echo "=== aos-api pytest ==="
set +e
"$PY" -m pytest tests/ -q --tb=line ${AOS_PYTEST_ARGS:-}
code=$?
set -e

echo
if [ "$code" -eq 0 ]; then
  echo "RESULT: PYTEST OK"
  exit 0
fi
echo "RESULT: PYTEST FAIL (exit=$code)"
exit "$code"
