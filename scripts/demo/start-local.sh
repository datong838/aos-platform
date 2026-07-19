#!/usr/bin/env bash
# TB.0 · macOS/Linux 本地演示一键启动（对齐 start-local.ps1）
# 文档：docs/palantier/20_tech/24 §4.3 · 72
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
LOG_DIR="$ROOT/deploy/dev"
PID_DIR="$LOG_DIR/demo-pids"
mkdir -p "$PID_DIR"

INFRA_ONLY=0
SKIP_INSTALL=0
SKIP_WEB=0
for arg in "$@"; do
  case "$arg" in
    --infra-only) INFRA_ONLY=1 ;;
    --skip-install) SKIP_INSTALL=1 ;;
    --skip-web) SKIP_WEB=1 ;;
    -h|--help)
      echo "Usage: $0 [--infra-only] [--skip-install] [--skip-web]"
      exit 0
      ;;
  esac
done

step() { echo; echo "=== $* ==="; }

# Prefer Docker Desktop CLI if present
if [ -x "$HOME/Applications/Docker.app/Contents/Resources/bin/docker" ]; then
  export PATH="$HOME/Applications/Docker.app/Contents/Resources/bin:$PATH"
fi
if [ -x "$HOME/tools/bin/micromamba" ]; then
  export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/tools/micromamba-root}"
  # shellcheck disable=SC1091
  eval "$("$HOME/tools/bin/micromamba" shell hook -s bash)"
  micromamba activate aos 2>/dev/null || true
fi
if [ -d "$HOME/tools/node-v22.17.0-darwin-arm64/bin" ]; then
  export PATH="$HOME/tools/node-v22.17.0-darwin-arm64/bin:$PATH"
fi

command -v docker >/dev/null || { echo "docker not found"; exit 1; }
command -v python >/dev/null || command -v python3 >/dev/null || { echo "python>=3.11 required"; exit 1; }
PYTHON="$(command -v python || true)"
[ -n "$PYTHON" ] || PYTHON="$(command -v python3)"

step "TB.0 start-local.sh · root=$ROOT"

COMPOSE="deploy/dev/docker-compose.yml"
[ -f "$COMPOSE" ] || { echo "missing $COMPOSE"; exit 1; }

step "Docker compose up (core stack)"
docker compose -f "$COMPOSE" up -d \
  aos-dev-pg aos-dev-minio aos-dev-minio-init \
  aos-dev-mysql aos-dev-llm-echo aos-dev-litellm aos-dev-ocr aos-dev-analytics

step "Wait PostgreSQL"
ok=0
for _ in $(seq 1 45); do
  if docker exec aos-dev-pg pg_isready -U aos_app -d aos_meta >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done
[ "$ok" = 1 ] || { echo "PostgreSQL not ready on :5433"; exit 1; }
echo "PostgreSQL ONLINE"

if [ "$INFRA_ONLY" = 1 ]; then
  step "InfraOnly health"
  bash "$(dirname "$0")/health-check.sh" --infra-only
  exit $?
fi

step "aos-api :8080"
API_DIR="$ROOT/services/aos-api"
if [ "$SKIP_INSTALL" = 0 ]; then
  (cd "$API_DIR" && "$PYTHON" -m pip install -e . -q)
fi

if [ -f "$PID_DIR/aos-api.pid" ]; then
  old="$(cat "$PID_DIR/aos-api.pid" || true)"
  if [ -n "${old:-}" ]; then kill "$old" 2>/dev/null || true; fi
  rm -f "$PID_DIR/aos-api.pid"
fi

export AOS_LOG_LEVEL=debug
export AOS_LOG_FORMAT=json
export AOS_AUTH_ALLOW_DEV=1
export AOS_DATABASE_URL="${AOS_DATABASE_URL:-postgresql://aos_app:aos_dev_only_change_me@127.0.0.1:5433/aos_meta}"
export AOS_S3_ENDPOINT="${AOS_S3_ENDPOINT:-http://127.0.0.1:9000}"
export AOS_S3_BUCKET="${AOS_S3_BUCKET:-aos-media}"
export AOS_ANALYTICS_URL="${AOS_ANALYTICS_URL:-http://127.0.0.1:8084}"

nohup "$PYTHON" -m uvicorn aos_api.main:app --host 127.0.0.1 --port 8080 \
  >"$LOG_DIR/aos-api.out.log" 2>"$LOG_DIR/aos-api.err.log" &
echo $! >"$PID_DIR/aos-api.pid"
echo "aos-api pid=$(cat "$PID_DIR/aos-api.pid") log=$LOG_DIR/aos-api.out.log"

api_ok=0
for _ in $(seq 1 45); do
  if curl -sf "http://127.0.0.1:8080/v1/health" >/dev/null; then
    api_ok=1
    break
  fi
  sleep 1
done
if [ "$api_ok" != 1 ]; then
  echo "aos-api /v1/health not 200 — tail err:"
  tail -n 40 "$LOG_DIR/aos-api.err.log" || true
  exit 1
fi
echo "aos-api ONLINE"

if [ "$SKIP_WEB" = 0 ]; then
  step "web :5173"
  command -v npm >/dev/null || { echo "npm not found"; exit 1; }
  WEB_DIR="$ROOT/apps/web"
  if [ "$SKIP_INSTALL" = 0 ] && [ ! -d "$WEB_DIR/node_modules" ]; then
    (cd "$WEB_DIR" && npm install)
  fi
  if [ -f "$PID_DIR/aos-web.pid" ]; then
    old="$(cat "$PID_DIR/aos-web.pid" || true)"
    if [ -n "${old:-}" ]; then kill "$old" 2>/dev/null || true; fi
    rm -f "$PID_DIR/aos-web.pid"
  fi
  nohup npm --prefix "$WEB_DIR" run dev -- --host 127.0.0.1 --port 5173 \
    >"$LOG_DIR/aos-web.out.log" 2>"$LOG_DIR/aos-web.err.log" &
  echo $! >"$PID_DIR/aos-web.pid"
  echo "web pid=$(cat "$PID_DIR/aos-web.pid") log=$LOG_DIR/aos-web.out.log"
  web_ok=0
  for _ in $(seq 1 60); do
    code="$(curl -sf -o /dev/null -w '%{http_code}' "http://127.0.0.1:5173/" || true)"
    if [ "${code:-000}" != "000" ] && [ "${code}" -lt 500 ] 2>/dev/null; then
      web_ok=1
      break
    fi
    sleep 1
  done
  if [ "$web_ok" = 1 ]; then echo "web ONLINE"; else echo "web not ready yet — check $LOG_DIR/aos-web.err.log"; fi
fi

step "health-check"
bash "$(dirname "$0")/health-check.sh"
code=$?
echo
echo "Demo URLs:"
echo "  API   http://127.0.0.1:8080/v1/health"
echo "  Web   http://127.0.0.1:5173/"
echo "  Auth  Bearer dev  (AOS_AUTH_ALLOW_DEV=1)"
echo "Stop:   bash scripts/demo/stop-local.sh"
exit "$code"
