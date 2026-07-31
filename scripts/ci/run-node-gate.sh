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

if [ ! -d "$package_dir/node_modules" ] && [ ! -d "$ROOT/node_modules" ]; then
  echo "FAIL local Node dependencies not found for $component; CI does not install dependencies" >&2
  exit 1
fi

echo "NODE: $("$NODE_BIN" --version 2>&1)"

package_manager="${AOS_CI_PACKAGE_MANAGER:-auto}"
NPM_BIN="${AOS_CI_NPM:-$(command -v npm || true)}"
PNPM_BIN="${AOS_CI_PNPM:-$(command -v pnpm || true)}"
needs_package_manager=true
if [ "$component:$action" = "web:typecheck" ]; then
  needs_package_manager=false
fi

if [ "$needs_package_manager" = true ]; then
  case "$package_manager" in
    auto)
      if [ -n "$NPM_BIN" ] && [ -x "$NPM_BIN" ]; then
        package_manager="npm"
        package_manager_bin="$NPM_BIN"
      elif [ -n "$PNPM_BIN" ] && [ -x "$PNPM_BIN" ]; then
        package_manager="pnpm"
        package_manager_bin="$PNPM_BIN"
      else
        echo "FAIL required npm or pnpm executable not found" >&2
        exit 1
      fi
      ;;
    npm)
      if [ -z "$NPM_BIN" ] || [ ! -x "$NPM_BIN" ]; then
        echo "FAIL requested npm executable not found" >&2
        exit 1
      fi
      package_manager_bin="$NPM_BIN"
      ;;
    pnpm)
      if [ -z "$PNPM_BIN" ] || [ ! -x "$PNPM_BIN" ]; then
        echo "FAIL requested pnpm executable not found" >&2
        exit 1
      fi
      package_manager_bin="$PNPM_BIN"
      ;;
    *)
      echo "FAIL AOS_CI_PACKAGE_MANAGER must be auto, npm, or pnpm" >&2
      exit 2
      ;;
  esac
  echo "PACKAGE_MANAGER: $package_manager $("$package_manager_bin" --version 2>&1)"
fi

run_package_script() {
  script_name="$1"
  case "$package_manager" in
    npm) "$package_manager_bin" --prefix "$package_dir" run "$script_name" ;;
    pnpm) "$package_manager_bin" --dir "$package_dir" run "$script_name" ;;
  esac
}

case "$component:$action" in
  web:test)
    run_package_script test
    ;;
  web:typecheck)
    if [ -x "$package_dir/node_modules/.bin/tsc" ]; then
      "$package_dir/node_modules/.bin/tsc" --noEmit -p "$package_dir/tsconfig.json"
    elif [ -x "$ROOT/node_modules/.bin/tsc" ]; then
      "$ROOT/node_modules/.bin/tsc" --noEmit -p "$package_dir/tsconfig.json"
    else
      echo "FAIL local TypeScript compiler not found for web" >&2
      exit 1
    fi
    ;;
  web:build)
    run_package_script build
    ;;
  desktop:test)
    run_package_script test
    ;;
  desktop:typecheck)
    run_package_script typecheck
    ;;
  desktop:build)
    run_package_script build
    ;;
  sdk:test)
    run_package_script test
    ;;
esac
