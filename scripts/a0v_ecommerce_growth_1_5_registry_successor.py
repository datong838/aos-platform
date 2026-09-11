#!/usr/bin/env python3
"""Publish the signed ecommerce growth 1.5 successor; preflight by default."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"
RECOVERY_ROOT = ROOT.parent / ".aos-recovery-20260912"
FIRST_INSTALL_STATE = (
    ROOT.parent
    / ".aos-recovery-20260910/state/a0v-canonical-ecommerce-first-install"
)
BUILD_DIR = RECOVERY_ROOT / "builds/ecommerce-runtime-1.5.0-v2"
BUILD_RECEIPT = RECOVERY_ROOT / "logs/ecommerce-runtime-1.5.0-build-v2.json"
QUALIFICATION_RECEIPT = (
    RECOVERY_ROOT / "logs/ecommerce-runtime-1.5.0-qualification-v2.json"
)
STATE_DIR = RECOVERY_ROOT / "state/ecommerce-growth-1.5.0-registry-successor-v2"
OUTPUT = RECOVERY_ROOT / "logs/ecommerce-growth-1.5.0-registry-successor-v2.json"
DOCKER_CONTEXT = "colima-aos-extension"
DATABASE_CONTAINER = "aos-a0v-recovery-pg"
DATABASE_NAME = "aos_meta_head"
PLATFORM = "linux/arm64"
SOURCE_ALIAS = "a0v-canonical"
TARGET_ID = "solution.ecommerce.growth"
TARGET_VERSION = "1.5.0"
SIGNING_KEY_ID = "a0v-local-ecommerce-canonical-v1"
CREATE_ROLES = frozenset({"asset-publisher", "asset-registry-admin", "developer"})
PUBLISH_ROLES = frozenset({"asset-publisher", "asset-registry-admin"})
PUBLISHER_SCOPES = frozenset({"aos"})
EXPECTED_EFFECTS = {
    "registryPublishCount": 0,
    "installationMutationCount": 0,
    "providerInvocationCount": 0,
    "externalPublicationCount": 0,
}
EXPECTED_TAMPER_REJECTIONS = (
    "imageIndexBytes",
    "imageDigest",
    "dependencyLock",
    "sbom",
    "backend",
    "schemaCompatibility",
    "schemaRequirements",
)
CURRENT_COORDINATES = (
    ("domain.ecommerce.core/1.1.0", "domain.ecommerce.core", "1.1.0"),
    ("platform.ecommerce.niushop/1.1.0", "platform.ecommerce.niushop", "1.1.0"),
    ("solution.ecommerce.growth/1.5.0", TARGET_ID, TARGET_VERSION),
    (
        "solution.ecommerce.operations-base/1.2.0",
        "solution.ecommerce.operations-base",
        "1.2.0",
    ),
)
HISTORICAL_COORDINATES = (
    ("domain.ecommerce.core/1.1.0", "domain.ecommerce.core", "1.1.0"),
    ("platform.ecommerce.niushop/1.1.0", "platform.ecommerce.niushop", "1.1.0"),
    ("solution.ecommerce.growth/1.4.0", TARGET_ID, "1.4.0"),
    (
        "solution.ecommerce.operations-base/1.2.0",
        "solution.ecommerce.operations-base",
        "1.2.0",
    ),
)


class SuccessorBlocked(RuntimeError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _load_script(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SuccessorBlocked("SCRIPT_UNAVAILABLE", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _builder() -> Any:
    return _load_script("growth_1_5_builder", ROOT / "scripts/build_ecommerce_runtime_candidates.py")


def _first_installer() -> Any:
    return _load_script(
        "growth_1_5_first_installer",
        ROOT / "scripts/a0v_canonical_ecommerce_first_install.py",
    )


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, reason: str) -> dict[str, Any]:
    try:
        value = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SuccessorBlocked(reason, str(path)) from exc
    if not isinstance(value, dict):
        raise SuccessorBlocked(reason, str(path))
    return value


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, stderr=subprocess.PIPE
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise SuccessorBlocked("SOURCE_REVISION_INVALID", "git verification failed") from exc


def _verify_source_revision(receipt_head: str) -> str:
    if not isinstance(receipt_head, str) or len(receipt_head) != 40:
        raise SuccessorBlocked("BUILD_RECEIPT_GIT_HEAD_INVALID", "invalid git head")
    current = _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", receipt_head, current)
    scoped = (
        "bundles/candidates/ecommerce/solution.ecommerce.growth/1.5.0",
        "bundles/candidates/ecommerce/domain.ecommerce.core/1.1.0",
        "bundles/candidates/ecommerce/platform.ecommerce.niushop/1.1.0",
        "bundles/candidates/ecommerce/solution.ecommerce.operations-base/1.2.0",
        "scripts/build_ecommerce_runtime_candidates.py",
    )
    if _git("diff", "--name-only", f"{receipt_head}..{current}", "--", *scoped):
        raise SuccessorBlocked(
            "CANDIDATE_SOURCE_ADVANCED_AFTER_BUILD", "candidate source advanced"
        )
    if _git("status", "--porcelain", "--untracked-files=all", "--", *scoped):
        raise SuccessorBlocked("CANDIDATE_SOURCE_DIRTY", "candidate source is dirty")
    return current


def verify_inputs(
    *, build_dir: Path, build_receipt_path: Path, qualification_receipt_path: Path
) -> dict[str, Any]:
    builder = _builder()
    try:
        build_dir = build_dir.resolve(strict=True)
    except OSError as exc:
        raise SuccessorBlocked("BUILD_OUTPUT_MISSING", str(build_dir)) from exc
    if build_dir == ROOT or build_dir.is_relative_to(ROOT):
        raise SuccessorBlocked("BUILD_OUTPUT_NOT_ISOLATED", str(build_dir))
    build = _read_json(build_receipt_path, "BUILD_RECEIPT_INVALID")
    qualification = _read_json(
        qualification_receipt_path, "QUALIFICATION_RECEIPT_INVALID"
    )
    if (
        build.get("outcome") != "BUILD_GREEN"
        or build.get("output") != str(build_dir)
        or build.get("outputTreeHash") != builder._tree_hash(build_dir)
        or build.get("contentHashes") != builder._content_hashes(build_dir)
        or build.get("effects") != EXPECTED_EFFECTS
        or (build.get("engine") or {}).get("platform") != PLATFORM
    ):
        raise SuccessorBlocked("BUILD_RECEIPT_MISMATCH", str(build_receipt_path))
    current_head = _verify_source_revision(build.get("gitHead"))
    expected = {
        "outcome": "QUALIFICATION_GREEN",
        "gitHead": build["gitHead"],
        "buildReceipt": str(build_receipt_path.resolve()),
        "buildReceiptHash": _sha256(build_receipt_path.resolve().read_bytes()),
        "outputTreeHash": build["outputTreeHash"],
        "moduleCount": 8,
        "runtimeMemberCount": 3,
        "ephemeralSignaturePersisted": False,
        "effects": EXPECTED_EFFECTS,
    }
    if any(qualification.get(key) != value for key, value in expected.items()):
        raise SuccessorBlocked(
            "QUALIFICATION_RECEIPT_MISMATCH", str(qualification_receipt_path)
        )
    if tuple(qualification.get("tamperRejections") or ()) != EXPECTED_TAMPER_REJECTIONS:
        raise SuccessorBlocked("QUALIFICATION_TAMPER_MATRIX_MISMATCH", "tamper drift")
    resolved = {
        (item.get("id"), item.get("version"))
        for item in qualification.get("resolved") or ()
        if isinstance(item, dict)
    }
    if resolved != {(bundle_id, version) for _, bundle_id, version in CURRENT_COORDINATES}:
        raise SuccessorBlocked("QUALIFICATION_RESOLUTION_MISMATCH", str(resolved))
    runtime_ids = {bundle_id for _, bundle_id, _ in CURRENT_COORDINATES[:3]}
    if set(qualification.get("runtimeAdmissions") or {}) != runtime_ids:
        raise SuccessorBlocked("RUNTIME_ADMISSIONS_MISMATCH", "runtime set drifted")
    if set(qualification.get("schemaRequirements") or {}) != runtime_ids:
        raise SuccessorBlocked("SCHEMA_REQUIREMENTS_MISMATCH", "schema set drifted")
    return {
        "outcome": "PREFLIGHT_GREEN",
        "mode": "preflight",
        "buildGitHead": build["gitHead"],
        "currentGitHead": current_head,
        "buildOutput": str(build_dir),
        "buildReceiptHash": _sha256(build_receipt_path.resolve().read_bytes()),
        "qualificationReceiptHash": _sha256(
            qualification_receipt_path.resolve().read_bytes()
        ),
        "outputTreeHash": build["outputTreeHash"],
        "contentHashes": build["contentHashes"],
        "effects": EXPECTED_EFFECTS.copy(),
    }


def _persistent_signer(first_state: Path) -> tuple[Ed25519PrivateKey, Path, str]:
    key_path = first_state.resolve() / "signing/registry-ed25519.pem"
    trust_path = first_state.resolve() / "signing/trust-roots.json"
    if (
        not key_path.is_file()
        or key_path.is_symlink()
        or stat.S_IMODE(key_path.stat().st_mode) != 0o600
    ):
        raise SuccessorBlocked("PERSISTENT_SIGNING_KEY_INVALID", str(key_path))
    try:
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise SuccessorBlocked("PERSISTENT_SIGNING_KEY_INVALID", str(key_path)) from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise SuccessorBlocked("PERSISTENT_SIGNING_KEY_INVALID", str(key_path))
    trust = _read_json(trust_path, "PERSISTENT_TRUST_ROOT_INVALID")
    roots = trust.get("trustRoots")
    if not isinstance(roots, list) or len(roots) != 1:
        raise SuccessorBlocked("PERSISTENT_TRUST_ROOT_INVALID", str(trust_path))
    root = roots[0]
    public = base64.b64encode(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    if (
        not isinstance(root, dict)
        or root.get("publisher") != "aos"
        or root.get("keyId") != SIGNING_KEY_ID
        or root.get("algorithm") != "Ed25519"
        or root.get("publicKey") != public
        or not isinstance(root.get("revision"), str)
    ):
        raise SuccessorBlocked("PERSISTENT_TRUST_ROOT_DRIFT", str(trust_path))
    return key, trust_path, root["revision"]


def prepare_successor_signed_tree(
    *, build_dir: Path, first_state: Path, state_dir: Path
) -> dict[str, Any]:
    builder = _builder()
    key, trust_path, trust_revision = _persistent_signer(first_state)
    source = first_state.resolve() / "signed-bundles-v4"
    target = state_dir.resolve() / "signed-bundles-v5"
    if not source.is_dir() or source.is_symlink():
        raise SuccessorBlocked("HISTORICAL_SIGNED_TREE_INVALID", str(source))
    sys.path.insert(0, str(API_ROOT))
    try:
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.release_policy import ReleasePolicy
        from aos_api.asset_registry.signature import FileTrustRootProvider

        trust = FileTrustRootProvider(trust_path).snapshot()
        policy = ReleasePolicy(trust_roots=trust)
        historical_loader = ManifestLoader({SOURCE_ALIAS: source}, trust_roots=trust)
        historical_hashes: dict[str, str] = {}
        for relative, bundle_id, version in HISTORICAL_COORDINATES:
            loaded = historical_loader.load(f"bundle://{SOURCE_ALIAS}/{relative}")
            policy.evaluate(builder._release_record(loaded), checked_at=datetime.now(UTC))
            historical_hashes[f"{bundle_id}@{version}"] = loaded.content_hash
        if not target.exists():
            state_dir.resolve().mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = Path(
                tempfile.mkdtemp(prefix="signed-bundles-v5-", dir=state_dir.resolve())
            )
            try:
                shutil.copytree(source, temporary, dirs_exist_ok=True)
                shutil.copytree(build_dir.resolve(strict=True), temporary, dirs_exist_ok=True)
                unsigned = ManifestLoader({SOURCE_ALIAS: temporary})
                signed_at = datetime.now(UTC).isoformat()
                for relative, _bundle_id, _version in CURRENT_COORDINATES:
                    signature_path = temporary / relative / "bundle.signature.json"
                    signature_path.unlink(missing_ok=True)
                    loaded = unsigned.load(f"bundle://{SOURCE_ALIAS}/{relative}")
                    signature_path.write_text(
                        json.dumps(
                            {
                                "algorithm": "Ed25519",
                                "keyId": SIGNING_KEY_ID,
                                "signature": base64.b64encode(
                                    key.sign(builder._signature_payload(loaded))
                                ).decode("ascii"),
                                "signedAt": signed_at,
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                temporary.replace(target)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary, ignore_errors=True)
        loader = ManifestLoader({SOURCE_ALIAS: target}, trust_roots=trust)
        all_hashes: dict[str, str] = {}
        validation_coordinates = (
            *HISTORICAL_COORDINATES,
            ("solution.ecommerce.growth/1.5.0", TARGET_ID, TARGET_VERSION),
        )
        loaded_coordinates = [
            (
                loader.load(f"bundle://{SOURCE_ALIAS}/{relative}"),
                bundle_id,
                version,
            )
            for relative, bundle_id, version in validation_coordinates
        ]
        checked_at = datetime.now(UTC)
        for loaded, bundle_id, version in loaded_coordinates:
            policy.evaluate(builder._release_record(loaded), checked_at=checked_at)
            all_hashes[f"{bundle_id}@{version}"] = loaded.content_hash
        if any(all_hashes[key] != value for key, value in historical_hashes.items()):
            raise SuccessorBlocked("HISTORICAL_SIGNED_CONTENT_DRIFT", str(target))
        expected_current = builder._content_hashes(build_dir.resolve())
        for _relative, bundle_id, version in CURRENT_COORDINATES:
            if all_hashes[f"{bundle_id}@{version}"] != expected_current[bundle_id]:
                raise SuccessorBlocked("SUCCESSOR_SIGNED_CONTENT_DRIFT", bundle_id)
        return {
            "keyId": SIGNING_KEY_ID,
            "trustRootRevision": trust_revision,
            "trustRootsPath": str(trust_path),
            "signedBundleRoot": str(target),
            "coordinates": all_hashes,
        }
    finally:
        sys.path.remove(str(API_ROOT))


def _database_counts(connect: Any) -> dict[str, int]:
    with connect() as conn:
        row = conn.execute(
            """SELECT
                 (SELECT count(*) FROM asset_bundle_version v JOIN asset_bundle b
                   ON b.bundle_pk=v.bundle_pk WHERE b.publisher='aos'
                    AND b.bundle_id=%s AND v.version=%s) AS target_versions,
                 (SELECT count(*) FROM bundle_installation) AS installations,
                 (SELECT count(*) FROM bundle_installation
                   WHERE org_id='org-org' AND project_id='dev-project') AS positive,
                 (SELECT count(*) FROM bundle_installation
                   WHERE org_id='dev-org' AND project_id='dev-project') AS canary""",
            (TARGET_ID, TARGET_VERSION),
        ).fetchone()
    return {key: int(row[key]) for key in row.keys()}


def _database_backup(*, context: str, container: str, state_dir: Path) -> dict[str, Any]:
    if context != DOCKER_CONTEXT or container != DATABASE_CONTAINER:
        raise SuccessorBlocked("DATABASE_TARGET_MISMATCH", container)
    try:
        inspected = json.loads(
            subprocess.check_output(
                ["docker", "--context", context, "inspect", "--format", "{{json .}}", container],
                text=True,
                stderr=subprocess.PIPE,
                timeout=15,
            )
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise SuccessorBlocked("DATABASE_CONTAINER_UNAVAILABLE", container) from exc
    environment = {}
    for item in (inspected.get("Config") or {}).get("Env") or ():
        if isinstance(item, str) and "=" in item:
            name, value = item.split("=", 1)
            environment[name] = value
    user = environment.get("POSTGRES_USER", "postgres")
    directory = state_dir.resolve() / "backups"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    target = directory / "aos_meta_head-pre-growth-1.5-registry.dump"
    if not target.exists():
        temporary = target.with_name(target.name + ".tmp-" + uuid.uuid4().hex)
        try:
            with temporary.open("xb") as handle:
                completed = subprocess.run(
                    [
                        "docker", "--context", context, "exec", container,
                        "pg_dump", "-U", user, "--dbname", DATABASE_NAME,
                        "--format=custom", "--no-owner", "--no-privileges",
                    ],
                    stdout=handle,
                    stderr=subprocess.PIPE,
                    timeout=120,
                    check=False,
                )
            if completed.returncode != 0 or temporary.stat().st_size <= 0:
                raise SuccessorBlocked("DATABASE_BACKUP_FAILED", str(target))
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return {"path": str(target), "size": target.stat().st_size, "sha256": _sha256(target.read_bytes())}


def publish_successor(*, connect: Any, signed_root: Path, trust_path: Path) -> dict[str, Any]:
    first = _first_installer()
    sys.path.insert(0, str(API_ROOT))
    try:
        from aos_api.asset_registry.errors import AssetNotFoundError
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.registry_service import RegistryService
        from aos_api.asset_registry.registry_store import PostgresRegistryStore
        from aos_api.asset_registry.signature import FileTrustRootProvider

        trust = FileTrustRootProvider(trust_path).snapshot()
        loader = ManifestLoader({SOURCE_ALIAS: signed_root}, trust_roots=trust)
        store = PostgresRegistryStore(connect_factory=connect)
        service = RegistryService(
            store=store,
            loader=loader,
            clock=lambda: _database_clock(connect),
            trust_roots=trust,
        )
        historical = store.get_version(TARGET_ID, "1.4.0", publisher="aos")
        if str(historical.get("status", "")).lower() != "published":
            raise SuccessorBlocked("HISTORICAL_RELEASE_NOT_PUBLISHED", TARGET_ID)
        source_ref = f"bundle://{SOURCE_ALIAS}/{TARGET_ID}/{TARGET_VERSION}"
        loaded = loader.load(source_ref)
        expected = first._expected_registry_version(loaded)
        mutations = {"versionCreateCount": 0, "validateCount": 0, "publishCount": 0}
        try:
            current = store.get_version(TARGET_ID, TARGET_VERSION, publisher="aos")
        except AssetNotFoundError:
            current = service.create_version(
                publisher="aos",
                bundle_id=TARGET_ID,
                source_ref=source_ref,
                actor="a0v-growth-1.5-version-creator",
                roles=CREATE_ROLES,
                publisher_scopes=PUBLISHER_SCOPES,
            )
            mutations["versionCreateCount"] += 1
        try:
            first.assert_registry_version_exact(current, expected)
        except first.FirstInstallBlocked as exc:
            raise SuccessorBlocked(exc.reason_code, str(exc)) from exc
        status = str(current.get("status", "")).lower()
        if status == "draft":
            current = service.validate(
                publisher="aos", bundle_id=TARGET_ID, version=TARGET_VERSION,
                actor="a0v-growth-1.5-validator", roles=CREATE_ROLES,
                publisher_scopes=PUBLISHER_SCOPES,
            )
            mutations["validateCount"] += 1
            status = str(current.get("status", "")).lower()
        if status == "validated":
            current = service.publish(
                publisher="aos", bundle_id=TARGET_ID, version=TARGET_VERSION,
                actor="a0v-growth-1.5-publisher", roles=PUBLISH_ROLES,
                publisher_scopes=PUBLISHER_SCOPES,
            )
            mutations["publishCount"] += 1
            status = str(current.get("status", "")).lower()
        if status != "published":
            raise SuccessorBlocked("SUCCESSOR_NOT_PUBLISHED", status)
        final = store.get_version(TARGET_ID, TARGET_VERSION, publisher="aos")
        try:
            first.assert_registry_version_exact(final, expected)
        except first.FirstInstallBlocked as exc:
            raise SuccessorBlocked(exc.reason_code, str(exc)) from exc
        return {"bundleId": TARGET_ID, "version": TARGET_VERSION, "status": status,
                "contentHash": loaded.content_hash, "mutations": mutations}
    finally:
        sys.path.remove(str(API_ROOT))


def _database_clock(connect: Any) -> datetime:
    with connect() as conn:
        return conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]


def configure_runtime_env(*, env_path: Path, signed_root: Path, trust_path: Path, state_dir: Path) -> dict[str, Any]:
    expected = {
        "AOS_BUNDLE_ROOT": str(signed_root.resolve()),
        "AOS_BUNDLE_TRUST_ROOTS_FILE": str(trust_path.resolve()),
        "AOS_EXTENSION_RUNTIME_PLATFORM": PLATFORM,
    }
    raw = env_path.read_bytes() if env_path.exists() else b""
    lines = raw.decode("utf-8").splitlines()
    seen: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key in expected:
            if key in seen:
                raise SuccessorBlocked("RUNTIME_ENV_DUPLICATE", key)
            seen[key] = value.strip().strip('"').strip("'")
    drift = [key for key, value in seen.items() if value != expected[key]]
    if drift:
        raise SuccessorBlocked("RUNTIME_ENV_DRIFT", ",".join(sorted(drift)))
    missing = [key for key in expected if key not in seen]
    if missing:
        backup_dir = state_dir.resolve() / "config-backups"
        backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(backup_dir, 0o700)
        backup = backup_dir / "aos-platform.env.before-growth-1.5"
        if not backup.exists():
            descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(raw)
        addition = "" if not lines or lines[-1] == "" else "\n"
        updated = raw.decode("utf-8") + addition + "\n".join(
            f"{key}={expected[key]}" for key in missing
        ) + "\n"
        temporary = env_path.with_name(env_path.name + ".tmp-" + uuid.uuid4().hex)
        temporary.write_text(updated, encoding="utf-8")
        if env_path.exists():
            os.chmod(temporary, stat.S_IMODE(env_path.stat().st_mode))
        temporary.replace(env_path)
    return {
        "path": str(env_path.resolve()),
        "configuredKeys": sorted(expected),
        "addedKeys": sorted(missing),
        "sha256": _sha256(env_path.read_bytes()),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database-name")
    parser.add_argument("--docker-context", default=DOCKER_CONTEXT)
    parser.add_argument("--database-container", default=DATABASE_CONTAINER)
    parser.add_argument("--build-dir", type=Path, default=BUILD_DIR)
    parser.add_argument("--build-receipt", type=Path, default=BUILD_RECEIPT)
    parser.add_argument("--qualification-receipt", type=Path, default=QUALIFICATION_RECEIPT)
    parser.add_argument("--first-state", type=Path, default=FIRST_INSTALL_STATE)
    parser.add_argument("--state-dir", type=Path, default=STATE_DIR)
    parser.add_argument("--env-path", type=Path, default=ROOT / ".env")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, Any]:
    evidence = verify_inputs(
        build_dir=args.build_dir,
        build_receipt_path=args.build_receipt,
        qualification_receipt_path=args.qualification_receipt,
    )
    _persistent_signer(args.first_state)
    historical = args.first_state.resolve() / "signed-bundles-v4"
    if not historical.is_dir() or historical.is_symlink():
        raise SuccessorBlocked("HISTORICAL_SIGNED_TREE_INVALID", str(historical))
    evidence["persistentPreflight"] = {
        "firstState": str(args.first_state.resolve()),
        "historicalSignedRoot": str(historical),
        "ready": True,
    }
    if not args.apply:
        return evidence
    if args.database_name != DATABASE_NAME:
        raise SuccessorBlocked("EXPLICIT_ISOLATED_DATABASE_REQUIRED", DATABASE_NAME)
    first = _first_installer()
    connect = first.container_database_connect_factory(
        context=args.docker_context,
        container=args.database_container,
        database_name=args.database_name,
    )
    before = _database_counts(connect)
    evidence["databaseBackup"] = _database_backup(
        context=args.docker_context,
        container=args.database_container,
        state_dir=args.state_dir,
    )
    signing = prepare_successor_signed_tree(
        build_dir=args.build_dir,
        first_state=args.first_state,
        state_dir=args.state_dir,
    )
    evidence["signing"] = signing
    publication = publish_successor(
        connect=connect,
        signed_root=Path(signing["signedBundleRoot"]),
        trust_path=Path(signing["trustRootsPath"]),
    )
    after = _database_counts(connect)
    if after["target_versions"] != 1:
        raise SuccessorBlocked("SUCCESSOR_REGISTRY_CARDINALITY_INVALID", str(after))
    for key in ("installations", "positive", "canary"):
        if after[key] != before[key]:
            raise SuccessorBlocked("INSTALLATION_MUTATION_DETECTED", key)
    evidence["registry"] = publication
    evidence["databaseCounts"] = {"before": before, "after": after}
    evidence["runtimeEnvironment"] = configure_runtime_env(
        env_path=args.env_path,
        signed_root=Path(signing["signedBundleRoot"]),
        trust_path=Path(signing["trustRootsPath"]),
        state_dir=args.state_dir,
    )
    evidence["mode"] = "apply"
    evidence["outcome"] = "GROWTH_1_5_REGISTRY_SUCCESSOR_PUBLISHED"
    evidence["effects"] = {
        "canonicalRegistry": publication["mutations"],
        "installationMutationCount": 0,
        "providerInvocationCount": 0,
        "externalPublicationCount": 0,
    }
    return evidence


def _write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    temporary.write_text(raw, encoding="utf-8")
    temporary.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run(args)
    except SuccessorBlocked as exc:
        result = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.reason_code, "message": str(exc)}
        code = 2
    except Exception as exc:
        result = {
            "outcome": "SAFE_BLOCKED",
            "reasonCode": "UNEXPECTED_DOMAIN_ERROR",
            "errorType": type(exc).__name__,
            "message": str(exc),
        }
        code = 2
    else:
        code = 0
    _write_result(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
