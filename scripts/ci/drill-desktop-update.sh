#!/usr/bin/env bash
# 199m · Desktop update CDN/Ferry drill (fixture verify). ≠ customer CDN sign-off.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REPORT_DIR="${ROOT}/deploy/dev/_desktop_update_drill"
FIXTURE_DIR="${REPORT_DIR}/fixture"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
REQUIRE_REPORT=0

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/drill-desktop-update.sh [--require-report] [--help]

  Writes a signed-shaped fixture + markdown drill report.
  Does NOT hit customer CDN. Scheme 199m · align 138.

  Boundary: 演练 ≠ 客户更新全链路签收
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --require-report) REQUIRE_REPORT=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

mkdir -p "${FIXTURE_DIR}"
REPORT="${REPORT_DIR}/drill-${TS}.md"
FIXTURE="${FIXTURE_DIR}/manifest-${TS}.json"

echo "drill-desktop-update (scheme 199m) · NOT customer CDN sign-off"

# Minimal fixture (signature placeholder; vitest covers real aos-v1)
cat >"${FIXTURE}" <<EOF
{
  "version": "9.9.9-drill",
  "url": "https://cdn.example.invalid/aos-desktop-${TS}.dmg",
  "sha256": "deadbeef",
  "notes": "199m drill fixture · not for install",
  "signature": "aos-v1:drill-placeholder"
}
EOF

{
  echo "# Desktop update CDN drill report"
  echo
  echo "- scheme: **199m** (align 138)"
  echo "- utc: ${TS}"
  echo "- boundary: **演练 ≠ 客户 CDN / Ferry 更新全链路签收**"
  echo
  echo "## Checklist"
  echo
  echo "| 步骤 | 结果 |"
  echo "| --- | --- |"
  echo "| fixture_written | OK \`${FIXTURE}\` |"
  echo "| inject_or_source_url | 客户端可用 localStorage / VITE_AOS_UPDATE_MANIFEST_URL |"
  echo "| signature_gate | 生产须真 aos-v1/cosign（本 fixture 占位） |"
  echo "| customer_signoff | SKIP（不在本刀） |"
  echo
  echo "## Notes"
  echo
  echo "- 正式清单由发布流水线签名；本报告仅演练证据。"
} >"${REPORT}"

echo "  fixture: ${FIXTURE}"
echo "  report: ${REPORT}"
if [[ "${REQUIRE_REPORT}" -eq 1 && ! -f "${REPORT}" ]]; then
  echo "FAIL: report missing"
  exit 1
fi
echo "drill-desktop-update done (drill only)"
exit 0
