#!/usr/bin/env bash
# CI 入口脚本：串联 pytest + vitest + tsc --noEmit
# 用法：bash scripts/ci.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$ROOT/services/aos-api"
WEB_DIR="$ROOT/apps/web"

echo "========================================="
echo " AOS Platform CI"
echo "========================================="

failures=0

# --- 1. 后端 pytest ---
echo
echo "[1/3] 后端 pytest..."
if bash "$ROOT/scripts/ci/run-pytest.sh" "$@"; then
  echo "✅ pytest passed"
else
  echo "❌ pytest failed"
  failures=$((failures + 1))
fi

# --- 2. 前端 vitest ---
echo
echo "[2/3] 前端 vitest..."
if [ -d "$WEB_DIR" ]; then
  cd "$WEB_DIR"
  if command -v npx >/dev/null 2>&1; then
    if npx vitest run 2>&1; then
      echo "✅ vitest passed"
    else
      echo "❌ vitest failed"
      failures=$((failures + 1))
    fi
  else
    echo "⚠️  npx not available, skipping vitest"
  fi
else
  echo "⚠️  web dir not found, skipping vitest"
fi

# --- 3. 前端 tsc --noEmit ---
echo
echo "[3/3] 前端 tsc --noEmit..."
if [ -d "$WEB_DIR" ]; then
  cd "$WEB_DIR"
  if command -v npx >/dev/null 2>&1; then
    if npx tsc --noEmit 2>&1; then
      echo "✅ tsc passed"
    else
      echo "❌ tsc failed"
      failures=$((failures + 1))
    fi
  else
    echo "⚠️  npx not available, skipping tsc"
  fi
else
  echo "⚠️  web dir not found, skipping tsc"
fi

echo
echo "========================================="
if [ "$failures" -eq 0 ]; then
  echo " RESULT: ALL PASSED"
  echo "========================================="
  exit 0
else
  echo " RESULT: $failures FAILURE(S)"
  echo "========================================="
  exit 1
fi
