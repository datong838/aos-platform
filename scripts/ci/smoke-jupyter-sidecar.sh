#!/usr/bin/env bash
# 157 · Smoke true Jupyter sidecar (health + optional nbclient). SKIP when unavailable.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PATH="${HOME}/tools/micromamba-root/envs/aos/bin:${HOME}/tools/bin:${PATH}"
API="${AOS_ANALYTICS_URL:-http://127.0.0.1:8084}"
NB="${ROOT}/deploy/dev/analytics-runtime/notebooks/aos_smoke.ipynb"
REQUIRE=0

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/smoke-jupyter-sidecar.sh [--require] [--help]

  1) GET /health — prefer engine=jupyter-server
  2) if nbclient+notebook present — execute aos_smoke.ipynb headless

Skip (exit 0) when sidecar down unless --require.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --require) REQUIRE=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

echo "smoke-jupyter-sidecar (scheme 157) → ${API}"
code="$(curl -sS -o /tmp/aos-jupy-health.json -w '%{http_code}' --connect-timeout 3 --max-time 8 \
  "${API}/health" 2>/dev/null || true)"
if [[ "${code}" != "200" ]]; then
  if [[ "${REQUIRE}" -eq 1 ]]; then
    echo "FAIL health HTTP ${code}"
    exit 1
  fi
  echo "SKIP: analytics-runtime not up (${code})"
  echo "  bash scripts/demo/start-analytics-sidecar-host.sh --jupyter"
  echo "  or: docker compose -f deploy/dev/docker-compose.yml up -d --build aos-dev-analytics"
  exit 0
fi

eng="$(python3 -c "import json; print(json.load(open('/tmp/aos-jupy-health.json')).get('engine',''))" 2>/dev/null || true)"
echo "OK health engine=${eng}"
if [[ "${eng}" != "jupyter-server" ]]; then
  if [[ "${REQUIRE}" -eq 1 ]]; then
    echo "FAIL expected engine=jupyter-server, got ${eng}"
    exit 1
  fi
  echo "WARN not jupyter-server yet (shaped or pending) — continue to nbclient if possible"
fi

if ! python3 -c "import nbclient, nbformat" 2>/dev/null; then
  echo "SKIP nbclient not installed (pip install -r deploy/dev/analytics-runtime/requirements-jupyter.txt)"
  exit 0
fi
if [[ ! -f "${NB}" ]]; then
  echo "SKIP missing ${NB}"
  exit 0
fi

export AOS_SMOKE_NB="${NB}"

python3 - <<PY
import nbformat
from nbclient import NotebookClient
from pathlib import Path
import os
path = Path(os.environ["AOS_SMOKE_NB"])
nb = nbformat.read(path.open(encoding="utf-8"), as_version=4)
client = NotebookClient(nb, timeout=60, kernel_name="python3")
client.execute()
outs = []
for cell in nb.cells:
    if cell.get("cell_type") != "code":
        continue
    for o in cell.get("outputs") or []:
        if o.get("output_type") == "stream":
            outs.append("".join(o.get("text") or []))
text = "".join(outs)
assert "2" in text, text
print("OK nbclient aos_smoke.ipynb →", text.strip()[:80])
PY

echo "smoke-jupyter-sidecar OK"
