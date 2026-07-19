#!/usr/bin/env bash
# 158 · helm template for Full Spoke chart stub. SKIP when helm absent.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHART="${ROOT}/deploy/spoke-full/chart"
OUT_DIR="${ROOT}/deploy/dev/_helm_spoke_full"
REQUIRE=0

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/helm-template-spoke-full.sh [--require] [--help]

Renders deploy/spoke-full/chart via `helm template` (no cluster needed).
Skip exit 0 when helm CLI missing unless --require.
Scheme: docs/palantier/20_tech/158-Full-Spoke运行时MVP方案.md
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --require) REQUIRE=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

echo "helm-template-spoke-full (scheme 158)"
if ! command -v helm >/dev/null 2>&1; then
  if [[ "${REQUIRE}" -eq 1 ]]; then
    echo "FAIL helm CLI not found"
    exit 1
  fi
  echo "SKIP: helm not installed (brew install helm / https://helm.sh)"
  exit 0
fi

if [[ ! -f "${CHART}/Chart.yaml" ]]; then
  echo "FAIL missing ${CHART}/Chart.yaml"
  exit 1
fi

mkdir -p "${OUT_DIR}"
helm template aos-spoke-full "${CHART}" >"${OUT_DIR}/rendered.yaml"
if ! grep -q 'kind: Deployment' "${OUT_DIR}/rendered.yaml"; then
  echo "FAIL rendered manifest missing Deployment"
  exit 1
fi
if ! grep -q 'aos.platform/mode: full' "${OUT_DIR}/rendered.yaml"; then
  echo "FAIL missing full mode label"
  exit 1
fi
echo "OK wrote ${OUT_DIR}/rendered.yaml"
wc -l "${OUT_DIR}/rendered.yaml" | awk '{print "  lines="$1}'
echo "helm-template-spoke-full OK"
