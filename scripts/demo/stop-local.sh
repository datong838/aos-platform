#!/usr/bin/env bash
# TB.0 · 停止本机 API/Web；可选停 Docker 前置
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PID_DIR="$ROOT/deploy/dev/demo-pids"
ALSO_INFRA=0
for arg in "$@"; do
  case "$arg" in
    --also-infra) ALSO_INFRA=1 ;;
  esac
done

if [ -x "$HOME/Applications/Docker.app/Contents/Resources/bin/docker" ]; then
  export PATH="$HOME/Applications/Docker.app/Contents/Resources/bin:$PATH"
fi

stop_pid() {
  local f="$1"
  if [ -f "$f" ]; then
    local p
    p="$(cat "$f" || true)"
    if [ -n "${p:-}" ]; then kill "$p" 2>/dev/null || true; fi
    rm -f "$f"
  fi
}

stop_pid "$PID_DIR/aos-api.pid"
stop_pid "$PID_DIR/aos-web.pid"
# Vite 可能留下子进程
pkill -f "vite.*5173" 2>/dev/null || true
pkill -f "uvicorn aos_api.main:app" 2>/dev/null || true
echo "API/Web stopped"

if [ "$ALSO_INFRA" = 1 ]; then
  docker compose -f "$ROOT/deploy/dev/docker-compose.yml" stop
  echo "Docker infra stopped (volumes kept)"
fi
