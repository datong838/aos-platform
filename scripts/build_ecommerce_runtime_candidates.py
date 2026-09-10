#!/usr/bin/env python3
"""Build unsigned, locally cached ecommerce runtime candidates without publishing."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
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
RUNTIME_CASES = (
    ("domain.ecommerce.core/1.1.0", "domain.ecommerce.core", "1.1.0", "ecommerce_core"),
    (
        "platform.ecommerce.niushop/1.1.0",
        "platform.ecommerce.niushop",
        "1.1.0",
        "ecommerce_niushop",
    ),
    (
        "solution.ecommerce.growth/1.4.0",
        "solution.ecommerce.growth",
        "1.4.0",
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


def _runtime_registration(path: Path, package: str) -> tuple[str, ...]:
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
    operations = tuple(
        item.get("operationId") for item in contributions if isinstance(item, dict)
    )
    if (
        len(operations) != len(contributions)
        or any(not isinstance(item, str) or not item for item in operations)
        or len(set(operations)) != len(operations)
    ):
        raise CandidateBuildBlocked("REGISTRATION_INVALID", package)
    return operations


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
            operations = _runtime_registration(root, package)
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


REGISTRY_SERVER = r'''from http.server import BaseHTTPRequestHandler, HTTPServer
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
HTTPServer(('0.0.0.0',5000),Handler).serve_forever()
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
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                if time.monotonic() > deadline:
                    raise CandidateBuildBlocked("REGISTRY_START_TIMEOUT", name)
                time.sleep(0.1)
        for repository, identity in images.items():
            ref = f"127.0.0.1:{port}/{repository}@{identity['imageDigest']}"
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
    parser.add_argument("--docker-context", default=DEFAULT_CONTEXT)
    parser.add_argument("--registry-port", type=int, default=DEFAULT_REGISTRY_PORT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--receipt", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.build:
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
