"""Real PostgreSQL coverage for the M4 Integration Case Store."""

from __future__ import annotations

import importlib.util
import os
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import psycopg
import pytest
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    EvidenceIntegrityCorruptError,
    EvidenceReferenceInvalidError,
    IdempotencyConflictError,
    RevisionConflictError,
)
from aos_api.asset_registry.integration_contracts import (
    CreateIntegrationCaseRequest,
    SourceConnectionEvidence,
)
from aos_api.asset_registry.integration_store import (
    IntegrationCommandResult,
    PostgresIntegrationStore,
)
from aos_api.db import connect
from psycopg import sql
from psycopg.types.json import Jsonb

API_ROOT = Path(__file__).resolve().parents[2]
BASE_MIGRATIONS = (
    API_ROOT / "alembic/versions/228asset0_registry.py",
    API_ROOT / "alembic/versions/228asset0_security.py",
    API_ROOT / "alembic/versions/228asset0_invariants.py",
    API_ROOT / "alembic/versions/228asset0_evidence_snapshot.py",
    API_ROOT / "alembic/versions/228asset1_composition_installation.py",
)
M4_MIGRATION = Path(
    os.environ.get(
        "AOS_M4_MIGRATION_PATH",
        API_ROOT / "alembic/versions/228asset2_integration_cases.py",
    )
)
ORG = "org-store"
PROJECT = "project-store"
INSTALLATION_ID = uuid.UUID("53000000-0000-4000-8000-000000000002")
ZERO_HASH = "sha256:" + "0" * 64
START = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _statements(path: Path, name: str) -> list[str]:
    result: list[str] = []
    module = _load_module(path, name)
    fake = MagicMock()
    fake.execute.return_value.mappings.return_value = []
    with (
        patch.object(module.op, "execute", result.append),
        patch.object(module.op, "get_bind", return_value=fake),
    ):
        module.upgrade()
    return result


@contextmanager
def _schema() -> Iterator[Callable[[], object]]:
    if not M4_MIGRATION.exists():
        pytest.skip(
            "M4 migration is supplied by W1 and is not present before integration"
        )
    schema = f"integration_store_{uuid.uuid4().hex}"
    try:
        with connect() as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            for index, path in enumerate((*BASE_MIGRATIONS, M4_MIGRATION)):
                for statement in _statements(path, f"store_migration_{index}"):
                    conn.execute(statement)
            conn.commit()
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")

    @contextmanager
    def scoped_connect():
        with connect() as conn:
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            yield conn

    try:
        yield scoped_connect
    finally:
        with connect() as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )
            conn.commit()


def _seed_active_installation(connect_factory: Callable[[], object]) -> None:
    composition_pk = uuid.UUID("52000000-0000-4000-8000-000000000001")
    composition_id = uuid.UUID("52000000-0000-4000-8000-000000000002")
    installation_pk = uuid.UUID("53000000-0000-4000-8000-000000000001")
    request, registry = (
        {"requested": []},
        {
            "schemaVersion": "aos.dev/registry-snapshot/v1alpha1",
            "candidates": [],
        },
    )
    diff = {"baseline": {}, "target": {}, "added": {}, "removed": {}, "unchanged": {}}
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
    with connect_factory() as conn:
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
               ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'aos-resolver/1.0.0','test')""",
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
               ) VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s,'test')""",
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
            conn.execute(
                sql.SQL("ALTER TABLE {} DISABLE TRIGGER USER").format(
                    sql.Identifier(table)
                )
            )
        conn.execute(
            """INSERT INTO bundle_installation (
                 org_id,project_id,installation_pk,installation_id,display_name,
                 current_revision,active_revision,previous_active_revision,
                 etag_version,created_by
               ) VALUES (%s,%s,%s,%s,'active',1,1,NULL,1,'test')""",
            (ORG, PROJECT, installation_pk, INSTALLATION_ID),
        )
        conn.execute(
            """INSERT INTO bundle_installation_revision (
                 org_id,project_id,installation_pk,revision,parent_revision,state,
                 composition_pk,lock_revision,lock_hash,permission_diff_hash,
                 migration_plan_hash,contribution_diff_hash,overlay_revision,
                 requested_by
               ) VALUES (%s,%s,%s,1,NULL,'active',%s,1,%s,%s,%s,%s,
                         'overlay-v1','test')""",
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


class _Clock:
    def __init__(self) -> None:
        self.value = START

    def __call__(self) -> datetime:
        return self.value

    def advance(self) -> None:
        self.value += timedelta(seconds=1)


def _evidence(
    when: datetime, *, revision: int = 1, evidence_id: str | None = None
) -> SourceConnectionEvidence:
    payload = {
        "evidenceId": evidence_id or "54000000-0000-4000-8000-000000000001",
        "revision": revision,
        "evidenceType": "source_connection",
        "seriesKey": "连接器:微信小店",
        "subjectRef": "connector:weixin",
        "artifactRef": "artifact:连接器",
        "artifactHash": ZERO_HASH,
        "outcome": "valid",
        "observedAt": when,
        "expiresAt": None,
        "revokedAt": None,
        "requiredMarkings": [],
        "producer": "producer:测试",
        "claims": {
            "connectionRef": "connector:weixin",
            "authMode": "oauth",
            "readProbe": True,
            "tenantBinding": True,
        },
        "recordedAt": when,
    }
    hash_payload = dict(payload)
    hash_payload["observedAt"] = when.isoformat().replace("+00:00", "Z")
    hash_payload["recordedAt"] = when.isoformat().replace("+00:00", "Z")
    payload["evidenceHash"] = canonical_sha256(hash_payload)
    return SourceConnectionEvidence.model_validate(payload)


def _create(store: PostgresIntegrationStore):
    return store.create_current_case(
        org_id=ORG,
        project_id=PROJECT,
        request=CreateIntegrationCaseRequest.model_validate(
            {
                "installationId": str(INSTALLATION_ID),
                "overlayRevision": "overlay-v1",
                "displayName": "微信小店 · 达人任务",
            }
        ),
        owner="owner:运营",
        required_markings=["internal"],
    )


def test_create_restart_evidence_project_and_reference_isolation() -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        clock = _Clock()
        store = PostgresIntegrationStore(connect_factory, clock=clock)
        created = _create(store)
        assert created.current_revision == created.etag_version == 1
        assert created.computed_stage.value == "planned"

        restarted = PostgresIntegrationStore(connect_factory, clock=clock)
        assert (
            restarted.get_case(org_id=ORG, project_id=PROJECT, case_id=created.case_id)
            == created
        )
        with pytest.raises(AssetNotFoundError):
            restarted.get_case(
                org_id="other-org", project_id=PROJECT, case_id=created.case_id
            )

        clock.advance()
        first = _evidence(clock.value)
        restarted.append_evidence(
            org_id=ORG, project_id=PROJECT, case_id=created.case_id, evidence=first
        )
        clock.advance()
        second = _evidence(clock.value, revision=2, evidence_id=first.evidence_id)
        restarted.append_evidence(
            org_id=ORG,
            project_id=PROJECT,
            case_id=created.case_id,
            evidence=second,
        )
        clock.advance()
        projected = restarted.project_case(
            org_id=ORG,
            project_id=PROJECT,
            case_id=created.case_id,
            if_match_etag=1,
            cause="evidence_added",
        )
        assert projected.response.etag_version == 2
        assert projected.response.snapshot_revision == 2
        assert projected.response.evidence_count == 1
        assert projected.metrics.connector_count == 1
        assert (
            restarted.get_case(
                org_id=ORG, project_id=PROJECT, case_id=created.case_id
            ).current_revision
            == 2
        )

        reference = restarted.create_reference_case(
            org_id=ORG, project_id=PROJECT, display_name="脱敏参考案例"
        )
        assert reference.installation_id is None
        assert restarted.reference_counts(org_id=ORG, project_id=PROJECT) == (1, 1)


def test_tenant_composite_fk_rejects_cross_project_binding() -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        store = PostgresIntegrationStore(connect_factory, clock=_Clock())
        created = _create(store)
        with connect_factory() as conn:
            with pytest.raises(psycopg.IntegrityError):
                conn.execute(
                    """INSERT INTO integration_instance (
                         org_id,project_id,instance_pk,case_pk,current_revision,
                         etag_version
                       ) VALUES (%s,'other-project',%s,%s,1,1)""",
                    (ORG, uuid.uuid4(), created.case_pk),
                )
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
            conn.rollback()


def test_receipt_replay_conflict_and_same_etag_concurrency() -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        clock = _Clock()
        store = PostgresIntegrationStore(connect_factory, clock=clock)
        created = _create(store)
        request = {"caseId": created.case_id}

        def handler(conn: object) -> IntegrationCommandResult:
            case = conn.execute(
                """SELECT case_pk FROM integration_case
                     WHERE org_id=%s AND project_id=%s AND case_id=%s""",
                (ORG, PROJECT, uuid.UUID(created.case_id)),
            ).fetchone()
            return IntegrationCommandResult(
                case_pk=case["case_pk"],
                status_code=200,
                response_json={"caseId": created.case_id, "etagVersion": 1},
                response_etag='"1"',
            )

        receipt = store.execute_idempotent(
            org_id=ORG,
            project_id=PROJECT,
            operation="integration_cases.create",
            idempotency_key="create-1",
            subject="owner:test",
            request_json=request,
            if_match_etag=None,
            handler=handler,
        )
        replay = store.execute_idempotent(
            org_id=ORG,
            project_id=PROJECT,
            operation="integration_cases.create",
            idempotency_key="create-1",
            subject="owner:test",
            request_json=request,
            if_match_etag=None,
            handler=lambda _conn: pytest.fail("replay must not execute handler"),
        )
        assert not receipt.replayed and replay.replayed
        with pytest.raises(IdempotencyConflictError):
            store.execute_idempotent(
                org_id=ORG,
                project_id=PROJECT,
                operation="integration_cases.create",
                idempotency_key="create-1",
                subject="owner:test",
                request_json={"different": True},
                if_match_etag=None,
                handler=handler,
            )

        clock.advance()
        outcomes: list[str] = []

        def project() -> None:
            try:
                store.project_case(
                    org_id=ORG,
                    project_id=PROJECT,
                    case_id=created.case_id,
                    if_match_etag=1,
                )
                outcomes.append("ok")
            except RevisionConflictError:
                outcomes.append("conflict")

        workers = [threading.Thread(target=project) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        assert sorted(outcomes) == ["conflict", "ok"]


def test_unicode_number_null_hash_and_corruption_fail_closed() -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        clock = _Clock()
        store = PostgresIntegrationStore(connect_factory, clock=clock)
        created = _create(store)
        clock.advance()
        evidence = _evidence(clock.value)
        store.append_evidence(
            org_id=ORG,
            project_id=PROJECT,
            case_id=created.case_id,
            evidence=evidence,
        )
        with connect_factory() as conn:
            envelope = conn.execute(
                "SELECT envelope_json FROM integration_evidence"
            ).fetchone()["envelope_json"]
            pg_hash = conn.execute(
                "SELECT canonical_integration_case_sha256(%s::JSONB) AS hash",
                (
                    Jsonb(
                        {
                            key: value
                            for key, value in envelope.items()
                            if key != "evidenceHash"
                        }
                    ),
                ),
            ).fetchone()["hash"]
            assert pg_hash == evidence.evidence_hash
            conn.execute("ALTER TABLE integration_evidence DISABLE TRIGGER USER")
            conn.execute(
                "UPDATE integration_evidence SET evidence_hash=%s", (ZERO_HASH,)
            )
            conn.execute("ALTER TABLE integration_evidence ENABLE TRIGGER USER")
            conn.commit()
        with pytest.raises(EvidenceIntegrityCorruptError):
            PostgresIntegrationStore(connect_factory).get_case(
                org_id=ORG, project_id=PROJECT, case_id=created.case_id
            )


@pytest.mark.parametrize("damage", ["snapshot_hash", "event_sequence"])
def test_snapshot_hash_and_event_sequence_corruption_fail_closed(damage: str) -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        store = PostgresIntegrationStore(connect_factory, clock=_Clock())
        created = _create(store)
        with connect_factory() as conn:
            if damage == "snapshot_hash":
                table = "integration_evidence_snapshot"
                statement = "UPDATE integration_evidence_snapshot SET snapshot_hash=%s"
                params = (ZERO_HASH,)
            else:
                table = "integration_stage_event"
                statement = "UPDATE integration_stage_event SET sequence=3"
                params = ()
            conn.execute(
                sql.SQL("ALTER TABLE {} DISABLE TRIGGER USER").format(
                    sql.Identifier(table)
                )
            )
            conn.execute(statement, params)
            conn.execute(
                sql.SQL("ALTER TABLE {} ENABLE TRIGGER USER").format(
                    sql.Identifier(table)
                )
            )
            conn.commit()
        with pytest.raises(EvidenceIntegrityCorruptError):
            PostgresIntegrationStore(connect_factory).get_case(
                org_id=ORG, project_id=PROJECT, case_id=created.case_id
            )


def test_invalid_command_receipt_rolls_back_handler_business_writes() -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        store = PostgresIntegrationStore(connect_factory, clock=_Clock())
        request = CreateIntegrationCaseRequest.model_validate(
            {
                "installationId": str(INSTALLATION_ID),
                "overlayRevision": "overlay-v1",
                "displayName": "必须整体回滚",
            }
        )

        def handler(conn: object) -> IntegrationCommandResult:
            created = store.create_current_case_in_transaction(
                conn,
                org_id=ORG,
                project_id=PROJECT,
                request=request,
                owner="owner:rollback",
                required_markings=["internal"],
            )
            return IntegrationCommandResult(
                case_pk=created.case_pk,
                status_code=200,
                response_json={"caseId": created.case_id, "etagVersion": 1},
                response_etag="W/\"1\"",
            )

        with pytest.raises(EvidenceReferenceInvalidError):
            store.execute_idempotent(
                org_id=ORG,
                project_id=PROJECT,
                operation="integration_cases.create",
                idempotency_key="rollback-invalid-receipt",
                subject="owner:rollback",
                request_json=request.model_dump(mode="json", by_alias=True),
                if_match_etag=None,
                handler=handler,
            )
        with connect_factory() as conn:
            assert conn.execute("SELECT COUNT(*) AS n FROM integration_case").fetchone()[
                "n"
            ] == 0
            assert conn.execute(
                "SELECT COUNT(*) AS n FROM integration_case_command"
            ).fetchone()["n"] == 0


@pytest.mark.parametrize(
    ("table", "statement", "reference"),
    [
        (
            "integration_case_projection",
            "UPDATE integration_case_projection SET etag_version=etag_version+1",
            False,
        ),
        (
            "integration_evidence_snapshot",
            "UPDATE integration_evidence_snapshot SET etag_version=etag_version+1",
            False,
        ),
        (
            "integration_instance_revision",
            "UPDATE integration_instance_revision SET required_markings='[\"secret\"]'::JSONB",
            False,
        ),
        (
            "integration_case_projection",
            "UPDATE integration_case_projection SET connector_count=1",
            True,
        ),
    ],
)
def test_restart_detects_projection_snapshot_marking_and_reference_corruption(
    table: str, statement: str, reference: bool
) -> None:
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        store = PostgresIntegrationStore(connect_factory, clock=_Clock())
        created = (
            store.create_reference_case(
                org_id=ORG, project_id=PROJECT, display_name="脱敏参考"
            )
            if reference
            else _create(store)
        )
        with connect_factory() as conn:
            conn.execute(
                sql.SQL("ALTER TABLE {} DISABLE TRIGGER USER").format(
                    sql.Identifier(table)
                )
            )
            conn.execute(statement)
            conn.execute(
                sql.SQL("ALTER TABLE {} ENABLE TRIGGER USER").format(
                    sql.Identifier(table)
                )
            )
            conn.commit()
        with pytest.raises(EvidenceIntegrityCorruptError):
            PostgresIntegrationStore(connect_factory).get_case(
                org_id=ORG, project_id=PROJECT, case_id=created.case_id
            )
