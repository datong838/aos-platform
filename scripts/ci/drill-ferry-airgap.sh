#!/usr/bin/env bash
# 191m · Airgap Ferry drill checklist (aggregate probes). ≠ customer airgap sign-off.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API_BASE="${AOS_API_BASE:-http://127.0.0.1:8080}"
REPORT_DIR="${ROOT}/deploy/dev/_ferry_drill"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
REQUIRE_REPORT=0
SKIP_CURL=0

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/drill-ferry-airgap.sh [--api-base URL] [--require-report] [--skip-curl] [--help]

  Runs Ferry onsite drill probes (162 MVP chain). Missing tools → SKIP step.
  Writes markdown report under deploy/dev/_ferry_drill/.

  This is a DRILL checklist — NOT customer airgap Full Channel sign-off.

  Scheme: docs/palantier/20_tech/191m-气隙Ferry演练清单方案.md
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base) API_BASE="$2"; shift 2 ;;
    --require-report) REQUIRE_REPORT=1; shift ;;
    --skip-curl) SKIP_CURL=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

mkdir -p "${REPORT_DIR}"
REPORT="${REPORT_DIR}/drill-${TS}.md"

echo "drill-ferry-airgap (scheme 191m) · NOT customer sign-off"
echo "  api=${API_BASE}"

{
  echo "# Ferry airgap drill report"
  echo
  echo "- scheme: **191m** (align 162)"
  echo "- utc: ${TS}"
  echo "- api: \`${API_BASE}\`"
  echo "- boundary: **演练 ≠ 客户气隙签收**"
  echo
  echo "## Checklist"
  echo
  echo "| 步骤 | 结果 |"
  echo "| --- | --- |"
} >"${REPORT}"

record() {
  local step="$1"
  local result="$2"
  echo "| ${step} | ${result} |" >>"${REPORT}"
  echo "  ${step}: ${result}"
}

# 1) Ferry status (optional)
if [[ "${SKIP_CURL}" -eq 1 ]]; then
  record "ferry_status_curl" "SKIP (--skip-curl)"
else
  if command -v curl >/dev/null 2>&1; then
    set +e
    CODE="$(curl -sS -o /tmp/aos-ferry-status.json -w '%{http_code}' \
      -H 'Authorization: Bearer dev' \
      -H 'X-Org-Id: dev-org' \
      -H 'X-Project-Id: dev-project' \
      "${API_BASE}/v1/apollo/ferry/status" 2>/dev/null || echo "000")"
    set -e
    if [[ "${CODE}" == "200" ]]; then
      record "ferry_status_curl" "OK HTTP ${CODE}"
    else
      record "ferry_status_curl" "SKIP/FAIL HTTP ${CODE} (API may be down)"
    fi
  else
    record "ferry_status_curl" "SKIP (no curl)"
  fi
fi

run_probe() {
  local name="$1"
  local script="$2"
  if [[ ! -f "${script}" ]]; then
    record "${name}" "SKIP (script missing)"
    return 0
  fi
  set +e
  OUT="$(bash "${script}" --api-base "${API_BASE}" 2>&1)"
  RC=$?
  set -e
  if [[ "${RC}" -eq 0 ]]; then
    if echo "${OUT}" | grep -qi 'SKIP'; then
      record "${name}" "SKIP (tooling)"
    else
      record "${name}" "OK"
    fi
  else
    record "${name}" "FAIL exit ${RC}"
  fi
}

run_probe "probe_large_images" "${ROOT}/scripts/ci/probe-ferry-large-images.sh"
run_probe "probe_skopeo" "${ROOT}/scripts/ci/probe-ferry-skopeo.sh"
run_probe "probe_cosign" "${ROOT}/scripts/ci/probe-ferry-cosign.sh"

{
  echo
  echo "## Notes"
  echo
  echo "- Full Channel / 客户气隙书面签收不在本刀。"
  echo "- 现场以 162 + 本报告为演练证据；签收另走交付包。"
} >>"${REPORT}"

echo "report: ${REPORT}"
if [[ "${REQUIRE_REPORT}" -eq 1 && ! -f "${REPORT}" ]]; then
  echo "FAIL: report not written"
  exit 1
fi
echo "drill-ferry-airgap done (drill only)"
exit 0
