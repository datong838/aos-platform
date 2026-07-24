#!/usr/bin/env bash
# 157 · Host analytics-runtime (shaped or true Jupyter). Parallel to start-analytics-sidecar-host.ps1.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RT="$ROOT/deploy/dev/analytics-runtime"
export PATH="${HOME}/tools/micromamba-root/envs/aos/bin:${HOME}/tools/bin:${PATH}"

ENGINE="${AOS_ANALYTICS_ENGINE:-shaped}"
PORT="${AOS_ANALYTICS_PORT:-8084}"
JPORT="${AOS_JUPYTER_PORT:-8888}"

usage() {
  cat <<'EOF'
Usage: bash scripts/demo/start-analytics-sidecar-host.sh [--jupyter|--shaped] [--help]

  --jupyter   AOS_ANALYTICS_ENGINE=jupyter (needs notebook/jupyter_server)
  --shaped    HTML stub only (default)

Listens :8084 (ticket Facade). Jupyter mode also binds :8888.
Scheme: docs/palantier/20_tech/157-真Jupyter-Notebook7边车MVP方案.md
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jupyter) ENGINE=jupyter; shift ;;
    --shaped) ENGINE=shaped; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

if [[ ! -f "$RT/app.py" ]]; then
  echo "FAIL missing $RT/app.py"
  exit 1
fi

if [[ "$ENGINE" == "jupyter" ]]; then
  if ! python -c "import notebook, jupyter_server" 2>/dev/null; then
    echo "WARN jupyter packages missing — pip install -r $RT/requirements-jupyter.txt"
    echo "     falling back to shaped for this host start"
    ENGINE=shaped
  fi
fi

pkill -f "uvicorn app:app --host 127.0.0.1 --port ${PORT}" 2>/dev/null || true
# also stop prior jupyter spawned by sidecar on same port
sleep 0.5

export AOS_ANALYTICS_ENGINE="$ENGINE"
export AOS_ANALYTICS_PUBLIC_URL="http://127.0.0.1:${PORT}"
export AOS_JUPYTER_PORT="$JPORT"
export AOS_JUPYTER_PUBLIC_URL="http://127.0.0.1:${JPORT}"
export AOS_JUPYTER_ROOT="${AOS_JUPYTER_ROOT:-$RT/notebooks}"
export PYTHONPATH="$RT${PYTHONPATH:+:$PYTHONPATH}"

LOG_DIR="$ROOT/deploy/dev"
mkdir -p "$LOG_DIR/demo-pids" "$AOS_JUPYTER_ROOT"
cd "$RT"
nohup python -m uvicorn app:app --host 127.0.0.1 --port "$PORT" \
  >"$LOG_DIR/analytics-runtime.out.log" 2>"$LOG_DIR/analytics-runtime.err.log" &
echo $! >"$LOG_DIR/demo-pids/analytics-runtime.pid"

echo "started analytics-runtime engine=${ENGINE} http://127.0.0.1:${PORT}/health"
if [[ "$ENGINE" == "jupyter" ]]; then
  echo "  jupyter UI (after ticket): http://127.0.0.1:${JPORT}/"
fi
