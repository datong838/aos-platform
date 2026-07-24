#!/usr/bin/env bash
# 62 / 153 / 162 · Ferry large-image onsite packer (macOS/Linux). Parallel to pack-ferry-images-onsite.ps1.
# Does NOT push multi-GB blobs through aos-api export base64.
# Default sign = HMAC (cosign-dev-hmac). Opt-in: --sign-mode cosign (scheme 162).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MANIFEST="${ROOT}/deploy/ferry/customer-images.example.json"
OUT_DIR="${ROOT}/deploy/dev/_ferry_onsite"
HMAC_SECRET="${AOS_FERRY_HMAC_SECRET:-aos_dev_ferry_hmac_change_me}"
SKOPEO_IMAGE="${AOS_FERRY_SKOPEO_IMAGE:-quay.io/skopeo/stable:v1.16.1}"
TIMEOUT_SEC="${AOS_FERRY_SKOPEO_TIMEOUT:-900}"
SIGN_MODE="${AOS_FERRY_ONSITE_SIGN_MODE:-hmac}"
COSIGN_KEY="${AOS_FERRY_COSIGN_KEY:-${ROOT}/deploy/dev/cosign/cosign.key}"
COSIGN_IMAGE="${AOS_FERRY_COSIGN_IMAGE:-ghcr.io/sigstore/cosign/cosign:v2.4.1}"
PULL=0
SKIP_ARCHIVE=0

usage() {
  cat <<'EOF'
Usage: bash scripts/ci/pack-ferry-images-onsite.sh [options]

  --manifest PATH
  --out-dir PATH
  --hmac-secret STR     or AOS_FERRY_HMAC_SECRET
  --sign-mode hmac|cosign   default hmac (162); cosign requires key + CLI/docker
  --cosign-key PATH     or AOS_FERRY_COSIGN_KEY
  --pull                docker pull missing refs
  --skip-archive        digest-only images.json + sig (no tar)
  --timeout SEC         skopeo docker-run timeout
  --help

See docs/palantier/20_tech/62 · scheme 153 / 162
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest) MANIFEST="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --hmac-secret) HMAC_SECRET="$2"; shift 2 ;;
    --sign-mode) SIGN_MODE="$2"; shift 2 ;;
    --cosign-key) COSIGN_KEY="$2"; shift 2 ;;
    --pull) PULL=1; shift ;;
    --skip-archive) SKIP_ARCHIVE=1; shift ;;
    --timeout) TIMEOUT_SEC="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown: $1"; usage; exit 2 ;;
  esac
done

case "${SIGN_MODE}" in
  hmac|cosign) ;;
  *) echo "FAIL --sign-mode must be hmac|cosign (got ${SIGN_MODE})"; exit 2 ;;
esac

echo "pack-ferry-images-onsite.sh (scheme 62/153/162) sign=${SIGN_MODE}"
if [[ ! -f "${MANIFEST}" ]]; then
  echo "FAIL Manifest not found: ${MANIFEST}"
  exit 1
fi

need_py() {
  command -v python3 >/dev/null 2>&1 || { echo "FAIL python3 required"; exit 1; }
}
need_py

HAS_DOCKER=0
HAS_SKOPEO=0
if command -v docker >/dev/null 2>&1 && docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
  HAS_DOCKER=1
fi
if command -v skopeo >/dev/null 2>&1; then
  HAS_SKOPEO=1
fi

if [[ "${HAS_DOCKER}" -eq 0 && "${HAS_SKOPEO}" -eq 0 && "${SKIP_ARCHIVE}" -eq 0 ]]; then
  echo "SKIP: neither docker nor skopeo (digest-only pass with --skip-archive)"
  echo "  or: docker pull <refs> then re-run"
  exit 0
fi

mkdir -p "${OUT_DIR}/archives"

export MANIFEST OUT_DIR HMAC_SECRET SKOPEO_IMAGE TIMEOUT_SEC PULL SKIP_ARCHIVE HAS_DOCKER HAS_SKOPEO
export SIGN_MODE COSIGN_KEY COSIGN_IMAGE
python3 <<'PY'
import hashlib, hmac, json, os, re, subprocess, time
from pathlib import Path

manifest = Path(os.environ["MANIFEST"])
out_dir = Path(os.environ["OUT_DIR"])
arch_dir = out_dir / "archives"
secret = os.environ["HMAC_SECRET"].encode()
skopeo_image = os.environ["SKOPEO_IMAGE"]
timeout = int(os.environ["TIMEOUT_SEC"])
pull = os.environ["PULL"] == "1"
skip_archive = os.environ["SKIP_ARCHIVE"] == "1"
has_docker = os.environ["HAS_DOCKER"] == "1"
has_skopeo = os.environ["HAS_SKOPEO"] == "1"
sign_mode = (os.environ.get("SIGN_MODE") or "hmac").strip().lower()
cosign_key = Path(os.environ.get("COSIGN_KEY") or "")
cosign_image = os.environ.get("COSIGN_IMAGE") or "ghcr.io/sigstore/cosign/cosign:v2.4.1"

doc = json.loads(manifest.read_text())
items = doc.get("images") or []
if not items:
    raise SystemExit("manifest.images missing")


def safe_name(ref: str) -> str:
    s = re.sub(r"[\\/:]", "_", ref)
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s)
    return (s[:120] if len(s) > 120 else s) + ".tar"


def docker_digest(ref: str) -> tuple[str, str]:
    if has_docker:
        p = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{json .RepoDigests}}|{{.Id}}", ref],
            capture_output=True, text=True,
        )
        if p.returncode == 0 and p.stdout:
            m = re.search(r"sha256:[a-f0-9]{64}", p.stdout)
            if m:
                return m.group(0), "docker-inspect"
    h = hashlib.sha256(ref.encode()).hexdigest()
    return f"sha256:{h}", "synthetic"


def image_local(ref: str) -> bool:
    if not has_docker:
        return False
    p = subprocess.run(["docker", "images", "-q", ref], capture_output=True, text=True)
    return bool(p.stdout.strip())


def try_archive(ref: str, tar_path: Path) -> bool:
    if tar_path.exists():
        tar_path.unlink()
    if has_skopeo:
        for src in (f"docker-daemon:{ref}", f"docker://{ref}"):
            p = subprocess.run(["skopeo", "copy", src, f"docker-archive:{tar_path}"], capture_output=True)
            if p.returncode == 0 and tar_path.exists() and tar_path.stat().st_size > 0:
                return True
    if has_docker:
        cmd = [
            "docker", "run", "--rm",
            "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "-v", f"{arch_dir.resolve()}:/out",
            skopeo_image,
            "copy", f"docker-daemon:{ref}", f"docker-archive:/out/{tar_path.name}",
        ]
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=timeout)
            if p.returncode == 0 and tar_path.exists() and tar_path.stat().st_size > 0:
                return True
        except subprocess.TimeoutExpired:
            print(f"WARN skopeo timeout {timeout}s for {ref}")
    return False

images = []
skopeo_used = False
for item in items:
    ref = str(item.get("ref") or "")
    if not ref:
        continue
    want_archive = bool(item.get("archive"))
    max_gib = float(item.get("maxGiB") or 0)

    if has_docker and not image_local(ref):
        if pull:
            print(f"pull {ref} ...")
            p = subprocess.run(["docker", "pull", ref])
            if p.returncode != 0:
                print(f"WARN pull failed: {ref} — skip")
                continue
        else:
            print(f"WARN image not local: {ref} (use --pull or docker pull)")
            if want_archive and not skip_archive:
                continue

    digest, source = docker_digest(ref)
    archive_rel = None
    if want_archive and not skip_archive:
        tar_name = safe_name(ref)
        tar_path = arch_dir / tar_name
        print(f"archive {ref} -> {tar_name}")
        if try_archive(ref, tar_path):
            nbytes = tar_path.stat().st_size
            if max_gib > 0 and (nbytes / (1024**3)) > max_gib:
                print(f"WARN archive {ref} size {nbytes/(1024**3):.2f}GiB > maxGiB={max_gib}")
            archive_rel = f"artifacts/archives/{tar_name}"
            skopeo_used = True
            print(f"  OK bytes={nbytes}")
        else:
            print(f"WARN archive failed: {ref}")

    images.append({
        "ref": ref,
        "digest": digest,
        "digestSource": source,
        "archive": archive_rel,
    })

cosign_mode = "cosign" if sign_mode == "cosign" else "cosign-dev-hmac"
images_doc = {
    "version": "1",
    "skopeoUsed": skopeo_used,
    "onsitePack": True,
    "cosignMode": cosign_mode,
    "images": images,
}
images_path = out_dir / "images.json"
body = json.dumps(images_doc, indent=2, ensure_ascii=False).encode("utf-8")
images_path.write_bytes(body)

sig_path = out_dir / "images.sig"
if sign_mode == "cosign":
    if not cosign_key.is_file():
        raise SystemExit(f"FAIL --sign-mode cosign but key missing: {cosign_key}")
    has_cosign = subprocess.run(["bash", "-lc", "command -v cosign"], capture_output=True).returncode == 0
    export_pw = {**os.environ, "COSIGN_PASSWORD": ""}
    if has_cosign:
        p = subprocess.run(
            ["cosign", "sign-blob", "--yes", "--key", str(cosign_key), "--output-signature", str(sig_path), str(images_path)],
            env=export_pw, capture_output=True, text=True,
        )
        if p.returncode != 0:
            raise SystemExit(f"FAIL cosign sign-blob: {p.stderr or p.stdout}")
    elif has_docker:
        key_dir = cosign_key.parent.resolve()
        p = subprocess.run(
            [
                "docker", "run", "--rm", "-e", "COSIGN_PASSWORD=",
                "-v", f"{out_dir.resolve()}:/work",
                "-v", f"{key_dir}:/keys:ro",
                cosign_image,
                "sign-blob", "--yes", "--key", f"/keys/{cosign_key.name}",
                "--output-signature", "/work/images.sig", "/work/images.json",
            ],
            env=export_pw, capture_output=True, text=True,
        )
        if p.returncode != 0 or not sig_path.is_file():
            raise SystemExit(f"FAIL docker cosign sign-blob: {p.stderr or p.stdout}")
    else:
        raise SystemExit("FAIL --sign-mode cosign needs cosign CLI or docker")
    print(f"OK cosign signed images.sig via {'path' if has_cosign else 'docker'}")
else:
    sig = hmac.new(secret, b"ferry-images:" + body, hashlib.sha256).hexdigest()
    sig_path.write_text(sig, encoding="ascii")

readme = f"""# Ferry onsite image pack (scheme 62 / 153 / 162)

- Manifest: {manifest}
- images.json + images.sig (cosignMode={cosign_mode})
- archives/: docker-archive tar files (keep beside ferry-bundle; do not base64 via API)

Env for aos-api (optional digest-only):
  AOS_FERRY_IMAGES_MANIFEST={manifest}
  AOS_FERRY_SKOPEO=0
  AOS_FERRY_SKOPEO_MAX_MIB=64
"""
(out_dir / "README-ONSITE.md").write_text(readme, encoding="utf-8")
print(f"OK wrote {out_dir} (images={len(images)} skopeoUsed={skopeo_used} cosignMode={cosign_mode})")
PY
