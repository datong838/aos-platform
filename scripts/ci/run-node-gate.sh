#!/usr/bin/env bash
# Run one required Node package gate without installing dependencies.
# Usage: bash scripts/ci/run-node-gate.sh web|desktop|sdk test|typecheck|build
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if [ "$#" -ne 2 ]; then
  echo "Usage: bash scripts/ci/run-node-gate.sh web|desktop|sdk test|typecheck|build" >&2
  exit 2
fi

component="$1"
action="$2"

case "$component" in
  web) package_dir="$ROOT/apps/web" ;;
  desktop) package_dir="$ROOT/apps/desktop" ;;
  sdk) package_dir="$ROOT/packages/ontology-sdk" ;;
  *)
    echo "FAIL unknown Node component: $component" >&2
    exit 2
    ;;
esac

case "$component:$action" in
  web:test|web:typecheck|web:build|desktop:test|desktop:typecheck|desktop:build|sdk:test) ;;
  *)
    echo "FAIL unsupported Node gate: $component:$action" >&2
    exit 2
    ;;
esac

if [ ! -d "$package_dir" ]; then
  echo "FAIL required package directory not found: $package_dir" >&2
  exit 1
fi
if [ ! -f "$package_dir/package.json" ]; then
  echo "FAIL package manifest not found: $package_dir/package.json" >&2
  exit 1
fi

NODE_BIN="${AOS_CI_NODE:-$(command -v node || true)}"
if [ -z "$NODE_BIN" ] || [ ! -x "$NODE_BIN" ]; then
  echo "FAIL required Node executable not found" >&2
  exit 1
fi

echo "NODE: $("$NODE_BIN" --version 2>&1)"
export PATH="$(dirname "$NODE_BIN"):$PATH"

PNPM_BIN="${AOS_CI_PNPM:-$(command -v pnpm || true)}"
if [ "${AOS_CI_PACKAGE_MANAGER:-pnpm}" != "pnpm" ]; then
  echo "FAIL AOS_CI_PACKAGE_MANAGER only supports pnpm" >&2
  exit 2
fi
if [ -z "$PNPM_BIN" ] || [ ! -x "$PNPM_BIN" ]; then
  echo "FAIL required pnpm executable not found" >&2
  exit 1
fi
if [ ! -f "$ROOT/pnpm-lock.yaml" ] || [ ! -f "$ROOT/pnpm-workspace.yaml" ]; then
  echo "FAIL pnpm workspace metadata not found" >&2
  exit 1
fi

package_manager_spec="$(sed -n 's/^[[:space:]]*"packageManager"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$ROOT/package.json")"
expected_pnpm_version="${package_manager_spec#pnpm@}"
actual_pnpm_version="$("$PNPM_BIN" --version 2>&1)"
if [ "$package_manager_spec" = "$expected_pnpm_version" ] || [ -z "$expected_pnpm_version" ]; then
  echo "FAIL root packageManager must pin pnpm" >&2
  exit 1
fi
if [ "$actual_pnpm_version" != "$expected_pnpm_version" ]; then
  echo "FAIL pnpm version mismatch: expected=$expected_pnpm_version actual=$actual_pnpm_version" >&2
  exit 1
fi
echo "PACKAGE_MANAGER: pnpm $actual_pnpm_version"

case "$action" in
  test) required_bin="vitest" ;;
  typecheck) required_bin="tsc" ;;
  build) required_bin="vite" ;;
esac
required_bin_path="$package_dir/node_modules/.bin/$required_bin"
if [ ! -x "$required_bin_path" ]; then
  echo "FAIL local $required_bin dependency not resolvable for $component; run pnpm install --frozen-lockfile at repository root" >&2
  exit 1
fi
if [ "$component:$action" = "web:build" ] && [ ! -x "$package_dir/node_modules/.bin/tsc" ]; then
  echo "FAIL local tsc dependency not resolvable for web; run pnpm install --frozen-lockfile at repository root" >&2
  exit 1
fi

case "$component:$action" in
  web:test)
    (cd "$package_dir" && "$required_bin_path" run)
    ;;
  web:typecheck)
    "$required_bin_path" --noEmit -p "$package_dir/tsconfig.json"
    ;;
  web:build)
    "$package_dir/node_modules/.bin/tsc" -p "$package_dir/tsconfig.json"
    (cd "$package_dir" && "$required_bin_path" build)
    ;;
  desktop:test)
    (cd "$package_dir" && "$required_bin_path" run)
    ;;
  desktop:typecheck)
    "$required_bin_path" --noEmit -p "$package_dir/tsconfig.json"
    ;;
  desktop:build)
    (cd "$package_dir" && "$required_bin_path" build)
    ;;
  sdk:test)
    (cd "$package_dir" && "$required_bin_path" run)
    ;;
esac
