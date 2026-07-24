#!/usr/bin/env bash
# 151 · macOS desktop pack (check / optional tauri bundle). Does not touch Windows *.ps1.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MODE="check"

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/pack-desktop-mac.sh [--check|--bundle|--help]

  --check   (default) toolchain + ontology-sdk/web/desktop tests + web npm run build + desktop vite build
  --bundle  also run tauri build (requires Rust / Xcode CLT)
  --help    this message

See scripts/pack/macos-desktop.md · scheme 151
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) MODE="check"; shift ;;
    --bundle) MODE="bundle"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown arg: $1"; usage; exit 2 ;;
  esac
done

export PATH="${HOME}/tools/node-v22.17.0-darwin-arm64/bin:${HOME}/tools/bin:${PATH}"

echo "=== pack-desktop-mac (${MODE}) ==="
echo "root=${ROOT}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "FAIL missing: $1"
    exit 1
  fi
  echo "OK   $1=$($1 --version 2>/dev/null | head -1 || echo present)"
}

need node
need npm

node_major="$(node -p "process.versions.node.split('.')[0]")"
if [[ "${node_major}" -lt 18 ]]; then
  echo "FAIL Node >= 18 required (got $(node -v))"
  exit 1
fi

echo "--- ontology-sdk test ---"
(cd "${ROOT}/packages/ontology-sdk" && npm test)

echo "--- web test + npm run build ---"
# Full gate: tsc + vite (see 155 · Web tsc 门禁清零)
(cd "${ROOT}/apps/web" && npm test && npm run build)

echo "--- desktop test + vite build ---"
(cd "${ROOT}/apps/desktop" && npm test && npm run build)

if [[ "${MODE}" == "bundle" ]]; then
  need cargo
  need rustc
  if ! xcode-select -p >/dev/null 2>&1; then
    echo "FAIL xcode-select CLT not found"
    exit 1
  fi
  echo "OK   xcode-select=$(xcode-select -p)"
  echo "--- tauri build ---"
  (cd "${ROOT}/apps/desktop" && npm run tauri -- build)
  echo "bundle artifacts under apps/desktop/src-tauri/target/release/bundle/ (if any)"
else
  echo "SKIP tauri bundle (pass --bundle when Rust/CLT ready)"
fi

echo "=== pack-desktop-mac OK (${MODE}) ==="
echo "checklist: scripts/pack/macos-desktop.md"
echo "NOTE: do not ship MinIO / Dev Compose / Dev Keycloak in customer packages (24)"
