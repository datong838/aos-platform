#!/usr/bin/env bash
# Probe Ferry cosign keychain — scheme 64 / 162
# Parallel to probe-ferry-cosign.ps1 (does NOT rewrite the ps1).
# Skip when no cosign/docker or no keys.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API_BASE="${AOS_API_BASE:-http://127.0.0.1:8080}"
KEY="${AOS_FERRY_COSIGN_KEY:-${ROOT}/deploy/dev/cosign/cosign.key}"
PUB="${AOS_FERRY_COSIGN_PUB:-${ROOT}/deploy/dev/cosign/cosign.pub}"
COSIGN_IMAGE="${AOS_FERRY_COSIGN_IMAGE:-ghcr.io/sigstore/cosign/cosign:v2.4.1}"

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/probe-ferry-cosign.sh [--api-base URL] [--key PATH] [--pub PATH]

  See docs/palantier/20_tech/64 · scheme 162
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base) API_BASE="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    --pub) PUB="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

echo "probe-ferry-cosign.sh (scheme 64/162)"

HAS_PATH=0
HAS_DOCKER=0
command -v cosign >/dev/null 2>&1 && HAS_PATH=1
if command -v docker >/dev/null 2>&1 && docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
  HAS_DOCKER=1
fi

if [[ "${HAS_PATH}" -eq 0 && "${HAS_DOCKER}" -eq 0 ]]; then
  echo "SKIP: no cosign CLI and no docker"
  exit 0
fi
if [[ ! -f "${KEY}" || ! -f "${PUB}" ]]; then
  echo "SKIP: keys missing — run bash scripts/ci/gen-ferry-cosign-keys.sh"
  exit 0
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/aos-ferry-cosign.XXXXXX")"
cleanup() { rm -rf "${TMP}"; }
trap cleanup EXIT

BLOB="${TMP}/blob.txt"
SIG="${TMP}/blob.sig"
printf 'aos-ferry-cosign-probe' > "${BLOB}"
export COSIGN_PASSWORD=""

KEY_DIR="$(cd "$(dirname "${KEY}")" && pwd)"
KEY_NAME="$(basename "${KEY}")"
PUB_NAME="$(basename "${PUB}")"

if [[ "${HAS_PATH}" -eq 1 ]]; then
  cosign sign-blob --yes --key "${KEY}" --output-signature "${SIG}" "${BLOB}"
  cosign verify-blob --key "${PUB}" --signature "${SIG}" "${BLOB}"
else
  docker run --rm -e COSIGN_PASSWORD= \
    -v "${TMP}:/work" -v "${KEY_DIR}:/keys:ro" \
    "${COSIGN_IMAGE}" \
    sign-blob --yes --key "/keys/${KEY_NAME}" --output-signature /work/blob.sig /work/blob.txt
  docker run --rm \
    -v "${TMP}:/work" -v "${KEY_DIR}:/keys:ro" \
    "${COSIGN_IMAGE}" \
    verify-blob --key "/keys/${PUB_NAME}" --signature /work/blob.sig /work/blob.txt
fi

echo "OK cosign sign+verify blob"

if command -v curl >/dev/null 2>&1; then
  if curl -fsS -H "Authorization: Bearer dev" -H "X-Org-Id: dev-org" -H "X-Project-Id: dev-project" \
    "${API_BASE}/v1/apollo/ferry/status" >/tmp/aos-ferry-cosign-status.json 2>/dev/null; then
    echo "OK status (see /tmp/aos-ferry-cosign-status.json)"
  else
    echo "WARN aos-api status optional (unreachable)"
  fi
fi

echo "probe-ferry-cosign OK"
exit 0
