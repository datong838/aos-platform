#!/usr/bin/env python3
"""Recover BM registry material through new immutable patch releases."""
from __future__ import annotations

import argparse
import base64
from datetime import UTC, datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services/aos-api"
SOURCE_ROOT = ROOT / "bundles/candidates/ecommerce"
STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/bm-trust-root-rotation"
CANDIDATES = STATE / "candidates"
BUILD = STATE / "build"
SIGNED = STATE / "signed-bundles"
BUILD_RECEIPT = STATE / "build-result.json"
QUALIFICATION_RECEIPT = STATE / "qualification-result.json"
TRUST = STATE / "signing/trust-roots.json"
KEY = STATE / "signing/registry-ed25519.pem"
CONTEXT = "colima-aos-extension"
DATABASE_CONTAINER = "aos-a0v-recovery-pg"
DATABASE_NAME = "aos_meta_head"
REGISTRY_PORT = 18436
KEY_ID = "a0v-local-ecommerce-recovery-v2"
SOURCE_ALIAS = "a0v-bm-recovery"
COORDINATES = (
    ("domain.ecommerce.core", "1.4.0", "1.4.1", "ecommerce_core"),
    ("platform.ecommerce.niushop", "1.23.0", "1.23.1", "ecommerce_niushop"),
    ("solution.ecommerce.growth", "1.10.0", "1.10.1", "ecommerce_growth"),
    ("solution.ecommerce.operations-base", "1.2.0", "1.2.1", None),
)
CREATE_ROLES = frozenset({"asset-publisher", "asset-registry-admin", "developer"})
PUBLISH_ROLES = frozenset({"asset-publisher", "asset-registry-admin"})
PUBLISHER_SCOPES = frozenset({"aos"})


class RotationBlocked(RuntimeError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RotationBlocked("SCRIPT_UNAVAILABLE", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _builder() -> Any:
    scripts = str(ROOT / "scripts")
    inserted = scripts not in sys.path
    if inserted:
        sys.path.insert(0, scripts)
    try:
        builder = _load(
            "bm_event_builder", ROOT / "scripts/build_ecommerce_event_candidates.py"
        ).load_builder()
    finally:
        if inserted:
            sys.path.remove(scripts)
    builder.CANDIDATE_ROOT = CANDIDATES
    builder.RUNTIME_CASES = tuple(
        (f"{bundle_id}/{new}", bundle_id, new, package)
        for bundle_id, _old, new, package in COORDINATES if package is not None
    )
    builder.ALL_CASES = tuple(
        (f"{bundle_id}/{new}", bundle_id, new, package)
        for bundle_id, _old, new, package in COORDINATES
    )
    builder.EXPECTED_RUNTIME_OPERATION_COUNT = 15
    return builder


def _helpers() -> tuple[Any, Any]:
    legacy = _load("bm_registry_helpers", ROOT / "scripts/a0v_ecommerce_growth_1_5_registry_successor.py")
    return legacy, legacy._first_installer()


def _connect() -> Any:
    _legacy, first = _helpers()
    return first.container_database_connect_factory(
        context=CONTEXT, container=DATABASE_CONTAINER, database_name=DATABASE_NAME
    )


def _write_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise RotationBlocked("RESULT_ALREADY_EXISTS", str(path))
        return
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _counts(connect: Any) -> dict[str, int]:
    pairs = [(bundle_id, new) for bundle_id, _old, new, _package in COORDINATES]
    with connect() as conn:
        row = conn.execute(
            """SELECT
              (SELECT count(*) FROM asset_bundle_version) AS versions,
              (SELECT count(*) FROM bundle_installation) AS installations,
              (SELECT count(*) FROM bundle_installation WHERE org_id='org-org' AND project_id='dev-project') AS positive,
              (SELECT count(*) FROM bundle_installation WHERE org_id='dev-org' AND project_id='dev-project') AS canary"""
        ).fetchone()
        targets = sum(
            int(conn.execute(
                """SELECT count(*) AS n FROM asset_bundle_version v JOIN asset_bundle b ON b.bundle_pk=v.bundle_pk
                   WHERE b.publisher='aos' AND b.bundle_id=%s AND v.version=%s""",
                pair,
            ).fetchone()["n"])
            for pair in pairs
        )
    return {**{key: int(row[key]) for key in row.keys()}, "targets": targets}


def _port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def preflight() -> dict[str, Any]:
    connect = _connect()
    counts = _counts(connect)
    if counts["canary"] != 0:
        raise RotationBlocked("CANARY_NOT_ZERO", str(counts["canary"]))
    sources = []
    for bundle_id, old, new, _package in COORDINATES:
        source = SOURCE_ROOT / bundle_id / old
        if not source.is_dir() or source.is_symlink():
            raise RotationBlocked("SOURCE_CANDIDATE_MISSING", str(source))
        if (source / "bundle.signature.json").exists() or (source / "artifacts/runtime-image-index.json").exists():
            raise RotationBlocked("SOURCE_CANDIDATE_NOT_UNSIGNED", str(source))
        sources.append({"bundleId": bundle_id, "oldVersion": old, "newVersion": new})
    return {
        "outcome": "PREFLIGHT_GREEN", "gitHead": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(), "sources": sources, "counts": counts,
        "port18181Open": _port_open(18181), "effects": {"sourceReadCount": 0, "installationMutationCount": 0},
    }


def prepare() -> dict[str, Any]:
    baseline = preflight()
    if baseline["port18181Open"]:
        raise RotationBlocked("RUNTIME_PORT_ACTIVE", "18181")
    if CANDIDATES.exists():
        result = _builder().preflight()
        return {**baseline, "outcome": "CANDIDATES_READY", "candidatePreflight": result}
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = Path(tempfile.mkdtemp(prefix="candidates-", dir=STATE))
    try:
        for bundle_id, old, new, _package in COORDINATES:
            source = SOURCE_ROOT / bundle_id / old
            target = temporary / bundle_id / new
            shutil.copytree(source, target)
            replacements = 0
            for path in sorted(item for item in target.rglob("*") if item.is_file()):
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                updated = text.replace(old, new)
                if updated != text:
                    path.write_text(updated, encoding="utf-8")
                    replacements += text.count(old)
            if replacements == 0:
                raise RotationBlocked("VERSION_TOKEN_MISSING", f"{bundle_id}@{old}")
        temporary.replace(CANDIDATES)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
    result = _builder().preflight()
    return {**baseline, "outcome": "CANDIDATES_READY", "candidatePreflight": result}


def build() -> dict[str, Any]:
    prepare()
    if BUILD_RECEIPT.exists():
        receipt = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
        if receipt.get("outputTreeHash") != _builder()._tree_hash(BUILD):
            raise RotationBlocked("BUILD_RECEIPT_MISMATCH", str(BUILD_RECEIPT))
        return receipt
    result = _builder().build(context=CONTEXT, port=REGISTRY_PORT, output=BUILD)
    _write_once(BUILD_RECEIPT, result)
    return result


def qualify() -> dict[str, Any]:
    build()
    if QUALIFICATION_RECEIPT.exists():
        return json.loads(QUALIFICATION_RECEIPT.read_text(encoding="utf-8"))
    result = _builder().qualify(
        output=BUILD, build_receipt=BUILD_RECEIPT, context=CONTEXT
    )
    _write_once(QUALIFICATION_RECEIPT, result)
    return result


def _private_key() -> Ed25519PrivateKey:
    KEY.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not KEY.exists():
        key = Ed25519PrivateKey.generate()
        raw = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        descriptor = os.open(KEY, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    if KEY.is_symlink() or stat.S_IMODE(KEY.stat().st_mode) != 0o600:
        raise RotationBlocked("SIGNING_KEY_PERMISSIONS_INVALID", str(KEY))
    loaded = serialization.load_pem_private_key(KEY.read_bytes(), password=None)
    if not isinstance(loaded, Ed25519PrivateKey):
        raise RotationBlocked("SIGNING_KEY_INVALID", str(KEY))
    return loaded


def sign() -> dict[str, Any]:
    qualification = qualify()
    if qualification.get("outcome") != "QUALIFICATION_GREEN":
        raise RotationBlocked("QUALIFICATION_NOT_GREEN", str(qualification.get("outcome")))
    sys.path.insert(0, str(API))
    try:
        from aos_api.asset_registry.canonical_json import canonical_sha256
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.release_policy import ReleasePolicy
        from aos_api.asset_registry.signature import FileTrustRootProvider
        key = _private_key()
        public = base64.b64encode(key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )).decode("ascii")
        now = datetime.now(UTC)
        root = {"publisher": "aos", "keyId": KEY_ID, "algorithm": "Ed25519", "publicKey": public,
                "notBefore": (now - timedelta(days=1)).isoformat(),
                "notAfter": (now + timedelta(days=3650)).isoformat(), "revokedAt": None}
        root["revision"] = canonical_sha256(root)
        trust_raw = (json.dumps({"trustRoots": [root]}, sort_keys=True, separators=(",", ":")) + "\n").encode()
        if TRUST.exists() and TRUST.read_bytes() != trust_raw:
            # Validity timestamps are frozen on first creation; reconstruct from the file thereafter.
            existing = json.loads(TRUST.read_text(encoding="utf-8"))
            if (existing.get("trustRoots") or [{}])[0].get("publicKey") != public:
                raise RotationBlocked("TRUST_ROOT_DRIFT", str(TRUST))
        elif not TRUST.exists():
            descriptor = os.open(TRUST, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(trust_raw); stream.flush(); os.fsync(stream.fileno())
        trust = FileTrustRootProvider(TRUST).snapshot()
        if not SIGNED.exists():
            temporary = Path(tempfile.mkdtemp(prefix="signed-", dir=STATE))
            try:
                shutil.copytree(BUILD, temporary, dirs_exist_ok=True)
                unsigned = ManifestLoader({SOURCE_ALIAS: temporary})
                signed_at = now.isoformat()
                for bundle_id, _old, new, _package in COORDINATES:
                    loaded = unsigned.load(f"bundle://{SOURCE_ALIAS}/{bundle_id}/{new}")
                    envelope = {"algorithm": "Ed25519", "keyId": KEY_ID,
                        "signature": base64.b64encode(key.sign(_builder()._signature_payload(loaded))).decode("ascii"),
                        "signedAt": signed_at}
                    (temporary / bundle_id / new / "bundle.signature.json").write_text(
                        json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
                temporary.replace(SIGNED)
            finally:
                if temporary.exists(): shutil.rmtree(temporary, ignore_errors=True)
        loader = ManifestLoader({SOURCE_ALIAS: SIGNED}, trust_roots=trust)
        policy = ReleasePolicy(trust_roots=trust)
        hashes = {}
        for bundle_id, _old, new, _package in COORDINATES:
            loaded = loader.load(f"bundle://{SOURCE_ALIAS}/{bundle_id}/{new}")
            policy.evaluate(_builder()._release_record(loaded), checked_at=datetime.now(UTC))
            hashes[f"{bundle_id}@{new}"] = loaded.content_hash
        return {"outcome": "SIGNED_GREEN", "keyId": KEY_ID, "trustRootRevision":
                (json.loads(TRUST.read_text())["trustRoots"][0]["revision"]), "contentHashes": hashes}
    finally:
        sys.path.remove(str(API))


def _backup() -> dict[str, Any]:
    target = STATE / "backups/aos_meta_head-pre-bm-registry.dump"
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not target.exists():
        inspected = json.loads(subprocess.check_output(
            ["docker", "--context", CONTEXT, "inspect", DATABASE_CONTAINER],
            text=True, timeout=15,
        ))
        environment = {}
        for item in ((inspected[0].get("Config") or {}).get("Env") or ()):
            if isinstance(item, str) and "=" in item:
                name, value = item.split("=", 1)
                environment[name] = value
        user = environment.get("POSTGRES_USER")
        if not user:
            raise RotationBlocked("DATABASE_USER_UNAVAILABLE", DATABASE_CONTAINER)
        temporary = target.with_suffix(".tmp")
        with temporary.open("xb") as stream:
            completed = subprocess.run(
                ["docker", "--context", CONTEXT, "exec", DATABASE_CONTAINER,
                 "pg_dump", "-U", user, "--dbname", DATABASE_NAME,
                 "--format=custom", "--no-owner", "--no-privileges"],
                stdout=stream, stderr=subprocess.PIPE, check=False, timeout=120)
        if completed.returncode != 0 or temporary.stat().st_size == 0:
            temporary.unlink(missing_ok=True)
            raise RotationBlocked("DATABASE_BACKUP_FAILED", str(target))
        temporary.replace(target)
    return {"path": str(target), "size": target.stat().st_size}


def publish() -> dict[str, Any]:
    signed = sign()
    legacy, first = _helpers()
    connect = _connect()
    before = _counts(connect)
    if before["canary"] != 0:
        raise RotationBlocked("CANARY_NOT_ZERO", str(before["canary"]))
    backup = _backup()
    sys.path.insert(0, str(API))
    try:
        from aos_api.asset_registry.errors import AssetNotFoundError
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.registry_service import RegistryService
        from aos_api.asset_registry.registry_store import PostgresRegistryStore
        from aos_api.asset_registry.signature import FileTrustRootProvider
        trust = FileTrustRootProvider(TRUST).snapshot()
        loader = ManifestLoader({SOURCE_ALIAS: SIGNED}, trust_roots=trust)
        store = PostgresRegistryStore(connect_factory=connect)
        service = RegistryService(store=store, loader=loader,
            clock=lambda: legacy._database_clock(connect), trust_roots=trust)
        releases = []
        for bundle_id, _old, new, _package in COORDINATES:
            source = f"bundle://{SOURCE_ALIAS}/{bundle_id}/{new}"
            expected = first._expected_registry_version(loader.load(source))
            mutations = {"create": 0, "validate": 0, "publish": 0}
            try:
                row = store.get_version(bundle_id, new, publisher="aos")
            except AssetNotFoundError:
                row = service.create_version(publisher="aos", bundle_id=bundle_id, source_ref=source,
                    actor="a0v-bm-recovery-creator", roles=CREATE_ROLES, publisher_scopes=PUBLISHER_SCOPES)
                mutations["create"] = 1
            first.assert_registry_version_exact(row, expected)
            if str(row["status"]).lower() == "draft":
                row = service.validate(publisher="aos", bundle_id=bundle_id, version=new,
                    actor="a0v-bm-recovery-validator", roles=CREATE_ROLES, publisher_scopes=PUBLISHER_SCOPES)
                mutations["validate"] = 1
            if str(row["status"]).lower() == "validated":
                row = service.publish(publisher="aos", bundle_id=bundle_id, version=new,
                    actor="a0v-bm-recovery-publisher", roles=PUBLISH_ROLES, publisher_scopes=PUBLISHER_SCOPES)
                mutations["publish"] = 1
            if str(row["status"]).lower() != "published":
                raise RotationBlocked("REGISTRY_STATE_UNKNOWN", f"{bundle_id}@{new}:{row['status']}")
            first.assert_registry_version_exact(store.get_version(bundle_id, new, publisher="aos"), expected)
            releases.append({"bundleId": bundle_id, "version": new, "mutations": mutations})
    finally:
        sys.path.remove(str(API))
    after = _counts(connect)
    expected_delta = 4 - before["targets"]
    if (after["installations"], after["positive"], after["canary"], after["targets"]) != (
        before["installations"], before["positive"], 0, 4
    ) or after["versions"] - before["versions"] != expected_delta:
        raise RotationBlocked("POST_PUBLISH_COUNT_DRIFT", json.dumps({"before": before, "after": after}))
    return {"outcome": "BM_REGISTRY_ROTATION_GREEN", "signed": signed, "backup": backup,
            "before": before, "after": after, "releases": releases,
            "effects": {"installationMutationCount": 0, "providerInvocationCount": 0,
                        "sourceReadCount": 0, "externalPublicationCount": 0}}


def observe() -> dict[str, Any]:
    if not SIGNED.is_dir() or not TRUST.is_file() or not BUILD_RECEIPT.is_file():
        raise RotationBlocked("ROTATION_MATERIAL_INCOMPLETE", str(STATE))
    legacy, first = _helpers()
    connect = _connect()
    counts = _counts(connect)
    if counts["targets"] != 4 or counts["canary"] != 0:
        raise RotationBlocked("ROTATION_COUNTS_INVALID", json.dumps(counts))
    build_receipt = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
    sys.path.insert(0, str(API))
    try:
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.registry_store import PostgresRegistryStore
        from aos_api.asset_registry.release_policy import ReleasePolicy
        from aos_api.asset_registry.signature import FileTrustRootProvider
        trust = FileTrustRootProvider(TRUST).snapshot()
        loader = ManifestLoader({SOURCE_ALIAS: SIGNED}, trust_roots=trust)
        store = PostgresRegistryStore(connect_factory=connect)
        policy = ReleasePolicy(trust_roots=trust)
        releases = []
        for bundle_id, _old, new, _package in COORDINATES:
            loaded = loader.load(f"bundle://{SOURCE_ALIAS}/{bundle_id}/{new}")
            policy.evaluate(_builder()._release_record(loaded), checked_at=legacy._database_clock(connect))
            expected_hash = build_receipt["contentHashes"][bundle_id]
            if loaded.content_hash != expected_hash:
                raise RotationBlocked("SIGNED_CONTENT_DRIFT", f"{bundle_id}@{new}")
            row = store.get_version(bundle_id, new, publisher="aos")
            first.assert_registry_version_exact(row, first._expected_registry_version(loaded))
            if str(row["status"]).lower() != "published":
                raise RotationBlocked("REGISTRY_STATE_UNKNOWN", f"{bundle_id}@{new}:{row['status']}")
            releases.append({"bundleId": bundle_id, "version": new,
                             "status": "published", "contentHash": loaded.content_hash})
    finally:
        sys.path.remove(str(API))
    return {"outcome": "BM_REGISTRY_ROTATION_OBSERVED", "counts": counts,
            "releases": releases, "port18181Open": _port_open(18181),
            "effects": {"mutationCount": 0, "sourceReadCount": 0, "providerInvocationCount": 0}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "prepare", "build", "qualify", "sign", "publish", "observe"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = globals()[args.action]()
        status = 0
    except RotationBlocked as exc:
        result = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.reason_code, "message": str(exc)}
        status = 2
    except Exception as exc:  # fail closed at the CLI boundary
        result = {"outcome": "SAFE_BLOCKED", "reasonCode": type(exc).__name__.upper(), "message": str(exc)}
        status = 2
    _write_once(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
