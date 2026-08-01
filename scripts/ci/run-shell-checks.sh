#!/usr/bin/env bash
# Validate CI shell syntax and run the deterministic entrypoint self-test.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CI_DIR="$ROOT/scripts/ci"

if [ ! -f "$ROOT/scripts/ci.sh" ]; then
  echo "FAIL CI entrypoint not found: $ROOT/scripts/ci.sh" >&2
  exit 1
fi

checked=0
while IFS= read -r script; do
  bash -n "$script"
  checked=$((checked + 1))
done < <(find "$CI_DIR" -maxdepth 1 -type f -name 'run-*.sh' | sort)
bash -n "$ROOT/scripts/ci.sh"
checked=$((checked + 1))

echo "SHELL_SYNTAX_CHECKED: $checked"
bash "$CI_DIR/run-ci-selftest.sh"
python3 -m unittest "$CI_DIR/test_interaction_honesty.py"
python3 "$CI_DIR/check-interaction-honesty.py" --root "$ROOT"
