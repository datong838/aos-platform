#!/usr/bin/env bash
# Ferry skopeo archive drill — scheme 59 / 162
# Parallel to probe-ferry-skopeo.ps1 (does NOT rewrite the ps1).
# Skip when Docker/skopeo unavailable or image not local.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API_BASE="${AOS_API_BASE:-http://127.0.0.1:8080}"
SKOPEO_REF="${AOS_FERRY_SKOPEO_REFS:-alpine:latest}"
SKOPEO_REF="${SKOPEO_REF%%,*}"
SKOPEO_IMAGE="${AOS_FERRY_SKOPEO_IMAGE:-quay.io/skopeo/stable:v1.16.1}"
OUT_DIR="${ROOT}/deploy/dev/_skopeo_probe"

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/probe-ferry-skopeo.sh [--ref IMAGE] [--api-base URL]

  Prefer a local docker image (no registry pull in probe).
  See docs/palantier/20_tech/59 · scheme 162
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref) SKOPEO_REF="$2"; shift 2 ;;
    --api-base) API_BASE="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

echo "probe-ferry-skopeo.sh (scheme 59/162)"

HAS_DOCKER=0
HAS_SKOPEO=0
if command -v docker >/dev/null 2>&1 && docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
  HAS_DOCKER=1
fi
command -v skopeo >/dev/null 2>&1 && HAS_SKOPEO=1

if [[ "${HAS_DOCKER}" -eq 0 && "${HAS_SKOPEO}" -eq 0 ]]; then
  echo "SKIP: neither docker nor skopeo on PATH"
  exit 0
fi

if [[ "${HAS_DOCKER}" -eq 1 ]]; then
  img="$(docker images -q "${SKOPEO_REF}" 2>/dev/null || true)"
  if [[ -z "${img}" ]]; then
    echo "SKIP: image ${SKOPEO_REF} not local (avoid registry pull in probe)"
    echo "  docker pull ${SKOPEO_REF}   # then re-run"
    exit 0
  fi
fi

mkdir -p "${OUT_DIR}"
TAR="${OUT_DIR}/probe.tar"
rm -f "${TAR}"

ok=0
if [[ "${HAS_SKOPEO}" -eq 1 ]]; then
  if skopeo copy "docker-daemon:${SKOPEO_REF}" "docker-archive:${TAR}" >/dev/null 2>&1 \
    && [[ -f "${TAR}" ]]; then
    ok=1
  fi
fi

if [[ "${ok}" -eq 0 && "${HAS_DOCKER}" -eq 1 ]]; then
  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${OUT_DIR}:/out" \
    "${SKOPEO_IMAGE}" \
    copy "docker-daemon:${SKOPEO_REF}" "docker-archive:/out/probe.tar" \
    || true
  [[ -f "${TAR}" && -s "${TAR}" ]] && ok=1
fi

if [[ "${ok}" -eq 0 ]]; then
  echo "FAIL skopeo copy failed"
  exit 1
fi

len="$(wc -c < "${TAR}" | tr -d ' ')"
echo "OK archive bytes=${len}"

if command -v curl >/dev/null 2>&1; then
  if curl -fsS -H "Authorization: Bearer dev" -H "X-Org-Id: dev-org" -H "X-Project-Id: dev-project" \
    "${API_BASE}/v1/apollo/ferry/status" >/dev/null 2>&1; then
    echo "OK ferry status reachable"
  else
    echo "WARN aos-api status not reachable (optional). Sidecar skopeo copy OK."
  fi
fi

echo "HINT: set AOS_FERRY_SKOPEO=1 AOS_FERRY_SKOPEO_REFS=${SKOPEO_REF} then POST /v1/apollo/ferry/export"
echo "probe-ferry-skopeo OK"
exit 0
