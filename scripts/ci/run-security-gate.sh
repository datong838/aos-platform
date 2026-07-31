#!/usr/bin/env bash
# Run redacted source scanning, scanner tests, and optional delivery scans.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCANNER="$ROOT/scripts/security/scan_sensitive.py"
SCANNER_TEST="$ROOT/scripts/security/test_scan_sensitive.py"

if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "$1" != "--artifacts" ]; }; then
  echo "Usage: bash scripts/ci/run-security-gate.sh [--artifacts]" >&2
  exit 2
fi

if [ -n "${AOS_CI_PYTHON:-}" ]; then
  PY="$AOS_CI_PYTHON"
else
  PY="$(command -v python || command -v python3 || true)"
fi
if [ -z "$PY" ] || [ ! -x "$PY" ]; then
  echo "FAIL required Python interpreter not found for security gate" >&2
  exit 1
fi
if [ ! -f "$SCANNER" ] || [ ! -f "$SCANNER_TEST" ]; then
  echo "FAIL security scanner or tests not found" >&2
  exit 1
fi

"$PY" "$SCANNER_TEST"
"$PY" "$SCANNER" --report summary

if [ "$#" -eq 1 ]; then
  WEB_DIST="$ROOT/apps/web/dist"
  DESKTOP_DIST="$ROOT/apps/desktop/dist"
  if [ ! -d "$WEB_DIST" ] || [ ! -d "$DESKTOP_DIST" ]; then
    echo "FAIL required delivery artifacts not found; run builds first" >&2
    exit 1
  fi
  "$PY" "$SCANNER" --report summary "$WEB_DIST" "$DESKTOP_DIST"
fi
