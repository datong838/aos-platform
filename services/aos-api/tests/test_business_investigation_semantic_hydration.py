"""BI-W3-05 governed semantic hydration job and receipt tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from importlib import util
from pathlib import Path
from unittest.mock import patch

import pytest
import psycopg
from alembic import command
from psycopg.rows import dict_row
from pydantic import ValidationError

from aos_api.business_investigation_hydration import (
    BusinessInvestigationHydrationStore,
    BusinessInvestigationHydrationConflict,
    HydrationCounts,
    SemanticHydrationJobRevision,
    SemanticHydrationReceipt,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw3_005_semantic_hydration_job.py"
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
NOW = datetime.now(UTC)
HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"
HASH_C = f"sha256:{'c' * 64}"


def ref(kind: str, identity: str, *, content_hash: str = HASH_A):
    return {"resourceType": kind, "resourceId": identity, "revision": 1, "contentHash": content_hash}


def job_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.semantic-hydration-job/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "hydrationJobId": "hydration-job-1", "revision": 1, "contentHash": HASH_A,
        "profileRef": ref("AdaptiveProfileRevision", "profile-1", content_hash=HASH_C),
        "mappingRefs": [ref("SourceMappingRevision", "mapping-1")],
        "receiptRefs": [ref("ObservationReceipt", "receipt-1")],
        "observationRefs": [ref("PlatformObservation", "observation-1")],
        "sourceSnapshotRef": ref("PlatformSourceSnapshotRevision", "snapshot-1"),
        "cutoffAt": NOW,
        "ownerCommandBindings": [{
            "mappingRef": ref("SourceMappingRevision", "mapping-1"),
            "ownerCommandRef": ref("OntologyOwnerWriteCommandRevision", "owner-command-1"),
            "canonicalTargetRef": ref("OntologyFieldRevision", "Order.paidAmount"),
        }],
        "unknownFields": ["order.member_id"], "status": "requested", "blockers": [],
        "idempotencyKey": "hydration-request-1", "requestHash": HASH_B,
        "createdBy": "data-owner-orchestrator", "createdAt": NOW,
    }
    value.update(changes)
    return value


def receipt_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.semantic-hydration-receipt/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "hydrationId": "hydration-1", "contentHash": HASH_B,
        "jobRef": ref("SemanticHydrationJobRevision", "hydration-job-1"),
        "mappingRefs": [ref("SourceMappingRevision", "mapping-1")],
        "ownerWriteReceiptRefs": [ref("OntologyOwnerWriteReceiptRevision", "owner-receipt-1")],
        "outputRefs": [ref("OntologyObjectRevision", "order-1")],
        "status": "succeeded",
        "counts": {"attempted": 2, "created": 1, "updated": 0, "quarantined": 0, "unknown": 1},
        "zeroObserved": False, "unknownFields": ["order.member_id"],
        "identityResolutionMethod": "exact", "qualityViolationRefs": [],
        "watermarkRef": ref("WatermarkRevision", "watermark-1"),
        "outboxReceiptRef": ref("OwnerOutboxReceiptRevision", "outbox-1"),
        "lineageRef": ref("LineageEventRevision", "lineage-1"),
        "maskedPolicyRef": ref("DataMarkingPolicyRevision", "marking-1"),
        "unmetSemanticFacts": ["order.member_id"],
        "rollbackRef": ref("OwnerRollbackPlanRevision", "rollback-1"),
        "rebuildRef": ref("ProjectionRebuildPlanRevision", "rebuild-1"),
        "hydratedAt": NOW, "blockers": [],
        "idempotencyKey": "hydration-record-1", "requestHash": HASH_C,
        "createdBy": "data-owner-orchestrator",
    }
    value.update(changes)
    return value


def _migration():
    spec = util.spec_from_file_location("biw3_005", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_job_accepts_only_exact_owner_commands_and_no_raw_values() -> None:
    SemanticHydrationJobRevision.model_validate(job_payload())
    with pytest.raises(ValidationError, match="ownerCommandBindings.ownerCommandRef"):
        SemanticHydrationJobRevision.model_validate(
            job_payload(ownerCommandBindings=[{
                "mappingRef": ref("SourceMappingRevision", "mapping-1"),
                "ownerCommandRef": ref("DirectTableWrite", "write-1"),
                "canonicalTargetRef": ref("OntologyFieldRevision", "Order.paidAmount"),
            }])
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        SemanticHydrationJobRevision.model_validate(job_payload(sampleValues=["secret"] ))


def test_receipt_conserves_counts_unknowns_and_owner_outputs() -> None:
    receipt = SemanticHydrationReceipt.model_validate(receipt_payload())
    receipt.validate_job(SemanticHydrationJobRevision.model_validate(job_payload()))
    assert receipt.counts.attempted == 2
    with pytest.raises(ValidationError, match="counts"):
        SemanticHydrationReceipt.model_validate(
            receipt_payload(counts={"attempted": 1, "created": 1, "updated": 0, "quarantined": 1, "unknown": 0})
        )
    with pytest.raises(ValidationError, match="owner write receipt"):
        SemanticHydrationReceipt.model_validate(receipt_payload(ownerWriteReceiptRefs=[]))
    with pytest.raises(ValueError, match="unknown fields"):
        receipt.validate_job(
            SemanticHydrationJobRevision.model_validate(job_payload(unknownFields=["other.field"]))
        )


def test_zero_observed_is_distinct_from_unknown_or_failed() -> None:
    zero = SemanticHydrationReceipt.model_validate(
        receipt_payload(
            counts={"attempted": 0, "created": 0, "updated": 0, "quarantined": 0, "unknown": 0},
            zeroObserved=True, outputRefs=[], unknownFields=[], unmetSemanticFacts=[],
        )
    )
    assert zero.zero_observed
    with pytest.raises(ValidationError, match="zeroObserved"):
        SemanticHydrationReceipt.model_validate(
            receipt_payload(status="unknown", zeroObserved=True, outputRefs=[], blockers=["QUERY_FAILED"])
        )


def test_migration_is_append_only_owner_receipt_first_and_tenant_scoped() -> None:
    module = _migration()
    assert module.revision == "biw3_005" and module.down_revision == "biw3_004"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "business_investigation_semantic_hydration_job_revision" in sql
    assert "business_investigation_semantic_hydration_receipt" in sql
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 2 and sql.count("FORCE ROW LEVEL SECURITY") == 2
    assert "semantic_hydration_request_biw3_005" in sql and "semantic_hydration_record_biw3_005" in sql
    assert "OntologyOwnerWriteReceiptRevision" in sql and "DataProductOwnerWriteReceiptRevision" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "GRANT INSERT ON business_investigation_semantic_hydration" not in sql


def test_store_requests_and_records_through_controlled_functions() -> None:
    class Cursor:
        def __init__(self, row): self.row = row
        def fetchone(self): return self.row
    class Connection:
        def __init__(self): self.calls = []; self.commits = 0
        def execute(self, sql, params=None):
            self.calls.append((" ".join(sql.split()), params))
            return Cursor({"authority_data": params[-1].obj, "replayed": False})
        def commit(self): self.commits += 1
    connection = Connection()
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection
    store = BusinessInvestigationHydrationStore(connect)
    assert not store.request(SCOPE, SemanticHydrationJobRevision.model_validate(job_payload())).replayed
    assert not store.record(SCOPE, SemanticHydrationReceipt.model_validate(receipt_payload())).replayed
    assert connection.commits == 2
    assert "semantic_hydration_request_biw3_005" in connection.calls[0][0]
    assert "semantic_hydration_record_biw3_005" in connection.calls[1][0]


def test_disposable_database_empty_upgrade_and_downgrade() -> None:
    with isolated_aip_migration_database("biw3_semantic_hydration") as (config, _dsn):
        command.downgrade(config, "biw3_004")
        command.upgrade(config, "head")


def test_disposable_database_receipt_first_idempotency_isolation_and_downgrade() -> None:
    with isolated_aip_migration_database("biw3_hydration_authority") as (config, dsn):
        with psycopg.connect(dsn) as conn:
            job_data = {"receiptRefs": [ref("ObservationReceipt", "receipt-1")], "observationRefs": [ref("PlatformObservation", "observation-1")]}
            conn.execute("INSERT INTO business_investigation_schema_profiling_job_revision(org_id,project_id,job_id,revision,content_hash,status,cutoff_at,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','job-1',1,%s,'requested',NOW(),'seed-job',%s,%s)", (HASH_A, HASH_B, psycopg.types.json.Jsonb(job_data)))
            hypothesis_data = {"targetRef": ref("OntologyFieldRevision", "Order.paidAmount")}
            conn.execute("INSERT INTO business_investigation_semantic_hypothesis_revision(org_id,project_id,hypothesis_id,revision,content_hash,job_id,job_revision,source_field,target_resource_type,risk_category,requires_human_review,authority_data) VALUES('org-org','dev-project','hypothesis-1',1,%s,'job-1',1,'order.pay_amount','OntologyFieldRevision','ordinary',false,%s)", (HASH_B, psycopg.types.json.Jsonb(hypothesis_data)))
            profile_data = {"hypothesisRefs": [ref("SemanticHypothesisRevision", "hypothesis-1", content_hash=HASH_B)], "coveredFields": ["order.pay_amount"], "unknownFields": ["order.member_id"]}
            conn.execute("INSERT INTO business_investigation_adaptive_profile_revision(org_id,project_id,profile_id,revision,content_hash,job_id,job_revision,status,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','profile-1',1,%s,'job-1',1,'completed','seed-profile',%s,%s)", (HASH_C, HASH_A, psycopg.types.json.Jsonb(profile_data)))
            conn.execute("INSERT INTO business_investigation_source_mapping_review_decision_revision(org_id,project_id,decision_id,revision,content_hash,job_id,job_revision,profile_id,profile_revision,hypothesis_id,hypothesis_revision,source_field,canonical_target_type,canonical_target_id,decision,reviewer,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','review-1',1,%s,'job-1',1,'profile-1',1,'hypothesis-1',1,'order.pay_amount','OntologyFieldRevision','Order.paidAmount','confirmed','reviewer','seed-review',%s,'{}')", (HASH_A, HASH_B))
            conn.execute("INSERT INTO business_investigation_source_mapping_revision(org_id,project_id,mapping_id,revision,content_hash,job_id,job_revision,job_content_hash,profile_id,profile_revision,profile_content_hash,hypothesis_id,hypothesis_revision,hypothesis_content_hash,receipt_id,observation_id,source_field,canonical_target_type,canonical_target_id,canonical_target_revision,canonical_target_hash,status,confirmation_id,confirmation_revision,confirmation_hash,confirmed_by,confirmed_at,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','mapping-1',1,%s,'job-1',1,%s,'profile-1',1,%s,'hypothesis-1',1,%s,'receipt-1','observation-1','order.pay_amount','OntologyFieldRevision','Order.paidAmount','1',%s,'active','review-1',1,%s,'reviewer',NOW(),'seed-mapping',%s,'{}')", (HASH_A, HASH_A, HASH_C, HASH_B, HASH_A, HASH_A, HASH_B))
            conn.execute("INSERT INTO business_investigation_source_mapping_head(org_id,project_id,mapping_id,current_revision,current_content_hash,source_field,canonical_target_type,canonical_target_id,status,version) VALUES('org-org','dev-project','mapping-1',1,%s,'order.pay_amount','OntologyFieldRevision','Order.paidAmount','active',1)", (HASH_A,))
            conn.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
                yield conn

        store = BusinessInvestigationHydrationStore(runtime_connect)
        job = SemanticHydrationJobRevision.model_validate(job_payload())
        assert not store.request(SCOPE, job).replayed
        assert store.request(SCOPE, job).replayed
        bad_target = job_payload(
            hydrationJobId="hydration-job-bad-target",
            idempotencyKey="hydration-bad-target",
            requestHash=HASH_C,
            ownerCommandBindings=[{
                "mappingRef": ref("SourceMappingRevision", "mapping-1"),
                "ownerCommandRef": ref("OntologyOwnerWriteCommandRevision", "owner-command-bad-target"),
                "canonicalTargetRef": ref("OntologyFieldRevision", "Order.wrongTarget"),
            }],
        )
        with pytest.raises(BusinessInvestigationHydrationConflict):
            store.request(SCOPE, SemanticHydrationJobRevision.model_validate(bad_target))
        with pytest.raises(BusinessInvestigationHydrationConflict):
            store.request(SCOPE, SemanticHydrationJobRevision.model_validate(job_payload(requestHash=HASH_C)),)
        receipt = SemanticHydrationReceipt.model_validate(receipt_payload())
        assert not store.record(SCOPE, receipt).replayed
        assert store.record(SCOPE, receipt).replayed
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
            conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            assert conn.execute("SELECT count(*) FROM business_investigation_semantic_hydration_receipt").fetchone()[0] == 0
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("INSERT INTO business_investigation_semantic_hydration_job_revision(org_id,project_id,hydration_job_id,revision,content_hash,status,profile_id,profile_revision,cutoff_at,idempotency_key,request_hash,authority_data) VALUES('dev-org','dev-project','direct',1,%s,'requested','profile-1',1,NOW(),'direct',%s,'{}')", (HASH_A, HASH_B))
        with pytest.raises(Exception, match="cannot downgrade biw3_005"):
            command.downgrade(config, "biw3_004")
