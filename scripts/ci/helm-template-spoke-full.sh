#!/usr/bin/env bash
# Deterministic static verification for the Full Spoke Helm reference chart.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHART="${ROOT}/deploy/spoke-full/chart"
PRODUCTION_VALUES="${CHART}/ci/production-values.yaml"
REQUIRE=0

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/helm-template-spoke-full.sh [--require] [--help]

Runs Helm lint, renders default and production-like values twice, compares the
outputs, and checks the static security contract. No Kubernetes connection or
resource mutation is performed.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --require) REQUIRE=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if ! command -v helm >/dev/null 2>&1; then
  if [[ "${REQUIRE}" -eq 1 ]]; then
    echo "FAIL helm CLI not found" >&2
    exit 1
  fi
  echo "SKIP helm CLI not found; rerun with --require in CI"
  exit 0
fi

for required_file in "${CHART}/Chart.yaml" "${CHART}/values.yaml" "${CHART}/values.schema.json" "${PRODUCTION_VALUES}"; do
  if [[ ! -f "${required_file}" ]]; then
    echo "FAIL missing ${required_file}" >&2
    exit 1
  fi
done

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aos-helm-spoke.XXXXXX")"
trap 'rm -rf "${TMP_DIR}"' EXIT

helm lint "${CHART}" --strict

render_twice() {
  local profile="$1"
  shift
  helm template aos-spoke-full "${CHART}" "$@" >"${TMP_DIR}/${profile}-1.yaml"
  helm template aos-spoke-full "${CHART}" "$@" >"${TMP_DIR}/${profile}-2.yaml"
  diff -u "${TMP_DIR}/${profile}-1.yaml" "${TMP_DIR}/${profile}-2.yaml"
}

render_twice default
render_twice production -f "${PRODUCTION_VALUES}"

DEFAULT_RENDER="${TMP_DIR}/default-1.yaml"
PRODUCTION_RENDER="${TMP_DIR}/production-1.yaml"

assert_contains() {
  local file="$1"
  local pattern="$2"
  local message="$3"
  if ! grep -Eq -- "${pattern}" "${file}"; then
    echo "FAIL ${message}" >&2
    exit 1
  fi
}

for pattern in 'kind: Deployment' 'kind: Service' 'kind: ServiceAccount' 'livenessProbe:' 'readinessProbe:' 'allowPrivilegeEscalation: false' 'readOnlyRootFilesystem: true' 'runAsNonRoot: true' 'resources:' 'aos.platform/mode: full'; do
  assert_contains "${DEFAULT_RENDER}" "${pattern}" "default render missing ${pattern}"
done

for pattern in 'kind: Ingress' 'kind: PersistentVolumeClaim' 'secretKeyRef:' 'name: "aos-spoke-runtime"'; do
  assert_contains "${PRODUCTION_RENDER}" "${pattern}" "production render missing ${pattern}"
done

if grep -Eq '^[[:space:]]*image:[[:space:]].*:latest([[:space:]]|$)' "${DEFAULT_RENDER}" "${PRODUCTION_RENDER}"; then
  echo "FAIL mutable latest image tag rendered" >&2
  exit 1
fi
if grep -A2 -E 'name: AOS_HUB_TOKEN' "${PRODUCTION_RENDER}" | grep -Eq '^[[:space:]]*value:'; then
  echo "FAIL hub token rendered as plaintext value" >&2
  exit 1
fi
if grep -Eiq '(password|private[_-]?key|client[_-]?secret):[[:space:]]+[^[:space:]{}]' "${CHART}/values.yaml" "${PRODUCTION_VALUES}"; then
  echo "FAIL possible plaintext credential in chart values" >&2
  exit 1
fi

echo "PASS helm lint and deterministic render profiles"
echo "  helm=$(helm version --short)"
echo "  default_sha256=$(shasum -a 256 "${DEFAULT_RENDER}" | awk '{print $1}')"
echo "  production_sha256=$(shasum -a 256 "${PRODUCTION_RENDER}" | awk '{print $1}')"
