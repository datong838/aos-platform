#!/usr/bin/env python3
"""Build unsigned, locally cached ecommerce runtime candidates without publishing."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ROOT = REPOSITORY_ROOT / "bundles/candidates/ecommerce"
SDK_ROOT = REPOSITORY_ROOT / "packages/aos-extension-sdk/python/aos_extension_sdk"
API_ROOT = REPOSITORY_ROOT / "services/aos-api"
DEFAULT_CONTEXT = "colima-aos-extension"
DEFAULT_REGISTRY_PORT = 18436
BASE_IMAGE = "python:3.11-alpine"
PLATFORM = "linux/arm64"
RUNTIME_LOCK = b"aos-extension-sdk=repository-source-tree\n"
QUALIFICATION_KEY_ID = "a0v-ephemeral-candidate-qualification"
SCHEMA_REQUIREMENT_VERSION = "aos-platform-a0v-001"
SCHEMA_COMPATIBILITY_REVISION = "a0v_001"
SCHEMA_COMPATIBILITY_RELATIONS = (
    "public.asset_bundle",
    "public.asset_bundle_artifact",
    "public.asset_bundle_evidence",
    "public.asset_bundle_version",
    "public.bundle_composition",
    "public.bundle_composition_lock",
    "public.bundle_installation",
    "public.bundle_installation_revision",
    "public.extension_operation_dispatch_binding",
    "public.extension_runtime_binding",
    "public.extension_runtime_operation",
    "public.extension_runtime_resource_lease",
    "public.extension_schema_installation",
)
RUNTIME_CASES = (
    ("domain.ecommerce.core/1.3.0", "domain.ecommerce.core", "1.3.0", "ecommerce_core"),
    (
        "platform.ecommerce.niushop/1.3.0",
        "platform.ecommerce.niushop",
        "1.3.0",
        "ecommerce_niushop",
    ),
    (
        "solution.ecommerce.growth/1.7.0",
        "solution.ecommerce.growth",
        "1.7.0",
        "ecommerce_growth",
    ),
)
ALL_CASES = RUNTIME_CASES + (
    (
        "solution.ecommerce.operations-base/1.2.0",
        "solution.ecommerce.operations-base",
        "1.2.0",
        None,
    ),
)


class CandidateBuildBlocked(RuntimeError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class _ReleaseRecord:
    def __init__(
        self,
        *,
        publisher: str,
        manifest: Any,
        content_hash: str,
        signature: Any,
        status: Any,
        evidence: list[Any],
        artifacts: list[dict[str, object]],
        persisted_manifest: dict[str, object] | None = None,
    ) -> None:
        self.publisher = publisher
        self.manifest = manifest
        self.content_hash = content_hash
        self.signature = signature
        self.status = status
        self.evidence = evidence
        self.artifacts = artifacts
        self.persisted_manifest = persisted_manifest


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = str(path.relative_to(root))
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        raw = path.read_bytes()
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(str(len(raw)).encode("ascii") + b"\0")
        digest.update(raw)
    return "sha256:" + digest.hexdigest()


def _load_manifest(path: Path) -> dict[str, Any]:
    value = yaml.safe_load((path / "bundle.yaml").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CandidateBuildBlocked("MANIFEST_INVALID", str(path))
    return value


def _runtime_registration(path: Path, package: str) -> tuple[tuple[str, str, str, str], ...]:
    entrypoint = path / "backend" / package / "__init__.py"
    if not entrypoint.is_file():
        raise CandidateBuildBlocked("RUNTIME_ENTRYPOINT_MISSING", str(entrypoint))
    spec = importlib.util.spec_from_file_location(f"candidate_build_{package}", entrypoint)
    if spec is None or spec.loader is None:
        raise CandidateBuildBlocked("RUNTIME_ENTRYPOINT_INVALID", str(entrypoint))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    registration = module.register(object())
    contributions = registration.get("contributions") if isinstance(registration, dict) else None
    if not isinstance(contributions, list):
        raise CandidateBuildBlocked("REGISTRATION_INVALID", package)
    declared = (_load_manifest(path).get("spec") or {}).get("contributions") or []
    def identities(items):
        return sorted(json.dumps(item, sort_keys=True, separators=(",", ":")) for item in items)
    if identities(contributions) != identities(declared):
        raise CandidateBuildBlocked("MANIFEST_RUNTIME_API_MISMATCH", package)
    if len(set(identities(contributions))) != len(contributions):
        raise CandidateBuildBlocked("REGISTRATION_INVALID", package)
    contributions = [item for item in contributions if isinstance(item, dict) and item.get("kind") == "api"]
    operations = tuple(
        (item.get("operationId"), item.get("method"), item.get("path"), item.get("mode"))
        for item in contributions if isinstance(item, dict)
    )
    if (
        len(operations) != len(contributions)
        or any(
            not all(isinstance(value, str) and value for value in item)
            or item[1] != item[1].upper() or item[2].endswith("/") or item[3] != "exclusive"
            for item in operations
        )
        or len(set(operations)) != len(operations)
    ):
        raise CandidateBuildBlocked("REGISTRATION_INVALID", package)
    return operations


def _manifest_api_registration(manifest: dict[str, Any]) -> tuple[tuple[str, str, str, str], ...]:
    contributions = (manifest.get("spec") or {}).get("contributions") or []
    values = tuple(
        (item.get("operationId"), item.get("method"), item.get("path"), item.get("mode"))
        for item in contributions if isinstance(item, dict) and item.get("kind") == "api"
    )
    if len(set(values)) != len(values):
        raise CandidateBuildBlocked("MANIFEST_API_DUPLICATE", str((manifest.get("metadata") or {}).get("id")))
    return values


def _schema_compatibility(path: Path, bundle_id: str) -> str:
    compatibility_path = path / "artifacts/schema-compatibility.json"
    requirements_path = path / "artifacts/schema-requirements.json"
    try:
        compatibility_raw = compatibility_path.read_bytes()
        compatibility = json.loads(compatibility_raw)
        requirements = json.loads(requirements_path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateBuildBlocked("SCHEMA_COMPATIBILITY_MISSING", bundle_id) from exc
    if compatibility != {
        "schemaVersion": 1,
        "bundleId": bundle_id,
        "alembicRevision": SCHEMA_COMPATIBILITY_REVISION,
        "noPackageOwnedMigration": True,
        "requiredRelations": list(SCHEMA_COMPATIBILITY_RELATIONS),
    }:
        raise CandidateBuildBlocked("SCHEMA_COMPATIBILITY_DRIFT", bundle_id)
    compatibility_hash = _sha256(compatibility_raw)
    if requirements != {
        "schemaVersion": 1,
        "requirements": [
            {
                "version": SCHEMA_REQUIREMENT_VERSION,
                "migrationHash": compatibility_hash,
            }
        ],
    }:
        raise CandidateBuildBlocked("SCHEMA_REQUIREMENT_DRIFT", bundle_id)
    return compatibility_hash


def preflight() -> dict[str, Any]:
    bundles: list[dict[str, Any]] = []
    operation_ids: set[str] = set()
    module_ids: set[str] = set()
    routes: set[str] = set()
    for relative, expected_id, expected_version, package in ALL_CASES:
        root = CANDIDATE_ROOT / relative
        manifest = _load_manifest(root)
        metadata = manifest.get("metadata") or {}
        if (metadata.get("id"), metadata.get("version")) != (expected_id, expected_version):
            raise CandidateBuildBlocked("CANDIDATE_COORDINATE_DRIFT", relative)
        runtime = (manifest.get("spec") or {}).get("runtime")
        operations: tuple[str, ...] = ()
        schema_compatibility_hash: str | None = None
        if package is None:
            if runtime is not None:
                raise CandidateBuildBlocked("UNEXPECTED_RUNTIME", relative)
        else:
            backend = (runtime or {}).get("backend") if isinstance(runtime, dict) else None
            expected_entrypoint = f"backend/{package}/__init__.py:register"
            if (
                not isinstance(backend, dict)
                or backend.get("entrypoint") != expected_entrypoint
                or backend.get("pythonPackage") != package
                or backend.get("profileId") != "internal-python-v1"
                or backend.get("imageIndex") != "artifacts/runtime-image-index.json"
            ):
                raise CandidateBuildBlocked("RUNTIME_DECLARATION_DRIFT", relative)
            registration = _runtime_registration(root, package)
            declared = _manifest_api_registration(manifest)
            if set(registration) != set(declared) or len(registration) != len(declared):
                raise CandidateBuildBlocked("MANIFEST_RUNTIME_API_MISMATCH", relative)
            operations = tuple(item[0] for item in registration)
            schema_compatibility_hash = _schema_compatibility(root, expected_id)
            if operation_ids.intersection(operations):
                raise CandidateBuildBlocked("DUPLICATE_RUNTIME_OPERATION", relative)
            operation_ids.update(operations)
        for item in (manifest.get("spec") or {}).get("contributions") or []:
            if item.get("kind") == "ui" and item.get("slot") == "workshop.primary.ecommerce":
                module_id = item.get("id")
                if not isinstance(module_id, str) or module_id in module_ids:
                    raise CandidateBuildBlocked("DUPLICATE_WORKSHOP_MODULE", relative)
                module_ids.add(module_id)
            if item.get("kind") == "navigation":
                route = item.get("route")
                if not isinstance(route, str) or route in routes:
                    raise CandidateBuildBlocked("DUPLICATE_WORKSHOP_ROUTE", relative)
                routes.add(route)
        bundles.append(
            {
                "id": expected_id,
                "version": expected_version,
                "sourceTreeHash": _tree_hash(root),
                "runtimeOperations": list(operations),
                "schemaCompatibilityHash": schema_compatibility_hash,
            }
        )
    if len(module_ids) != 8 or len(routes) != 8 or len(operation_ids) != 12:
        raise CandidateBuildBlocked(
            "CANDIDATE_INVENTORY_MISMATCH",
            f"modules={len(module_ids)} routes={len(routes)} operations={len(operation_ids)}",
        )
    return {
        "outcome": "PREFLIGHT_GREEN",
        "mode": "preflight",
        "bundleCount": 4,
        "runtimeMemberCount": 3,
        "moduleCount": 8,
        "operationCount": 12,
        "bundles": bundles,
    }


def _docker(context: str, *arguments: str, timeout: int = 60) -> str:
    completed = subprocess.run(
        ["docker", "--context", context, *arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return completed.stdout.strip()


def _require_isolated_engine(context: str) -> dict[str, str]:
    raw = _docker(context, "info", "--format", "{{json .}}", timeout=15)
    info = json.loads(raw)
    options = info.get("SecurityOptions") or []
    architecture = info.get("Architecture")
    if (
        info.get("OSType") != "linux"
        or architecture != "aarch64"
        or "name=userns" not in options
        or not any(str(item).startswith("name=seccomp") for item in options)
    ):
        raise CandidateBuildBlocked("ENGINE_ISOLATION_UNAVAILABLE", context)
    base = json.loads(_docker(context, "image", "inspect", BASE_IMAGE, timeout=15))
    if len(base) != 1 or not re.fullmatch(r"sha256:[0-9a-f]{64}", base[0].get("Id", "")):
        raise CandidateBuildBlocked("CACHED_BASE_IMAGE_UNAVAILABLE", BASE_IMAGE)
    return {"platform": PLATFORM, "baseImage": BASE_IMAGE, "baseConfigDigest": base[0]["Id"]}


def _augment_sbom(bundle: Path, *, sdk_hash: str, base_config_digest: str) -> None:
    path = bundle / "evidence/sbom.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    components = document.get("components")
    if not isinstance(components, list):
        raise CandidateBuildBlocked("SBOM_INVALID", str(path))
    runtime_components = [
        {"type": "library", "name": "aos-extension-sdk", "version": sdk_hash},
        {"type": "container", "name": BASE_IMAGE, "version": base_config_digest},
    ]
    names = {item.get("name") for item in components if isinstance(item, dict)}
    components.extend(item for item in runtime_components if item["name"] not in names)
    path.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _build_image(
    *, context: str, bundle: Path, package: str, work: Path
) -> tuple[str, Path]:
    build = work / f"build-{package}"
    build.mkdir()
    shutil.copytree(SDK_ROOT, build / "aos_extension_sdk")
    shutil.copytree(bundle, build / "bundle")
    manifest = _load_manifest(bundle)
    backend = manifest["spec"]["runtime"]["backend"]
    (build / "runtime.json").write_text(
        json.dumps(
            {"entrypoint": backend["entrypoint"], "pythonPackage": backend["pythonPackage"]},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    (build / "runner.py").write_text(
        "from aos_extension_sdk.runner import main\nmain()\n", encoding="utf-8"
    )
    (build / "Dockerfile").write_text(
        "FROM python:3.11-alpine\n"
        "COPY aos_extension_sdk /usr/local/lib/python3.11/site-packages/aos_extension_sdk\n"
        "COPY bundle /aos/bundle\n"
        "COPY runtime.json runner.py /aos/\n"
        "USER 65534:65534\n",
        encoding="utf-8",
    )
    image_id = _docker(
        context,
        "build",
        "--network=none",
        "--pull=false",
        "-q",
        str(build),
        timeout=120,
    )
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise CandidateBuildBlocked("IMAGE_BUILD_ID_INVALID", package)
    archive = work / f"{package}.tar"
    _docker(context, "image", "save", "-o", str(archive), image_id, timeout=120)
    return image_id, archive


def _export_registry_manifest(archive: Path, registry: Path, repository: str) -> dict[str, str]:
    manifests = registry / "manifests"
    blobs = registry / "blobs"
    manifests.mkdir(parents=True, exist_ok=True)
    blobs.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as source:
        index_file = source.extractfile("manifest.json")
        if index_file is None:
            raise CandidateBuildBlocked("IMAGE_ARCHIVE_INVALID", str(archive))
        index = json.load(index_file)
        if not isinstance(index, list) or len(index) != 1:
            raise CandidateBuildBlocked("IMAGE_ARCHIVE_INVALID", str(archive))

        def blob(name: str, media_type: str) -> dict[str, Any]:
            member = source.getmember(name)
            if member.size < 0 or member.size > 256 * 1024 * 1024:
                raise CandidateBuildBlocked("IMAGE_LAYER_SIZE_INVALID", name)
            handle = source.extractfile(member)
            if handle is None:
                raise CandidateBuildBlocked("IMAGE_ARCHIVE_INVALID", name)
            raw = handle.read()
            digest = hashlib.sha256(raw).hexdigest()
            target = blobs / digest
            if target.exists() and target.read_bytes() != raw:
                raise CandidateBuildBlocked("IMAGE_BLOB_COLLISION", digest)
            target.write_bytes(raw)
            return {"mediaType": media_type, "digest": f"sha256:{digest}", "size": len(raw)}

        config = blob(index[0]["Config"], "application/vnd.oci.image.config.v1+json")
        layers = [
            blob(name, "application/vnd.oci.image.layer.v1.tar")
            for name in index[0]["Layers"]
        ]
    raw_manifest = json.dumps(
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": config,
            "layers": layers,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    manifest_digest = _sha256(raw_manifest)
    (manifests / f"{repository}.json").write_bytes(raw_manifest)
    return {"imageDigest": manifest_digest, "configDigest": config["digest"]}


REGISTRY_SERVER = r'''from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import hashlib, re
ROOT=Path('/fixture')
class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self): self.respond(False)
    def do_GET(self): self.respond(True)
    def respond(self, send_body):
        if self.path == '/v2/': raw,kind,digest=b'{}','application/json',None
        else:
            match=re.fullmatch(r'/v2/([a-z0-9._-]+)/manifests/(sha256:[0-9a-f]{64})',self.path)
            blob=re.fullmatch(r'/v2/([a-z0-9._-]+)/blobs/sha256:([0-9a-f]{64})',self.path)
            if match:
                path=ROOT/'manifests'/(match.group(1)+'.json')
                if not path.is_file(): self.send_error(404); return
                raw=path.read_bytes(); digest='sha256:'+hashlib.sha256(raw).hexdigest()
                if digest != match.group(2): self.send_error(404); return
                kind='application/vnd.oci.image.manifest.v1+json'
            elif blob:
                path=ROOT/'blobs'/blob.group(2)
                if not path.is_file(): self.send_error(404); return
                raw=path.read_bytes(); kind='application/octet-stream'; digest=None
            else: self.send_error(404); return
        self.send_response(200); self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Docker-Distribution-Api-Version','registry/2.0')
        if digest: self.send_header('Docker-Content-Digest',digest)
        self.end_headers()
        if send_body: self.wfile.write(raw)
    def log_message(self,*args): pass
ThreadingHTTPServer(('0.0.0.0',5000),Handler).serve_forever()
'''


def _port_is_free(port: int) -> bool:
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _pull_exact_images(
    *, context: str, port: int, work: Path, images: dict[str, dict[str, str]]
) -> dict[str, dict[str, str]]:
    if not _port_is_free(port):
        raise CandidateBuildBlocked("REGISTRY_PORT_UNAVAILABLE", str(port))
    registry = work / "registry"
    (registry / "server.py").write_text(REGISTRY_SERVER, encoding="utf-8")
    (registry / "Dockerfile").write_text(
        "FROM python:3.11-alpine\nCOPY fixture /fixture\nCOPY server.py /server.py\n"
        "USER 65534:65534\nCMD [\"python\",\"/server.py\"]\n",
        encoding="utf-8",
    )
    helper = _docker(
        context,
        "build",
        "--network=none",
        "--pull=false",
        "-q",
        str(registry),
        timeout=120,
    )
    name = "a0v-candidate-registry-" + uuid.uuid4().hex
    endpoint = json.loads(
        subprocess.check_output(
            ["docker", "context", "inspect", context, "--format", "{{json .Endpoints.docker.Host}}"],
            text=True,
            timeout=15,
        )
    )
    docker_config = work / "docker-config"
    docker_config.mkdir()
    (docker_config / "config.json").write_text('{"auths":{}}\n', encoding="utf-8")
    pulled: dict[str, dict[str, str]] = {}
    try:
        _docker(
            context,
            "run",
            "-d",
            "--name",
            name,
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory=256m",
            "--pids-limit=32",
            "-p",
            f"127.0.0.1:{port}:5000",
            helper,
            timeout=15,
        )
        deadline = time.monotonic() + 10
        while True:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/v2/", timeout=1
                ) as response:
                    if response.status == 200 and response.read() == b"{}":
                        break
            except (OSError, ValueError):
                if time.monotonic() > deadline:
                    raise CandidateBuildBlocked("REGISTRY_START_TIMEOUT", name)
                time.sleep(0.1)
        for repository, identity in images.items():
            ref = f"127.0.0.1:{port}/{repository}@{identity['imageDigest']}"
            try:
                subprocess.run(
                    [
                        "docker",
                        "--config",
                        str(docker_config),
                        "--host",
                        endpoint,
                        "pull",
                        ref,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except subprocess.CalledProcessError as exc:
                detail = (exc.stderr or exc.stdout or "exact image pull failed").strip()
                logs = subprocess.run(
                    ["docker", "--context", context, "logs", name],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                container_detail = (logs.stderr or logs.stdout or "").strip()
                if container_detail:
                    detail = detail + " | registry: " + container_detail
                raise CandidateBuildBlocked(
                    "EXACT_IMAGE_PULL_FAILED", detail[-2000:]
                ) from exc
            rows = json.loads(_docker(context, "image", "inspect", identity["configDigest"]))
            if len(rows) != 1:
                raise CandidateBuildBlocked("CACHED_IMAGE_MISSING", repository)
            row = rows[0]
            digests = {value.rsplit("@", 1)[-1] for value in row.get("RepoDigests", [])}
            if (
                row.get("Id") != identity["configDigest"]
                or identity["imageDigest"] not in digests
                or f"{row.get('Os')}/{row.get('Architecture')}" != PLATFORM
                or (row.get("Config") or {}).get("Volumes")
            ):
                raise CandidateBuildBlocked("CACHED_IMAGE_IDENTITY_MISMATCH", repository)
            pulled[repository] = {**identity, "localRef": ref}
    finally:
        subprocess.run(
            ["docker", "--context", context, "rm", "-f", name],
            capture_output=True,
            text=True,
            timeout=15,
        )
        subprocess.run(
            ["docker", "--context", context, "image", "rm", helper],
            capture_output=True,
            text=True,
            timeout=15,
        )
    return pulled


def _content_hashes(output: Path) -> dict[str, str]:
    sys.path.insert(0, str(API_ROOT))
    try:
        from aos_api.asset_registry.manifest_loader import ManifestLoader

        loader = ManifestLoader({"a0v-candidate": output})
        return {
            bundle_id: loader.load(f"bundle://a0v-candidate/{relative}").content_hash
            for relative, bundle_id, _version, _package in ALL_CASES
        }
    finally:
        sys.path.remove(str(API_ROOT))


def _artifact_rows(bundle: Any) -> list[dict[str, object]]:
    return [
        {
            "relativePath": item.relative_path,
            "digest": item.digest,
            "size": item.size,
            "mediaType": item.media_type,
        }
        for item in bundle.artifacts
    ]


def _signature_payload(bundle: Any) -> bytes:
    from aos_api.asset_registry.canonical_json import canonical_json

    return canonical_json(
        {
            "manifest": bundle.manifest.model_dump(
                mode="json", by_alias=True, exclude_none=False
            ),
            "artifacts": _artifact_rows(bundle),
        }
    )


def _release_record(bundle: Any) -> _ReleaseRecord:
    from aos_api.asset_registry.contracts import BundleVersionStatus

    return _ReleaseRecord(
        publisher=bundle.manifest.metadata.publisher,
        manifest=bundle.manifest,
        content_hash=bundle.content_hash,
        signature=bundle.signature,
        status=BundleVersionStatus.PUBLISHED,
        evidence=list(bundle.evidence),
        artifacts=_artifact_rows(bundle),
    )


def _snapshot_candidate(bundle: Any, approved: Any) -> Any:
    from aos_api.asset_registry.composition_contracts import RegistrySnapshotCandidate

    manifest = bundle.manifest
    spec = manifest.spec
    publisher = manifest.metadata.publisher
    return RegistrySnapshotCandidate.model_validate(
        {
            "publisher": publisher,
            "id": manifest.metadata.id,
            "version": manifest.metadata.version,
            "kind": manifest.kind,
            "manifest": manifest,
            "contentHash": bundle.content_hash,
            "signatureFingerprint": approved.signature_fingerprint,
            "releaseEvidenceRevision": approved.release_evidence_revision,
            "dependencies": [
                {
                    "publisher": item.publisher or publisher,
                    "id": item.id,
                    "version": item.version,
                }
                for item in spec.dependencies
            ],
            "optionalDependencies": [
                {
                    "publisher": item.publisher or publisher,
                    "id": item.id,
                    "version": item.version,
                }
                for item in spec.optional_dependencies
            ],
            "conflicts": [
                {
                    "publisher": item.publisher or publisher,
                    "id": item.id,
                    "version": item.version,
                }
                for item in spec.conflicts
            ],
            "capabilities": spec.capabilities.model_dump(mode="json", by_alias=True),
            "permissions": spec.permissions.model_dump(mode="json", by_alias=True),
            "migration": {
                "planRef": spec.migrations.plan,
                "downgradePolicy": spec.migrations.downgrade_policy,
            },
            "contributions": [
                item.model_dump(mode="json", by_alias=True)
                for item in spec.contributions
            ],
        }
    )


def _read_receipt(path: Path, *, output: Path) -> dict[str, Any]:
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateBuildBlocked("BUILD_RECEIPT_INVALID", str(path)) from exc
    if (
        not isinstance(receipt, dict)
        or receipt.get("outcome") != "BUILD_GREEN"
        or receipt.get("output") != str(output)
        or receipt.get("outputTreeHash") != _tree_hash(output)
    ):
        raise CandidateBuildBlocked("BUILD_RECEIPT_MISMATCH", str(path))
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True
    ).strip()
    if receipt.get("gitHead") != head:
        raise CandidateBuildBlocked("BUILD_RECEIPT_GIT_HEAD_MISMATCH", head)
    if receipt.get("effects") != {
        "registryPublishCount": 0,
        "installationMutationCount": 0,
        "providerInvocationCount": 0,
        "externalPublicationCount": 0,
    }:
        raise CandidateBuildBlocked("BUILD_RECEIPT_EFFECTS_INVALID", str(path))
    if (receipt.get("engine") or {}).get("platform") != PLATFORM:
        raise CandidateBuildBlocked("BUILD_RECEIPT_PLATFORM_MISMATCH", str(path))
    return receipt


def _sign_staging_tree(root: Path, *, checked_at: datetime) -> tuple[Any, Any]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.signature import FrozenTrustRootProvider, TrustRoot

    unsigned_loader = ManifestLoader({"a0v-candidate": root})
    unsigned = {
        bundle_id: unsigned_loader.load(f"bundle://a0v-candidate/{relative}")
        for relative, bundle_id, _version, _package in ALL_CASES
    }
    key = Ed25519PrivateKey.generate()
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_key_b64 = base64.b64encode(public_key).decode("ascii")
    trust_root = TrustRoot(
        publisher="aos",
        key_id=QUALIFICATION_KEY_ID,
        public_key=public_key,
        revision=canonical_sha256(
            {
                "publisher": "aos",
                "keyId": QUALIFICATION_KEY_ID,
                "algorithm": "Ed25519",
                "publicKey": public_key_b64,
            }
        ),
        not_before=checked_at - timedelta(minutes=5),
        not_after=checked_at + timedelta(hours=1),
    )
    trust = FrozenTrustRootProvider({("aos", QUALIFICATION_KEY_ID): trust_root})
    for relative, bundle_id, _version, _package in ALL_CASES:
        envelope = {
            "algorithm": "Ed25519",
            "keyId": QUALIFICATION_KEY_ID,
            "signature": base64.b64encode(
                key.sign(_signature_payload(unsigned[bundle_id]))
            ).decode("ascii"),
            "signedAt": checked_at.isoformat(),
        }
        (root / relative / "bundle.signature.json").write_text(
            json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    return ManifestLoader({"a0v-candidate": root}, trust_roots=trust), trust


def _assert_signed_tampering_rejected(
    *, signed_root: Path, loader: Any, policy: Any, checked_at: datetime
) -> list[str]:
    cases = {
        "imageIndexBytes": (
            "domain.ecommerce.core/1.2.0/artifacts/runtime-image-index.json",
            lambda raw: raw + b" ",
        ),
        "imageDigest": (
            "domain.ecommerce.core/1.2.0/artifacts/runtime-image-index.json",
            lambda raw: raw.replace(b'"imageDigest":"sha256:', b'"imageDigest":"sha256:0', 1),
        ),
        "dependencyLock": (
            "domain.ecommerce.core/1.2.0/artifacts/python-dependencies.lock",
            lambda raw: raw + b"# tampered\n",
        ),
        "sbom": (
            "domain.ecommerce.core/1.2.0/evidence/sbom.json",
            lambda raw: raw + b" ",
        ),
        "backend": (
            "domain.ecommerce.core/1.2.0/backend/ecommerce_core/__init__.py",
            lambda raw: raw + b"\n# tampered\n",
        ),
        "schemaCompatibility": (
            "domain.ecommerce.core/1.2.0/artifacts/schema-compatibility.json",
            lambda raw: raw + b" ",
        ),
        "schemaRequirements": (
            "domain.ecommerce.core/1.2.0/artifacts/schema-requirements.json",
            lambda raw: raw + b" ",
        ),
    }
    rejected: list[str] = []
    for label, (relative, transform) in cases.items():
        path = signed_root / relative
        original = path.read_bytes()
        try:
            path.write_bytes(transform(original))
            bundle = loader.load("bundle://a0v-candidate/domain.ecommerce.core/1.2.0")
            policy.evaluate(_release_record(bundle), checked_at=checked_at)
        except Exception:
            rejected.append(label)
        else:
            raise CandidateBuildBlocked("SIGNED_TAMPERING_ACCEPTED", label)
        finally:
            path.write_bytes(original)
    return rejected


def _qualify_session(*, driver, image_id, contributions, journal_root: Path):
    """Persist a one-use diagnostic resource identity before any container create."""
    from aos_api.extension_runtime.contracts import RegistrationDescription
    from aos_api.extension_runtime.session_supervisor import open_session
    from aos_api.extension_runtime.supervisor import ResourceIdentity

    declared = RegistrationDescription(contributions=contributions)
    identity = ResourceIdentity(uuid.uuid4().hex)
    journal_root.mkdir(parents=True, exist_ok=True)
    journal = journal_root / (identity.owner + ".jsonl")
    with journal.open("x", encoding="utf-8") as stream:
        os.chmod(journal, 0o600)
        def record(state):
            stream.write(json.dumps({"state": state, "resourceName": identity.name,
                "owner": identity.owner, "imageId": image_id, "context": driver.context}, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        record("claimed")
        async def run():
            async with open_session(driver, image_id=image_id, declared=declared,
                                    resource_identity=identity) as session:
                for _ in range(2048):
                    await session.check_health()
                record("registered_and_alive")
        try:
            asyncio.run(run())
        except BaseException:
            record("failed_requires_observation")
            raise
        record("released")
    return {"registration": "exact", "heartbeat": "alive", "cleanup": "released",
            "contributionCount": len(declared.contributions), "heartbeatChecks": 2048, "journal": str(journal)}


def qualify(
    *, output: Path, build_receipt: Path, context: str, driver: Any | None = None
) -> dict[str, Any]:
    output = output.resolve(strict=True)
    if output == REPOSITORY_ROOT or output.is_relative_to(REPOSITORY_ROOT):
        raise CandidateBuildBlocked("OUTPUT_MUST_BE_OUTSIDE_REPOSITORY", str(output))
    receipt = _read_receipt(build_receipt.resolve(strict=True), output=output)
    if receipt.get("contentHashes") != _content_hashes(output):
        raise CandidateBuildBlocked("BUILD_CONTENT_HASH_MISMATCH", str(output))

    sys.path.insert(0, str(API_ROOT))
    signed_root = Path(tempfile.mkdtemp(prefix="a0v-ecommerce-candidate-qualification-"))
    try:
        from aos_api.asset_registry.composition_contracts import (
            CompositionRequest,
            RegistrySnapshot,
        )
        from aos_api.asset_registry.release_policy import ReleasePolicy
        from aos_api.asset_registry.resolver import resolve
        from aos_api.extension_runtime.admission import admit_runtime_artifact
        from aos_api.extension_runtime.oci_driver import OciDriver
        from aos_api.extension_runtime.schema_conditions import (
            admit_schema_requirements,
        )

        shutil.rmtree(signed_root)
        shutil.copytree(output, signed_root)
        signed_at = datetime.now(UTC)
        loader, trust = _sign_staging_tree(signed_root, checked_at=signed_at)
        policy = ReleasePolicy(trust_roots=trust)
        bundles: dict[str, Any] = {}
        candidates = []
        for relative, bundle_id, _version, _package in ALL_CASES:
            bundle = loader.load(f"bundle://a0v-candidate/{relative}")
            bundles[bundle_id] = bundle
        checked_at = datetime.now(UTC)
        for _relative, bundle_id, _version, _package in ALL_CASES:
            bundle = bundles[bundle_id]
            approved = policy.evaluate(_release_record(bundle), checked_at=checked_at)
            candidates.append(_snapshot_candidate(bundle, approved))
        snapshot = RegistrySnapshot.build(candidates=candidates, checked_at=checked_at)
        requested_ids = (
            "platform.ecommerce.niushop",
            "solution.ecommerce.operations-base",
            "solution.ecommerce.growth",
        )
        versions = {item.id: item.version for item in snapshot.candidates}
        request = CompositionRequest.model_validate(
            {
                "requested": [
                    {"publisher": "aos", "id": item, "version": versions[item]}
                    for item in requested_ids
                ],
                "platformApiVersion": "1.7.0",
                "platformRelease": "aos-platform/1.7.0",
                "environment": "dev",
                "registrySnapshotHash": snapshot.snapshot_hash,
                "currentInstallationRef": None,
            }
        )
        composition = resolve(request, snapshot, None)
        resolved_by_id = {item.id: item for item in composition.resolved}
        actual_driver = driver or OciDriver(context=context)
        admitted = {}
        sessions = {}
        schema_requirements = {}
        for relative, bundle_id, _version, _package in RUNTIME_CASES:
            root = signed_root / relative
            record = _release_record(bundles[bundle_id])
            requirements = admit_schema_requirements(
                record=record,
                selected=resolved_by_id[bundle_id],
                policy=policy,
                checked_at=checked_at,
                read_artifact=lambda path, limit, root=root: (root / path).read_bytes(),
            )
            if len(requirements) != 1:
                raise CandidateBuildBlocked(
                    "SCHEMA_REQUIREMENT_COUNT_MISMATCH", bundle_id
                )
            requirement = requirements[0]
            schema_requirements[bundle_id] = {
                "packageId": requirement.package_id,
                "schemaVersion": requirement.schema_version,
                "migrationHash": requirement.migration_hash,
            }
            artifact = admit_runtime_artifact(
                record=record,
                selected=resolved_by_id[bundle_id],
                policy=policy,
                checked_at=checked_at,
                read_artifact=lambda path, limit, root=root: (root / path).read_bytes(),
                platform=PLATFORM,
                driver=actual_driver,
            )
            admitted[bundle_id] = {
                "imageId": artifact.image_id,
                "packageHash": artifact.package_hash,
            }
            receipt_identity = (receipt.get("images") or {}).get(
                bundle_id.replace(".", "-")
            )
            index_document = json.loads(
                (root / "artifacts/runtime-image-index.json").read_text(encoding="utf-8")
            )
            index_identity = next(
                (
                    item
                    for item in index_document.get("images", [])
                    if item.get("platform") == PLATFORM
                ),
                None,
            )
            if (
                not isinstance(receipt_identity, dict)
                or not isinstance(index_identity, dict)
                or receipt_identity.get("configDigest") != artifact.image_id
                or receipt_identity.get("configDigest")
                != index_identity.get("configDigest")
                or receipt_identity.get("imageDigest")
                != index_identity.get("imageDigest")
            ):
                raise CandidateBuildBlocked("BUILD_RECEIPT_IMAGE_MISMATCH", bundle_id)
            sessions[bundle_id] = _qualify_session(
                driver=actual_driver, image_id=artifact.image_id,
                contributions=record.manifest.spec.contributions,
                journal_root=build_receipt.parent / "qualification-session-journal",
            )
        tamper_rejections = _assert_signed_tampering_rejected(
            signed_root=signed_root,
            loader=loader,
            policy=policy,
            checked_at=checked_at,
        )
        module_ids = {
            item.module_id for bundle in bundles.values() for item in bundle.workshop_modules
        }
        return {
            "outcome": "QUALIFICATION_GREEN",
            "mode": "qualification",
            "gitHead": receipt["gitHead"],
            "buildReceipt": str(build_receipt.resolve()),
            "buildReceiptHash": _sha256(build_receipt.read_bytes()),
            "outputTreeHash": receipt["outputTreeHash"],
            "snapshotHash": snapshot.snapshot_hash,
            "resolved": [
                {"id": item.id, "version": item.version, "reason": item.selection_reason}
                for item in composition.resolved
            ],
            "runtimeAdmissions": admitted,
            "runtimeSessions": sessions,
            "schemaRequirements": schema_requirements,
            "moduleCount": len(module_ids),
            "runtimeMemberCount": len(admitted),
            "tamperRejections": tamper_rejections,
            "ephemeralSignaturePersisted": False,
            "effects": receipt["effects"],
        }
    finally:
        shutil.rmtree(signed_root, ignore_errors=True)
        sys.path.remove(str(API_ROOT))


def build(*, context: str, port: int, output: Path) -> dict[str, Any]:
    source = preflight()
    output = output.resolve()
    if output == REPOSITORY_ROOT or output.is_relative_to(REPOSITORY_ROOT):
        raise CandidateBuildBlocked("OUTPUT_MUST_BE_OUTSIDE_REPOSITORY", str(output))
    if output.exists():
        raise CandidateBuildBlocked("OUTPUT_ALREADY_EXISTS", str(output))
    engine = _require_isolated_engine(context)
    sdk_hash = _tree_hash(SDK_ROOT)
    work = Path(tempfile.mkdtemp(prefix="a0v-ecommerce-candidate-build-"))
    try:
        output.mkdir(parents=True)
        for relative, _bundle_id, _version, _package in ALL_CASES:
            shutil.copytree(CANDIDATE_ROOT / relative, output / relative)
        for relative, _bundle_id, _version, package in RUNTIME_CASES:
            bundle = output / relative
            artifacts = bundle / "artifacts"
            artifacts.mkdir(exist_ok=True)
            (artifacts / "python-dependencies.lock").write_bytes(RUNTIME_LOCK)
            _augment_sbom(
                bundle,
                sdk_hash=sdk_hash,
                base_config_digest=engine["baseConfigDigest"],
            )

        registry_fixture = work / "registry" / "fixture"
        images: dict[str, dict[str, str]] = {}
        for relative, bundle_id, _version, package in RUNTIME_CASES:
            assert package is not None
            _image_id, archive = _build_image(
                context=context, bundle=output / relative, package=package, work=work
            )
            repository = bundle_id.replace(".", "-")
            images[repository] = _export_registry_manifest(
                archive, registry_fixture, repository
            )
        pulled = _pull_exact_images(
            context=context, port=port, work=work, images=images
        )
        lock_hash = _sha256(RUNTIME_LOCK)
        for relative, bundle_id, _version, _package in RUNTIME_CASES:
            repository = bundle_id.replace(".", "-")
            identity = pulled[repository]
            index = {
                "schemaVersion": 1,
                "images": [
                    {
                        "platform": PLATFORM,
                        "imageDigest": identity["imageDigest"],
                        "configDigest": identity["configDigest"],
                        "dependencyLockHash": lock_hash,
                        "sbomPath": "evidence/sbom.json",
                    }
                ],
            }
            path = output / relative / "artifacts/runtime-image-index.json"
            path.write_text(
                json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
        content_hashes = _content_hashes(output)
        return {
            **source,
            "outcome": "BUILD_GREEN",
            "mode": "build",
            "gitHead": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True
            ).strip(),
            "output": str(output),
            "outputTreeHash": _tree_hash(output),
            "engine": engine,
            "sdkTreeHash": sdk_hash,
            "dependencyLockHash": lock_hash,
            "contentHashes": content_hashes,
            "images": pulled,
            "effects": {
                "registryPublishCount": 0,
                "installationMutationCount": 0,
                "providerInvocationCount": 0,
                "externalPublicationCount": 0,
            },
        }
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--qualify-output", type=Path)
    parser.add_argument("--build-receipt", type=Path)
    parser.add_argument("--docker-context", default=DEFAULT_CONTEXT)
    parser.add_argument("--registry-port", type=int, default=DEFAULT_REGISTRY_PORT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--receipt", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.build and args.qualify_output is not None:
            raise CandidateBuildBlocked(
                "MODE_CONFLICT", "--build and --qualify-output are mutually exclusive"
            )
        if args.qualify_output is not None:
            if args.build_receipt is None or args.receipt is None:
                raise CandidateBuildBlocked(
                    "QUALIFICATION_INPUT_REQUIRED",
                    "--qualify-output requires --build-receipt and --receipt",
                )
            result = qualify(
                output=args.qualify_output,
                build_receipt=args.build_receipt,
                context=args.docker_context,
            )
        elif args.build:
            if args.output_dir is None or args.receipt is None:
                raise CandidateBuildBlocked(
                    "BUILD_OUTPUT_REQUIRED", "--build requires --output-dir and --receipt"
                )
            result = build(
                context=args.docker_context,
                port=args.registry_port,
                output=args.output_dir,
            )
        else:
            result = preflight()
    except CandidateBuildBlocked as exc:
        result = {
            "outcome": "SAFE_BLOCKED",
            "reasonCode": exc.reason_code,
            "message": str(exc),
        }
        status = 2
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, json.JSONDecodeError) as exc:
        result = {
            "outcome": "SAFE_BLOCKED",
            "reasonCode": type(exc).__name__.upper(),
            "message": str(exc),
        }
        status = 2
    else:
        status = 0
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.receipt is not None:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
