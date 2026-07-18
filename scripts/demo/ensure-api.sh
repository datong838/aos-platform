#!/usr/bin/env bash
# 76 · 确保 aos-api :8080 在线（掉线则拉起；独立 session，避免 Agent shell 收尾连带杀掉）
# 用法：bash scripts/demo/ensure-api.sh [--restart]
# 日志：deploy/dev/aos-api.out.log · aos-api.err.log
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="$ROOT/deploy/dev"
PID_DIR="$LOG_DIR/demo-pids"
mkdir -p "$PID_DIR" "$LOG_DIR"

export PATH="${HOME}/tools/micromamba-root/envs/aos/bin:${HOME}/tools/bin:${HOME}/tools/node-v22.17.0-darwin-arm64/bin:${PATH}"

RESTART=0
if [ "${1:-}" = "--restart" ]; then
  RESTART=1
fi

stop_api() {
  if [ -f "$PID_DIR/aos-api.pid" ]; then
    kill "$(cat "$PID_DIR/aos-api.pid")" 2>/dev/null || true
  fi
  pkill -f "uvicorn aos_api.main:app --host 127.0.0.1 --port 8080" 2>/dev/null || true
  sleep 1
}

load_platform_env() {
  # shellcheck disable=SC2046
  eval "$(ROOT="$ROOT" python3 - <<'PY'
import os
import shlex
from pathlib import Path

root = Path(os.environ["ROOT"])
prefixes = ("AGNES_", "AOS_LLM_", "AOS_LITELLM_", "AOS_S3_", "MINIO_", "AOS_MYSQL_", "MYSQL_", "AOS_OCR_")
for path in (root / ".env", root / "deploy" / "dev" / ".env"):
    if not path.is_file():
        continue
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if not key or not val:
            continue
        if key.startswith(prefixes):
            print(f"export {key}={shlex.quote(val)}")
    break
PY
)"
}

if [ "$RESTART" = "0" ] && curl -sf --max-time 2 http://127.0.0.1:8080/v1/health >/dev/null; then
  echo "OK  aos-api already up  http://127.0.0.1:8080/v1/health"
  exit 0
fi

if [ "$RESTART" = "1" ]; then
  echo "WARN aos-api restart requested…"
else
  echo "WARN aos-api down — restarting…"
fi
stop_api

if [ -f "$ROOT/deploy/dev/.secrets.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/deploy/dev/.secrets.env"
  set +a
fi

load_platform_env

export AOS_LOG_LEVEL="${AOS_LOG_LEVEL:-debug}"
export AOS_LOG_FORMAT="${AOS_LOG_FORMAT:-json}"
export AOS_AUTH_ALLOW_DEV=1
export AOS_DATABASE_URL="${AOS_DATABASE_URL:-postgresql://aos_app:aos_dev_only_change_me@127.0.0.1:5433/aos_meta}"
export AOS_S3_ENDPOINT="${AOS_S3_ENDPOINT:-http://127.0.0.1:9000}"
export AOS_S3_BUCKET="${AOS_S3_BUCKET:-aos-media}"
export AOS_S3_ACCESS_KEY="${AOS_S3_ACCESS_KEY:-aosdev}"
export AOS_S3_SECRET_KEY="${AOS_S3_SECRET_KEY:-aos_dev_only_change_me}"
export PYTHONPATH="$ROOT/services/aos-api${PYTHONPATH:+:$PYTHONPATH}"

export AOS_ENSURE_ROOT="$ROOT"
export AOS_ENSURE_OUT="$LOG_DIR/aos-api.out.log"
export AOS_ENSURE_ERR="$LOG_DIR/aos-api.err.log"
export AOS_ENSURE_PID="$PID_DIR/aos-api.pid"

# start_new_session=True → 脱离 Cursor/Agent 进程组
python - <<'PY'
import os, subprocess, sys

root = os.environ["AOS_ENSURE_ROOT"]
out_log = os.environ["AOS_ENSURE_OUT"]
err_log = os.environ["AOS_ENSURE_ERR"]
pid_file = os.environ["AOS_ENSURE_PID"]
env = os.environ.copy()
with open(out_log, "ab") as out, open(err_log, "ab") as err:
    p = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "aos_api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8080",
        ],
        cwd=os.path.join(root, "services", "aos-api"),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=out,
        stderr=err,
        start_new_session=True,
    )
with open(pid_file, "w", encoding="utf-8") as f:
    f.write(str(p.pid))
print(f"pid={p.pid}  log={out_log}")
PY

for _ in $(seq 1 45); do
  if curl -sf --max-time 2 http://127.0.0.1:8080/v1/health >/dev/null; then
    echo "OK  aos-api restarted (detached session)"
    exit 0
  fi
  sleep 1
done

echo "FAIL aos-api did not become healthy — tail $AOS_ENSURE_ERR"
tail -40 "$AOS_ENSURE_ERR" 2>/dev/null || true
exit 1
