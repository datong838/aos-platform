#!/usr/bin/env bash
# AOS Platform unified CI entrypoint.
# Usage: bash scripts/ci.sh quick|wave|full
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CI_DIR="$ROOT/scripts/ci"

usage() {
  cat <<'EOF'
Usage: bash scripts/ci.sh <quick|wave|full>

  quick  CI shell syntax and entrypoint self-tests
  wave   quick + backend + Web/Desktop/SDK tests and typechecks
  full   wave + Web/Desktop production builds

Required directories, commands, runners, and local dependencies must exist.
This command never installs dependencies.
EOF
}

if [ "$#" -ne 1 ]; then
  usage >&2
  exit 2
fi

MODE="$1"
case "$MODE" in
  quick|wave|full) ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    echo "FAIL unknown CI mode: $MODE" >&2
    usage >&2
    exit 2
    ;;
esac

failures=0
passes=0
gate_index=0
total_gates=0

case "$MODE" in
  quick) total_gates=1 ;;
  wave) total_gates=7 ;;
  full) total_gates=9 ;;
esac

run_gate() {
  gate_index=$((gate_index + 1))
  gate_name="$1"
  shift

  echo
  echo "[$gate_index/$total_gates] $gate_name"
  printf 'COMMAND:'
  printf ' %q' "$@"
  printf '\n'

  if "$@"; then
    echo "PASS $gate_name"
    passes=$((passes + 1))
  else
    gate_code=$?
    echo "FAIL $gate_name (exit=$gate_code)"
    failures=$((failures + 1))
  fi
}

require_runner() {
  runner="$1"
  if [ ! -f "$runner" ]; then
    echo "FAIL required CI runner not found: $runner" >&2
    return 1
  fi
  if [ ! -r "$runner" ]; then
    echo "FAIL required CI runner is not readable: $runner" >&2
    return 1
  fi
}

run_required_gate() {
  gate_name="$1"
  runner="$2"
  shift 2

  if require_runner "$runner"; then
    run_gate "$gate_name" bash "$runner" "$@"
  else
    gate_index=$((gate_index + 1))
    echo
    echo "[$gate_index/$total_gates] $gate_name"
    echo "FAIL $gate_name (required runner unavailable)"
    failures=$((failures + 1))
  fi
}

echo "========================================="
echo " AOS Platform CI"
echo " MODE: $MODE"
echo " ROOT: $ROOT"
echo "========================================="

run_required_gate "CI shell checks" "$CI_DIR/run-shell-checks.sh"

if [ "$MODE" = "wave" ] || [ "$MODE" = "full" ]; then
  run_required_gate "Backend pytest" "$CI_DIR/run-pytest.sh"
  run_required_gate "Web tests" "$CI_DIR/run-node-gate.sh" web test
  run_required_gate "Web typecheck" "$CI_DIR/run-node-gate.sh" web typecheck
  run_required_gate "Desktop tests" "$CI_DIR/run-node-gate.sh" desktop test
  run_required_gate "Desktop typecheck" "$CI_DIR/run-node-gate.sh" desktop typecheck
  run_required_gate "Ontology SDK tests" "$CI_DIR/run-node-gate.sh" sdk test
fi

if [ "$MODE" = "full" ]; then
  run_required_gate "Web build" "$CI_DIR/run-node-gate.sh" web build
  run_required_gate "Desktop build" "$CI_DIR/run-node-gate.sh" desktop build
fi

echo
echo "========================================="
echo " SUMMARY: mode=$MODE passed=$passes failed=$failures total=$total_gates"
if [ "$failures" -eq 0 ]; then
  echo " RESULT: PASSED"
  echo "========================================="
  exit 0
fi

echo " RESULT: FAILED"
echo "========================================="
exit 1
