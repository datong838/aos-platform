#!/usr/bin/env bash
# 190m · IdP B-layer acceptance pack (sample token → probe green).
# Wraps accept-customer-idp.sh but REQUIRES a token (no silent JWKS-only pass).
# ≠ customer written sign-off (layer C).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE=""
REQUIRE_REPORT=0

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/accept-idp-b-layer.sh [--env FILE] [--require-report] [--help]

  B-layer (190m): must provide AOS_PROBE_TOKEN or AOS_PROBE_TOKEN_FILE
  (via --env or environment). Without token → FAIL (not SKIP).

  Does NOT auto-complete customer written sign-off (layer C).

  Scheme: docs/palantier/20_tech/190m-IdP验收B层联调包方案.md
  Upstream: 161 · scripts/ci/accept-customer-idp.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV_FILE="$2"; shift 2 ;;
    --require-report) REQUIRE_REPORT=1; shift ;;
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
fi

TOKEN="${AOS_PROBE_TOKEN:-}"
TOKEN_FILE="${AOS_PROBE_TOKEN_FILE:-}"
if [[ -z "${TOKEN}" && -n "${TOKEN_FILE}" && -f "${TOKEN_FILE}" ]]; then
  TOKEN="$(tr -d '\r\n' <"${TOKEN_FILE}")"
fi

echo "accept-idp-b-layer (scheme 190m) · NOT customer sign-off"
echo "  checklist:"
echo "    [ ] AOS_OIDC_ISSUER + AOS_OIDC_JWKS_URL"
echo "    [ ] sample token present"
echo "    [ ] probe --reject-dev --require-me"
echo "    [ ] /v1/me 200"
echo "    [ ] layer C written sign-off = human only"

if [[ -z "${TOKEN}" ]]; then
  echo "FAIL B-layer: missing sample token (AOS_PROBE_TOKEN or AOS_PROBE_TOKEN_FILE)"
  echo "  cp deploy/dev/customer-idp.mall.example.env … and fill token"
  exit 1
fi

if [[ -z "${AOS_OIDC_ISSUER:-}" || -z "${AOS_OIDC_JWKS_URL:-}" ]]; then
  echo "FAIL B-layer: set AOS_OIDC_ISSUER + AOS_OIDC_JWKS_URL"
  exit 1
fi

ARGS=(--require)
if [[ -n "${ENV_FILE}" ]]; then
  ARGS+=(--env "${ENV_FILE}")
fi

set +e
bash "${ROOT}/scripts/ci/accept-customer-idp.sh" "${ARGS[@]}"
RC=$?
set -e

REPORT_DIR="${ROOT}/deploy/dev/_idp_accept"
LATEST="$(ls -1t "${REPORT_DIR}"/*.md 2>/dev/null | head -1 || true)"
if [[ "${REQUIRE_REPORT}" -eq 1 ]]; then
  if [[ -z "${LATEST}" || ! -f "${LATEST}" ]]; then
    echo "FAIL B-layer: expected report under ${REPORT_DIR}"
    exit 1
  fi
  echo "report: ${LATEST}"
fi

if [[ "${RC}" -ne 0 ]]; then
  echo "FAIL B-layer probe exit ${RC}"
  exit "${RC}"
fi
echo "B-layer OK · written sign-off (C) still human"
exit 0
