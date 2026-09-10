#!/usr/bin/env python3
"""A0-V canonical ecommerce first install; preflight is the default mode."""

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
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "services/aos-api"
RECOVERY_ROOT = REPOSITORY_ROOT.parent / ".aos-recovery-20260910"
DEFAULT_BUILD_DIR = (
    RECOVERY_ROOT / "builds/a0v-ecommerce-runtime-candidates-20260910-v4"
)
DEFAULT_BUILD_RECEIPT = (
    RECOVERY_ROOT / "logs/a0v-ecommerce-runtime-candidate-build-v4.json"
)
DEFAULT_QUALIFICATION_RECEIPT = (
    RECOVERY_ROOT / "logs/a0v-ecommerce-runtime-candidate-qualification-v4.json"
)
BUILDER_PATH = REPOSITORY_ROOT / "scripts/build_ecommerce_runtime_candidates.py"
SCOPED_SOURCE_PATHS = (
    "bundles/candidates/ecommerce/domain.ecommerce.core/1.1.0",
    "bundles/candidates/ecommerce/platform.ecommerce.niushop/1.1.0",
    "bundles/candidates/ecommerce/solution.ecommerce.growth/1.4.0",
    "bundles/candidates/ecommerce/solution.ecommerce.operations-base/1.2.0",
    "scripts/build_ecommerce_runtime_candidates.py",
)
ORG_ID = "org-org"
PROJECT_ID = "dev-project"
CANARY_ORG_ID = "dev-org"
CANARY_PROJECT_ID = "dev-project"
EXPECTED_DATABASE = "aos_meta_head"
PLATFORM = "linux/arm64"
DOCKER_CONTEXT = "colima-aos-extension"
DATABASE_CONTAINER = "aos-a0v-recovery-pg"
STATE_ROOT = RECOVERY_ROOT / "state/a0v-canonical-ecommerce-first-install"
SIGNING_KEY_ID = "a0v-local-ecommerce-canonical-v1"
SIGNING_NOT_BEFORE = datetime(2026, 1, 1, tzinfo=UTC)
SIGNING_NOT_AFTER = datetime(2036, 1, 1, tzinfo=UTC)
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
REGISTRY_CREATE_ROLES = frozenset({"asset-publisher", "asset-registry-admin", "developer"})
REGISTRY_PUBLISH_ROLES = frozenset({"asset-publisher", "asset-registry-admin"})
PUBLISHER_SCOPES = frozenset({"aos"})
INSTALL_MAKER = "a0v-canonical-ecommerce-first-install-maker"
INSTALL_CHECKER = "a0v-canonical-ecommerce-first-install-checker"
INSTALL_MAKER_ROLES = frozenset({"asset-installer"})
INSTALL_CHECKER_ROLES = frozenset({"asset-install-approver"})
INSTALL_MARKINGS = frozenset()
INSTALL_IDEMPOTENCY_PREFIX = "a0v-canonical-ecommerce-first-install-v1"


class FirstInstallBlocked(RuntimeError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database-name")
    parser.add_argument("--docker-context", default=DOCKER_CONTEXT)
    parser.add_argument("--database-container", default=DATABASE_CONTAINER)
    parser.add_argument("--state-dir", type=Path, default=STATE_ROOT)
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR)
    parser.add_argument("--build-receipt", type=Path, default=DEFAULT_BUILD_RECEIPT)
    parser.add_argument(
        "--qualification-receipt",
        type=Path,
        default=DEFAULT_QUALIFICATION_RECEIPT,
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, reason_code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FirstInstallBlocked(reason_code, str(path)) from exc
    if not isinstance(value, dict):
        raise FirstInstallBlocked(reason_code, str(path))
    return value


def _load_builder() -> Any:
    spec = importlib.util.spec_from_file_location("a0v_candidate_builder", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise FirstInstallBlocked("BUILDER_UNAVAILABLE", str(BUILDER_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(*arguments: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *arguments], cwd=REPOSITORY_ROOT, text=True, stderr=subprocess.PIPE
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise FirstInstallBlocked("SOURCE_REVISION_INVALID", "git verification failed") from exc


def _verify_source_revision(receipt_head: str) -> str:
    if not isinstance(receipt_head, str) or len(receipt_head) != 40:
        raise FirstInstallBlocked("BUILD_RECEIPT_GIT_HEAD_INVALID", "invalid git head")
    current_head = _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", receipt_head, current_head)
    if _git("diff", "--name-only", f"{receipt_head}..{current_head}", "--", *SCOPED_SOURCE_PATHS):
        raise FirstInstallBlocked(
            "CANDIDATE_SOURCE_ADVANCED_AFTER_BUILD",
            "candidate source or builder changed after the bound build",
        )
    if _git("status", "--porcelain", "--untracked-files=all", "--", *SCOPED_SOURCE_PATHS):
        raise FirstInstallBlocked(
            "CANDIDATE_SOURCE_DIRTY", "candidate source or builder has local changes"
        )
    return current_head


def verify_v4_inputs(
    *, build_dir: Path, build_receipt_path: Path, qualification_receipt_path: Path
) -> dict[str, Any]:
    builder = _load_builder()
    try:
        build_dir = build_dir.resolve(strict=True)
    except OSError as exc:
        raise FirstInstallBlocked("BUILD_OUTPUT_MISSING", str(build_dir)) from exc
    if build_dir == REPOSITORY_ROOT or build_dir.is_relative_to(REPOSITORY_ROOT):
        raise FirstInstallBlocked("BUILD_OUTPUT_NOT_ISOLATED", str(build_dir))
    build_receipt_path = build_receipt_path.resolve(strict=True)
    qualification_receipt_path = qualification_receipt_path.resolve(strict=True)
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
        raise FirstInstallBlocked("BUILD_RECEIPT_MISMATCH", str(build_receipt_path))
    current_head = _verify_source_revision(build.get("gitHead"))
    expected_qualification = {
        "outcome": "QUALIFICATION_GREEN",
        "gitHead": build["gitHead"],
        "buildReceipt": str(build_receipt_path),
        "buildReceiptHash": _sha256(build_receipt_path.read_bytes()),
        "outputTreeHash": build["outputTreeHash"],
        "moduleCount": 8,
        "runtimeMemberCount": 3,
        "ephemeralSignaturePersisted": False,
        "effects": EXPECTED_EFFECTS,
    }
    for key, expected in expected_qualification.items():
        if qualification.get(key) != expected:
            raise FirstInstallBlocked(
                "QUALIFICATION_RECEIPT_MISMATCH", f"qualification field drift: {key}"
            )
    if tuple(qualification.get("tamperRejections") or ()) != EXPECTED_TAMPER_REJECTIONS:
        raise FirstInstallBlocked(
            "QUALIFICATION_TAMPER_MATRIX_MISMATCH", "tamper matrix drifted"
        )
    resolved = {
        (item.get("id"), item.get("version"))
        for item in qualification.get("resolved") or ()
        if isinstance(item, dict)
    }
    expected_resolved = {
        ("domain.ecommerce.core", "1.1.0"),
        ("platform.ecommerce.niushop", "1.1.0"),
        ("solution.ecommerce.growth", "1.4.0"),
        ("solution.ecommerce.operations-base", "1.2.0"),
    }
    if resolved != expected_resolved:
        raise FirstInstallBlocked("QUALIFICATION_RESOLUTION_MISMATCH", str(resolved))
    schema_requirements = qualification.get("schemaRequirements")
    runtime_admissions = qualification.get("runtimeAdmissions")
    if not isinstance(schema_requirements, dict) or set(schema_requirements) != {
        item[0] for item in expected_resolved if item[0] != "solution.ecommerce.operations-base"
    }:
        raise FirstInstallBlocked("SCHEMA_REQUIREMENTS_MISMATCH", "runtime schema set drifted")
    if not isinstance(runtime_admissions, dict) or set(runtime_admissions) != set(
        schema_requirements
    ):
        raise FirstInstallBlocked("RUNTIME_ADMISSIONS_MISMATCH", "runtime set drifted")
    return {
        "outcome": "PREFLIGHT_GREEN",
        "mode": "preflight",
        "orgId": ORG_ID,
        "projectId": PROJECT_ID,
        "canaryOrgId": CANARY_ORG_ID,
        "canaryProjectId": CANARY_PROJECT_ID,
        "buildGitHead": build["gitHead"],
        "currentGitHead": current_head,
        "buildOutput": str(build_dir),
        "buildReceiptHash": _sha256(build_receipt_path.read_bytes()),
        "qualificationReceiptHash": _sha256(qualification_receipt_path.read_bytes()),
        "outputTreeHash": build["outputTreeHash"],
        "contentHashes": build["contentHashes"],
        "runtimeAdmissions": runtime_admissions,
        "schemaRequirements": schema_requirements,
        "moduleCount": 8,
        "runtimeMemberCount": 3,
        "effects": EXPECTED_EFFECTS,
    }


def inspect_isolated_database(connect_factory: Any) -> dict[str, Any]:
    builder = _load_builder()
    with connect_factory() as conn:
        identity = conn.execute(
            "SELECT current_database() AS database_name, current_user AS database_user"
        ).fetchone()
        if identity is None or identity["database_name"] != EXPECTED_DATABASE:
            raise FirstInstallBlocked(
                "DATABASE_IDENTITY_MISMATCH", str((identity or {}).get("database_name"))
            )
        revision_rows = conn.execute(
            "SELECT version_num FROM alembic_version ORDER BY version_num"
        ).fetchall()
        revisions = [row["version_num"] for row in revision_rows]
        if revisions != [builder.SCHEMA_COMPATIBILITY_REVISION]:
            raise FirstInstallBlocked("ALEMBIC_REVISION_MISMATCH", str(revisions))
        relation_rows = conn.execute(
            """
            SELECT table_schema || '.' || table_name AS relation
              FROM information_schema.tables
             WHERE table_schema = 'public'
            """
        ).fetchall()
        relations = {row["relation"] for row in relation_rows}
        missing = sorted(set(builder.SCHEMA_COMPATIBILITY_RELATIONS) - relations)
        if missing:
            raise FirstInstallBlocked("REQUIRED_RELATION_MISSING", ",".join(missing))
        roles = {}
        for role in ("aos_app", "aos_runtime", "aos_extension_maintainer"):
            row = conn.execute(
                """
                SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=%s) AS exists,
                       pg_has_role(current_user,%s,'MEMBER') AS member
                """,
                (role, role),
            ).fetchone()
            roles[role] = {"exists": bool(row["exists"]), "member": bool(row["member"])}
        if not all(item["exists"] and item["member"] for item in roles.values()):
            raise FirstInstallBlocked("DATABASE_CONTROL_ROLE_UNAVAILABLE", str(roles))
        target_versions = conn.execute(
            """
            SELECT b.bundle_id, v.version, v.status, v.content_hash
              FROM asset_bundle b
              JOIN asset_bundle_version v ON v.bundle_pk=b.bundle_pk
             WHERE b.publisher='aos' AND (
                   (b.bundle_id='domain.ecommerce.core' AND v.version='1.1.0') OR
                   (b.bundle_id='platform.ecommerce.niushop' AND v.version='1.1.0') OR
                   (b.bundle_id='solution.ecommerce.growth' AND v.version='1.4.0') OR
                   (b.bundle_id='solution.ecommerce.operations-base' AND v.version='1.2.0'))
             ORDER BY b.bundle_id
            """
        ).fetchall()
        tenant = conn.execute(
            """
            SELECT
              (SELECT count(*) FROM bundle_composition
                WHERE org_id=%s AND project_id=%s) AS compositions,
              (SELECT count(*) FROM bundle_installation
                WHERE org_id=%s AND project_id=%s) AS installations,
              (SELECT count(*) FROM bundle_installation_revision
                WHERE org_id=%s AND project_id=%s AND state='active') AS active_revisions,
              (SELECT count(*) FROM extension_runtime_operation
                WHERE org_id=%s AND project_id=%s) AS runtime_operations,
              (SELECT count(*) FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s) AS runtime_bindings
            """,
            (ORG_ID, PROJECT_ID) * 5,
        ).fetchone()
        canary = conn.execute(
            """
            SELECT
              (SELECT count(*) FROM bundle_installation
                WHERE org_id=%s AND project_id=%s) AS installations,
              (SELECT count(*) FROM extension_runtime_operation
                WHERE org_id=%s AND project_id=%s) AS runtime_operations,
              (SELECT count(*) FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s) AS runtime_bindings
            """,
            (CANARY_ORG_ID, CANARY_PROJECT_ID) * 3,
        ).fetchone()
        if any(int(canary[key]) for key in canary.keys()):
            raise FirstInstallBlocked("CANARY_TENANT_NOT_EMPTY", str(dict(canary)))
        if int(tenant["active_revisions"]) != 0:
            raise FirstInstallBlocked("UNKNOWN_ACTIVE_INSTALLATION", str(dict(tenant)))
        if len(target_versions) not in {0, 4}:
            raise FirstInstallBlocked(
                "PARTIAL_CANONICAL_REGISTRY_BASELINE", str(len(target_versions))
            )
        return {
            "databaseName": identity["database_name"],
            "alembicRevisions": revisions,
            "requiredRelationCount": len(builder.SCHEMA_COMPATIBILITY_RELATIONS),
            "controlRoles": roles,
            "targetVersions": [dict(row) for row in target_versions],
            "tenantCounts": dict(tenant),
            "canaryCounts": dict(canary),
        }


def inspect_runtime_configuration_authority(connect_factory: Any) -> dict[str, Any]:
    """Read potential current four-source authority before runtime ownership starts."""
    with connect_factory() as conn:
        row = conn.execute(
            """
            SELECT
              (SELECT count(*) FROM aip_responsibility_plan_head h
                 JOIN aip_responsibility_plan_revision r
                   ON r.org_id=h.org_id AND r.project_id=h.project_id
                  AND r.plan_id=h.plan_id AND r.revision=h.current_revision
                WHERE h.org_id=%s AND h.project_id=%s
                  AND r.lifecycle='frozen') AS responsibility_plans,
              (SELECT count(*) FROM aip_runtime_policy_head h
                 JOIN aip_runtime_policy_revision r
                   ON r.org_id=h.org_id AND r.project_id=h.project_id
                  AND r.runtime_policy_id=h.runtime_policy_id
                  AND r.revision=h.current_revision
                WHERE h.org_id=%s AND h.project_id=%s
                  AND r.lifecycle='active') AS runtime_policies,
              (SELECT count(*) FROM aip_runtime_guard_policy_head h
                 JOIN aip_runtime_guard_policy_revision r
                   ON r.org_id=h.org_id AND r.project_id=h.project_id
                  AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id
                  AND r.revision=h.current_revision
                WHERE h.org_id=%s AND h.project_id=%s
                  AND h.policy_kind='data_classification' AND r.lifecycle='active'
                  AND r.effective_from<=clock_timestamp()
                  AND r.effective_until>clock_timestamp()) AS data_policies,
              (SELECT count(*) FROM aip_runtime_guard_policy_head h
                 JOIN aip_runtime_guard_policy_revision r
                   ON r.org_id=h.org_id AND r.project_id=h.project_id
                  AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id
                  AND r.revision=h.current_revision
                WHERE h.org_id=%s AND h.project_id=%s
                  AND h.policy_kind='egress' AND r.lifecycle='active'
                  AND r.effective_from<=clock_timestamp()
                  AND r.effective_until>clock_timestamp()) AS egress_policies,
              (SELECT count(*) FROM aip_network_policy_head h
                 JOIN aip_network_policy_revision r
                   ON r.org_id=h.org_id AND r.project_id=h.project_id
                  AND r.policy_id=h.policy_id AND r.revision=h.current_revision
                WHERE h.org_id=%s AND h.project_id=%s
                  AND r.lifecycle='active' AND r.effective_from<=clock_timestamp()
                  AND r.effective_until>clock_timestamp()) AS network_policies,
              (SELECT count(*) FROM aip_model_governance_policy_head h
                 JOIN aip_model_governance_policy_revision r
                   ON r.org_id=h.org_id AND r.project_id=h.project_id
                  AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id
                  AND r.revision=h.current_revision
                WHERE h.org_id=%s AND h.project_id=%s
                  AND h.policy_kind='quota' AND r.lifecycle='active'
                  AND r.effective_from<=clock_timestamp()
                  AND r.effective_until>clock_timestamp()) AS quota_policies,
              (SELECT count(*) FROM aip_model_governance_policy_head h
                 JOIN aip_model_governance_policy_revision r
                   ON r.org_id=h.org_id AND r.project_id=h.project_id
                  AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id
                  AND r.revision=h.current_revision
                WHERE h.org_id=%s AND h.project_id=%s
                  AND h.policy_kind='budget' AND r.lifecycle='active'
                  AND r.effective_from<=clock_timestamp()
                  AND r.effective_until>clock_timestamp()) AS budget_policies,
              (SELECT count(*) FROM aip_budget_head h
                 JOIN aip_budget_revision r
                   ON r.org_id=h.org_id AND r.project_id=h.project_id
                  AND r.budget_id=h.budget_id AND r.revision=h.current_revision
                WHERE h.org_id=%s AND h.project_id=%s
                  AND r.lifecycle='active' AND r.effective_from<=clock_timestamp()
                  AND r.effective_until>clock_timestamp()) AS budgets
            """,
            (ORG_ID, PROJECT_ID) * 8,
        ).fetchone()
    if row is None:
        raise FirstInstallBlocked(
            "RUNTIME_CONFIGURATION_AUTHORITY_INSPECTION_FAILED", "empty authority result"
        )
    counts = {key: int(row[key]) for key in row.keys()}
    blockers = [key for key, count in counts.items() if count < 1]
    return {"counts": counts, "blockers": blockers, "ready": not blockers}


def container_database_connect_factory(
    *, context: str, container: str, database_name: str
) -> Any:
    if (context, container, database_name) != (
        DOCKER_CONTEXT,
        DATABASE_CONTAINER,
        EXPECTED_DATABASE,
    ):
        raise FirstInstallBlocked("DATABASE_TARGET_MISMATCH", "database target is not exact")
    try:
        raw = subprocess.check_output(
            [
                "docker",
                "--context",
                context,
                "inspect",
                "--format",
                "{{json .}}",
                container,
            ],
            text=True,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        inspected = json.loads(raw)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise FirstInstallBlocked("DATABASE_CONTAINER_UNAVAILABLE", container) from exc
    if (
        inspected.get("Name") != "/" + container
        or not (inspected.get("State") or {}).get("Running")
    ):
        raise FirstInstallBlocked("DATABASE_CONTAINER_IDENTITY_MISMATCH", container)
    bindings = ((inspected.get("NetworkSettings") or {}).get("Ports") or {}).get(
        "5432/tcp"
    )
    if not isinstance(bindings, list) or len(bindings) != 1:
        raise FirstInstallBlocked("DATABASE_PORT_BINDING_INVALID", container)
    host_port = bindings[0].get("HostPort")
    if not isinstance(host_port, str) or not host_port.isdigit():
        raise FirstInstallBlocked("DATABASE_PORT_BINDING_INVALID", container)
    environment = {}
    for entry in (inspected.get("Config") or {}).get("Env") or ():
        if isinstance(entry, str) and "=" in entry:
            name, value = entry.split("=", 1)
            environment[name] = value
    user = environment.get("POSTGRES_USER", "postgres")
    password = environment.get("POSTGRES_PASSWORD")
    if not password:
        raise FirstInstallBlocked("DATABASE_CREDENTIAL_UNAVAILABLE", container)

    @contextmanager
    def connect():
        import psycopg
        from psycopg.rows import dict_row

        try:
            with psycopg.connect(
                host="127.0.0.1",
                port=int(host_port),
                dbname=database_name,
                user=user,
                password=password,
                row_factory=dict_row,
            ) as connection:
                yield connection
        except psycopg.Error as exc:
            raise FirstInstallBlocked(
                "DATABASE_CONNECTION_FAILED", "isolated database connection failed"
            ) from exc

    return connect


def create_pre_mutation_backup(
    *, context: str, container: str, database_name: str, state_dir: Path
) -> dict[str, Any]:
    if (context, container, database_name) != (
        DOCKER_CONTEXT,
        DATABASE_CONTAINER,
        EXPECTED_DATABASE,
    ):
        raise FirstInstallBlocked("BACKUP_TARGET_MISMATCH", "backup target is not exact")
    backup_dir = state_dir.resolve() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(backup_dir, 0o700)
    try:
        inspected = json.loads(
            subprocess.check_output(
                [
                    "docker",
                    "--context",
                    context,
                    "inspect",
                    "--format",
                    "{{json .}}",
                    container,
                ],
                text=True,
                stderr=subprocess.PIPE,
                timeout=15,
            )
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise FirstInstallBlocked("DATABASE_CONTAINER_UNAVAILABLE", container) from exc
    environment = {}
    for entry in (inspected.get("Config") or {}).get("Env") or ():
        if isinstance(entry, str) and "=" in entry:
            name, value = entry.split("=", 1)
            environment[name] = value
    database_user = environment.get("POSTGRES_USER", "postgres")
    target = backup_dir / "aos_meta_head-pre-canonical-first-install.dump"
    if not target.exists():
        temporary = target.with_name(target.name + ".tmp-" + uuid.uuid4().hex)
        try:
            with temporary.open("xb") as handle:
                completed = subprocess.run(
                    [
                        "docker",
                        "--context",
                        context,
                        "exec",
                        container,
                        "pg_dump",
                        "-U",
                        database_user,
                        "--dbname",
                        database_name,
                        "--format=custom",
                        "--no-owner",
                        "--no-privileges",
                    ],
                    stdout=handle,
                    stderr=subprocess.PIPE,
                    timeout=120,
                    check=False,
                )
            if completed.returncode != 0:
                raise FirstInstallBlocked("DATABASE_BACKUP_FAILED", "pg_dump failed")
            if temporary.stat().st_size <= 0:
                raise FirstInstallBlocked("DATABASE_BACKUP_EMPTY", str(temporary))
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    raw_hash = _sha256(target.read_bytes())
    if target.stat().st_size <= 0:
        raise FirstInstallBlocked("DATABASE_BACKUP_EMPTY", str(target))
    return {"path": str(target), "size": target.stat().st_size, "sha256": raw_hash}


def _private_key(path: Path) -> Ed25519PrivateKey:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    if not path.exists():
        key = Ed25519PrivateKey.generate()
        raw = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != 0o600 or not path.is_file() or path.is_symlink():
        raise FirstInstallBlocked("SIGNING_KEY_PERMISSIONS_INVALID", oct(mode))
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise FirstInstallBlocked("SIGNING_KEY_INVALID", str(path)) from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise FirstInstallBlocked("SIGNING_KEY_INVALID", str(path))
    return key


def prepare_persistent_signed_tree(*, build_dir: Path, state_dir: Path) -> dict[str, Any]:
    sys.path.insert(0, str(API_ROOT))
    builder = _load_builder()
    try:
        from aos_api.asset_registry.canonical_json import canonical_sha256
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.release_policy import ReleasePolicy
        from aos_api.asset_registry.signature import FileTrustRootProvider

        signing_dir = state_dir.resolve() / "signing"
        key_path = signing_dir / "registry-ed25519.pem"
        trust_path = signing_dir / "trust-roots.json"
        signed_root = state_dir.resolve() / "signed-bundles-v4"
        key = _private_key(key_path)
        public = key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        root_fields = {
            "publisher": "aos",
            "keyId": SIGNING_KEY_ID,
            "algorithm": "Ed25519",
            "publicKey": base64.b64encode(public).decode("ascii"),
            "notBefore": SIGNING_NOT_BEFORE.isoformat(),
            "notAfter": SIGNING_NOT_AFTER.isoformat(),
            "revokedAt": None,
        }
        root_fields["revision"] = canonical_sha256(root_fields)
        trust_document = {"trustRoots": [root_fields]}
        trust_raw = (
            json.dumps(trust_document, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        if trust_path.exists() and trust_path.read_bytes() != trust_raw:
            raise FirstInstallBlocked("TRUST_ROOT_DRIFT", str(trust_path))
        if not trust_path.exists():
            trust_path.write_bytes(trust_raw)
            os.chmod(trust_path, 0o600)
        provider = FileTrustRootProvider(trust_path).snapshot()
        if not signed_root.exists():
            temporary = Path(
                tempfile.mkdtemp(prefix="signed-bundles-v4-", dir=state_dir.resolve())
            )
            try:
                shutil.copytree(build_dir, temporary, dirs_exist_ok=True)
                unsigned = ManifestLoader({"a0v-canonical": temporary})
                signed_at = datetime.now(UTC).isoformat()
                for relative, bundle_id, _version, _package in builder.ALL_CASES:
                    loaded = unsigned.load(f"bundle://a0v-canonical/{relative}")
                    signature = {
                        "algorithm": "Ed25519",
                        "keyId": SIGNING_KEY_ID,
                        "signature": base64.b64encode(
                            key.sign(builder._signature_payload(loaded))
                        ).decode("ascii"),
                        "signedAt": signed_at,
                    }
                    (temporary / relative / "bundle.signature.json").write_text(
                        json.dumps(signature, sort_keys=True, separators=(",", ":"))
                        + "\n",
                        encoding="utf-8",
                    )
                temporary.replace(signed_root)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary, ignore_errors=True)
        loader = ManifestLoader({"a0v-canonical": signed_root}, trust_roots=provider)
        policy = ReleasePolicy(trust_roots=provider)
        loaded_bundles = [
            loader.load(f"bundle://a0v-canonical/{relative}")
            for relative, _bundle_id, _version, _package in builder.ALL_CASES
        ]
        content_hashes = {}
        checked_at = datetime.now(UTC)
        for loaded, (_relative, bundle_id, _version, _package) in zip(
            loaded_bundles, builder.ALL_CASES, strict=True
        ):
            policy.evaluate(builder._release_record(loaded), checked_at=checked_at)
            content_hashes[bundle_id] = loaded.content_hash
        if content_hashes != builder._content_hashes(build_dir):
            raise FirstInstallBlocked("SIGNED_TREE_CONTENT_MISMATCH", str(signed_root))
        return {
            "keyId": SIGNING_KEY_ID,
            "trustRootRevision": root_fields["revision"],
            "privateKeyPath": str(key_path),
            "privateKeyMode": "0600",
            "trustRootsPath": str(trust_path),
            "signedBundleRoot": str(signed_root),
            "contentHashes": content_hashes,
        }
    finally:
        sys.path.remove(str(API_ROOT))


def _expected_registry_version(loaded: Any) -> dict[str, Any]:
    from aos_api.asset_registry.canonical_json import canonical_sha256

    return {
        "sourceRef": loaded.source_ref,
        "contentHash": loaded.content_hash,
        "manifestHash": canonical_sha256(
            loaded.manifest.model_dump(mode="json", by_alias=True, exclude_none=False)
        ),
        "artifacts": sorted(
            (
                {
                    "relativePath": item.relative_path,
                    "artifactRef": item.artifact_ref,
                    "digest": item.digest,
                }
                for item in loaded.artifacts
            ),
            key=lambda item: item["artifactRef"],
        ),
    }


def _comparable_registry_version(record: dict[str, Any]) -> dict[str, Any]:
    from aos_api.asset_registry.canonical_json import canonical_sha256

    source_artifacts = sorted(
        record.get("artifacts", []), key=lambda item: item.get("artifactRef", "")
    )
    artifacts = [
        {
            "relativePath": item.get("relativePath"),
            "artifactRef": item.get("artifactRef"),
            "digest": item.get("digest"),
        }
        for item in source_artifacts
    ]
    source_ref = record.get("sourceRef")
    if source_ref is None:
        refs = {
            item["artifactRef"][: -(len(item["relativePath"]) + 1)]
            for item in artifacts
            if isinstance(item["relativePath"], str)
            and isinstance(item["artifactRef"], str)
            and item["artifactRef"].endswith("/" + item["relativePath"])
        }
        source_ref = next(iter(refs)) if len(refs) == 1 else None
    manifest_hash = record.get("manifestHash")
    if manifest_hash is None and isinstance(record.get("manifest"), dict):
        manifest_hash = canonical_sha256(record["manifest"])
    return {
        "sourceRef": source_ref,
        "contentHash": record.get("contentHash"),
        "manifestHash": manifest_hash,
        "artifacts": artifacts,
    }


def assert_registry_version_exact(
    existing: dict[str, Any], expected: dict[str, Any]
) -> None:
    if _comparable_registry_version(existing) != expected:
        raise FirstInstallBlocked(
            "EXISTING_VERSION_DRIFT", "existing canonical version is not exact"
        )


def publish_canonical_releases(*, connect_factory: Any, state_dir: Path) -> dict[str, Any]:
    sys.path.insert(0, str(API_ROOT))
    builder = _load_builder()
    try:
        from aos_api.asset_registry.errors import AssetNotFoundError
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.registry_service import RegistryService
        from aos_api.asset_registry.registry_store import PostgresRegistryStore
        from aos_api.asset_registry.signature import FileTrustRootProvider

        signed_root = state_dir.resolve() / "signed-bundles-v4"
        trust_path = state_dir.resolve() / "signing/trust-roots.json"
        trust = FileTrustRootProvider(trust_path).snapshot()
        loader = ManifestLoader({"a0v-canonical": signed_root}, trust_roots=trust)
        store = PostgresRegistryStore(connect_factory=connect_factory)

        def database_clock() -> datetime:
            with connect_factory() as conn:
                return conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]

        service = RegistryService(
            store=store, loader=loader, clock=database_clock, trust_roots=trust
        )
        published = []
        mutations = {
            "bundleCreateCount": 0,
            "versionCreateCount": 0,
            "validateCount": 0,
            "publishCount": 0,
        }
        for relative, bundle_id, version, _package in builder.ALL_CASES:
            source_ref = f"bundle://a0v-canonical/{relative}"
            loaded = loader.load(source_ref)
            manifest = loaded.manifest
            try:
                bundle = store.get_bundle(bundle_id, publisher="aos")
            except AssetNotFoundError:
                bundle = service.create_bundle(
                    publisher="aos",
                    bundle_id=bundle_id,
                    kind=manifest.kind,
                    display_name=manifest.metadata.display_name,
                    actor=f"a0v-first-install-{bundle_id}-bundle-creator",
                    roles=REGISTRY_CREATE_ROLES,
                    publisher_scopes=PUBLISHER_SCOPES,
                )
                mutations["bundleCreateCount"] += 1
            if (
                bundle.get("publisher") != "aos"
                or bundle.get("bundleId") != bundle_id
                or bundle.get("kind") != manifest.kind.value
                or bundle.get("displayName") != manifest.metadata.display_name
            ):
                raise FirstInstallBlocked("EXISTING_BUNDLE_DRIFT", bundle_id)
            expected = _expected_registry_version(loaded)
            try:
                current = store.get_version(bundle_id, version, publisher="aos")
            except AssetNotFoundError:
                current = service.create_version(
                    publisher="aos",
                    bundle_id=bundle_id,
                    source_ref=source_ref,
                    actor=f"a0v-first-install-{bundle_id}-version-creator",
                    roles=REGISTRY_CREATE_ROLES,
                    publisher_scopes=PUBLISHER_SCOPES,
                )
                mutations["versionCreateCount"] += 1
            assert_registry_version_exact(current, expected)
            status = str(current.get("status", "")).lower()
            if status == "draft":
                current = service.validate(
                    publisher="aos",
                    bundle_id=bundle_id,
                    version=version,
                    actor=f"a0v-first-install-{bundle_id}-validator",
                    roles=REGISTRY_CREATE_ROLES,
                    publisher_scopes=PUBLISHER_SCOPES,
                )
                mutations["validateCount"] += 1
                status = str(current.get("status", "")).lower()
            if status == "validated":
                current = service.publish(
                    publisher="aos",
                    bundle_id=bundle_id,
                    version=version,
                    actor=f"a0v-first-install-{bundle_id}-publisher",
                    roles=REGISTRY_PUBLISH_ROLES,
                    publisher_scopes=PUBLISHER_SCOPES,
                )
                mutations["publishCount"] += 1
                status = str(current.get("status", "")).lower()
            if status != "published":
                raise FirstInstallBlocked("CANONICAL_VERSION_NOT_PUBLISHED", bundle_id)
            final = store.get_version(bundle_id, version, publisher="aos")
            assert_registry_version_exact(final, expected)
            published.append(
                {
                    "bundleId": bundle_id,
                    "version": version,
                    "status": "published",
                    "contentHash": loaded.content_hash,
                }
            )
        return {"versions": published, "mutations": mutations}
    finally:
        sys.path.remove(str(API_ROOT))


def create_approved_first_installation(
    *, connect_factory: Any, state_dir: Path
) -> dict[str, Any]:
    sys.path.insert(0, str(API_ROOT))
    try:
        from aos_api.asset_registry.composition_contracts import (
            ApproveInstallationRequest,
            CompositionRequest,
            CreateInstallationRequest,
            EmptyInstallationActionRequest,
            InstallationResponse,
            StoredCompositionLock,
        )
        from aos_api.asset_registry.composition_service import CompositionService
        from aos_api.asset_registry.composition_store import PostgresCompositionStore
        from aos_api.asset_registry.installation_revalidation import (
            InstallationRevalidator,
        )
        from aos_api.asset_registry.installation_service import InstallationService
        from aos_api.asset_registry.installation_store import PostgresInstallationStore
        from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
        from aos_api.asset_registry.release_policy import ReleasePolicy
        from aos_api.asset_registry.signature import FileTrustRootProvider
        from aos_api.extension_runtime.release_revalidation import (
            RuntimeReleaseRevalidator,
        )

        trust = FileTrustRootProvider(
            state_dir.resolve() / "signing/trust-roots.json"
        ).snapshot()
        policy = ReleasePolicy(trust_roots=trust)
        installation_store = PostgresInstallationStore(connect_factory=connect_factory)
        composition_store = PostgresCompositionStore(connect_factory=connect_factory)
        snapshot_reader = RegistrySnapshotReader(
            connect_factory=connect_factory, release_policy=policy
        )
        composition_service = CompositionService(
            snapshot_reader=snapshot_reader,
            composition_store=composition_store,
            command_store=installation_store,
            baseline_reader=installation_store,
        )
        snapshot = snapshot_reader.read()
        request = CompositionRequest.model_validate(
            {
                "requested": [
                    {
                        "publisher": "aos",
                        "id": "platform.ecommerce.niushop",
                        "version": "1.1.0",
                    },
                    {
                        "publisher": "aos",
                        "id": "solution.ecommerce.growth",
                        "version": "1.4.0",
                    },
                    {
                        "publisher": "aos",
                        "id": "solution.ecommerce.operations-base",
                        "version": "1.2.0",
                    },
                ],
                "platformApiVersion": "1.7.0",
                "platformRelease": "aos-platform/1.7.0",
                "environment": "dev",
                "registrySnapshotHash": snapshot.snapshot_hash,
                "currentInstallationRef": None,
            }
        )
        composition_receipt = composition_service.resolve(
            request=request,
            org_id=ORG_ID,
            project_id=PROJECT_ID,
            actor=INSTALL_MAKER,
            roles=INSTALL_MAKER_ROLES,
            markings=INSTALL_MARKINGS,
            idempotency_key=f"{INSTALL_IDEMPOTENCY_PREFIX}-composition",
        )
        lock = StoredCompositionLock.model_validate_json(
            json.dumps(composition_receipt.response_json, default=str)
        )
        expected_coordinates = {
            ("domain.ecommerce.core", "1.1.0"),
            ("platform.ecommerce.niushop", "1.1.0"),
            ("solution.ecommerce.growth", "1.4.0"),
            ("solution.ecommerce.operations-base", "1.2.0"),
        }
        coordinates = {(item.id, item.version) for item in lock.payload.resolved}
        if coordinates != expected_coordinates:
            raise FirstInstallBlocked("COMPOSITION_RESOLUTION_DRIFT", str(coordinates))
        if lock.payload.current_installation_ref is not None or len(lock.payload.edges) != 3:
            raise FirstInstallBlocked("COMPOSITION_BASELINE_DRIFT", lock.lock_hash)
        contribution_count = sum(
            len(item.contributions) for item in lock.payload.resolved
        )
        module_count = sum(
            1
            for item in lock.payload.resolved
            for contribution in item.contributions
            if contribution.kind == "ui"
            and contribution.slot == "workshop.primary.ecommerce"
        )
        if module_count != 8:
            raise FirstInstallBlocked(
                "COMPOSITION_MODULE_INVENTORY_DRIFT", str(module_count)
            )
        runtime_revalidator = RuntimeReleaseRevalidator(release_policy=policy)
        service = InstallationService(
            store=installation_store,
            composition_store=composition_store,
            revalidator=InstallationRevalidator(release_policy=policy),
            planning_revalidator=runtime_revalidator,
        )
        created = service.create(
            request=CreateInstallationRequest.model_validate(
                {
                    "compositionId": lock.composition_id,
                    "lockRevision": lock.revision,
                    "overlayRevision": "a0v-canonical-ecommerce-v1",
                    "displayName": "A0-V Canonical 电商八工作台首装",
                }
            ),
            org_id=ORG_ID,
            project_id=PROJECT_ID,
            actor=INSTALL_MAKER,
            roles=INSTALL_MAKER_ROLES,
            markings=INSTALL_MARKINGS,
            idempotency_key=f"{INSTALL_IDEMPOTENCY_PREFIX}-create",
        )
        initial = InstallationResponse.model_validate_json(
            json.dumps(created.response_json, default=str)
        )
        installation_id = initial.installation_id
        current = installation_store.get_installation(
            org_id=ORG_ID, project_id=PROJECT_ID, installation_id=installation_id
        )
        transitions = []
        if current.state == "draft":
            service.submit(
                installation_id=installation_id,
                request=EmptyInstallationActionRequest(),
                org_id=ORG_ID,
                project_id=PROJECT_ID,
                actor=INSTALL_MAKER,
                roles=INSTALL_MAKER_ROLES,
                markings=INSTALL_MARKINGS,
                idempotency_key=f"{INSTALL_IDEMPOTENCY_PREFIX}-submit",
                if_match=f'"{current.etag_version}"',
            )
            transitions.append("submit")
            current = installation_store.get_installation(
                org_id=ORG_ID, project_id=PROJECT_ID, installation_id=installation_id
            )
        if current.state == "submitted":
            service.approve(
                installation_id=installation_id,
                request=ApproveInstallationRequest.model_validate(
                    {
                        "lockHash": lock.lock_hash,
                        "permissionDiffHash": lock.permission_diff_hash,
                        "migrationPlanHash": lock.migration_plan_hash,
                        "contributionDiffHash": lock.contribution_diff_hash,
                    }
                ),
                org_id=ORG_ID,
                project_id=PROJECT_ID,
                actor=INSTALL_CHECKER,
                roles=INSTALL_CHECKER_ROLES,
                markings=INSTALL_MARKINGS,
                idempotency_key=f"{INSTALL_IDEMPOTENCY_PREFIX}-approve",
                if_match=f'"{current.etag_version}"',
            )
            transitions.append("approve")
            current = installation_store.get_installation(
                org_id=ORG_ID, project_id=PROJECT_ID, installation_id=installation_id
            )
        if current.state not in {"approved", "applied", "active"}:
            raise FirstInstallBlocked("INSTALLATION_NOT_APPROVED", current.state)
        return {
            "snapshotHash": snapshot.snapshot_hash,
            "compositionId": lock.composition_id,
            "lockRevision": lock.revision,
            "lockHash": lock.lock_hash,
            "permissionDiffHash": lock.permission_diff_hash,
            "migrationPlanHash": lock.migration_plan_hash,
            "contributionDiffHash": lock.contribution_diff_hash,
            "resolved": [
                {
                    "bundleId": item.id,
                    "version": item.version,
                    "contentHash": item.content_hash,
                    "selectionReason": item.selection_reason,
                }
                for item in lock.payload.resolved
            ],
            "edgeCount": len(lock.payload.edges),
            "contributionCount": contribution_count,
            "moduleCount": module_count,
            "installationId": installation_id,
            "installationState": current.state,
            "installationRevision": current.current_revision,
            "installationEtag": current.etag_version,
            "transitions": transitions,
            "maker": INSTALL_MAKER,
            "checker": INSTALL_CHECKER,
        }
    finally:
        sys.path.remove(str(API_ROOT))


def run(args: argparse.Namespace) -> dict[str, Any]:
    evidence = verify_v4_inputs(
        build_dir=args.build_dir,
        build_receipt_path=args.build_receipt,
        qualification_receipt_path=args.qualification_receipt,
    )
    if not args.apply:
        return evidence
    if args.database_name != EXPECTED_DATABASE:
        raise FirstInstallBlocked(
            "EXPLICIT_ISOLATED_DATABASE_REQUIRED", EXPECTED_DATABASE
        )
    connect = container_database_connect_factory(
        context=args.docker_context,
        container=args.database_container,
        database_name=args.database_name,
    )
    evidence["database"] = inspect_isolated_database(connect)
    evidence["backup"] = create_pre_mutation_backup(
        context=args.docker_context,
        container=args.database_container,
        database_name=args.database_name,
        state_dir=args.state_dir,
    )
    evidence["signing"] = prepare_persistent_signed_tree(
        build_dir=args.build_dir.resolve(strict=True), state_dir=args.state_dir
    )
    registry = publish_canonical_releases(
        connect_factory=connect, state_dir=args.state_dir
    )
    evidence["candidateBuildEffects"] = evidence.pop("effects")
    evidence["published"] = registry["versions"]
    evidence["effects"] = {
        "canonicalRegistry": registry["mutations"],
        "installationMutationCount": 0,
        "providerInvocationCount": 0,
        "externalPublicationCount": 0,
    }
    prior_installation_count = int(evidence["database"]["tenantCounts"]["installations"])
    evidence["installation"] = create_approved_first_installation(
        connect_factory=connect, state_dir=args.state_dir
    )
    evidence["effects"]["installationMutationCount"] = len(
        evidence["installation"]["transitions"]
    ) + (1 if prior_installation_count == 0 else 0)
    evidence["runtimeConfigurationAuthority"] = inspect_runtime_configuration_authority(
        connect
    )
    if not evidence["runtimeConfigurationAuthority"]["ready"]:
        evidence["mode"] = "apply-runtime-configuration-precondition"
        evidence["outcome"] = "RUNTIME_CONFIGURATION_AUTHORITY_BLOCKED"
        return evidence
    evidence["mode"] = "apply-installation-approved"
    evidence["outcome"] = "CANONICAL_INSTALLATION_APPROVED"
    return evidence


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        evidence = run(args)
    except FirstInstallBlocked as exc:
        evidence = {
            "outcome": "SAFE_BLOCKED",
            "reasonCode": exc.reason_code,
            "message": str(exc),
        }
        status = 2
    else:
        status = 0
    rendered = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
