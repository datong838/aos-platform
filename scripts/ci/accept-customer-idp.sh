#!/usr/bin/env bash
# 161 · Customer production IdP acceptance (e.g. 微商城 online case).
# Wraps probe-prod-idp.sh with --reject-dev; writes local report under deploy/dev/_idp_accept/.
# ≠ auto sign-off. No token → SKIP or partial (JWKS only).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CASE_NAME="${AOS_IDP_CASE_NAME:-customer}"
API_BASE="${AOS_API_BASE:-http://127.0.0.1:8080}"
ISSUER="${AOS_OIDC_ISSUER:-}"
JWKS_URL="${AOS_OIDC_JWKS_URL:-}"
AUDIENCE="${AOS_OIDC_AUDIENCE:-aos-api}"
TOKEN="${AOS_PROBE_TOKEN:-}"
TOKEN_FILE="${AOS_PROBE_TOKEN_FILE:-}"
REQUIRE=0
REPORT_DIR="${ROOT}/deploy/dev/_idp_accept"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/accept-customer-idp.sh [--require] [--env FILE] [--help]

  Loads optional --env (e.g. deploy/dev/customer-idp.mall.env).
  Runs probe-prod-idp.sh with --reject-dev.
  With token: also --require-me.
  Without issuer/jwks: SKIP exit 0 (unless --require).

Scheme: docs/palantier/20_tech/161-客户生产IdP验收规程-微商城案例.md
Handbook: docs/palantier/20_tech/60-生产IdP联调手册.md §6.3
EOF
}

ENV_FILE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --require) REQUIRE=1; shift ;;
    --env) ENV_FILE="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

if [[ -n "${ENV_FILE}" ]]; then
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "FAIL env file missing: ${ENV_FILE}"
    exit 1
  fi
  # shellcheck disable=SC1090
  set -a
  # shellcheck disable=SC1091
  source "${ENV_FILE}"
  set +a
  CASE_NAME="${AOS_IDP_CASE_NAME:-$CASE_NAME}"
  API_BASE="${AOS_API_BASE:-$API_BASE}"
  ISSUER="${AOS_OIDC_ISSUER:-$ISSUER}"
  JWKS_URL="${AOS_OIDC_JWKS_URL:-$JWKS_URL}"
  AUDIENCE="${AOS_OIDC_AUDIENCE:-$AUDIENCE}"
  TOKEN="${AOS_PROBE_TOKEN:-$TOKEN}"
  TOKEN_FILE="${AOS_PROBE_TOKEN_FILE:-$TOKEN_FILE}"
fi

if [[ -z "${TOKEN}" && -n "${TOKEN_FILE}" && -f "${TOKEN_FILE}" ]]; then
  TOKEN="$(tr -d '\r\n' <"${TOKEN_FILE}")"
fi

echo "accept-customer-idp (scheme 161) case=${CASE_NAME}"
echo "  api=${API_BASE}"
echo "  issuer=${ISSUER:-<unset>}"

if [[ -z "${ISSUER}" || -z "${JWKS_URL}" ]]; then
  if [[ "${REQUIRE}" -eq 1 ]]; then
    echo "FAIL: set AOS_OIDC_ISSUER + AOS_OIDC_JWKS_URL (see customer-idp.mall.example.env)"
    exit 1
  fi
  echo "SKIP: no customer issuer/jwks yet"
  echo "  cp deploy/dev/customer-idp.mall.example.env deploy/dev/customer-idp.mall.env"
  echo "  fill values + optional token, then:"
  echo "  bash scripts/ci/accept-customer-idp.sh --env deploy/dev/customer-idp.mall.env"
  exit 0
fi

mkdir -p "${REPORT_DIR}"
REPORT="${REPORT_DIR}/${CASE_NAME}-${TS}.md"
ARGS=(
  --issuer "${ISSUER}"
  --jwks "${JWKS_URL}"
  --audience "${AUDIENCE}"
  --api-base "${API_BASE}"
  --reject-dev
)
if [[ -n "${TOKEN}" ]]; then
  ARGS+=(--token "${TOKEN}" --require-me)
  echo "  token=present (not logged)"
else
  echo "  token=absent → JWKS/discovery only (B 联调未完整)"
fi

set +e
OUT="$(bash "${ROOT}/scripts/ci/probe-prod-idp.sh" "${ARGS[@]}" 2>&1)"
RC=$?
set -e
echo "${OUT}"

{
  echo "# IdP acceptance report · ${CASE_NAME}"
  echo
  echo "- scheme: 161"
  echo "- utc: ${TS}"
  echo "- issuer: \`${ISSUER}\`"
  echo "- jwks: \`${JWKS_URL}\`"
  echo "- audience: \`${AUDIENCE}\`"
  echo "- api: \`${API_BASE}\`"
  echo "- tokenProvided: $([[ -n "${TOKEN}" ]] && echo yes || echo no)"
  echo "- probeExit: ${RC}"
  echo
  echo "## Probe output"
  echo
  echo '```'
  echo "${OUT}"
  echo '```'
  echo
  echo "## Sign-off (human)"
  echo
  echo "| 项 | 结果 |"
  echo "| --- | --- |"
  echo "| discovery/JWKS | |"
  echo "| /v1/me OIDC | |"
  echo "| claim org/project/roles | |"
  echo "| AOS_AUTH_ALLOW_DEV=0 | |"
  echo "| 客户确认人/日期 | |"
  echo
  echo "口径：本报告 ≠ 自动签收；客户书面确认后记入交付包。"
} >"${REPORT}"

echo "report: ${REPORT}"
if [[ "${RC}" -ne 0 ]]; then
  echo "FAIL probe exit ${RC}"
  exit "${RC}"
fi
echo "accept-customer-idp OK (layer A/B probe · sign-off still human)"
