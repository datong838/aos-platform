#!/usr/bin/env bash
# 204m · Install package dry-run drill. ≠ formal installer / customer ship.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REPORT_DIR="${ROOT}/deploy/dev/_install_drill"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
REQUIRE_REPORT=0

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/drill-install-package.sh [--require-report] [--help]

  Dry-run checklist for desktop pack scripts (151/152). Does NOT run full
  tauri bundle. Scheme 204m · T5.1 drill only.

  Boundary: 演练 ≠ 正式安装包全集 / 客户交付签收
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --require-report) REQUIRE_REPORT=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

mkdir -p "${REPORT_DIR}"
REPORT="${REPORT_DIR}/drill-${TS}.md"

echo "drill-install-package (scheme 204m) · NOT formal installer"

record_row() {
  echo "| $1 | $2 |" >>"${REPORT}"
  echo "  $1: $2"
}

{
  echo "# Install package dry-run drill report"
  echo
  echo "- scheme: **204m** (align T5.1 / 151)"
  echo "- utc: ${TS}"
  echo "- boundary: **演练 ≠ 正式安装包全集**"
  echo
  echo "## Checklist"
  echo
  echo "| 步骤 | 结果 |"
  echo "| --- | --- |"
} >"${REPORT}"

if command -v node >/dev/null 2>&1; then
  record_row "node" "OK $($(command -v node) --version 2>/dev/null | head -1)"
else
  record_row "node" "SKIP (missing)"
fi

if command -v rustc >/dev/null 2>&1; then
  record_row "rustc" "OK $(rustc --version 2>/dev/null | head -1)"
else
  record_row "rustc" "SKIP (missing · bundle needs it)"
fi

MAC="${ROOT}/scripts/ci/pack-desktop-mac.sh"
LIN="${ROOT}/scripts/ci/pack-desktop-linux.sh"
if [[ -f "${MAC}" ]]; then
  if bash "${MAC}" --help >/dev/null 2>&1; then
    record_row "pack_desktop_mac_help" "OK"
  else
    record_row "pack_desktop_mac_help" "FAIL"
  fi
else
  record_row "pack_desktop_mac_help" "SKIP (missing)"
fi
if [[ -f "${LIN}" ]]; then
  if bash "${LIN}" --help >/dev/null 2>&1; then
    record_row "pack_desktop_linux_help" "OK"
  else
    record_row "pack_desktop_linux_help" "FAIL"
  fi
else
  record_row "pack_desktop_linux_help" "SKIP (missing)"
fi

{
  echo
  echo "## Notes"
  echo
  echo "- Full \`--check\` / \`--bundle\` 留给发布流水线；本刀只证明脚本与工具链可见。"
  echo "- 客户正式安装包签收不在本刀。"
} >>"${REPORT}"

echo "report: ${REPORT}"
if [[ "${REQUIRE_REPORT}" -eq 1 && ! -f "${REPORT}" ]]; then
  echo "FAIL: report missing"
  exit 1
fi
echo "drill-install-package done (drill only)"
exit 0
