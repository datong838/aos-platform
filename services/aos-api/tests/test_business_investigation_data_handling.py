"""BI-W3-06 investigation marking, redaction and retention tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from importlib import util
from pathlib import Path
from unittest.mock import patch

import psycopg
import pytest
from alembic import command
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from aos_api.business_investigation_data_handling import (
    BusinessInvestigationDataHandlingConflict,
    BusinessInvestigationDataHandlingStore,
    InvestigationDataHandlingBindingRevision,
    InvestigationRedactionReceipt,
    InvestigationRetentionDispositionReceipt,
)
from aos_api.ontology_operational_authority import canonical_hash
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw3_006_investigation_data_handling.py"
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
NOW = datetime.now(UTC)
HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"
HASH_C = f"sha256:{'c' * 64}"
HASH_D = f"sha256:{'d' * 64}"


def ref(kind: str, identity: str, *, content_hash: str = HASH_A):
    return {"resourceType": kind, "resourceId": identity, "revision": 1, "contentHash": content_hash}


RETENTION_PAYLOAD = {
    "dataCategory": "business-investigation-redacted-artifact",
    "durationDays": 30,
    "cleanupMode": "delete_content_keep_hash",
    "policyOwner": "security-owner",
}
RETENTION_HASH = "sha256:" + canonical_hash(RETENTION_PAYLOAD)


def binding_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.data-handling-binding/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "bindingId": "handling-1", "revision": 1, "contentHash": HASH_C,
        "subjectRefs": [ref("SemanticHydrationReceipt", "hydration-1", content_hash=HASH_B)],
        "markingPolicyRef": ref("DataMarkingPolicyRevision", "marking-1"),
        "purposePolicyRef": ref("PurposePolicyRevision", "purpose-1"),
        "minimumPopulationPolicyRef": ref("MinimumPopulationPolicyRevision", "population-1"),
        "secretHandlingPolicyRef": ref("SecretHandlingPolicyRevision", "secret-policy-1"),
        "retentionPolicyRef": ref("OntologyRetentionPolicyRevision", "retention-1", content_hash=RETENTION_HASH),
        "domMode": "redacted_only", "screenshotMode": "redacted_only", "logMode": "redacted_only",
        "sampleMode": "blocked", "exportMode": "blocked",
        "customerOrderDetailAllowed": False, "downloadAllowed": False,
        "status": "active", "blockers": [], "idempotencyKey": "handling-bind-1",
        "requestHash": HASH_D, "createdBy": "security-owner", "createdAt": NOW,
    }
    value.update(changes)
    return value


def redaction_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.redaction-receipt/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "redactionId": "redaction-1", "contentHash": HASH_A,
        "bindingRef": ref("InvestigationDataHandlingBindingRevision", "handling-1", content_hash=HASH_C),
        "inputArtifactRef": ref("PageScreenshotArtifactRevision", "screenshot-1"),
        "outputArtifactRef": ref("RedactedArtifactRevision", "redacted-1", content_hash=HASH_B),
        "scannerRef": ref("SensitiveDataScannerRevision", "scanner-1"),
        "markingPolicyRef": ref("DataMarkingPolicyRevision", "marking-1"),
        "retentionPolicyRef": ref("OntologyRetentionPolicyRevision", "retention-1", content_hash=RETENTION_HASH),
        "status": "safe", "categoryCounts": {"pii": 2, "secret": 1},
        "redactedFieldPaths": ["customer.mobile", "session.secret_ref"],
        "rawBodyPersisted": False, "downloadAllowed": False,
        "inspectedAt": NOW, "blockers": [], "idempotencyKey": "redaction-record-1",
        "requestHash": HASH_B, "createdBy": "security-scanner",
    }
    value.update(changes)
    return value


def retention_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.retention-disposition-receipt/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "dispositionId": "disposition-1", "contentHash": HASH_D,
        "bindingRef": ref("InvestigationDataHandlingBindingRevision", "handling-1", content_hash=HASH_C),
        "artifactRef": ref("RedactedArtifactRevision", "redacted-1", content_hash=HASH_B),
        "retentionPolicyRef": ref("OntologyRetentionPolicyRevision", "retention-1", content_hash=RETENTION_HASH),
        "disposition": "retain_redacted", "retainedContentHash": HASH_B,
        "dueAt": NOW + timedelta(days=30), "decidedAt": NOW, "blockers": [],
        "idempotencyKey": "retention-record-1", "requestHash": HASH_C,
        "createdBy": "retention-controller",
    }
    value.update(changes)
    return value


def _migration():
    spec = util.spec_from_file_location("biw3_006", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_binding_is_redacted_only_and_rejects_sensitive_extra_values() -> None:
    binding = InvestigationDataHandlingBindingRevision.model_validate(binding_payload())
    assert not binding.download_allowed and not binding.customer_order_detail_allowed
    with pytest.raises(ValidationError, match="redacted_only"):
        InvestigationDataHandlingBindingRevision.model_validate(binding_payload(screenshotMode="restricted_raw"))
    with pytest.raises(ValidationError, match="Extra inputs"):
        InvestigationDataHandlingBindingRevision.model_validate(binding_payload(rawBody="customer secret"))


def test_redaction_receipt_requires_safe_output_and_exact_binding_policies() -> None:
    binding = InvestigationDataHandlingBindingRevision.model_validate(binding_payload())
    receipt = InvestigationRedactionReceipt.model_validate(redaction_payload())
    receipt.validate_binding(binding)
    with pytest.raises(ValidationError, match="safe redaction requires"):
        InvestigationRedactionReceipt.model_validate(redaction_payload(outputArtifactRef=None))
    with pytest.raises(ValueError, match="policy refs"):
        InvestigationRedactionReceipt.model_validate(
            redaction_payload(markingPolicyRef=ref("DataMarkingPolicyRevision", "other"))
        ).validate_binding(binding)
    with pytest.raises(ValidationError, match="logical paths"):
        InvestigationRedactionReceipt.model_validate(
            redaction_payload(redactedFieldPaths=["customer.mobile=not-a-logical-path"])
        )


def test_retention_delete_requires_cleanup_receipt_and_expired_retain_fails() -> None:
    binding = InvestigationDataHandlingBindingRevision.model_validate(binding_payload())
    receipt = InvestigationRetentionDispositionReceipt.model_validate(retention_payload())
    receipt.validate_binding(binding)
    with pytest.raises(ValidationError, match="cleanup receipt"):
        InvestigationRetentionDispositionReceipt.model_validate(
            retention_payload(disposition="delete_content_keep_hash")
        )
    deleted = InvestigationRetentionDispositionReceipt.model_validate(
        retention_payload(
            disposition="delete_content_keep_hash",
            cleanupReceiptRef=ref("OntologyEvidenceCleanupReceipt", "cleanup-1"),
        )
    )
    assert deleted.cleanup_receipt_ref is not None
    with pytest.raises(ValidationError, match="expired retention"):
        InvestigationRetentionDispositionReceipt.model_validate(
            retention_payload(dueAt=NOW - timedelta(days=1))
        )


def test_migration_is_immutable_tenant_scoped_and_function_only() -> None:
    module = _migration()
    assert module.revision == "biw3_006" and module.down_revision == "biw3_005"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert sql.count("ENABLE ROW LEVEL SECURITY") == 3
    assert sql.count("FORCE ROW LEVEL SECURITY") == 3
    assert sql.count("INVESTIGATION_DATA_HANDLING_IMMUTABLE") == 1
    assert "current exact retention policy is required" in sql
    assert "restricted raw artifact mode is not authorized" in sql
    assert sql.count("GRANT EXECUTE ON FUNCTION") == 3
    assert "GRANT INSERT ON business_investigation" not in sql


def test_store_uses_three_controlled_functions() -> None:
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
    store = BusinessInvestigationDataHandlingStore(connect)
    assert not store.bind(SCOPE, InvestigationDataHandlingBindingRevision.model_validate(binding_payload())).replayed
    assert not store.record_redaction(SCOPE, InvestigationRedactionReceipt.model_validate(redaction_payload())).replayed
    assert not store.record_retention(SCOPE, InvestigationRetentionDispositionReceipt.model_validate(retention_payload())).replayed
    assert connection.commits == 3
    assert "investigation_data_handling_bind_biw3_006" in connection.calls[0][0]
    assert "investigation_redaction_record_biw3_006" in connection.calls[1][0]
    assert "investigation_retention_record_biw3_006" in connection.calls[2][0]


def test_disposable_database_empty_upgrade_and_downgrade() -> None:
    with isolated_aip_migration_database("biw3_data_handling") as (config, _dsn):
        command.downgrade(config, "biw3_005")
        command.upgrade(config, "head")


def test_disposable_database_exact_policy_receipts_isolation_and_downgrade() -> None:
    with isolated_aip_migration_database("biw3_data_handling_authority") as (config, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','BI-W3') ON CONFLICT DO NOTHING")
            conn.execute("INSERT INTO ontology_retention_policy_head(org_id,workspace_id,record_id,active_revision) VALUES('org-org','dev-project','retention-1',1)")
            conn.execute(
                "INSERT INTO ontology_retention_policy_revision(org_id,workspace_id,record_id,revision,payload,payload_hash,created_by) VALUES('org-org','dev-project','retention-1',1,%s,%s,'security-owner')",
                (Jsonb(RETENTION_PAYLOAD), RETENTION_HASH.removeprefix("sha256:")),
            )
            conn.execute("INSERT INTO business_investigation_schema_profiling_job_revision(org_id,project_id,job_id,revision,content_hash,status,cutoff_at,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','profile-job',1,%s,'requested',NOW(),'profile-job',%s,'{}')", (HASH_A, HASH_B))
            conn.execute("INSERT INTO business_investigation_adaptive_profile_revision(org_id,project_id,profile_id,revision,content_hash,job_id,job_revision,status,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','profile-1',1,%s,'profile-job',1,'completed','profile-1',%s,%s)", (HASH_A, HASH_B, Jsonb({"unknownFields": []})))
            hydration_job = {"mappingRefs": [], "unknownFields": []}
            conn.execute("INSERT INTO business_investigation_semantic_hydration_job_revision(org_id,project_id,hydration_job_id,revision,content_hash,status,profile_id,profile_revision,cutoff_at,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','hydration-job-1',1,%s,'requested','profile-1',1,NOW(),'hydration-job-1',%s,%s)", (HASH_A, HASH_B, Jsonb(hydration_job)))
            conn.execute("INSERT INTO business_investigation_semantic_hydration_receipt(org_id,project_id,hydration_id,hydration_job_id,hydration_job_revision,content_hash,status,attempted,created_count,updated_count,quarantined_count,unknown_count,zero_observed,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','hydration-1','hydration-job-1',1,%s,'succeeded',0,0,0,0,0,true,'hydration-1',%s,'{}')", (HASH_B, HASH_C))
            conn.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
                yield conn

        store = BusinessInvestigationDataHandlingStore(runtime_connect)
        binding = InvestigationDataHandlingBindingRevision.model_validate(binding_payload())
        assert not store.bind(SCOPE, binding).replayed
        assert store.bind(SCOPE, binding).replayed
        with pytest.raises(BusinessInvestigationDataHandlingConflict):
            store.bind(
                SCOPE,
                InvestigationDataHandlingBindingRevision.model_validate(
                    binding_payload(
                        bindingId="handling-bad-policy",
                        idempotencyKey="handling-bad-policy",
                        requestHash=HASH_A,
                        retentionPolicyRef=ref("OntologyRetentionPolicyRevision", "retention-1", content_hash=HASH_D),
                    )
                ),
            )
        raw_bypass = redaction_payload(
            redactionId="raw-bypass",
            outputArtifactRef=None,
            idempotencyKey="raw-bypass",
            requestHash=HASH_D,
            rawBody="must-not-persist",
        )
        raw_bypass["inspectedAt"] = NOW.isoformat()
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
            with pytest.raises(psycopg.Error):
                conn.execute(
                    "SELECT * FROM investigation_redaction_record_biw3_006(%s,%s,%s,%s)",
                    ("raw-bypass", "raw-bypass", HASH_D, Jsonb(raw_bypass)),
                )
        redaction = InvestigationRedactionReceipt.model_validate(redaction_payload())
        assert not store.record_redaction(SCOPE, redaction).replayed
        assert store.record_redaction(SCOPE, redaction).replayed
        disposition = InvestigationRetentionDispositionReceipt.model_validate(retention_payload())
        assert not store.record_retention(SCOPE, disposition).replayed
        with pytest.raises(BusinessInvestigationDataHandlingConflict):
            store.record_retention(
                SCOPE,
                InvestigationRetentionDispositionReceipt.model_validate(
                    retention_payload(
                        dispositionId="missing-cleanup",
                        disposition="delete_content_keep_hash",
                        cleanupReceiptRef=ref("OntologyEvidenceCleanupReceipt", "00000000-0000-0000-0000-000000000000"),
                        idempotencyKey="missing-cleanup",
                        requestHash=HASH_D,
                    )
                ),
            )
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','dev-org',true),set_config('aos.project_id','dev-project',true)")
            assert conn.execute("SELECT count(*) FROM business_investigation_redaction_receipt").fetchone()[0] == 0
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("INSERT INTO business_investigation_redaction_receipt(org_id,project_id,redaction_id,binding_id,binding_revision,content_hash,status,raw_body_persisted,download_allowed,idempotency_key,request_hash,authority_data) VALUES('dev-org','dev-project','direct','handling-1',1,%s,'safe',false,false,'direct',%s,'{}')", (HASH_A, HASH_B))
        with pytest.raises(Exception, match="cannot downgrade biw3_006"):
            command.downgrade(config, "biw3_005")
