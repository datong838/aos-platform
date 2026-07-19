#!/usr/bin/env bash
# 152 · Linux desktop pack (check / optional tauri bundle). Parallel to pack-desktop-mac.sh — does not replace it or Windows *.ps1.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MODE="check"

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/pack-desktop-linux.sh [--check|--bundle|--help]

  --check   (default) toolchain + ontology-sdk/web/desktop tests + web npm run build + desktop vite build
  --bundle  also run tauri build (requires Rust + webkit2gtk/gtk)
  --help    this message

See scripts/pack/linux-desktop.md · scheme 152
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

# Soft PATH prepend for common user-local toolchains (no-op if absent)
export PATH="${HOME}/tools/bin:${HOME}/.local/bin:${PATH}"
for d in "${HOME}"/tools/node-*/bin; do
  if [[ -d "${d}" ]]; then
    export PATH="${d}:${PATH}"
    break
  fi
done

echo "=== pack-desktop-linux (${MODE}) ==="
echo "root=${ROOT} uname=$(uname -s)-$(uname -m)"

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
  if command -v pkg-config >/dev/null 2>&1; then
    if pkg-config --exists webkit2gtk-4.1 2>/dev/null || pkg-config --exists webkit2gtk-4.0 2>/dev/null; then
      echo "OK   webkit2gtk via pkg-config"
    else
      echo "WARN webkit2gtk pkg-config not found — tauri build may fail; see scripts/pack/linux-desktop.md"
    fi
  else
    echo "WARN pkg-config missing — cannot probe webkit2gtk"
  fi
  echo "--- tauri build ---"
  (cd "${ROOT}/apps/desktop" && npm run tauri -- build)
  echo "bundle artifacts under apps/desktop/src-tauri/target/release/bundle/ (if any)"
else
  echo "SKIP tauri bundle (pass --bundle when Rust + GTK/WebKit ready)"
fi

echo "=== pack-desktop-linux OK (${MODE}) ==="
echo "checklist: scripts/pack/linux-desktop.md"
echo "NOTE: do not ship MinIO / Dev Compose / Dev Keycloak in customer packages (24)"
