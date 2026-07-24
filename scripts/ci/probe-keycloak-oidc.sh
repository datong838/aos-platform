#!/usr/bin/env bash
# 50 / 154 · Dev Keycloak OIDC probe (macOS/Linux). Parallel to probe-keycloak-oidc.ps1.
set -euo pipefail

KEYCLOAK_BASE="${AOS_KEYCLOAK_BASE:-http://127.0.0.1:8083}"
REALM="${AOS_KEYCLOAK_REALM:-aos}"
API_BASE="${AOS_API_BASE:-http://127.0.0.1:8080}"
USERNAME="${AOS_KC_USER:-alice}"
PASSWORD="${AOS_KC_PASSWORD:-aos_dev_only_change_me}"
CLIENT_ID="${AOS_OIDC_CLIENT_ID:-aos-api}"

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/probe-keycloak-oidc.sh [options]

  --keycloak-base URL   default http://127.0.0.1:8083
  --realm NAME          default aos
  --api-base URL        default http://127.0.0.1:8080
  --user NAME
  --password STR
  --client-id ID
  --help

Skip (exit 0) when Keycloak JWKS unreachable.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keycloak-base) KEYCLOAK_BASE="$2"; shift 2 ;;
    --realm) REALM="$2"; shift 2 ;;
    --api-base) API_BASE="$2"; shift 2 ;;
    --user) USERNAME="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --client-id) CLIENT_ID="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

JWKS="${KEYCLOAK_BASE}/realms/${REALM}/protocol/openid-connect/certs"
TOKEN_URL="${KEYCLOAK_BASE}/realms/${REALM}/protocol/openid-connect/token"
ISSUER="${KEYCLOAK_BASE}/realms/${REALM}"

code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 8 "${JWKS}" 2>/dev/null || true)"
echo "probe-keycloak-oidc.sh JWKS: ${JWKS}"
if [[ ! "${code}" =~ ^[23] ]]; then
  echo "SKIP: Keycloak not up. Start with:"
  echo "  docker compose -f deploy/dev/docker-compose.yml --profile oidc up -d aos-dev-keycloak"
  exit 0
fi
echo "OK JWKS reachable"

TOK_JSON="$(curl -sS --connect-timeout 10 --max-time 20 \
  -X POST "${TOKEN_URL}" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "grant_type=password&client_id=${CLIENT_ID}&username=${USERNAME}&password=${PASSWORD}" || true)"

ACCESS="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('access_token') or '')" "${TOK_JSON}" 2>/dev/null || true)"
if [[ -z "${ACCESS}" ]]; then
  echo "FAIL no access_token from Keycloak"
  echo "${TOK_JSON}" | head -c 400
  echo
  exit 1
fi
echo "OK password grant"

ME_CODE="$(curl -sS -o /tmp/aos-kc-me.json -w '%{http_code}' --connect-timeout 8 --max-time 12 \
  -H "Authorization: Bearer ${ACCESS}" \
  -H "X-Org-Id: dev-org" \
  -H "X-Project-Id: dev-project" \
  "${API_BASE}/v1/me" || true)"

if [[ "${ME_CODE}" != "200" ]]; then
  echo "WARN /v1/me HTTP ${ME_CODE} (aos-api may need OIDC env). IdP grant still OK."
  echo "HINT env:"
  echo "  AOS_OIDC_ISSUER=${ISSUER}"
  echo "  AOS_OIDC_AUDIENCE=aos-api"
  echo "  AOS_OIDC_JWKS_URL=${JWKS}"
  echo "  AOS_OIDC_TOKEN_URL=${TOKEN_URL}"
  exit 0
fi

python3 - <<'PY'
import json
me = json.load(open("/tmp/aos-kc-me.json"))
print(f"OK /v1/me subject={me.get('subject')} tokenKind={me.get('tokenKind')}")
if me.get("tokenKind") != "oidc":
    print("WARN tokenKind!=oidc — point aos-api at this Keycloak JWKS/issuer then restart")
PY

echo "probe-keycloak-oidc OK"
exit 0
