#!/usr/bin/env bash
# Generate Dev cosign keypair for Ferry images layer — scheme 64 / 162
# Parallel to gen-ferry-cosign-keys.ps1 (does NOT rewrite the ps1).
# Writes deploy/dev/cosign/cosign.key + cosign.pub (gitignored).
# Empty password for local Dev only — never commit keys.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="${AOS_FERRY_COSIGN_OUT:-${ROOT}/deploy/dev/cosign}"
COSIGN_IMAGE="${AOS_FERRY_COSIGN_IMAGE:-ghcr.io/sigstore/cosign/cosign:v2.4.1}"

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/gen-ferry-cosign-keys.sh [--out-dir PATH]

  Env: AOS_FERRY_COSIGN_OUT, AOS_FERRY_COSIGN_IMAGE
  See docs/palantier/20_tech/64 · scheme 162
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

mkdir -p "${OUT_DIR}"
export COSIGN_PASSWORD=""

echo "gen-ferry-cosign-keys.sh -> ${OUT_DIR}"

if command -v cosign >/dev/null 2>&1; then
  (cd "${OUT_DIR}" && cosign generate-key-pair)
elif command -v docker >/dev/null 2>&1 && docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
  echo "Pulling ${COSIGN_IMAGE} (may be slow)..."
  if ! docker pull "${COSIGN_IMAGE}" >/dev/null 2>&1; then
    echo "SKIP: docker pull failed — install PATH cosign or retry later"
    exit 0
  fi
  docker run --rm -e COSIGN_PASSWORD= -v "${OUT_DIR}:/work" -w /work "${COSIGN_IMAGE}" generate-key-pair \
    || { echo "SKIP: docker cosign generate-key-pair failed"; exit 0; }
else
  echo "SKIP: neither cosign nor docker available"
  exit 0
fi

KEY="${OUT_DIR}/cosign.key"
PUB="${OUT_DIR}/cosign.pub"
if [[ ! -f "${KEY}" || ! -f "${PUB}" ]]; then
  echo "FAIL expected cosign.key and cosign.pub under ${OUT_DIR}"
  exit 1
fi

echo "OK key=${KEY}"
echo "OK pub=${PUB}"
echo "HINT: export AOS_FERRY_COSIGN_KEY=${KEY} AOS_FERRY_COSIGN_PUB=${PUB}"
exit 0
