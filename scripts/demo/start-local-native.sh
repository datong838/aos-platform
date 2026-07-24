#!/usr/bin/env bash
# TB.0 · macOS 原生降级启动（Docker Hub 不可达时）
# 文档：24 §4.4
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="$ROOT/deploy/dev"
PID_DIR="$LOG_DIR/demo-pids"
mkdir -p "$PID_DIR"

export PATH="${HOME}/tools/micromamba-root/envs/aos/bin:${HOME}/tools/bin:${HOME}/tools/node-v22.17.0-darwin-arm64/bin:${PATH}"
export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/tools/micromamba-root}"

step() { echo; echo "=== $* ==="; }

step "Native start · root=$ROOT"

# --- PG ---
step "PostgreSQL :5433"
if ! pg_isready -h 127.0.0.1 -p 5433 -U aos_app >/dev/null 2>&1; then
  PGDATA="${AOS_PGDATA:-$HOME/tools/aos-pgdata}"
  if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "missing cluster at $PGDATA — run initdb first (see 24 §4.4)"
    exit 1
  fi
  pg_ctl -D "$PGDATA" -l "$PGDATA/pg.log" start
fi
pg_isready -h 127.0.0.1 -p 5433 -U aos_app
# ensure UTF8 db
if ! psql -p 5433 -U aos_app -d aos_meta -Atc "SELECT 1" >/dev/null 2>&1; then
  createdb -p 5433 -U aos_app -E UTF8 -T template0 aos_meta || true
fi
enc="$(psql -p 5433 -U aos_app -d aos_meta -Atc 'SHOW server_encoding;')"
echo "aos_meta encoding=$enc"
if [ "$enc" != "UTF8" ]; then
  echo "WARN: recreate with createdb -E UTF8 -T template0 aos_meta"
fi

# --- MinIO ---
step "MinIO :9000"
if ! curl -sf http://127.0.0.1:9000/minio/health/live >/dev/null; then
  command -v minio >/dev/null || { echo "minio binary not in PATH"; exit 1; }
  export MINIO_ROOT_USER=aosdev MINIO_ROOT_PASSWORD=aos_dev_only_change_me
  DATA="${AOS_MINIO_DATA:-$HOME/tools/aos-minio-data}"
  mkdir -p "$DATA"
  # macOS: no setsid — caller should keep this shell / use a dedicated terminal
  nohup minio server "$DATA" --address 127.0.0.1:9000 --console-address 127.0.0.1:9001 \
    >"$HOME/tools/aos-minio.log" 2>&1 &
  echo $! >"$HOME/tools/aos-minio.pid"
  for _ in $(seq 1 30); do
    curl -sf http://127.0.0.1:9000/minio/health/live >/dev/null && break
    sleep 1
  done
fi
curl -sf -o /dev/null -w "MinIO HTTP %{http_code}\n" http://127.0.0.1:9000/minio/health/live

# bucket (best-effort)
python - <<'PY' 2>/dev/null || true
from minio import Minio
from io import BytesIO
c = Minio("127.0.0.1:9000", access_key="aosdev", secret_key="aos_dev_only_change_me", secure=False)
if not c.bucket_exists("aos-media"):
    c.make_bucket("aos-media")
c.put_object("aos-media", "dev-probe.txt", BytesIO(b"probe"), 5)
print("bucket aos-media OK")
PY

# --- API ---
step "aos-api :8080"
API_DIR="$ROOT/services/aos-api"
(cd "$API_DIR" && python -m pip install -e . -q)
if [ -f "$PID_DIR/aos-api.pid" ]; then
  kill "$(cat "$PID_DIR/aos-api.pid")" 2>/dev/null || true
fi
export AOS_LOG_LEVEL=debug AOS_LOG_FORMAT=json AOS_AUTH_ALLOW_DEV=1
export AOS_DATABASE_URL="${AOS_DATABASE_URL:-postgresql://aos_app:aos_dev_only_change_me@127.0.0.1:5433/aos_meta}"
export AOS_S3_ENDPOINT="${AOS_S3_ENDPOINT:-http://127.0.0.1:9000}"
export AOS_S3_BUCKET="${AOS_S3_BUCKET:-aos-media}"
export AOS_S3_ACCESS_KEY="${AOS_S3_ACCESS_KEY:-aosdev}"
export AOS_S3_SECRET_KEY="${AOS_S3_SECRET_KEY:-aos_dev_only_change_me}"
nohup python -m uvicorn aos_api.main:app --host 127.0.0.1 --port 8080 \
  >"$LOG_DIR/aos-api.out.log" 2>"$LOG_DIR/aos-api.err.log" &
echo $! >"$PID_DIR/aos-api.pid"
for _ in $(seq 1 45); do
  curl -sf http://127.0.0.1:8080/v1/health >/dev/null && break
  sleep 1
done
curl -sf http://127.0.0.1:8080/v1/health
echo

# --- Web ---
step "web :5173"
WEB_DIR="$ROOT/apps/web"
[ -d "$WEB_DIR/node_modules" ] || (cd "$WEB_DIR" && npm install)
if [ -f "$PID_DIR/aos-web.pid" ]; then
  kill "$(cat "$PID_DIR/aos-web.pid")" 2>/dev/null || true
fi
nohup npm --prefix "$WEB_DIR" run dev -- --host 127.0.0.1 --port 5173 \
  >"$LOG_DIR/aos-web.out.log" 2>"$LOG_DIR/aos-web.err.log" &
echo $! >"$PID_DIR/aos-web.pid"
for _ in $(seq 1 60); do
  code="$(curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1:5173/ || true)"
  [ "${code:-000}" = "200" ] && break
  sleep 1
done

bash "$(dirname "$0")/health-check.sh" --require-web
echo "Native URLs: API http://127.0.0.1:8080/v1/health  Web http://127.0.0.1:5173/"
