from __future__ import annotations

import importlib.util
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from psycopg import sql

from aos_api.aip_contracts import ArtifactRef, TenantContext
from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityConflict,
    AipEvalAuthorityNotFound,
    AipEvalAuthorityStore,
    AipEvalAuthorityTransitionBlocked,
)
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    DatasetRevisionRef,
    EvalRunAuthorityRecord,
    EvalRunEvent,
    EvalRunStatus,
    EvidenceQuality,
    JudgeRevisionRef,
    LineageEvent,
    LineageEventType,
    LineageRootType,
    MetricDefinitionRevision,
    PublicationEvent,
    PublicationEventType,
    ReleaseGateDecision,
    ReleaseGateStatus,
    UsageAdjustment,
    UsageKind,
    UsageReceipt,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 11, 10, 0, tzinfo=UTC)
H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
SCOPE_A = TenantScope("org-a", "project-a")
SCOPE_B = TenantScope("org-b", "project-b")


@pytest.fixture()
def authority_store():
    schema = f"aip4_store_{uuid.uuid4().hex}"
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/aip4_001_eval_lineage_observability_contract.py"
    )
    spec = importlib.util.spec_from_file_location("aip4_store_migration", migration_path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    with patch.object(migration.op, "execute", statements.append):
        migration.upgrade()
    create_tables = [
        statement for statement in statements if statement.lstrip().startswith("CREATE TABLE")
    ]
    try:
        with connect() as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            conn.execute(
                """CREATE TABLE twa_workspace (
                   org_id TEXT NOT NULL, project_id TEXT NOT NULL,
                   PRIMARY KEY (org_id,project_id))"""
            )
            conn.execute(
                "INSERT INTO twa_workspace VALUES ('org-a','project-a'),('org-b','project-b')"
            )
            for statement in create_tables:
                conn.execute(statement)
            conn.commit()
    except Exception as exc:  # noqa: BLE001 - PostgreSQL is optional in developer CI
        pytest.skip(f"PG unavailable: {exc}")

    @contextmanager
    def scoped_connect(_scope: TenantScope | None = None):
        with connect() as conn:
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            yield conn

    yield AipEvalAuthorityStore(connect_factory=scoped_connect), scoped_connect
    with connect() as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.commit()


def _tenant(scope: TenantScope) -> TenantContext:
    return TenantContext(org_id=scope.org_id, project_id=scope.project_id)


def _asset(asset_type: AssetType, asset_id: str, content_hash: str = H1):
    return AssetRevisionRef(
        asset_type=asset_type,
        asset_id=asset_id,
        revision="1",
        content_hash=content_hash,
    )


def _dataset() -> DatasetRevisionRef:
    return DatasetRevisionRef(
        dataset_id="dataset-1",
        revision=1,
        content_hash=H1,
        source_hash=H2,
        redaction_policy=_asset(AssetType.POLICY, "redaction-1", H3),
    )


def _run(scope: TenantScope = SCOPE_A) -> EvalRunAuthorityRecord:
    return EvalRunAuthorityRecord(
        tenant=_tenant(scope),
        run_id="run-1",
        suite_ref=_asset(AssetType.EVAL_SUITE, "suite-1"),
        target=_asset(AssetType.LOGIC_GRAPH, "logic-1", H2),
        dataset=_dataset(),
        judge=JudgeRevisionRef(
            judge_id="judge-1", revision=1, content_hash=H3
        ),
        status=EvalRunStatus.QUEUED,
        idempotency_key="run-once",
        created_by="alice",
        created_at=NOW,
        version=1,
    )


def _event(
    scope: TenantScope,
    *,
    event_id: str,
    sequence: int,
    from_status: EvalRunStatus | None,
    to_status: EvalRunStatus,
) -> EvalRunEvent:
    return EvalRunEvent(
        tenant=_tenant(scope),
        event_id=event_id,
        run_id="run-1",
        sequence=sequence,
        event_type=f"run.{to_status.value}",
        from_status=from_status,
        to_status=to_status,
        payload_hash=H1,
        actor="alice",
        created_at=NOW,
    )


def test_dataset_revision_survives_recreation_and_is_tenant_scoped(
    authority_store,
) -> None:
    store, scoped_connect = authority_store
    ref = _dataset()
    assert store.create_dataset_revision(
        SCOPE_A, ref, manifest={"cases": 12}, actor="alice"
    ) == ref
    with pytest.raises(AipEvalAuthorityConflict):
        store.create_dataset_revision(
            SCOPE_A, ref, manifest={"cases": 13}, actor="alice"
        )
    assert store.create_dataset_revision(
        SCOPE_A, ref, manifest={"cases": 12}, actor="alice"
    ) == ref
    restarted = AipEvalAuthorityStore(connect_factory=scoped_connect)
    assert restarted.get_dataset_revision(SCOPE_A, "dataset-1", 1) == ref
    with pytest.raises(AipEvalAuthorityNotFound):
        restarted.get_dataset_revision(SCOPE_B, "dataset-1", 1)
    with pytest.raises(AipEvalAuthorityConflict):
        store.create_dataset_revision(
            SCOPE_A,
            ref.model_copy(update={"content_hash": H3}),
            manifest={"cases": 12},
            actor="alice",
        )


def test_eval_run_idempotency_transition_and_restart(authority_store) -> None:
    store, scoped_connect = authority_store
    record = _run()
    initial = _event(
        SCOPE_A,
        event_id="event-1",
        sequence=1,
        from_status=None,
        to_status=EvalRunStatus.QUEUED,
    )
    assert store.create_eval_run(SCOPE_A, record, initial) == record
    assert store.create_eval_run(SCOPE_A, record, initial) == record
    with pytest.raises(AipEvalAuthorityConflict):
        store.create_eval_run(
            SCOPE_A, record, initial.model_copy(update={"event_id": "other-event"})
        )
    running = store.transition_eval_run(
        SCOPE_A,
        _event(
            SCOPE_A,
            event_id="event-2",
            sequence=2,
            from_status=EvalRunStatus.QUEUED,
            to_status=EvalRunStatus.RUNNING,
        ),
        expected_version=1,
    )
    assert running.status is EvalRunStatus.RUNNING
    assert running.version == 2
    restarted = AipEvalAuthorityStore(connect_factory=scoped_connect)
    assert restarted.get_eval_run(SCOPE_A, "run-1") == running
    with pytest.raises(AipEvalAuthorityNotFound):
        restarted.get_eval_run(SCOPE_B, "run-1")
    with pytest.raises(AipEvalAuthorityConflict):
        store.transition_eval_run(
            SCOPE_A,
            _event(
                SCOPE_A,
                event_id="event-3",
                sequence=3,
                from_status=EvalRunStatus.QUEUED,
                to_status=EvalRunStatus.RUNNING,
            ),
            expected_version=1,
        )
    with pytest.raises(AipEvalAuthorityTransitionBlocked):
        store.transition_eval_run(
            SCOPE_A,
            _event(
                SCOPE_A,
                event_id="event-4",
                sequence=3,
                from_status=EvalRunStatus.RUNNING,
                to_status=EvalRunStatus.QUEUED,
            ),
            expected_version=2,
        )


def test_gate_publication_lineage_usage_and_metric_are_idempotent(
    authority_store,
) -> None:
    store, _ = authority_store
    store.create_eval_run(
        SCOPE_A,
        _run(),
        _event(
            SCOPE_A,
            event_id="event-1",
            sequence=1,
            from_status=None,
            to_status=EvalRunStatus.QUEUED,
        ),
    )
    gate = ReleaseGateDecision(
        tenant=_tenant(SCOPE_A),
        decision_id="gate-1",
        target=_asset(AssetType.LOGIC_GRAPH, "logic-1", H2),
        suite_ref=_asset(AssetType.EVAL_SUITE, "suite-1"),
        eval_run_id="run-1",
        eval_report=ArtifactRef(
            artifact_id="report-1",
            artifact_type="eval_report",
            revision="1",
            content_hash=H3,
        ),
        status=ReleaseGateStatus.PASSED,
        decision_hash=H1,
        decided_by="alice",
        decided_at=NOW,
    )
    assert store.append_release_gate(SCOPE_A, gate) == gate
    assert store.append_release_gate(SCOPE_A, gate) == gate
    publication = PublicationEvent(
        tenant=_tenant(SCOPE_A),
        event_id="publication-event-1",
        publication_id="publication-1",
        target=gate.target,
        event_type=PublicationEventType.PUBLISHED,
        release_gate_decision_id=gate.decision_id,
        reason_hash=H2,
        actor="alice",
        occurred_at=NOW,
    )
    assert store.append_publication_event(SCOPE_A, publication) == publication
    lineage = LineageEvent(
        tenant=_tenant(SCOPE_A),
        event_id="lineage-event-1",
        lineage_id="lineage-1",
        root_type=LineageRootType.TASK_RUN,
        root_id="run-1",
        sequence=1,
        event_type=LineageEventType.EVAL,
        subject=gate.target,
        payload_hash=H3,
        quality=EvidenceQuality.MEASURED,
        occurred_at=NOW,
        observed_at=NOW,
    )
    assert store.append_lineage_event(SCOPE_A, lineage) == lineage
    assert store.list_lineage_events(SCOPE_A, "lineage-1") == [lineage]
    assert store.list_lineage_events(SCOPE_B, "lineage-1") == []
    receipt = UsageReceipt(
        tenant=_tenant(SCOPE_A),
        receipt_id="usage-1",
        provider="provider-1",
        provider_receipt_id="provider-receipt-1",
        lineage_id="lineage-1",
        usage_kind=UsageKind.INPUT_TOKEN,
        quantity=123,
        unit="token",
        quality=EvidenceQuality.MEASURED,
        source_hash=H1,
        observed_at=NOW,
    )
    assert store.append_usage_receipt(SCOPE_A, receipt) == receipt
    adjustment = UsageAdjustment(
        tenant=_tenant(SCOPE_A),
        adjustment_id="adjustment-1",
        receipt_id=receipt.receipt_id,
        delta=-3,
        reason_hash=H2,
        actor="alice",
        created_at=NOW,
    )
    assert store.append_usage_adjustment(SCOPE_A, adjustment) == adjustment
    metric = MetricDefinitionRevision(
        metric_id="tokens.input",
        revision=1,
        content_hash=H3,
        name="Input tokens",
        unit="token",
        source="provider_receipt",
        window="run",
        aggregation="sum",
        accepted_quality=[EvidenceQuality.MEASURED],
    )
    assert store.create_metric_definition(SCOPE_A, metric, actor="alice") == metric
    assert store.create_metric_definition(SCOPE_A, metric, actor="alice") == metric
    with pytest.raises(ValueError, match="authenticated scope"):
        store.append_lineage_event(
            SCOPE_B, lineage
        )


def test_usage_without_scoped_lineage_fails_closed(authority_store) -> None:
    store, _ = authority_store
    receipt = UsageReceipt(
        tenant=_tenant(SCOPE_A),
        receipt_id="usage-missing",
        provider="provider-1",
        provider_receipt_id="provider-receipt-missing",
        lineage_id="missing",
        usage_kind=UsageKind.COST,
        quantity=1.5,
        unit="usd",
        currency="USD",
        quality=EvidenceQuality.MEASURED,
        source_hash=H1,
        observed_at=NOW,
    )
    with pytest.raises(AipEvalAuthorityNotFound):
        store.append_usage_receipt(SCOPE_A, receipt)
