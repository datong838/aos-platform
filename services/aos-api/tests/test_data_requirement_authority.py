"""BI-W2-01 DataRequirement authority migration and contract tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib import util
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import psycopg
from alembic import command
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect

from tests.aip._migration_test_support import isolated_aip_migration_database

from aos_api.data_requirement_contracts import (
    DataFulfillmentReceiptRecord,
    DataRequirementHeadRecord,
    DataRequirementRevisionRecord,
)


MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "biw2_001_data_requirement_authority.py"
)
NOW = datetime(2026, 8, 26, 3, 30, tzinfo=UTC)
HASH = f"sha256:{'a' * 64}"
TENANT = {"orgId": "org-org", "projectId": "dev-project"}


def ref(
    resource_type: str,
    resource_id: str,
    revision: int = 1,
    *,
    receipt_id: str | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": revision,
        "contentHash": HASH,
    }
    if receipt_id is not None:
        value["receiptId"] = receipt_id
    return value


def requirement() -> dict[str, object]:
    return {
        "schemaVersion": "aos.data-requirement-authority/v1",
        "tenant": TENANT,
        "requirementId": "requirement-1",
        "revision": 1,
        "priorRef": None,
        "contentHash": HASH,
        "status": "requested",
        "caseRef": ref("BusinessInvestigationCaseRevision", "case-1"),
        "runRef": ref("BusinessInvestigationRun", "run-1"),
        "checkpointRef": ref("CheckpointRevision", "checkpoint-1"),
        "purposeCode": "business_portrait_gap",
        "channelRef": ref("ChannelRevision", "channel-niushop"),
        "entityRef": ref("BusinessEntityRevision", "shop-qyh"),
        "requiredFacts": ["Order", "Product"],
        "timeWindow": {"startAt": NOW - timedelta(days=30), "endAt": NOW},
        "grain": "day",
        "cutoffAt": NOW,
        "freshnessMaxAgeSeconds": 3600,
        "qualityThreshold": 0.95,
        "markings": ["INTERNAL"],
        "piiAllowed": False,
        "minPopulation": 20,
        "acceptableDegradation": ["narrow_time_window"],
        "requestedOutputs": ["DataProductRevision", "EvidenceBundleRevision"],
        "budgetMinor": 1000,
        "expiresAt": NOW + timedelta(days=1),
        "createdBy": "principal-1",
        "createdAt": NOW,
        "blockers": [],
    }


def _load_migration():
    spec = util.spec_from_file_location("biw2_001_data_requirement_authority", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_is_linear_tenant_scoped_append_only_and_exact() -> None:
    module = _load_migration()
    assert module.revision == "biw2_001"
    assert module.down_revision == "w7_006"
    assert module.TABLES == (
        "data_requirement_head",
        "data_requirement_revision",
        "data_requirement_event",
        "data_requirement_outbox",
        "data_fulfillment_receipt",
    )
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    for table in module.TABLES:
        assert f"CREATE TABLE {table}" in sql
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql
        assert f"tenant_scope_{table}_biw2_001" in sql
        assert f"REVOKE UPDATE,DELETE,TRUNCATE ON {table}" in sql
    for table in module.APPEND_ONLY_TABLES:
        assert f"trg_{table}_append_only_biw2_001" in sql
        assert f"trg_{table}_truncate_guard_biw2_001" in sql
    assert "FOREIGN KEY(org_id,project_id,requirement_id,requirement_revision)" in sql
    assert "UNIQUE(org_id,project_id,operation,idempotency_key)" in sql
    assert "CHECK(content_hash ~ '^[0-9a-f]{64}$')" in sql
    assert "jsonb_typeof(artifact_refs)='array'" in sql


def test_migration_downgrade_refuses_nonempty_authority() -> None:
    module = _load_migration()
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.downgrade()
    guard = statements[0]
    assert "cannot downgrade biw2_001 with DataRequirement authority data" in guard
    assert "ERRCODE='55000'" in guard
    for table in module.TABLES:
        assert f"EXISTS (SELECT 1 FROM {table} LIMIT 1)" in guard
    assert statements[1:] == [
        f"DROP TABLE IF EXISTS {table} CASCADE" for table in reversed(module.TABLES)
    ]


def test_requirement_revision_and_head_are_strict_tenant_exact_records() -> None:
    parsed = DataRequirementRevisionRecord.model_validate(requirement())
    assert parsed.tenant.org_id == "org-org"
    assert parsed.required_facts == ["Order", "Product"]

    head = DataRequirementHeadRecord.model_validate(
        {
            "schemaVersion": "aos.data-requirement-head/v1",
            "tenant": TENANT,
            "requirementId": "requirement-1",
            "currentRevision": 1,
            "currentContentHash": HASH,
            "status": "requested",
            "version": 1,
            "updatedAt": NOW,
        }
    )
    assert head.version == 1

    leaked = {**requirement(), "rawPayload": {"mobile": "13800000000"}}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DataRequirementRevisionRecord.model_validate(leaked)

    duplicate = {**requirement(), "requiredFacts": ["Order", "Order"]}
    with pytest.raises(ValidationError, match="requiredFacts"):
        DataRequirementRevisionRecord.model_validate(duplicate)

    bad_hash = {**requirement(), "contentHash": "a" * 64}
    with pytest.raises(ValidationError, match="sha256"):
        DataRequirementRevisionRecord.model_validate(bad_hash)


def test_requirement_revision_chain_time_and_status_fail_closed() -> None:
    second = {
        **requirement(),
        "revision": 2,
        "priorRef": ref("DataRequirementRevision", "requirement-1", 1),
        "status": "accepted",
    }
    assert DataRequirementRevisionRecord.model_validate(second).revision == 2

    missing_prior = {**second, "priorRef": None}
    with pytest.raises(ValidationError, match="priorRef"):
        DataRequirementRevisionRecord.model_validate(missing_prior)

    bad_window = {
        **requirement(),
        "timeWindow": {"startAt": NOW, "endAt": NOW - timedelta(seconds=1)},
    }
    with pytest.raises(ValidationError, match="timeWindow"):
        DataRequirementRevisionRecord.model_validate(bad_window)

    unknown_without_blocker = {**requirement(), "status": "unknown"}
    with pytest.raises(ValidationError, match="blocker"):
        DataRequirementRevisionRecord.model_validate(unknown_without_blocker)


def test_fulfillment_receipt_requires_exact_artifacts_and_honest_unknown() -> None:
    fulfilled = DataFulfillmentReceiptRecord.model_validate(
        {
            "schemaVersion": "aos.data-fulfillment-authority-receipt/v1",
            "tenant": TENANT,
            "fulfillmentId": "fulfillment-1",
            "receiptId": "receipt-1",
            "requirementRef": ref("DataRequirementRevision", "requirement-1"),
            "status": "fulfilled",
            "artifactRefs": [ref("DataProductRevision", "data-product-1")],
            "sourceReadinessRef": ref(
                "SourceReadinessEnvelope",
                "readiness-1",
                receipt_id="source-readiness-receipt-1",
            ),
            "cutoffAt": NOW,
            "fulfilledAt": NOW,
            "contentHash": HASH,
            "createdBy": "principal-1",
            "blockers": [],
        }
    )
    assert fulfilled.artifact_refs[0].resource_type == "DataProductRevision"

    unknown = {
        **fulfilled.model_dump(by_alias=True),
        "status": "unknown",
        "artifactRefs": [],
        "blockers": [
            {
                "code": "SOURCE_READINESS_STALE",
                "severity": "blocking",
                "dependency": "P01",
                "requiredAction": "取得当前 cutoff 的 readiness",
            }
        ],
    }
    assert DataFulfillmentReceiptRecord.model_validate(unknown).status.value == "unknown"

    manual_url = {
        **fulfilled.model_dump(by_alias=True),
        "artifactRefs": [ref("ExternalUrl", "https://example.invalid/latest")],
    }
    with pytest.raises(ValidationError, match="artifactRefs"):
        DataFulfillmentReceiptRecord.model_validate(manual_url)


def test_disposable_database_rls_and_empty_only_downgrade() -> None:
    tables = {
        "data_requirement_head",
        "data_requirement_revision",
        "data_requirement_event",
        "data_requirement_outbox",
        "data_fulfillment_receipt",
    }
    with isolated_aip_migration_database("biw2_requirement") as (config, dsn):
        engine = create_engine(dsn.replace("postgresql://", "postgresql+psycopg://", 1))
        try:
            assert tables <= set(inspect(engine).get_table_names())
        finally:
            engine.dispose()

        suffix = uuid4().hex[:10]
        org_a, org_b = f"biw2-a-{suffix}", f"biw2-b-{suffix}"
        requirement_id = f"requirement-{suffix}"
        with psycopg.connect(dsn) as conn:
            for org_id in (org_a, org_b):
                conn.execute(
                    """INSERT INTO data_requirement_head
                       (org_id,project_id,requirement_id,current_revision,
                        current_content_hash,status,version,created_by)
                       VALUES (%s,'dev-project',%s,1,%s,'requested',1,'pytest')""",
                    (org_id, requirement_id, "a" * 64),
                )
            conn.commit()

            conn.execute("SELECT set_config('aos.org_id','',true)")
            conn.execute("SELECT set_config('aos.project_id','',true)")
            conn.execute("SET LOCAL ROLE aos_runtime")
            assert conn.execute("SELECT count(*) FROM data_requirement_head").fetchone()[0] == 0

            conn.execute("RESET ROLE")
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (org_a,))
            conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            conn.execute("SET LOCAL ROLE aos_runtime")
            visible = conn.execute(
                "SELECT org_id FROM data_requirement_head ORDER BY org_id"
            ).fetchall()
            assert visible == [(org_a,)]
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "UPDATE data_requirement_head SET version=2 WHERE requirement_id=%s",
                    (requirement_id,),
                )
            conn.rollback()

            conn.execute("DELETE FROM data_requirement_head")
            conn.commit()

        command.downgrade(config, "w7_006")
        engine = create_engine(dsn.replace("postgresql://", "postgresql+psycopg://", 1))
        try:
            assert tables.isdisjoint(inspect(engine).get_table_names())
        finally:
            engine.dispose()
        command.upgrade(config, "head")

        with psycopg.connect(dsn) as conn:
            conn.execute(
                """INSERT INTO data_requirement_head
                   (org_id,project_id,requirement_id,current_revision,
                    current_content_hash,status,version,created_by)
                   VALUES (%s,'dev-project',%s,1,%s,'requested',1,'pytest')""",
                (org_a, requirement_id, "a" * 64),
            )
            conn.commit()
        with pytest.raises(Exception, match="cannot downgrade biw2_001"):
            command.downgrade(config, "w7_006")
