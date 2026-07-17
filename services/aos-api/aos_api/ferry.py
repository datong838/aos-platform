"""T5.6 Ferry — signed tar.gz + image layer (schemes 53/56/59/62/64).

Manifest: HMAC-SHA256 (A6). Images: cosign blob verify when binary/docker present,
else cosign-dev-hmac over artifacts/images.json.
Skopeo archive when AOS_FERRY_SKOPEO=1: PATH skopeo or Docker image fallback.
Scheme 62: customer manifest + timeout + API embed size gate.
Scheme 64: real cosign keychain (PATH|docker) + COSIGN_REQUIRED; Full Channel still deferred.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import uuid
from typing import Any

from aos_api.env_load import load_dotenv
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.ferry")
load_dotenv()

MANIFEST_NAME = "manifest.json"
ASSETS_NAME = "assets/payload.json"
CHECKSUMS_NAME = "checksums.sha256"
SIGNATURE_NAME = "signature.sig"
IMAGES_JSON = "artifacts/images.json"
IMAGES_SIG = "artifacts/images.sig"
DEFAULT_IMAGES = (
    "postgres:16-alpine",
    "minio/minio:RELEASE.2025-04-22T22-12-26Z",
)
DEFAULT_SKOPEO_REFS = ("alpine:latest",)
SKOPEO_IMAGE_DEFAULT = "quay.io/skopeo/stable:v1.16.1"
COSIGN_IMAGE_DEFAULT = "ghcr.io/sigstore/cosign/cosign:v2.4.1"
DEFAULT_SKOPEO_TIMEOUT_PATH = 600
DEFAULT_SKOPEO_TIMEOUT_DOCKER = 900
DEFAULT_SKOPEO_MAX_MIB = 64


def _secret() -> bytes:
    raw = (os.environ.get("AOS_FERRY_HMAC_SECRET") or "aos_dev_ferry_hmac_change_me").strip()
    return raw.encode("utf-8")


def _tool_on_path(name: str) -> bool:
    return bool(shutil.which(name))


def _skopeo_timeout(kind: str) -> int:
    raw = (os.environ.get("AOS_FERRY_SKOPEO_TIMEOUT") or "").strip()
    if raw.isdigit():
        return max(30, int(raw))
    if kind == "path":
        return DEFAULT_SKOPEO_TIMEOUT_PATH
    return DEFAULT_SKOPEO_TIMEOUT_DOCKER


def _skopeo_max_embed_bytes() -> int:
    raw = (os.environ.get("AOS_FERRY_SKOPEO_MAX_MIB") or str(DEFAULT_SKOPEO_MAX_MIB)).strip()
    try:
        mib = int(raw)
    except ValueError:
        mib = DEFAULT_SKOPEO_MAX_MIB
    return max(1, mib) * 1024 * 1024


def load_customer_images_manifest(path: str | None = None) -> dict[str, Any] | None:
    """Load scheme-62 customer images JSON. Returns None if unset/missing."""
    p = (path or os.environ.get("AOS_FERRY_IMAGES_MANIFEST") or "").strip()
    if not p:
        return None
    if not os.path.isfile(p):
        log.warning("ferry_images_manifest_missing path=%s", p)
        return None
    with open(p, encoding="utf-8") as f:
        doc = json.load(f)
    if not isinstance(doc, dict):
        raise ValueError("manifest must be object")
    images = doc.get("images")
    if not isinstance(images, list):
        raise ValueError("manifest.images must be list")
    return doc


def refs_from_manifest(doc: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (all_refs, archive_refs) from customer manifest."""
    all_refs: list[str] = []
    archive_refs: list[str] = []
    for item in doc.get("images") or []:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or "").strip()
        if not ref:
            continue
        all_refs.append(ref)
        if item.get("archive") is True:
            archive_refs.append(ref)
    # preserve order, dedupe
    def _dedupe(xs: list[str]) -> list[str]:
        return list(dict.fromkeys(xs))

    return _dedupe(all_refs), _dedupe(archive_refs)


def _skopeo_enabled() -> bool:
    return os.environ.get("AOS_FERRY_SKOPEO", "").strip() in {"1", "true", "TRUE", "yes"}


def _skopeo_image() -> str:
    return (os.environ.get("AOS_FERRY_SKOPEO_IMAGE") or SKOPEO_IMAGE_DEFAULT).strip()


def probe_docker() -> bool:
    if not _tool_on_path("docker"):
        return False
    try:
        proc = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def probe_skopeo() -> bool:
    """True if PATH skopeo or docker+skopeo image path usable."""
    return _tool_on_path("skopeo") or probe_docker()


def skopeo_mode() -> str:
    if _tool_on_path("skopeo"):
        return "path"
    if probe_docker():
        return "docker"
    return "none"


def probe_cosign() -> bool:
    return cosign_cli_mode() != "none"


def cosign_cli_mode() -> str:
    """path | docker | none — scheme 64."""
    if _tool_on_path("cosign"):
        return "path"
    if probe_docker():
        return "docker"
    return "none"


def _cosign_image() -> str:
    return (os.environ.get("AOS_FERRY_COSIGN_IMAGE") or COSIGN_IMAGE_DEFAULT).strip()


def _cosign_required() -> bool:
    return (os.environ.get("AOS_FERRY_COSIGN_REQUIRED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _cosign_key_path() -> str:
    return (os.environ.get("AOS_FERRY_COSIGN_KEY") or "").strip()


def _cosign_pub_path() -> str:
    return (os.environ.get("AOS_FERRY_COSIGN_PUB") or "").strip()


def _cosign_key_configured() -> bool:
    p = _cosign_key_path()
    return bool(p and os.path.isfile(p))


def _cosign_pub_configured() -> bool:
    p = _cosign_pub_path()
    return bool(p and os.path.isfile(p))


def ferry_status_payload() -> dict[str, Any]:
    mode = skopeo_mode()
    enabled = _skopeo_enabled()
    manifest = (os.environ.get("AOS_FERRY_IMAGES_MANIFEST") or "").strip() or None
    return {
        "deferred": False,
        "mode": "mvp-hmac+images",
        "reason": None,
        "message": (
            "Ferry: signed tar.gz + artifacts/images (HMAC manifest; "
            "cosign PATH|docker or cosign-dev-hmac; skopeo archive opt-in; "
            "large images onsite scheme 62; Full Channel deferred scheme 64)"
        ),
        "channels": ["lite", "dev", "staging", "stable"],
        "fullChannelDeferred": True,
        "fullSpokeRuntimeDeferred": True,
        "channelCatalogReady": True,
        "exportImport": "200",
        "skopeo": mode != "none",
        "skopeoMode": mode,
        "cosign": probe_cosign(),
        "cosignCliMode": cosign_cli_mode(),
        "cosignKeyConfigured": _cosign_key_configured(),
        "cosignPubConfigured": _cosign_pub_configured(),
        "cosignRequired": _cosign_required(),
        "skopeoArchiveEnabled": bool(enabled and mode != "none"),
        "skopeoRefs": list(_skopeo_refs()),
        "skopeoTimeoutSec": _skopeo_timeout("docker"),
        "skopeoMaxEmbedMiB": _skopeo_max_embed_bytes() // (1024 * 1024),
        "imagesManifest": manifest,
        "imageFerry": "digest+sig",
        "planRef": "T5.6 / T09 §9.1 / schemes 56/59/62/64",
    }


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sign_manifest(manifest_bytes: bytes) -> str:
    return hmac.new(_secret(), manifest_bytes, hashlib.sha256).hexdigest()


def _verify_manifest(manifest_bytes: bytes, signature_hex: str) -> bool:
    expected = _sign_manifest(manifest_bytes)
    return hmac.compare_digest(expected, (signature_hex or "").strip())


def _sign_images_dev(images_bytes: bytes) -> str:
    return hmac.new(_secret(), b"ferry-images:" + images_bytes, hashlib.sha256).hexdigest()


def _verify_images_dev(images_bytes: bytes, signature_hex: str) -> bool:
    expected = _sign_images_dev(images_bytes)
    return hmac.compare_digest(expected, (signature_hex or "").strip())


def _image_refs() -> list[str]:
    doc = load_customer_images_manifest()
    if doc is not None:
        all_refs, _ = refs_from_manifest(doc)
        if all_refs:
            return all_refs
    raw = (os.environ.get("AOS_FERRY_IMAGES") or "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return list(DEFAULT_IMAGES)


def _skopeo_refs() -> list[str]:
    """Refs to attempt docker-archive (default small alpine for drill)."""
    doc = load_customer_images_manifest()
    if doc is not None:
        _, archive_refs = refs_from_manifest(doc)
        if archive_refs:
            return archive_refs
    raw = (os.environ.get("AOS_FERRY_SKOPEO_REFS") or "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return list(DEFAULT_SKOPEO_REFS)


def _safe_archive_name(ref: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", ref.replace("/", "_").replace(":", "_"))
    return f"artifacts/archives/{s[:120]}.tar"


def _to_docker_bind(win_path: str) -> str:
    """Windows path → /mnt/<drive>/... for WSL-routed docker.cmd."""
    full = os.path.abspath(win_path)
    if re.match(r"^[A-Za-z]:", full):
        drive = full[0].lower()
        rest = full[2:].replace("\\", "/")
        return f"/mnt/{drive}{rest}"
    return full.replace("\\", "/")


def _docker_digest(ref: str) -> tuple[str, str]:
    """Return (digest, source). Prefer docker inspect; else synthetic."""
    docker = shutil.which("docker")
    if docker:
        try:
            out = subprocess.run(
                [
                    docker,
                    "image",
                    "inspect",
                    "--format",
                    "{{json .RepoDigests}}|{{.Id}}",
                    ref,
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if out.returncode == 0 and out.stdout.strip():
                line = out.stdout.strip()
                digests_part, _, id_part = line.partition("|")
                m = re.search(r"sha256:[a-f0-9]{64}", digests_part)
                if m:
                    return m.group(0), "docker-inspect"
                m2 = re.search(r"sha256:[a-f0-9]{64}", id_part)
                if m2:
                    return m2.group(0), "docker-inspect-id"
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.warning("docker_inspect_failed ref=%s err=%s", ref, exc)
    synth = "sha256:" + _sha256_bytes(ref.encode("utf-8"))
    return synth, "synthetic"


def _skopeo_copy_path(ref: str, dest_file: str) -> bool:
    skopeo = shutil.which("skopeo")
    if not skopeo:
        return False
    cmds = [
        [skopeo, "copy", f"docker-daemon:{ref}", f"docker-archive:{dest_file}"],
        [skopeo, "copy", f"docker://{ref}", f"docker-archive:{dest_file}"],
    ]
    for cmd in cmds:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_skopeo_timeout("path"),
            check=False,
        )
        if proc.returncode == 0 and os.path.isfile(dest_file):
            return True
        log.info("skopeo_path_try failed code=%s", proc.returncode)
    return False


def _skopeo_copy_docker(ref: str, dest_file: str) -> bool:
    if not probe_docker():
        return False
    out_dir = os.path.dirname(dest_file)
    out_name = os.path.basename(dest_file)
    os.makedirs(out_dir, exist_ok=True)
    bind = _to_docker_bind(out_dir)
    image = _skopeo_image()
    # Prefer local daemon (no registry); then registry pull
    attempts = [
        ["copy", f"docker-daemon:{ref}", f"docker-archive:/out/{out_name}"],
        ["copy", f"docker://{ref}", f"docker-archive:/out/{out_name}"],
    ]
    for args in attempts:
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",
            "-v",
            f"{bind}:/out",
            image,
            *args,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_skopeo_timeout("docker"),
            check=False,
        )
        if proc.returncode == 0 and os.path.isfile(dest_file):
            return True
        log.info(
            "skopeo_docker_try failed ref=%s code=%s err=%s",
            ref,
            proc.returncode,
            (proc.stderr or "")[-200:],
        )
    return False


def _try_skopeo_archive(ref: str, archive_rel: str, work: dict[str, bytes]) -> str | None:
    if not _skopeo_enabled():
        return None
    if skopeo_mode() == "none":
        return None
    if ref not in set(_skopeo_refs()):
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="aos-ferry-skopeo-") as td:
            dest = os.path.join(td, "img.tar")
            ok = False
            if skopeo_mode() == "path":
                ok = _skopeo_copy_path(ref, dest)
            if not ok:
                ok = _skopeo_copy_docker(ref, dest)
            if not ok:
                return None
            size = os.path.getsize(dest)
            max_b = _skopeo_max_embed_bytes()
            if size > max_b:
                log.warning(
                    "skopeo_archive_skip_embed ref=%s bytes=%s max=%s (use pack-ferry-images-onsite.ps1)",
                    ref,
                    size,
                    max_b,
                )
                return None
            with open(dest, "rb") as f:
                work[archive_rel] = f.read()
            log.info(
                "skopeo_archive ref=%s bytes=%s mode=%s",
                ref,
                len(work[archive_rel]),
                skopeo_mode(),
            )
            return archive_rel
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("skopeo_archive_failed ref=%s err=%s", ref, exc)
        return None


def _cosign_sign_blob(data: bytes) -> tuple[str, str] | None:
    """Return (sig_b64, mode) if cosign works; else None."""
    cli = cosign_cli_mode()
    if cli == "none":
        return None
    key = _cosign_key_path()
    if not key or not os.path.isfile(key):
        log.info("cosign_no_AOS_FERRY_COSIGN_KEY; using cosign-dev-hmac")
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="aos-cosign-") as td:
            blob = os.path.join(td, "images.json")
            sigp = os.path.join(td, "images.sig")
            with open(blob, "wb") as f:
                f.write(data)
            env = {**os.environ, "COSIGN_PASSWORD": os.environ.get("COSIGN_PASSWORD", "")}
            if cli == "path":
                cosign = shutil.which("cosign")
                if not cosign:
                    return None
                proc = subprocess.run(
                    [
                        cosign,
                        "sign-blob",
                        "--yes",
                        "--key",
                        key,
                        "--output-signature",
                        sigp,
                        blob,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                    env=env,
                )
            else:
                bind_work = _to_docker_bind(td)
                key_dir = os.path.dirname(os.path.abspath(key))
                key_name = os.path.basename(key)
                bind_key = _to_docker_bind(key_dir)
                proc = subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "-e",
                        "COSIGN_PASSWORD=",
                        "-v",
                        f"{bind_work}:/work",
                        "-v",
                        f"{bind_key}:/keys:ro",
                        _cosign_image(),
                        "sign-blob",
                        "--yes",
                        "--key",
                        f"/keys/{key_name}",
                        "--output-signature",
                        "/work/images.sig",
                        "/work/images.json",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
            if proc.returncode != 0 or not os.path.isfile(sigp):
                log.warning(
                    "cosign_sign_blob_failed mode=%s code=%s err=%s",
                    cli,
                    proc.returncode,
                    (proc.stderr or "")[-200:],
                )
                return None
            with open(sigp, "rb") as f:
                raw = f.read()
            return base64.b64encode(raw).decode("ascii"), "cosign"
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("cosign_sign_failed err=%s", exc)
        return None


def _cosign_verify_blob(data: bytes, sig_b64: str) -> bool | None:
    """True/False if cosign used; None if skip to dev verify."""
    cli = cosign_cli_mode()
    if cli == "none":
        return None
    pub = _cosign_pub_path()
    if not pub or not os.path.isfile(pub):
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="aos-cosign-v-") as td:
            blob = os.path.join(td, "images.json")
            sigp = os.path.join(td, "images.sig")
            with open(blob, "wb") as f:
                f.write(data)
            with open(sigp, "wb") as f:
                f.write(base64.b64decode(sig_b64))
            if cli == "path":
                cosign = shutil.which("cosign")
                if not cosign:
                    return None
                proc = subprocess.run(
                    [cosign, "verify-blob", "--key", pub, "--signature", sigp, blob],
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                )
            else:
                bind_work = _to_docker_bind(td)
                pub_dir = os.path.dirname(os.path.abspath(pub))
                pub_name = os.path.basename(pub)
                bind_pub = _to_docker_bind(pub_dir)
                proc = subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "-v",
                        f"{bind_work}:/work",
                        "-v",
                        f"{bind_pub}:/keys:ro",
                        _cosign_image(),
                        "verify-blob",
                        "--key",
                        f"/keys/{pub_name}",
                        "--signature",
                        "/work/images.sig",
                        "/work/images.json",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
            return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        log.warning("cosign_verify_failed err=%s", exc)
        return False


def build_images_artifact() -> tuple[bytes, bytes, dict[str, Any], dict[str, bytes]]:
    """Build images.json + sig + optional archive members."""
    extra: dict[str, bytes] = {}
    entries: list[dict[str, Any]] = []
    skopeo_used = False
    refs = list(dict.fromkeys([*_image_refs(), *_skopeo_refs()]))
    for ref in refs:
        digest, src = _docker_digest(ref)
        archive_rel = _safe_archive_name(ref)
        archived = _try_skopeo_archive(ref, archive_rel, extra)
        if archived:
            skopeo_used = True
        entries.append(
            {
                "ref": ref,
                "digest": digest,
                "digestSource": src,
                "archive": archived,
            }
        )

    cosign_mode = "cosign-dev-hmac"
    images_doc: dict[str, Any] = {
        "version": "1",
        "cosignMode": cosign_mode,
        "skopeoUsed": skopeo_used,
        "images": entries,
    }
    images_bytes = json.dumps(images_doc, ensure_ascii=False, sort_keys=True).encode("utf-8")
    sig_bytes = (_sign_images_dev(images_bytes) + "\n").encode("utf-8")

    # Prefer real cosign when key configured
    images_doc["cosignMode"] = "cosign"
    candidate = json.dumps(images_doc, ensure_ascii=False, sort_keys=True).encode("utf-8")
    cosign_try = _cosign_sign_blob(candidate)
    if cosign_try:
        sig_text, _ = cosign_try
        images_bytes = candidate
        sig_bytes = (sig_text + "\n").encode("utf-8")
        cosign_mode = "cosign"
    else:
        if _cosign_required():
            raise ApiError(
                code="FERRY_COSIGN_REQUIRED",
                message=(
                    "AOS_FERRY_COSIGN_REQUIRED=1 but cosign sign-blob unavailable "
                    "(need AOS_FERRY_COSIGN_KEY + PATH/docker cosign); see scheme 64"
                ),
                status_code=503,
            )
        images_doc["cosignMode"] = "cosign-dev-hmac"
        images_bytes = json.dumps(images_doc, ensure_ascii=False, sort_keys=True).encode("utf-8")
        sig_bytes = (_sign_images_dev(images_bytes) + "\n").encode("utf-8")
        cosign_mode = "cosign-dev-hmac"

    images_doc["cosignMode"] = cosign_mode
    return images_bytes, sig_bytes, images_doc, extra


def build_bundle(
    *,
    env: str = "dev",
    channel: str = "lite",
    org_id: str = "dev-org",
    contents: list[str] | None = None,
    include_images: bool = True,
) -> dict[str, Any]:
    """Pack ferry tar.gz; return metadata + base64."""
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    bundle_id = f"ferry-{uuid.uuid4().hex[:10]}"
    filename = f"ferry-bundle-{env}-{ts}.tar.gz"
    payload = {
        "bundleId": bundle_id,
        "platformVersion": "0.3.0-dev",
        "contents": contents or ["WorkOrder", "CloseWorkOrder", "mod-ops-inbox"],
        "orgId": org_id,
        "note": "asset snapshot + optional image layer (scheme 56)",
    }
    payload_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    payload_sha = _sha256_bytes(payload_bytes)

    artifacts_meta: list[dict[str, Any]] = [
        {"path": ASSETS_NAME, "kind": "asset-snapshot", "sha256": payload_sha},
    ]
    extra_files: dict[str, bytes] = {}
    images_doc = None
    mode = "mvp-hmac"

    if include_images:
        images_bytes, images_sig, images_doc, archives = build_images_artifact()
        extra_files[IMAGES_JSON] = images_bytes
        extra_files[IMAGES_SIG] = images_sig
        extra_files.update(archives)
        artifacts_meta.append(
            {
                "path": IMAGES_JSON,
                "kind": "image-list",
                "sha256": _sha256_bytes(images_bytes),
                "cosignMode": images_doc.get("cosignMode"),
            }
        )
        artifacts_meta.append(
            {
                "path": IMAGES_SIG,
                "kind": "image-signature",
                "sha256": _sha256_bytes(images_sig),
            }
        )
        for path, data in archives.items():
            artifacts_meta.append(
                {"path": path, "kind": "image-archive", "sha256": _sha256_bytes(data)}
            )
        mode = "mvp-hmac+images"

    manifest = {
        "version": "1.1" if include_images else "1.0",
        "bundleId": bundle_id,
        "env": env,
        "channel": channel,
        "orgId": org_id,
        "createdAt": ts,
        "artifacts": artifacts_meta,
        "signatures": [{"alg": "HMAC-SHA256", "of": MANIFEST_NAME}],
        "contentSha256": payload_sha,
        "includeImages": include_images,
    }
    if images_doc is not None:
        manifest["imageCosignMode"] = images_doc.get("cosignMode")
        manifest["skopeoUsed"] = images_doc.get("skopeoUsed")

    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
    sig = _sign_manifest(manifest_bytes)

    checksum_lines = [
        f"{_sha256_bytes(manifest_bytes)}  {MANIFEST_NAME}",
        f"{payload_sha}  {ASSETS_NAME}",
    ]
    for path, data in sorted(extra_files.items()):
        checksum_lines.append(f"{_sha256_bytes(data)}  {path}")
    checksums_bytes = ("\n".join(checksum_lines) + "\n").encode("utf-8")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:

        def add(name: str, data: bytes) -> None:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        add(MANIFEST_NAME, manifest_bytes)
        add(ASSETS_NAME, payload_bytes)
        for path, data in extra_files.items():
            add(path, data)
        add(CHECKSUMS_NAME, checksums_bytes)
        add(SIGNATURE_NAME, (sig + "\n").encode("utf-8"))

    raw = buf.getvalue()
    import base64

    log.info(
        "ferry_export bundleId=%s bytes=%s mode=%s images=%s",
        bundle_id,
        len(raw),
        mode,
        include_images,
    )
    return {
        "bundleId": bundle_id,
        "filename": filename,
        "contentBase64": base64.b64encode(raw).decode("ascii"),
        "sizeBytes": len(raw),
        "manifest": manifest,
        "mode": mode,
        "images": images_doc,
        "skopeo": probe_skopeo(),
        "cosign": probe_cosign(),
    }


def _read_tar_members(raw: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            f = tar.extractfile(m)
            if f is None:
                continue
            out[m.name] = f.read()
    return out


def _verify_images_layer(members: dict[str, bytes]) -> dict[str, Any] | None:
    if IMAGES_JSON not in members:
        return None
    images_bytes = members[IMAGES_JSON]
    if IMAGES_SIG not in members:
        raise ApiError(
            code="FERRY_IMAGE_SIGNATURE_MISSING",
            message="artifacts/images.sig missing; refuse import (scheme 56)",
            status_code=403,
        )
    sig_raw = members[IMAGES_SIG].decode("utf-8").strip()
    images_doc = json.loads(images_bytes.decode("utf-8"))
    mode = (images_doc.get("cosignMode") or "cosign-dev-hmac").strip()

    if mode == "cosign":
        verified = _cosign_verify_blob(images_bytes, sig_raw)
        if verified is True:
            return images_doc
        if verified is False:
            raise ApiError(
                code="FERRY_IMAGE_SIGNATURE_INVALID",
                message="cosign verify-blob failed for images.json",
                status_code=403,
            )
        # tool/key missing
        if _cosign_required():
            raise ApiError(
                code="FERRY_COSIGN_REQUIRED",
                message="cosignMode=cosign but verify unavailable (need PUB + cosign)",
                status_code=403,
            )
        # fall through to dev if cosign not configured for verify

    if _cosign_required() and mode != "cosign":
        raise ApiError(
            code="FERRY_COSIGN_REQUIRED",
            message="AOS_FERRY_COSIGN_REQUIRED=1 rejects cosign-dev-hmac images layer",
            status_code=403,
        )

    if not _verify_images_dev(images_bytes, sig_raw):
        raise ApiError(
            code="FERRY_IMAGE_SIGNATURE_INVALID",
            message="images.json signature mismatch",
            status_code=403,
        )
    return images_doc


def import_bundle(
    *,
    content_base64: str,
    require_signature: bool = True,
) -> dict[str, Any]:
    import base64

    try:
        raw = base64.b64decode(content_base64, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise ApiError(
            code="FERRY_INVALID_BUNDLE",
            message=f"invalid base64: {exc}",
            status_code=400,
        ) from exc

    try:
        members = _read_tar_members(raw)
    except Exception as exc:  # noqa: BLE001
        raise ApiError(
            code="FERRY_INVALID_BUNDLE",
            message=f"invalid tar.gz: {exc}",
            status_code=400,
        ) from exc

    if MANIFEST_NAME not in members:
        raise ApiError(
            code="FERRY_INVALID_BUNDLE",
            message="manifest.json missing",
            status_code=400,
        )

    manifest_bytes = members[MANIFEST_NAME]
    if require_signature:
        if SIGNATURE_NAME not in members:
            raise ApiError(
                code="FERRY_SIGNATURE_MISSING",
                message="signature.sig missing; refuse import (T09 A6)",
                status_code=403,
            )
        sig = members[SIGNATURE_NAME].decode("utf-8").strip()
        if not _verify_manifest(manifest_bytes, sig):
            raise ApiError(
                code="FERRY_SIGNATURE_INVALID",
                message="manifest signature mismatch",
                status_code=403,
            )

    if CHECKSUMS_NAME in members:
        for line in members[CHECKSUMS_NAME].decode("utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            expect_hash, path = parts[0], parts[-1]
            data = members.get(path)
            if data is None:
                raise ApiError(
                    code="FERRY_CHECKSUM_MISMATCH",
                    message=f"missing file for checksum: {path}",
                    status_code=400,
                )
            if _sha256_bytes(data) != expect_hash:
                raise ApiError(
                    code="FERRY_CHECKSUM_MISMATCH",
                    message=f"checksum failed: {path}",
                    status_code=400,
                )

    images_doc = _verify_images_layer(members)

    manifest = json.loads(manifest_bytes.decode("utf-8"))
    payload = None
    if ASSETS_NAME in members:
        payload = json.loads(members[ASSETS_NAME].decode("utf-8"))

    mode = "mvp-hmac+images" if images_doc is not None else "mvp-hmac"
    log.info("ferry_import ok bundleId=%s mode=%s", manifest.get("bundleId"), mode)
    return {
        "ok": True,
        "bundleId": manifest.get("bundleId"),
        "manifest": manifest,
        "payload": payload,
        "images": images_doc,
        "verified": True,
        "mode": mode,
    }
