"""BI-W3-03 governed schema reasoning and adaptive profiling tests."""

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

from aos_api.business_investigation_profiling import (
    AdaptiveProfileRevision,
    BusinessInvestigationProfilingConflict,
    BusinessInvestigationProfilingStore,
    FieldAggregateSummary,
    SchemaProfilingJobRevision,
    SemanticHypothesisRevision,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw3_003_schema_profiling_job.py"
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
OTHER_SCOPE = TenantScope(org_id="dev-org", project_id="dev-project")
NOW = datetime.now(UTC)
HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"
HASH_C = f"sha256:{'c' * 64}"


def ref(resource_type: str, resource_id: str, *, content_hash: str = HASH_A):
    return {"resourceType": resource_type, "resourceId": resource_id, "revision": 1, "contentHash": content_hash}


def field(**changes):
    value = {
        "sourceField": "order.pay_amount", "dataType": "decimal", "rowCount": 100,
        "nonNullCount": 90, "nullCount": 10, "distinctCount": 80, "duplicateCount": 10,
        "rangeSummaryRef": ref("AggregateRangeSummaryRevision", "range-1"),
        "distributionSummaryRef": ref("AggregateDistributionSummaryRevision", "distribution-1"),
        "markings": ["commercial"], "riskCategory": "ordinary",
        "receiptRef": ref("ObservationReceipt", "receipt-1"),
        "observationRef": ref("PlatformObservation", "observation-1"),
    }
    value.update(changes)
    return value


def job_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.schema-profiling-job/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "jobId": "job-1", "revision": 1, "contentHash": HASH_A,
        "receiptRefs": [ref("ObservationReceipt", "receipt-1")],
        "observationRefs": [ref("PlatformObservation", "observation-1")],
        "ontologyRequirementRef": ref("OntologyRequirementRevision", "ontology-requirement-1"),
        "fieldSummaries": [field()], "cutoffAt": NOW, "maxFields": 100,
        "status": "requested", "blockers": [], "idempotencyKey": "job-record-1",
        "requestHash": HASH_B, "createdBy": "data-adapter", "createdAt": NOW,
    }
    value.update(changes)
    return value


def hypothesis_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.semantic-hypothesis/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "hypothesisId": "hypothesis-1", "revision": 1, "contentHash": HASH_B,
        "jobRef": ref("SchemaProfilingJobRevision", "job-1"),
        "sourceField": "order.pay_amount", "targetRef": ref("OntologyFieldRevision", "Order.paidAmount"),
        "confidence": 0.92, "riskCategory": "ordinary", "requiresHumanReview": False,
        "conflicts": [], "evidenceRefs": [ref("ObservationReceipt", "receipt-1")],
        "rationale": "name and aggregate type are compatible", "createdAt": NOW,
    }
    value.update(changes)
    return value


def profile_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.adaptive-profile-revision/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "profileId": "profile-1", "revision": 1, "contentHash": HASH_C,
        "jobRef": ref("SchemaProfilingJobRevision", "job-1"),
        "hypothesisRefs": [ref("SemanticHypothesisRevision", "hypothesis-1", content_hash=HASH_B)],
        "requiredFields": ["order.pay_amount", "order.member_id"],
        "coveredFields": ["order.pay_amount"], "unknownFields": ["order.member_id"],
        "coverage": {"required": 2, "fulfilled": 1, "unknown": 1},
        "status": "completed", "conflicts": [], "blockers": [],
        "idempotencyKey": "profile-record-1", "requestHash": HASH_A,
        "createdBy": "data-adapter", "createdAt": NOW,
    }
    value.update(changes)
    return value


def _load_migration():
    spec = util.spec_from_file_location("biw3_003", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_field_summary_is_aggregate_only_and_conserves_counts() -> None:
    summary = FieldAggregateSummary.model_validate(field())
    assert summary.duplicate_count == summary.non_null_count - summary.distinct_count
    with pytest.raises(ValidationError, match="counts"):
        FieldAggregateSummary.model_validate(field(nullCount=11))
    with pytest.raises(ValidationError, match="Extra inputs"):
        FieldAggregateSummary.model_validate(field(exampleValues=["100.00"]))


def test_high_risk_hypothesis_always_requires_human_review() -> None:
    SemanticHypothesisRevision.model_validate(hypothesis_payload())
    for risk in ("identity", "customer_ownership", "commission", "health", "pii"):
        with pytest.raises(ValidationError, match="human review"):
            SemanticHypothesisRevision.model_validate(
                hypothesis_payload(riskCategory=risk, requiresHumanReview=False)
            )


def test_profile_conserves_covered_and_unknown_without_mapping_authority() -> None:
    hypothesis = SemanticHypothesisRevision.model_validate(hypothesis_payload())
    profile = AdaptiveProfileRevision.model_validate(profile_payload())
    profile.validate_hypotheses([hypothesis])
    assert profile.coverage.unknown == 1
    with pytest.raises(ValidationError, match="coverage"):
        AdaptiveProfileRevision.model_validate(profile_payload(unknownFields=[]))
    with pytest.raises(ValidationError, match="targetRef"):
        SemanticHypothesisRevision.model_validate(
            hypothesis_payload(targetRef=ref("SourceMappingRevision", "mapping-1"))
        )


def test_migration_is_append_only_rls_and_function_only() -> None:
    module = _load_migration()
    assert module.revision == "biw3_003" and module.down_revision == "biw3_002"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "business_investigation_schema_profiling_job_revision" in sql
    assert "business_investigation_semantic_hypothesis_revision" in sql
    assert "business_investigation_adaptive_profile_revision" in sql
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 3 and sql.count("FORCE ROW LEVEL SECURITY") == 3
    assert "schema_profiling_job_record_biw3_003" in sql and "schema_profiling_result_record_biw3_003" in sql
    assert "ObservationReceipt" in sql and "requiresHumanReview" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "GRANT INSERT ON business_investigation" not in sql


def test_store_records_job_and_atomic_profile_result_through_functions() -> None:
    class Cursor:
        def __init__(self, row): self.row = row
        def fetchone(self): return self.row

    class Connection:
        def __init__(self): self.calls = []; self.commits = 0
        def execute(self, sql, params=None):
            self.calls.append((" ".join(sql.split()), params))
            payload = params[-1].obj
            return Cursor({"authority_data": payload, "replayed": False})
        def commit(self): self.commits += 1

    connection = Connection()

    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection

    store = BusinessInvestigationProfilingStore(connect)
    job = SchemaProfilingJobRevision.model_validate(job_payload())
    hypothesis = SemanticHypothesisRevision.model_validate(hypothesis_payload())
    profile = AdaptiveProfileRevision.model_validate(profile_payload())
    assert not store.record_job(SCOPE, job).replayed
    assert not store.record_result(SCOPE, profile, [hypothesis]).replayed
    assert connection.commits == 2
    assert "schema_profiling_job_record_biw3_003" in connection.calls[0][0]
    assert "schema_profiling_result_record_biw3_003" in connection.calls[1][0]


def test_disposable_database_idempotency_isolation_direct_write_and_downgrade() -> None:
    with isolated_aip_migration_database("biw3_schema_profiling") as (config, dsn):
        command.downgrade(config, "biw3_002")
        command.upgrade(config, "head")
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO data_requirement_head(org_id,project_id,requirement_id,current_revision,current_content_hash,status,version,created_by) VALUES('org-org','dev-project','requirement-1',1,%s,'accepted',1,'pytest')",
                ("a" * 64,),
            )
            conn.execute(
                "INSERT INTO data_requirement_revision(org_id,project_id,requirement_id,revision,content_hash,status,operation,idempotency_key,request_hash,case_ref,run_ref,checkpoint_ref,payload,created_by) VALUES('org-org','dev-project','requirement-1',1,%s,'accepted','request','seed',%s,'{}','{}','{}','{}','pytest')",
                ("a" * 64, "b" * 64),
            )
            lease_data = {
                "tenant": {"orgId": "org-org", "projectId": "dev-project"},
                "leaseId": "lease-1", "revision": 1, "contentHash": HASH_A,
                "status": "active", "expiresAt": NOW.isoformat(),
            }
            conn.execute(
                "INSERT INTO business_investigation_observation_session_lease(org_id,project_id,lease_id,revision,state_version,content_hash,platform,requirement_id,requirement_revision,requirement_content_hash,status,expires_at,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','lease-1',1,1,%s,'niushop','requirement-1',1,%s,'active',NOW()+INTERVAL '1 hour','seed-lease',%s,%s)",
                (HASH_A, HASH_A, HASH_B, psycopg.types.json.Jsonb(lease_data)),
            )
            plan_data = {
                "tenant": {"orgId": "org-org", "projectId": "dev-project"},
                "planId": "plan-1", "revision": 1, "contentHash": HASH_B,
                "steps": [{"stepId": "step-1", "routePattern": "/orders/**"}],
            }
            conn.execute(
                "INSERT INTO business_investigation_observation_plan_head(org_id,project_id,plan_id,current_revision,current_content_hash,version) VALUES('org-org','dev-project','plan-1',1,%s,1)",
                (HASH_B,),
            )
            conn.execute(
                "INSERT INTO business_investigation_observation_plan_revision(org_id,project_id,plan_id,revision,content_hash,lease_id,lease_revision,lease_content_hash,requirement_id,requirement_revision,requirement_content_hash,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','plan-1',1,%s,'lease-1',1,%s,'requirement-1',1,%s,'seed-plan',%s,%s)",
                (HASH_B, HASH_A, HASH_A, HASH_B, psycopg.types.json.Jsonb(plan_data)),
            )
            conn.execute(
                "INSERT INTO business_investigation_observation_receipt(org_id,project_id,receipt_id,plan_id,plan_revision,plan_content_hash,step_id,capability_id,lease_id,lease_revision,lease_content_hash,requirement_id,requirement_revision,requirement_content_hash,status,semantic_route,cutoff_at,content_hash,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','receipt-1','plan-1',1,%s,'step-1','browser-read','lease-1',1,%s,'requirement-1',1,%s,'succeeded','/orders/**',NOW(),%s,'seed-receipt',%s,'{}')",
                (HASH_B, HASH_A, HASH_A, HASH_A, HASH_B),
            )
            conn.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute(
                    "SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",
                    scope.key,
                )
                yield conn

        store = BusinessInvestigationProfilingStore(runtime_connect)
        job = SchemaProfilingJobRevision.model_validate(job_payload())
        assert not store.record_job(SCOPE, job).replayed
        assert store.record_job(SCOPE, job).replayed
        with pytest.raises(BusinessInvestigationProfilingConflict):
            store.record_job(
                SCOPE,
                SchemaProfilingJobRevision.model_validate(job_payload(requestHash=HASH_C)),
            )
        hypothesis = SemanticHypothesisRevision.model_validate(hypothesis_payload())
        profile = AdaptiveProfileRevision.model_validate(profile_payload())
        assert not store.record_result(SCOPE, profile, [hypothesis]).replayed
        assert store.record_result(SCOPE, profile, [hypothesis]).replayed

        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
            conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            assert conn.execute(
                "SELECT count(*) FROM business_investigation_schema_profiling_job_revision"
            ).fetchone()[0] == 0
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "INSERT INTO business_investigation_schema_profiling_job_revision(org_id,project_id,job_id,revision,content_hash,status,cutoff_at,idempotency_key,request_hash,authority_data) VALUES('dev-org','dev-project','direct',1,%s,'requested',NOW(),'direct',%s,'{}')",
                    (HASH_A, HASH_B),
                )

        with pytest.raises(Exception, match="cannot downgrade biw3_003"):
            command.downgrade(config, "biw3_002")
