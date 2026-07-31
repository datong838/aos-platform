#!/usr/bin/env bash
# Verify the committed OpenAPI artifacts and their compatibility contract.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API_DIR="$ROOT/services/aos-api"
EXPORTER="$ROOT/scripts/export_openapi.py"
CONTRACT_TEST="$API_DIR/tests/test_openapi_contract.py"

PYTHON_BIN="${AOS_CI_PYTHON:-$(command -v python3 || command -v python || true)}"
if [ -z "$PYTHON_BIN" ] || [ ! -x "$PYTHON_BIN" ]; then
  echo "FAIL required Python executable not found" >&2
  exit 1
fi
for required_file in "$EXPORTER" "$CONTRACT_TEST" \
  "$ROOT/packages/contracts/openapi/v1.generated.json" \
  "$ROOT/packages/contracts/openapi/v1.inventory.json"; do
  if [ ! -f "$required_file" ]; then
    echo "FAIL required OpenAPI gate input not found: $required_file" >&2
    exit 1
  fi
done

echo "PYTHON: $($PYTHON_BIN --version 2>&1)"
"$PYTHON_BIN" "$EXPORTER" --check
(
  cd "$API_DIR"
  "$PYTHON_BIN" -m pytest -q tests/test_openapi_contract.py
)
