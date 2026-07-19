#!/usr/bin/env bash
# 62 / 153 · Ferry large-image preflight (macOS/Linux). Parallel to probe-ferry-large-images.ps1.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MANIFEST="${ROOT}/deploy/ferry/customer-images.example.json"

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/probe-ferry-large-images.sh [--manifest PATH] [--help]

Checks customer-images manifest + optional local docker presence. No copy.
See docs/palantier/20_tech/62-Ferry大镜像现场打包策略.md · scheme 153
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest) MANIFEST="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

echo "probe-ferry-large-images.sh (scheme 62/153)"
if [[ ! -f "${MANIFEST}" ]]; then
  echo "SKIP: manifest missing ${MANIFEST}"
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL python3 required to parse JSON"
  exit 1
fi

HAS_DOCKER=0
if command -v docker >/dev/null 2>&1 && docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
  HAS_DOCKER=1
fi

if [[ "${HAS_DOCKER}" -eq 0 ]]; then
  COUNT="$(python3 -c "import json;print(len(json.load(open('${MANIFEST}')).get('images') or []))")"
  echo "SKIP: docker not available (manifest parse OK)"
  echo "  images count=${COUNT}"
  exit 0
fi

python3 - "${MANIFEST}" <<'PY'
import json, subprocess, sys
path = sys.argv[1]
doc = json.load(open(path))
images = doc.get("images") or []
archive_count = 0
missing = []
for item in images:
    ref = str(item.get("ref") or "")
    if not ref:
        continue
    arch = bool(item.get("archive"))
    if arch:
        archive_count += 1
    q = subprocess.run(["docker", "images", "-q", ref], capture_output=True, text=True)
    local = bool(q.stdout.strip())
    size_hint = "?"
    if local:
        sz = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Size}}", ref],
            capture_output=True, text=True,
        )
        try:
            mib = float(sz.stdout.strip()) / (1024 * 1024)
            size_hint = f"{mib:.1f} MiB"
        except Exception:
            pass
    else:
        missing.append(ref)
    print(f"  {ref} local={local} archive={arch} size~{size_hint} maxGiB={item.get('maxGiB')}")
print(f"archive candidates={archive_count} missing={len(missing)}")
if missing:
    print("HINT: docker pull <ref> then bash scripts/ci/pack-ferry-images-onsite.sh")
print("probe-ferry-large-images OK")
PY
