#!/usr/bin/env bash
# Deterministic tests for scripts/ci.sh. Uses only a temporary fake repository.
set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/aos-ci-selftest.XXXXXX")"
TMP_ROOT="$(cd "$TMP_ROOT" && pwd)"
trap 'rm -rf "$TMP_ROOT"' EXIT

FAKE_ROOT="$TMP_ROOT/repo"
mkdir -p \
  "$FAKE_ROOT/scripts/ci" \
  "$FAKE_ROOT/apps/web/src" \
  "$FAKE_ROOT/apps/desktop/src" \
  "$FAKE_ROOT/packages/ontology-sdk/src" \
  "$FAKE_ROOT/services/aos-api/tests"
cp "$SOURCE_ROOT/scripts/ci.sh" "$FAKE_ROOT/scripts/ci.sh"

cat > "$FAKE_ROOT/scripts/ci/run-shell-checks.sh" <<'EOF'
#!/usr/bin/env bash
set -eu
echo "fake shell checks"
[ "${FAKE_FAIL_GATE:-}" != "shell" ]
EOF

cat > "$FAKE_ROOT/scripts/ci/run-pytest.sh" <<'EOF'
#!/usr/bin/env bash
set -eu
echo "fake backend tests"
[ "${FAKE_FAIL_GATE:-}" != "backend" ]
EOF

cat > "$FAKE_ROOT/scripts/ci/run-openapi-gate.sh" <<'EOF'
#!/usr/bin/env bash
set -eu
echo "fake openapi gate"
[ "${FAKE_FAIL_GATE:-}" != "openapi" ]
EOF

cat > "$FAKE_ROOT/scripts/ci/run-node-gate.sh" <<'EOF'
#!/usr/bin/env bash
set -eu
echo "fake node gate: $1:$2"
[ "${FAKE_FAIL_GATE:-}" != "$1:$2" ]
EOF

cat > "$FAKE_ROOT/scripts/ci/run-security-gate.sh" <<'EOF'
#!/usr/bin/env bash
set -eu
echo "fake security gate: ${1:-source}"
[ "${FAKE_FAIL_GATE:-}" != "security" ]
EOF
cat > "$FAKE_ROOT/scripts/ci/helm-template-spoke-full.sh" <<'EOF'
#!/usr/bin/env bash
set -eu
echo "fake helm gate: ${1:-}"
[ "${FAKE_FAIL_GATE:-}" != "helm" ]
EOF

assert_contains() {
  file="$1"
  expected="$2"
  if ! grep -F -- "$expected" "$file" >/dev/null; then
    echo "SELFTEST FAIL expected '$expected' in $file" >&2
    sed -n '1,200p' "$file" >&2
    exit 1
  fi
}

tests=0

help_output="$TMP_ROOT/help.log"
bash "$FAKE_ROOT/scripts/ci.sh" --help >"$help_output"
assert_contains "$help_output" "quick|wave|full"
tests=$((tests + 1))

invalid_output="$TMP_ROOT/invalid.log"
set +e
bash "$FAKE_ROOT/scripts/ci.sh" invalid >"$invalid_output" 2>&1
invalid_code=$?
set -e
if [ "$invalid_code" -ne 2 ]; then
  echo "SELFTEST FAIL invalid mode exit=$invalid_code, expected=2" >&2
  exit 1
fi
tests=$((tests + 1))

for cwd in "$FAKE_ROOT" "$FAKE_ROOT/apps/web" "$TMP_ROOT"; do
  quick_output="$TMP_ROOT/quick-$tests.log"
  (
    cd "$cwd"
    bash "$FAKE_ROOT/scripts/ci.sh" quick
  ) >"$quick_output"
  assert_contains "$quick_output" "ROOT: $FAKE_ROOT"
  assert_contains "$quick_output" "passed=2 failed=0 total=2"
  tests=$((tests + 1))
done

wave_output="$TMP_ROOT/wave-failure.log"
set +e
(
  cd "$TMP_ROOT"
  FAKE_FAIL_GATE=backend bash "$FAKE_ROOT/scripts/ci.sh" wave
) >"$wave_output" 2>&1
wave_code=$?
set -e
if [ "$wave_code" -eq 0 ]; then
  echo "SELFTEST FAIL wave child failure returned success" >&2
  exit 1
fi
assert_contains "$wave_output" "FAIL Backend pytest"
assert_contains "$wave_output" "fake node gate: sdk:test"
assert_contains "$wave_output" "passed=9 failed=1 total=10"
tests=$((tests + 1))

full_output="$TMP_ROOT/full.log"
bash "$FAKE_ROOT/scripts/ci.sh" full >"$full_output"
assert_contains "$full_output" "fake node gate: web:build"
assert_contains "$full_output" "fake node gate: desktop:build"
assert_contains "$full_output" "fake openapi gate"
assert_contains "$full_output" "fake helm gate: --require"
assert_contains "$full_output" "fake security gate: --artifacts"
assert_contains "$full_output" "passed=12 failed=0 total=12"
tests=$((tests + 1))

missing_output="$TMP_ROOT/missing-runner.log"
mv "$FAKE_ROOT/scripts/ci/run-node-gate.sh" "$FAKE_ROOT/scripts/ci/run-node-gate.sh.disabled"
set +e
bash "$FAKE_ROOT/scripts/ci.sh" wave >"$missing_output" 2>&1
missing_code=$?
set -e
if [ "$missing_code" -eq 0 ]; then
  echo "SELFTEST FAIL missing required runner returned success" >&2
  exit 1
fi
assert_contains "$missing_output" "required runner unavailable"
assert_contains "$missing_output" "passed=5 failed=5 total=10"
tests=$((tests + 1))

RUNNER_ROOT="$TMP_ROOT/runner-repo"
mkdir -p "$RUNNER_ROOT/scripts/ci" "$RUNNER_ROOT/services/aos-api"
cp "$SOURCE_ROOT/scripts/ci/run-node-gate.sh" "$RUNNER_ROOT/scripts/ci/run-node-gate.sh"
cp "$SOURCE_ROOT/scripts/ci/run-pytest.sh" "$RUNNER_ROOT/scripts/ci/run-pytest.sh"

missing_dir_output="$TMP_ROOT/missing-dir.log"
set +e
bash "$RUNNER_ROOT/scripts/ci/run-node-gate.sh" web test >"$missing_dir_output" 2>&1
missing_dir_code=$?
set -e
if [ "$missing_dir_code" -eq 0 ]; then
  echo "SELFTEST FAIL missing package directory returned success" >&2
  exit 1
fi
assert_contains "$missing_dir_output" "required package directory not found"
tests=$((tests + 1))

mkdir -p "$RUNNER_ROOT/apps/web"
printf '{"scripts":{"test":"true"}}\n' > "$RUNNER_ROOT/apps/web/package.json"
printf '{\n  "packageManager": "pnpm@11.9.0"\n}\n' > "$RUNNER_ROOT/package.json"
printf 'packages:\n  - "apps/*"\n' > "$RUNNER_ROOT/pnpm-workspace.yaml"
printf 'lockfileVersion: "9.0"\n' > "$RUNNER_ROOT/pnpm-lock.yaml"
missing_node_output="$TMP_ROOT/missing-node.log"
set +e
AOS_CI_NODE="$TMP_ROOT/missing-node" \
  bash "$RUNNER_ROOT/scripts/ci/run-node-gate.sh" web test >"$missing_node_output" 2>&1
missing_node_code=$?
set -e
if [ "$missing_node_code" -eq 0 ]; then
  echo "SELFTEST FAIL missing Node command returned success" >&2
  exit 1
fi
assert_contains "$missing_node_output" "required Node executable not found"
tests=$((tests + 1))

mkdir -p "$RUNNER_ROOT/apps/web/node_modules/.bin"
fake_node="$TMP_ROOT/fake-node"
fake_pnpm="$TMP_ROOT/fake-pnpm"
fake_vitest="$RUNNER_ROOT/apps/web/node_modules/.bin/vitest"
cat > "$fake_node" <<'EOF'
#!/usr/bin/env bash
echo "v-test"
EOF
cat > "$fake_pnpm" <<'EOF'
#!/usr/bin/env bash
if [ "${1:-}" = "--version" ]; then
  echo "11.9.0"
  exit 0
fi
exit 0
EOF
cat > "$fake_vitest" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" > "$FAKE_VITEST_ARGS"
EOF
chmod +x "$fake_node" "$fake_pnpm" "$fake_vitest"

vitest_args="$TMP_ROOT/vitest-args.log"
FAKE_VITEST_ARGS="$vitest_args" \
  AOS_CI_PACKAGE_MANAGER=pnpm \
  AOS_CI_NODE="$fake_node" \
  AOS_CI_PNPM="$fake_pnpm" \
  bash "$RUNNER_ROOT/scripts/ci/run-node-gate.sh" web test >/dev/null
assert_contains "$vitest_args" "run"
tests=$((tests + 1))

unsupported_manager_output="$TMP_ROOT/unsupported-manager.log"
set +e
AOS_CI_PACKAGE_MANAGER=auto \
  AOS_CI_NODE="$fake_node" \
  AOS_CI_PNPM="$fake_pnpm" \
  bash "$RUNNER_ROOT/scripts/ci/run-node-gate.sh" web test >"$unsupported_manager_output" 2>&1
unsupported_manager_code=$?
set -e
if [ "$unsupported_manager_code" -eq 0 ]; then
  echo "SELFTEST FAIL unsupported package manager returned success" >&2
  exit 1
fi
assert_contains "$unsupported_manager_output" "only supports pnpm"
tests=$((tests + 1))

rm "$fake_vitest"
missing_dependency_output="$TMP_ROOT/missing-dependency.log"
set +e
AOS_CI_NODE="$fake_node" AOS_CI_PNPM="$fake_pnpm" \
  bash "$RUNNER_ROOT/scripts/ci/run-node-gate.sh" web test >"$missing_dependency_output" 2>&1
missing_dependency_code=$?
set -e
if [ "$missing_dependency_code" -eq 0 ]; then
  echo "SELFTEST FAIL missing local dependency returned success" >&2
  exit 1
fi
assert_contains "$missing_dependency_output" "local vitest dependency not resolvable"
tests=$((tests + 1))

missing_python_output="$TMP_ROOT/missing-python.log"
set +e
AOS_CI_PYTHON="$TMP_ROOT/missing-python" \
  bash "$RUNNER_ROOT/scripts/ci/run-pytest.sh" >"$missing_python_output" 2>&1
missing_python_code=$?
set -e
if [ "$missing_python_code" -eq 0 ]; then
  echo "SELFTEST FAIL missing Python command returned success" >&2
  exit 1
fi
assert_contains "$missing_python_output" "AOS_CI_PYTHON is not executable"
tests=$((tests + 1))

echo "CI_SELFTESTS_PASSED: $tests"
