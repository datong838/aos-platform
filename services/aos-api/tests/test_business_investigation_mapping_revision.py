"""BI-W3-04 confirmed SourceField to CanonicalField mapping authority tests."""

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

from aos_api.business_investigation_mapping import (
    BusinessInvestigationMappingStore,
    BusinessInvestigationMappingConflict,
    SourceMappingRevision,
    SourceMappingReviewDecisionRevision,
)
from aos_api.business_investigation_profiling import (
    AdaptiveProfileRevision,
    SemanticHypothesisRevision,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw3_004_source_mapping_revision.py"
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
NOW = datetime.now(UTC)
HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"
HASH_C = f"sha256:{'c' * 64}"


def ref(resource_type: str, resource_id: str, *, revision: int = 1, content_hash: str = HASH_A):
    return {"resourceType": resource_type, "resourceId": resource_id, "revision": revision, "contentHash": content_hash}


def hypothesis_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.semantic-hypothesis/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "hypothesisId": "hypothesis-1", "revision": 1, "contentHash": HASH_B,
        "jobRef": ref("SchemaProfilingJobRevision", "job-1"),
        "sourceField": "order.pay_amount", "targetRef": ref("OntologyFieldRevision", "Order.paidAmount"),
        "confidence": 0.92, "riskCategory": "ordinary", "requiresHumanReview": False,
        "conflicts": [], "evidenceRefs": [ref("ObservationReceipt", "receipt-1")],
        "rationale": "aggregate schema is compatible", "createdAt": NOW,
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
        "idempotencyKey": "profile-1", "requestHash": HASH_A,
        "createdBy": "data-adapter", "createdAt": NOW,
    }
    value.update(changes)
    return value


def mapping_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.source-mapping-revision/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "mappingId": "mapping-1", "revision": 1, "priorRef": None,
        "contentHash": HASH_A,
        "jobRef": ref("SchemaProfilingJobRevision", "job-1"),
        "profileRef": ref("AdaptiveProfileRevision", "profile-1", content_hash=HASH_C),
        "hypothesisRef": ref("SemanticHypothesisRevision", "hypothesis-1", content_hash=HASH_B),
        "receiptRef": ref("ObservationReceipt", "receipt-1"),
        "observationRef": ref("PlatformObservation", "observation-1"),
        "sourceField": "order.pay_amount",
        "canonicalTargetRef": ref("OntologyFieldRevision", "Order.paidAmount"),
        "status": "active",
        "confirmationRef": ref("HumanReviewDecisionRevision", "review-1"),
        "confirmedBy": "ontology-reviewer", "confirmedAt": NOW,
        "reason": "confirmed against aggregate profile and ontology definition",
        "idempotencyKey": "mapping-publish-1", "requestHash": HASH_B,
        "createdBy": "ontology-reviewer", "createdAt": NOW,
    }
    value.update(changes)
    return value


def review_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.source-mapping-review-decision/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "decisionId": "review-1", "revision": 1, "contentHash": HASH_A,
        "jobRef": ref("SchemaProfilingJobRevision", "job-1"),
        "profileRef": ref("AdaptiveProfileRevision", "profile-1", content_hash=HASH_C),
        "hypothesisRef": ref("SemanticHypothesisRevision", "hypothesis-1", content_hash=HASH_B),
        "sourceField": "order.pay_amount",
        "canonicalTargetRef": ref("OntologyFieldRevision", "Order.paidAmount"),
        "decision": "confirmed", "reviewer": "ontology-reviewer",
        "reason": "reviewed against ontology definition", "decidedAt": NOW,
        "idempotencyKey": "review-record-1", "requestHash": HASH_A,
        "createdAt": NOW,
    }
    value.update(changes)
    return value


def _load_migration():
    spec = util.spec_from_file_location("biw3_004", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mapping_requires_exact_human_confirmation_and_immutable_revision_chain() -> None:
    mapping = SourceMappingRevision.model_validate(mapping_payload())
    review = SourceMappingReviewDecisionRevision.model_validate(review_payload())
    mapping.validate_review(review)
    assert mapping.confirmation_ref.resource_type == "HumanReviewDecisionRevision"
    with pytest.raises(ValidationError, match="confirmationRef"):
        SourceMappingRevision.model_validate(mapping_payload(confirmationRef=None))
    with pytest.raises(ValidationError, match="priorRef"):
        SourceMappingRevision.model_validate(mapping_payload(revision=2))
    SourceMappingRevision.model_validate(
        mapping_payload(
            revision=2,
            priorRef=ref("SourceMappingRevision", "mapping-1", content_hash=HASH_A),
            contentHash=HASH_C,
            idempotencyKey="mapping-publish-2",
        )
    )
    with pytest.raises(ValueError, match="confirmed human review"):
        mapping.validate_review(
            SourceMappingReviewDecisionRevision.model_validate(
                review_payload(decision="rejected")
            )
        )


def test_mapping_exactly_matches_profile_hypothesis_and_preserves_unknown() -> None:
    profile = AdaptiveProfileRevision.model_validate(profile_payload())
    hypothesis = SemanticHypothesisRevision.model_validate(hypothesis_payload())
    mapping = SourceMappingRevision.model_validate(mapping_payload())
    mapping.validate_profile_hypothesis(profile, hypothesis)
    with pytest.raises(ValueError, match="unknown"):
        SourceMappingRevision.model_validate(
            mapping_payload(sourceField="order.member_id")
        ).validate_profile_hypothesis(profile, hypothesis)
    with pytest.raises(ValueError, match="canonical target"):
        SourceMappingRevision.model_validate(
            mapping_payload(canonicalTargetRef=ref("OntologyFieldRevision", "Order.discountAmount"))
        ).validate_profile_hypothesis(profile, hypothesis)


def test_mapping_rejects_non_ontology_target_and_raw_values() -> None:
    with pytest.raises(ValidationError, match="canonicalTargetRef"):
        SourceMappingRevision.model_validate(
            mapping_payload(canonicalTargetRef=ref("SourceMappingRevision", "other"))
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        SourceMappingRevision.model_validate(mapping_payload(sampleValues=["100.00"]))


def test_migration_is_cas_append_only_rls_and_reverse_traceable() -> None:
    module = _load_migration()
    assert module.revision == "biw3_004" and module.down_revision == "biw3_003"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "business_investigation_source_mapping_revision" in sql
    assert "business_investigation_source_mapping_head" in sql
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 3
    assert sql.count("FORCE ROW LEVEL SECURITY") == 3
    assert "source_mapping_review_record_biw3_004" in sql
    assert "source_mapping_publish_biw3_004" in sql and "expected_version" in sql
    assert "HumanReviewDecisionRevision" in sql and "unknownFields" in sql
    assert "idx_source_mapping_reverse_biw3_004" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "GRANT INSERT ON business_investigation_source_mapping" not in sql


def test_store_publishes_only_through_controlled_function() -> None:
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

    mapping = SourceMappingRevision.model_validate(mapping_payload())
    result = BusinessInvestigationMappingStore(connect).publish(SCOPE, mapping, expected_version=0)
    assert not result.replayed and result.authority.mapping_id == "mapping-1"
    assert connection.commits == 1
    assert "source_mapping_publish_biw3_004" in connection.calls[0][0]


def test_disposable_database_cas_isolation_unknown_direct_write_and_downgrade() -> None:
    with isolated_aip_migration_database("biw3_source_mapping") as (config, dsn):
        command.downgrade(config, "biw3_003")
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
            conn.execute(
                "INSERT INTO business_investigation_observation_session_lease(org_id,project_id,lease_id,revision,state_version,content_hash,platform,requirement_id,requirement_revision,requirement_content_hash,status,expires_at,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','lease-1',1,1,%s,'niushop','requirement-1',1,%s,'active',NOW()+INTERVAL '1 hour','seed-lease',%s,'{}')",
                (HASH_A, HASH_A, HASH_B),
            )
            conn.execute(
                "INSERT INTO business_investigation_observation_plan_head(org_id,project_id,plan_id,current_revision,current_content_hash,version) VALUES('org-org','dev-project','plan-1',1,%s,1)",
                (HASH_B,),
            )
            conn.execute(
                "INSERT INTO business_investigation_observation_plan_revision(org_id,project_id,plan_id,revision,content_hash,lease_id,lease_revision,lease_content_hash,requirement_id,requirement_revision,requirement_content_hash,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','plan-1',1,%s,'lease-1',1,%s,'requirement-1',1,%s,'seed-plan',%s,'{}')",
                (HASH_B, HASH_A, HASH_A, HASH_B),
            )
            conn.execute(
                "INSERT INTO business_investigation_observation_receipt(org_id,project_id,receipt_id,plan_id,plan_revision,plan_content_hash,step_id,capability_id,lease_id,lease_revision,lease_content_hash,requirement_id,requirement_revision,requirement_content_hash,status,semantic_route,cutoff_at,content_hash,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','receipt-1','plan-1',1,%s,'step-1','browser-read','lease-1',1,%s,'requirement-1',1,%s,'succeeded','/orders/**',NOW(),%s,'seed-receipt',%s,'{}')",
                (HASH_B, HASH_A, HASH_A, HASH_A, HASH_B),
            )
            job_data = {
                "receiptRefs": [ref("ObservationReceipt", "receipt-1")],
                "observationRefs": [ref("PlatformObservation", "observation-1")],
            }
            conn.execute(
                "INSERT INTO business_investigation_schema_profiling_job_revision(org_id,project_id,job_id,revision,content_hash,status,cutoff_at,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','job-1',1,%s,'requested',NOW(),'seed-job',%s,%s)",
                (HASH_A, HASH_B, psycopg.types.json.Jsonb(job_data)),
            )
            hypothesis_data = SemanticHypothesisRevision.model_validate(
                hypothesis_payload()
            ).model_dump(by_alias=True, mode="json")
            conn.execute(
                "INSERT INTO business_investigation_semantic_hypothesis_revision(org_id,project_id,hypothesis_id,revision,content_hash,job_id,job_revision,source_field,target_resource_type,risk_category,requires_human_review,authority_data) VALUES('org-org','dev-project','hypothesis-1',1,%s,'job-1',1,'order.pay_amount','OntologyFieldRevision','ordinary',false,%s)",
                (HASH_B, psycopg.types.json.Jsonb(hypothesis_data)),
            )
            profile_data = AdaptiveProfileRevision.model_validate(
                profile_payload()
            ).model_dump(by_alias=True, mode="json")
            conn.execute(
                "INSERT INTO business_investigation_adaptive_profile_revision(org_id,project_id,profile_id,revision,content_hash,job_id,job_revision,status,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','profile-1',1,%s,'job-1',1,'completed','seed-profile',%s,%s)",
                (HASH_C, HASH_A, psycopg.types.json.Jsonb(profile_data)),
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

        store = BusinessInvestigationMappingStore(runtime_connect)
        review = SourceMappingReviewDecisionRevision.model_validate(review_payload())
        assert not store.record_review(SCOPE, review).replayed
        assert store.record_review(SCOPE, review).replayed
        mapping = SourceMappingRevision.model_validate(mapping_payload())
        assert not store.publish(SCOPE, mapping, expected_version=0).replayed
        assert store.publish(SCOPE, mapping, expected_version=0).replayed
        with pytest.raises(BusinessInvestigationMappingConflict):
            store.publish(
                SCOPE,
                SourceMappingRevision.model_validate(mapping_payload(requestHash=HASH_C)),
                expected_version=0,
            )
        with pytest.raises(BusinessInvestigationMappingConflict):
            store.publish(
                SCOPE,
                SourceMappingRevision.model_validate(
                    mapping_payload(
                        sourceField="order.member_id",
                        mappingId="mapping-unknown",
                        idempotencyKey="mapping-unknown",
                    )
                ),
                expected_version=0,
            )
        revision_two = SourceMappingRevision.model_validate(
            mapping_payload(
                revision=2,
                priorRef=ref("SourceMappingRevision", "mapping-1", content_hash=HASH_A),
                contentHash=HASH_C,
                idempotencyKey="mapping-publish-2",
                requestHash=HASH_C,
                status="deprecated",
            )
        )
        with pytest.raises(BusinessInvestigationMappingConflict):
            store.publish(SCOPE, revision_two, expected_version=0)
        assert not store.publish(SCOPE, revision_two, expected_version=1).replayed

        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
            conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            assert conn.execute(
                "SELECT count(*) FROM business_investigation_source_mapping_head"
            ).fetchone()[0] == 0
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "INSERT INTO business_investigation_source_mapping_head(org_id,project_id,mapping_id,current_revision,current_content_hash,source_field,canonical_target_type,canonical_target_id,status,version) VALUES('dev-org','dev-project','direct',1,%s,'x','OntologyFieldRevision','X.y','active',1)",
                    (HASH_A,),
                )

        with pytest.raises(Exception, match="cannot downgrade biw3_004"):
            command.downgrade(config, "biw3_003")
