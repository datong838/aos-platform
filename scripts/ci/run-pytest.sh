#!/usr/bin/env bash
# aos-api pytest regression runner (macOS/Linux).
# Usage: bash scripts/ci/run-pytest.sh [pytest arguments...]
# 可选：AOS_PYTEST_ARGS="-k align" 过滤子集
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API_DIR="$ROOT/services/aos-api"

if [ ! -d "$API_DIR" ]; then
  echo "FAIL aos-api directory not found: $API_DIR" >&2
  exit 1
fi

if [ -n "${AOS_CI_PYTHON:-}" ]; then
  PY="$AOS_CI_PYTHON"
  if [ ! -x "$PY" ]; then
    echo "FAIL AOS_CI_PYTHON is not executable: $PY" >&2
    exit 1
  fi
else
  PY="$(command -v python || command -v python3 || true)"
fi

if [ -z "$PY" ]; then
  echo "FAIL required Python interpreter not found" >&2
  exit 1
fi

echo "PYTHON: $("$PY" --version 2>&1)"

cd "$API_DIR"

if ! "$PY" -c "import pytest" >/dev/null 2>&1; then
  echo "FAIL pytest is not installed for $PY; CI does not install dependencies" >&2
  exit 1
fi

echo "=== aos-api pytest ==="
if [ -n "${AOS_PYTEST_ARGS:-}" ]; then
  # Intentional shell-style whitespace splitting for the documented filter variable.
  extra_args=()
  read -r -a extra_args <<< "$AOS_PYTEST_ARGS"
  "$PY" -m pytest tests/ -q --tb=line "${extra_args[@]}" "$@"
else
  "$PY" -m pytest tests/ -q --tb=line "$@"
fi
