#!/usr/bin/env bash
# 60 / 151 · Production IdP probe (macOS/Linux). Parallel to probe-prod-idp.ps1 — does not replace it.
set -euo pipefail

ISSUER="${AOS_OIDC_ISSUER:-}"
JWKS_URL="${AOS_OIDC_JWKS_URL:-}"
AUDIENCE="${AOS_OIDC_AUDIENCE:-aos-api}"
ACCESS_TOKEN="${AOS_PROBE_TOKEN:-}"
API_BASE="${AOS_API_BASE:-http://127.0.0.1:8080}"
REQUIRE_ME=0
REJECT_DEV=0

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/probe-prod-idp.sh [options]

  --issuer URL       or AOS_OIDC_ISSUER
  --jwks URL         or AOS_OIDC_JWKS_URL
  --audience AUD     default aos-api / AOS_OIDC_AUDIENCE
  --token JWT        or AOS_PROBE_TOKEN
  --api-base URL     default http://127.0.0.1:8080
  --require-me       fail if no token /me
  --reject-dev       fail if /v1/auth/oidc allowDevToken=true (pseudo-prod / prod gate · 156)
  --help

Handbook: docs/palantier/20_tech/60-生产IdP联调手册.md
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --issuer) ISSUER="$2"; shift 2 ;;
    --jwks) JWKS_URL="$2"; shift 2 ;;
    --audience) AUDIENCE="$2"; shift 2 ;;
    --token) ACCESS_TOKEN="$2"; shift 2 ;;
    --api-base) API_BASE="$2"; shift 2 ;;
    --require-me) REQUIRE_ME=1; shift ;;
    --reject-dev) REJECT_DEV=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "${JWKS_URL}" && -n "${AOS_OIDC_JWKS_URLS:-}" ]]; then
  JWKS_URL="$(echo "${AOS_OIDC_JWKS_URLS}" | awk -F',' '{print $1}' | xargs)"
fi

echo "probe-prod-idp.sh (scheme 60/151) audience=${AUDIENCE}"

if [[ -z "${ISSUER}" || -z "${JWKS_URL}" ]]; then
  echo "SKIP: set --issuer and --jwks (or AOS_OIDC_ISSUER / AOS_OIDC_JWKS_URL)"
  echo "See docs/palantier/20_tech/60-生产IdP联调手册.md"
  exit 0
fi

curl_ok() {
  local url="$1"
  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 10 --max-time 15 "$url" || true)"
  [[ "${code}" =~ ^[23] ]]
}

DISCOVERY="${ISSUER%/}/.well-known/openid-configuration"
echo "1) discovery: ${DISCOVERY}"
if curl_ok "${DISCOVERY}"; then
  echo "   OK"
else
  echo "   WARN discovery not reachable (some IdPs hide it; continue to JWKS)"
fi

echo "2) JWKS: ${JWKS_URL}"
if ! curl_ok "${JWKS_URL}"; then
  echo "FAIL JWKS unreachable"
  exit 1
fi
echo "   OK"

echo "3) aos-api /v1/auth/oidc (optional)"
if cfg="$(curl -sS --connect-timeout 5 --max-time 8 "${API_BASE}/v1/auth/oidc" 2>/dev/null)"; then
  echo "   ${cfg}" | head -c 400
  echo
  if echo "${cfg}" | grep -q '"allowDevToken"[[:space:]]*:[[:space:]]*true'; then
    if [[ "${REJECT_DEV}" -eq 1 ]]; then
      echo "FAIL allowDevToken=true (require AOS_AUTH_ALLOW_DEV=0 for --reject-dev / pseudo-prod)"
      exit 1
    fi
    echo "   WARN production should set AOS_AUTH_ALLOW_DEV=0"
  fi
else
  if [[ "${REJECT_DEV}" -eq 1 ]]; then
    echo "FAIL aos-api not reachable but --reject-dev set"
    exit 1
  fi
  echo "   WARN aos-api not reachable (ok if API not up)"
fi

echo "4) /v1/me with access token"
if [[ -z "${ACCESS_TOKEN}" ]]; then
  echo "   SKIP: pass --token or AOS_PROBE_TOKEN"
  if [[ "${REQUIRE_ME}" -eq 1 ]]; then
    echo "FAIL RequireMe set but no token"
    exit 1
  fi
  echo "probe-prod-idp OK (partial)"
  exit 0
fi

me_code="$(curl -sS -o /tmp/aos-probe-me.json -w '%{http_code}' --connect-timeout 10 --max-time 15 \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "X-Org-Id: dev-org" \
  -H "X-Project-Id: dev-project" \
  "${API_BASE}/v1/me" || true)"

if [[ "${me_code}" != "200" ]]; then
  echo "FAIL /v1/me HTTP ${me_code}"
  echo "HINT: check iss/aud/JWKS · clock · AOS_AUTH_ALLOW_DEV=0 · claim mappers (handbook §8)"
  exit 1
fi
echo "   OK $(head -c 300 /tmp/aos-probe-me.json)"
if grep -q '"tokenKind"[[:space:]]*:[[:space:]]*"dev"' /tmp/aos-probe-me.json; then
  echo "   WARN tokenKind=dev — not a production IdP JWT"
fi
echo "probe-prod-idp OK"
