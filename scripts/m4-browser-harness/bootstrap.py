#!/usr/bin/env python3
"""Prepare deterministic M4 browser facts in an isolated PostgreSQL database.

This script is test support only. It executes the checked-in production asset
migration bodies, then seeds Cases through the production Service/Store and
TrustedEvidenceWriter. No HTTP route or Web runtime is replaced.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "services/aos-api"
sys.path.insert(0, str(API_ROOT))

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.integration_contracts import (
    INTEGRATION_EVIDENCE_ADAPTER,
    CreateIntegrationCaseRequest,
    EvidenceType,
)
from aos_api.asset_registry.integration_projection import (
    IntegrationExpiryProjector,
)
from aos_api.asset_registry.integration_reader import (
    PostgresIntegrationCaseReader,
    PrincipalMarkingResolver,
)
from aos_api.asset_registry.integration_service import (
    IntegrationCaseService,
    IntegrationRequestContext,
    TrustedEvidenceWriter,
    TrustedProducerContext,
)
from aos_api.asset_registry.integration_store import (
    PostgresIntegrationStore,
)
from aos_api.db import connect, init_schema

ORG = "dev-org"
PROJECT = "dev-project"
INSTALLATION_ID = uuid.UUID("73000000-0000-4000-8000-000000000002")
ZERO_HASH = "sha256:" + "0" * 64
MIGRATIONS = (
    "228asset0_registry.py",
    "228asset0_security.py",
    "228asset0_invariants.py",
    "228asset0_evidence_snapshot.py",
    "228asset1_composition_installation.py",
    "228asset2_integration_cases.py",
)


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load migration: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade_statements(path: Path, index: int) -> list[str]:
    statements: list[str] = []
    module = _load(path, f"m4_browser_migration_{index}")
    binding = MagicMock()
    binding.execute.return_value.mappings.return_value = []
    with (
        patch.object(module.op, "execute", statements.append),
        patch.object(module.op, "get_bind", return_value=binding),
    ):
        module.upgrade()
    return statements


def _apply_production_asset_migrations() -> None:
    version_root = API_ROOT / "alembic/versions"
    with connect() as conn:
        for index, filename in enumerate(MIGRATIONS):
            for statement in _upgrade_statements(version_root / filename, index):
                conn.execute(statement)
        conn.commit()


def _seed_active_installation() -> None:
    composition_pk = uuid.UUID("72000000-0000-4000-8000-000000000001")
    composition_id = uuid.UUID("72000000-0000-4000-8000-000000000002")
    installation_pk = uuid.UUID("73000000-0000-4000-8000-000000000001")
    request = {"requested": []}
    registry = {
        "schemaVersion": "aos.dev/registry-snapshot/v1alpha1",
        "candidates": [],
    }
    diff = {
        "baseline": {},
        "target": {},
        "added": {},
        "removed": {},
        "unchanged": {},
    }
    lock = {
        "lockSchemaVersion": "aos.dev/composition-lock/v1alpha1",
        "resolverVersion": "aos-resolver/1.0.0",
        "request": {},
        "registrySnapshotHash": ZERO_HASH,
        "resolved": [],
        "edges": [],
        "capabilityProviders": [],
        "permissionDiff": diff,
        "migrationPlan": diff,
        "contributionDiff": diff,
        "currentInstallationRef": None,
    }
    with connect() as conn:
        registry_hash = conn.execute(
            "SELECT canonical_bundle_control_sha256(%s::JSONB) AS hash",
            (Jsonb(registry),),
        ).fetchone()["hash"]
        request_hash = conn.execute(
            "SELECT canonical_bundle_control_sha256(%s::JSONB) AS hash",
            (Jsonb(request),),
        ).fetchone()["hash"]
        lock_hash = conn.execute(
            "SELECT canonical_bundle_control_sha256(%s::JSONB) AS hash",
            (Jsonb(lock),),
        ).fetchone()["hash"]
        diff_hash = conn.execute(
            "SELECT canonical_bundle_control_sha256(%s::JSONB) AS hash",
            (Jsonb(diff),),
        ).fetchone()["hash"]
        conn.execute(
            """INSERT INTO bundle_composition (
                 org_id,project_id,composition_pk,composition_id,request_json,
                 request_hash,registry_snapshot_json,registry_snapshot_hash,
                 resolver_version,created_by
               ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'aos-resolver/1.0.0','harness')""",
            (
                ORG,
                PROJECT,
                composition_pk,
                composition_id,
                Jsonb(request),
                request_hash,
                Jsonb(registry),
                registry_hash,
            ),
        )
        conn.execute(
            """INSERT INTO bundle_composition_lock (
                 org_id,project_id,composition_pk,revision,lock_payload,lock_hash,
                 permission_diff_json,permission_diff_hash,migration_plan_json,
                 migration_plan_hash,contribution_diff_json,
                 contribution_diff_hash,created_by
               ) VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s,'harness')""",
            (
                ORG,
                PROJECT,
                composition_pk,
                Jsonb(lock),
                lock_hash,
                Jsonb(diff),
                diff_hash,
                Jsonb(diff),
                diff_hash,
                Jsonb(diff),
                diff_hash,
            ),
        )
        for table in (
            "bundle_installation",
            "bundle_installation_revision",
            "bundle_installation_event",
        ):
            conn.execute(f"ALTER TABLE {table} DISABLE TRIGGER USER")
        conn.execute(
            """INSERT INTO bundle_installation (
                 org_id,project_id,installation_pk,installation_id,display_name,
                 current_revision,active_revision,previous_active_revision,
                 etag_version,created_by
               ) VALUES (%s,%s,%s,%s,'M4 browser installation',1,1,NULL,1,'harness')""",
            (ORG, PROJECT, installation_pk, INSTALLATION_ID),
        )
        conn.execute(
            """INSERT INTO bundle_installation_revision (
                 org_id,project_id,installation_pk,revision,parent_revision,state,
                 composition_pk,lock_revision,lock_hash,permission_diff_hash,
                 migration_plan_hash,contribution_diff_hash,overlay_revision,
                 requested_by
               ) VALUES (%s,%s,%s,1,NULL,'active',%s,1,%s,%s,%s,%s,
                         'overlay-m4-browser','harness')""",
            (
                ORG,
                PROJECT,
                installation_pk,
                composition_pk,
                lock_hash,
                diff_hash,
                diff_hash,
                diff_hash,
            ),
        )
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        conn.commit()


class _UuidSequence:
    def __init__(self) -> None:
        self._next = 1

    def __call__(self) -> uuid.UUID:
        value = uuid.UUID(f"74000000-0000-4000-8000-{self._next:012d}")
        self._next += 1
        return value


def _evidence(
    *,
    case_number: int,
    evidence_number: int,
    evidence_type: str,
    now: datetime,
    expires_at: datetime | None,
):
    if evidence_type == "source_connection":
        claims = {
            "connectionRef": f"connector:m4-{case_number}",
            "authMode": "oauth",
            "readProbe": True,
            "tenantBinding": True,
        }
        series = f"source:m4-{case_number}"
    else:
        claims = {
            "positiveTenant": f"tenant:m4-{case_number}",
            "negativeTenant": f"tenant:other-{case_number}",
            "crossTenantDenied": True,
        }
        series = f"tenant:m4-{case_number}"
    payload = {
        "evidenceId": f"75000000-0000-4000-8000-{evidence_number:012d}",
        "revision": 1,
        "evidenceType": evidence_type,
        "seriesKey": series,
        "subjectRef": series,
        "artifactRef": f"artifact:{series}",
        "artifactHash": ZERO_HASH,
        "outcome": "valid",
        "observedAt": now,
        "expiresAt": expires_at,
        "revokedAt": None,
        "requiredMarkings": ["public", "restricted"],
        "producer": "producer:m4-browser",
        "claims": claims,
        "recordedAt": now,
    }
    canonical = {
        **payload,
        "observedAt": now.isoformat().replace("+00:00", "Z"),
        "expiresAt": (
            expires_at.isoformat().replace("+00:00", "Z") if expires_at else None
        ),
        "recordedAt": now.isoformat().replace("+00:00", "Z"),
    }
    payload["evidenceHash"] = canonical_sha256(canonical)
    return INTEGRATION_EVIDENCE_ADAPTER.validate_python(payload)


def _seed_cases() -> dict[str, object]:
    ids = _UuidSequence()
    store = PostgresIntegrationStore(uuid_factory=ids)
    reader = PostgresIntegrationCaseReader()
    service = IntegrationCaseService(
        store=store,
        reader=reader,
        marking_resolver=PrincipalMarkingResolver(),
        expiry_projector=IntegrationExpiryProjector(),
    )
    context = IntegrationRequestContext(
        org_id=ORG,
        project_id=PROJECT,
        subject="operator:m4-browser",
        roles=(
            "integration-case-reader",
            "integration-case-maker",
            "integration-case-projector",
        ),
        markings=("public", "restricted"),
    )

    def create(name: str, key: str) -> str:
        receipt = service.create_case(
            context=context,
            request=CreateIntegrationCaseRequest.model_validate(
                {
                    "installationId": str(INSTALLATION_ID),
                    "overlayRevision": "overlay-m4-browser",
                    "displayName": name,
                }
            ),
            idempotency_key=key,
        )
        return str(receipt.response_json["caseId"])

    stable_id = create("M4 稳定连接案例", "m4-browser-create-stable")
    expiring_id = create("M4 可过期连接案例", "m4-browser-create-expiring")
    reference = store.create_reference_case(
        org_id=ORG,
        project_id=PROJECT,
        display_name="M4 脱敏参考案例",
    )

    writer = TrustedEvidenceWriter(
        store=store,
        context=TrustedProducerContext(
            org_id=ORG,
            project_id=PROJECT,
            producer="producer:m4-browser",
            markings=("public", "restricted"),
            evidence_types=(
                EvidenceType.SOURCE_CONNECTION,
                EvidenceType.TENANT_ISOLATION,
            ),
        ),
    )
    now = datetime.now(UTC).replace(microsecond=0)
    expiry_seconds = int(os.getenv("AOS_M4_EXPIRY_SECONDS", "120"))
    expires_at = now + timedelta(seconds=expiry_seconds)
    evidence_number = 1
    for case_number, case_id, source_expiry in (
        (1, stable_id, None),
        (2, expiring_id, expires_at),
    ):
        for evidence_type in ("source_connection", "tenant_isolation"):
            writer.write(
                case_id=case_id,
                evidence=_evidence(
                    case_number=case_number,
                    evidence_number=evidence_number,
                    evidence_type=evidence_type,
                    now=now,
                    expires_at=(
                        source_expiry if evidence_type == "source_connection" else None
                    ),
                ),
            )
            evidence_number += 1
    return {
        "orgId": ORG,
        "projectId": PROJECT,
        "installationId": str(INSTALLATION_ID),
        "stableCaseId": stable_id,
        "expiringCaseId": expiring_id,
        "referenceCaseId": reference.case_id,
        "expiresAt": expires_at.isoformat().replace("+00:00", "Z"),
    }


def main() -> None:
    output = Path(os.environ["AOS_M4_SEED_OUTPUT"])
    init_schema()
    _apply_production_asset_migrations()
    _seed_active_installation()
    result = _seed_cases()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"M4 browser seed ready: {output}")


if __name__ == "__main__":
    main()
