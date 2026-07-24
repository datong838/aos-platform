#!/usr/bin/env bash
# 156 · Local pseudo-production IdP drill (ALLOW_DEV=0 + Dev KC JWT).
# ≠ customer-site acceptance (微商城等后序按 handbook 60 §6).
# Does NOT touch default demo API on :8080 — spins ephemeral API on :18080.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PATH="${HOME}/tools/micromamba-root/envs/aos/bin:${HOME}/tools/bin:${PATH}"

KEYCLOAK_BASE="${AOS_KEYCLOAK_BASE:-http://127.0.0.1:8083}"
REALM="${AOS_KEYCLOAK_REALM:-aos}"
PSEUDO_PORT="${AOS_PSEUDO_API_PORT:-18080}"
API_BASE="${AOS_PSEUDO_API_BASE:-http://127.0.0.1:${PSEUDO_PORT}}"
USERNAME="${AOS_KC_USER:-alice}"
PASSWORD="${AOS_KC_PASSWORD:-aos_dev_only_change_me}"
CLIENT_ID="${AOS_OIDC_CLIENT_ID:-aos-api}"
REQUIRE=0
KEEP_API=0
PID_FILE="${ROOT}/deploy/dev/demo-pids/aos-api-pseudo-prod.pid"
LOG_OUT="${ROOT}/deploy/dev/aos-api-pseudo-prod.out.log"
LOG_ERR="${ROOT}/deploy/dev/aos-api-pseudo-prod.err.log"
CHILD_PID=""

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/drill-local-pseudo-prod-idp.sh [options]

  --require     FAIL (not SKIP) when Dev Keycloak unreachable
  --keep-api    leave ephemeral :18080 API running after drill
  --help

Pseudo-prod matrix (scheme 156):
  1) temporary aos-api with AOS_AUTH_ALLOW_DEV=0 + OIDC → Dev KC
  2) Bearer "dev" must 401
  3) real OIDC JWT /v1/me must 200 and tokenKind ≠ dev
  4) probe-prod-idp.sh --reject-dev --require-me

Default demo on :8080 is untouched.
Customer site (e.g. 微商城) is out of scope — handbook 60 §6.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --require) REQUIRE=1; shift ;;
    --keep-api) KEEP_API=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

JWKS="${KEYCLOAK_BASE}/realms/${REALM}/protocol/openid-connect/certs"
TOKEN_URL="${KEYCLOAK_BASE}/realms/${REALM}/protocol/openid-connect/token"
ISSUER="${KEYCLOAK_BASE}/realms/${REALM}"

cleanup() {
  if [[ "${KEEP_API}" -eq 1 ]]; then
    return 0
  fi
  if [[ -n "${CHILD_PID}" ]] && kill -0 "${CHILD_PID}" 2>/dev/null; then
    kill "${CHILD_PID}" 2>/dev/null || true
    wait "${CHILD_PID}" 2>/dev/null || true
  fi
  if [[ -f "${PID_FILE}" ]]; then
    local old
    old="$(cat "${PID_FILE}" 2>/dev/null || true)"
    if [[ -n "${old}" ]]; then
      kill "${old}" 2>/dev/null || true
    fi
    rm -f "${PID_FILE}"
  fi
  pkill -f "uvicorn aos_api.main:app --host 127.0.0.1 --port ${PSEUDO_PORT}" 2>/dev/null || true
}
trap cleanup EXIT

echo "drill-local-pseudo-prod-idp (scheme 156) · ≠ customer site"
echo "  ephemeral API ${API_BASE} · ALLOW_DEV=0"

code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 8 "${JWKS}" 2>/dev/null || true)"
if [[ ! "${code}" =~ ^[23] ]]; then
  if [[ "${REQUIRE}" -eq 1 ]]; then
    echo "FAIL: Dev Keycloak not up (JWKS ${code}) and --require set"
    echo "  docker compose -f deploy/dev/docker-compose.yml --profile oidc up -d aos-dev-keycloak"
    exit 1
  fi
  echo "SKIP: Dev Keycloak not up (JWKS ${code})"
  echo "  start KC then re-run; pytest test_local_pseudo_prod_idp.py always covers matrix without Docker"
  exit 0
fi

mkdir -p "$(dirname "${PID_FILE}")" "$(dirname "${LOG_OUT}")"
# stop any previous pseudo API on same port
pkill -f "uvicorn aos_api.main:app --host 127.0.0.1 --port ${PSEUDO_PORT}" 2>/dev/null || true
sleep 0.5

export AOS_AUTH_ALLOW_DEV=0
export AOS_OIDC_ISSUER="${ISSUER}"
export AOS_OIDC_AUDIENCE=aos-api
export AOS_OIDC_JWKS_URL="${JWKS}"
export AOS_OIDC_TOKEN_URL="${TOKEN_URL}"
export AOS_OIDC_CLIENT_ID="${CLIENT_ID}"
export AOS_LOG_LEVEL="${AOS_LOG_LEVEL:-warning}"
export AOS_LOG_FORMAT="${AOS_LOG_FORMAT:-json}"
export PYTHONPATH="${ROOT}/services/aos-api${PYTHONPATH:+:$PYTHONPATH}"

nohup python -m uvicorn aos_api.main:app --host 127.0.0.1 --port "${PSEUDO_PORT}" \
  >"${LOG_OUT}" 2>"${LOG_ERR}" &
CHILD_PID=$!
echo "${CHILD_PID}" >"${PID_FILE}"

echo "waiting for ephemeral API…"
ready=0
for _ in $(seq 1 40); do
  if curl -sf --max-time 1 "${API_BASE}/v1/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.25
done
if [[ "${ready}" -ne 1 ]]; then
  echo "FAIL ephemeral API did not become healthy on ${API_BASE}"
  echo "--- err log ---"
  tail -n 40 "${LOG_ERR}" || true
  exit 1
fi
echo "OK ephemeral API up pid=${CHILD_PID}"

echo "1) /v1/auth/oidc must allowDevToken=false"
cfg="$(curl -sS --max-time 8 "${API_BASE}/v1/auth/oidc")"
echo "   ${cfg}" | head -c 400
echo
if echo "${cfg}" | grep -q '"allowDevToken"[[:space:]]*:[[:space:]]*true'; then
  echo "FAIL allowDevToken still true"
  exit 1
fi
if ! echo "${cfg}" | grep -q '"allowDevToken"[[:space:]]*:[[:space:]]*false'; then
  echo "FAIL allowDevToken=false not found in oidc config"
  exit 1
fi
echo "   OK allowDevToken=false"

echo "2) Bearer dev must be rejected (401)"
dev_code="$(curl -sS -o /tmp/aos-pseudo-dev.json -w '%{http_code}' --max-time 8 \
  -H 'Authorization: Bearer dev' \
  -H 'X-Org-Id: dev-org' \
  -H 'X-Project-Id: dev-project' \
  "${API_BASE}/v1/me" || true)"
if [[ "${dev_code}" != "401" ]]; then
  echo "FAIL expected 401 for Bearer dev, got ${dev_code}"
  cat /tmp/aos-pseudo-dev.json 2>/dev/null || true
  exit 1
fi
if ! grep -q 'AUTH_DEV_DISABLED' /tmp/aos-pseudo-dev.json 2>/dev/null; then
  echo "WARN body missing AUTH_DEV_DISABLED (still 401 — accept)"
fi
echo "   OK Bearer dev → 401"

echo "3) obtain OIDC access_token from Dev KC"
TOK_JSON="$(curl -sS --connect-timeout 10 --max-time 20 \
  -X POST "${TOKEN_URL}" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "grant_type=password&client_id=${CLIENT_ID}&username=${USERNAME}&password=${PASSWORD}" || true)"
ACCESS="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('access_token') or '')" "${TOK_JSON}" 2>/dev/null || true)"
if [[ -z "${ACCESS}" ]]; then
  echo "FAIL cannot obtain access_token"
  echo "${TOK_JSON}" | head -c 400
  exit 1
fi
echo "   OK token obtained (not logged)"

echo "4) OIDC JWT /v1/me must 200 and tokenKind ≠ dev"
me_code="$(curl -sS -o /tmp/aos-pseudo-me.json -w '%{http_code}' --max-time 15 \
  -H "Authorization: Bearer ${ACCESS}" \
  -H 'X-Org-Id: dev-org' \
  -H 'X-Project-Id: dev-project' \
  "${API_BASE}/v1/me" || true)"
if [[ "${me_code}" != "200" ]]; then
  echo "FAIL /v1/me HTTP ${me_code}"
  cat /tmp/aos-pseudo-me.json 2>/dev/null || true
  exit 1
fi
if grep -q '"tokenKind"[[:space:]]*:[[:space:]]*"dev"' /tmp/aos-pseudo-me.json; then
  echo "FAIL tokenKind=dev — not OIDC"
  exit 1
fi
echo "   OK $(head -c 280 /tmp/aos-pseudo-me.json)"

echo "5) probe-prod-idp.sh --reject-dev --require-me"
bash "${ROOT}/scripts/ci/probe-prod-idp.sh" \
  --issuer "${ISSUER}" \
  --jwks "${JWKS}" \
  --audience "aos-api" \
  --api-base "${API_BASE}" \
  --token "${ACCESS}" \
  --require-me \
  --reject-dev

echo "drill-local-pseudo-prod-idp OK (local pseudo-prod · not customer site)"
