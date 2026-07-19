#!/usr/bin/env bash
# 154 · Production IdP drill via Dev Keycloak (true OIDC JWT → probe-prod-idp.sh).
# Not a customer-site substitute; proves handbook 60 path with a real signed JWT when KC is up.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KEYCLOAK_BASE="${AOS_KEYCLOAK_BASE:-http://127.0.0.1:8083}"
REALM="${AOS_KEYCLOAK_REALM:-aos}"
API_BASE="${AOS_API_BASE:-http://127.0.0.1:8080}"
USERNAME="${AOS_KC_USER:-alice}"
PASSWORD="${AOS_KC_PASSWORD:-aos_dev_only_change_me}"
CLIENT_ID="${AOS_OIDC_CLIENT_ID:-aos-api}"
REQUIRE_ME=0

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/drill-prod-idp-via-dev-kc.sh [--require-me] [--help]

1) password-grant access_token from Dev Keycloak
2) run probe-prod-idp.sh with issuer/jwks/token

Skip (exit 0) when Keycloak unreachable.
Handbook: docs/palantier/20_tech/60 · scheme 154
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --require-me) REQUIRE_ME=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

JWKS="${KEYCLOAK_BASE}/realms/${REALM}/protocol/openid-connect/certs"
TOKEN_URL="${KEYCLOAK_BASE}/realms/${REALM}/protocol/openid-connect/token"
ISSUER="${KEYCLOAK_BASE}/realms/${REALM}"

echo "drill-prod-idp-via-dev-kc (scheme 154)"
code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 8 "${JWKS}" 2>/dev/null || true)"
if [[ ! "${code}" =~ ^[23] ]]; then
  echo "SKIP: Dev Keycloak not up (JWKS ${code})"
  echo "  docker compose -f deploy/dev/docker-compose.yml --profile oidc up -d aos-dev-keycloak"
  exit 0
fi

TOK_JSON="$(curl -sS --connect-timeout 10 --max-time 20 \
  -X POST "${TOKEN_URL}" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "grant_type=password&client_id=${CLIENT_ID}&username=${USERNAME}&password=${PASSWORD}" || true)"
ACCESS="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('access_token') or '')" "${TOK_JSON}" 2>/dev/null || true)"
if [[ -z "${ACCESS}" ]]; then
  echo "FAIL cannot obtain access_token"
  exit 1
fi
echo "OK obtained OIDC access_token (not logged)"

ARGS=(
  --issuer "${ISSUER}"
  --jwks "${JWKS}"
  --audience "aos-api"
  --api-base "${API_BASE}"
  --token "${ACCESS}"
)
if [[ "${REQUIRE_ME}" -eq 1 ]]; then
  ARGS+=(--require-me)
fi

bash "${ROOT}/scripts/ci/probe-prod-idp.sh" "${ARGS[@]}"
echo "drill-prod-idp-via-dev-kc OK"
