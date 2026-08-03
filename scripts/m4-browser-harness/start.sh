#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HARNESS_DIR="$ROOT/scripts/m4-browser-harness"
STATE_DIR="${AOS_M4_STATE_DIR:-${TMPDIR:-/tmp}/aos-m4-browser-harness}"
CONTAINER="${AOS_M4_PG_CONTAINER:-aos-m4-browser-pg}"
PG_PORT="${AOS_M4_PG_PORT:-55432}"
API_PORT="${AOS_M4_API_PORT:-18080}"
PROXY_PORT="${AOS_M4_PROXY_PORT:-18081}"
WEB_PORT="${AOS_M4_WEB_PORT:-1420}"
PG_USER="aos_m4"
PG_PASSWORD="aos_m4_browser_only"
PG_DATABASE="aos_m4"
DSN="$(printf 'postgresql://%s:%s@127.0.0.1:%s/%s' \
  "$PG_USER" "$PG_PASSWORD" "$PG_PORT" "$PG_DATABASE")"

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"

fail() { echo "FAIL $*" >&2; exit 1; }
port_free() {
  ! (command -v lsof >/dev/null && lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | grep -q .)
}
for port in "$PG_PORT" "$API_PORT" "$PROXY_PORT" "$WEB_PORT"; do
  port_free "$port" || fail "port $port is already in use"
done
command -v docker >/dev/null || fail "docker is required"
PYTHON=""
for candidate in \
  "${AOS_M4_PYTHON:-}" \
  "$HOME/tools/micromamba-root/envs/aos/bin/python" \
  "$(command -v python3.13 || true)" \
  "$(command -v python3.12 || true)" \
  "$(command -v python3.11 || true)" \
  "$(command -v python3 || true)" \
  "$(command -v python || true)"; do
  if [ -x "$candidate" ] && "$candidate" -c \
    'import sys; assert sys.version_info >= (3,11)' \
    >/dev/null 2>&1 && "$candidate" -m pip --version \
    >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done
[ -n "$PYTHON" ] || fail "python >=3.11 with aos-api dependencies is required (or set AOS_M4_PYTHON)"
if [ "${AOS_M4_SKIP_INSTALL:-0}" != 1 ]; then
  "$PYTHON" -m pip install -q -e "$ROOT/services/aos-api"
fi
"$PYTHON" -c 'import fastapi,psycopg,uvicorn,alembic,semantic_version,jwt' \
  >/dev/null 2>&1 || fail "aos-api dependencies are incomplete; unset AOS_M4_SKIP_INSTALL"
if ! command -v node >/dev/null; then
  for node_dir in \
    "$HOME/tools/node-v22.17.0-darwin-arm64/bin" \
    "/Applications/Cursor.app/Contents/Resources/app/resources/helpers"; do
    if [ -x "$node_dir/node" ]; then
      export PATH="$node_dir:$PATH"
      break
    fi
  done
fi
command -v node >/dev/null || fail "node is required"
command -v pnpm >/dev/null || fail "pnpm is required"
[ -x "$ROOT/apps/web/node_modules/.bin/vite" ] || fail "run pnpm install --frozen-lockfile first"
docker inspect "$CONTAINER" >/dev/null 2>&1 && fail "container $CONTAINER already exists; run stop.sh"

cleanup_on_error() {
  code=$?
  trap - EXIT
  if [ "$code" -ne 0 ]; then
    "$HARNESS_DIR/stop.sh" >/dev/null 2>&1 || true
  fi
  exit "$code"
}
trap cleanup_on_error EXIT

docker run --rm -d --name "$CONTAINER" \
  -e POSTGRES_USER="$PG_USER" \
  -e POSTGRES_PASSWORD="$PG_PASSWORD" \
  -e POSTGRES_DB="$PG_DATABASE" \
  -p "127.0.0.1:${PG_PORT}:5432" \
  postgres:16-alpine >"$STATE_DIR/postgres.container"

ready=0
for _ in $(seq 1 60); do
  if docker exec "$CONTAINER" pg_isready -U "$PG_USER" -d "$PG_DATABASE" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
[ "$ready" = 1 ] || fail "isolated PostgreSQL did not become ready"

export AOS_DATABASE_URL="$DSN"
export AOS_M4_SEED_OUTPUT="$STATE_DIR/seed.json"
export AOS_M4_EXPIRY_SECONDS="${AOS_M4_EXPIRY_SECONDS:-120}"
export PYTHONPATH="$ROOT/services/aos-api"
"$PYTHON" "$HARNESS_DIR/bootstrap.py"
chmod 600 "$STATE_DIR/seed.json"

nohup env \
  AOS_DATABASE_URL="$DSN" \
  AOS_DB_MIGRATION_MODE=disabled \
  AOS_AUTH_ALLOW_DEV=1 \
  AOS_TWA_STORE=memory \
  PYTHONPATH="$ROOT/services/aos-api" \
  "$PYTHON" -m uvicorn aos_api.main:app --host 127.0.0.1 --port "$API_PORT" \
  </dev/null >"$STATE_DIR/api.log" 2>&1 &
echo $! >"$STATE_DIR/api.pid"

ready=0
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${API_PORT}/v1/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
[ "$ready" = 1 ] || { tail -n 80 "$STATE_DIR/api.log" >&2 || true; fail "aos-api did not become ready"; }

curl -fsS -X POST "http://127.0.0.1:${API_PORT}/v1/auth/token" \
  -H 'Content-Type: application/json' \
  --data '{"grantType":"dev","subject":"operator:m4-browser","orgId":"dev-org","projectId":"dev-project","roles":["integration-case-reader","integration-case-maker","integration-case-projector"],"markings":["public","restricted"],"alg":"HS256"}' \
  >"$STATE_DIR/token-response.json"
"$PYTHON" - "$STATE_DIR/token-response.json" "$STATE_DIR/access-token" <<'PY'
import json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
token = payload.get("accessToken")
if not isinstance(token, str) or token.count(".") != 2:
    raise SystemExit("API did not issue a JWT")
pathlib.Path(sys.argv[2]).write_text(token + "\n")
PY
chmod 600 "$STATE_DIR/access-token" "$STATE_DIR/token-response.json"
rm "$STATE_DIR/token-response.json"

nohup "$PYTHON" "$HARNESS_DIR/jwt_proxy.py" \
  --listen-port "$PROXY_PORT" \
  --api-port "$API_PORT" \
  --token-file "$STATE_DIR/access-token" \
  </dev/null >"$STATE_DIR/proxy.log" 2>&1 &
echo $! >"$STATE_DIR/proxy.pid"

ready=0
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PROXY_PORT}/__harness/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
[ "$ready" = 1 ] || fail "JWT proxy did not become ready"

nohup env VITE_AOS_API_BASE="http://127.0.0.1:${PROXY_PORT}" \
  "$ROOT/apps/web/node_modules/.bin/vite" \
  "$ROOT/apps/web" \
  --host 127.0.0.1 --port "$WEB_PORT" --strictPort \
  </dev/null >"$STATE_DIR/web.log" 2>&1 &
echo $! >"$STATE_DIR/web.pid"

ready=0
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${WEB_PORT}/apollo/cases" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
[ "$ready" = 1 ] || { tail -n 80 "$STATE_DIR/web.log" >&2 || true; fail "Vite Web did not become ready"; }

"$HARNESS_DIR/health-check.sh"
trap - EXIT
echo "M4 browser harness ready"
echo "Web:     http://127.0.0.1:${WEB_PORT}/apollo/cases"
echo "API:     http://127.0.0.1:${API_PORT}/v1/health"
echo "JWT API: http://127.0.0.1:${PROXY_PORT}/v1/integration-cases?scope=current"
echo "Account: operator:m4-browser @ dev-org/dev-project"
echo "Seed:    $STATE_DIR/seed.json"
echo "Stop:    $HARNESS_DIR/stop.sh"

if [ "${AOS_M4_FOREGROUND:-0}" = 1 ]; then
  foreground_cleanup() {
    trap - EXIT INT TERM
    "$HARNESS_DIR/stop.sh" >/dev/null 2>&1 || true
  }
  trap foreground_cleanup EXIT INT TERM
  echo "Supervisor: foreground mode; Ctrl-C performs exact cleanup"
  while :; do
    for service in api proxy web; do
      pid="$(cat "$STATE_DIR/${service}.pid" 2>/dev/null || true)"
      if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
        fail "$service exited while foreground supervisor was active"
      fi
    done
    sleep 1
  done
fi
