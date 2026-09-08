"""BI-W3-02 exact observation receipt and evidence/fact separation tests."""

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
from pydantic import ValidationError

from aos_api.business_investigation_observation_contracts import ObservationReceiptRecord
from aos_api.business_investigation_observation_store import (
    BusinessInvestigationObservationConflict,
    BusinessInvestigationObservationStore,
    BusinessInvestigationObservationValidationError,
)
from aos_api.tenant_scope import TenantScope
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from tests.aip._migration_test_support import isolated_aip_migration_database


MIGRATION = Path(__file__).parents[1] / "alembic/versions/biw3_002_observation_receipt.py"
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
OTHER_SCOPE = TenantScope(org_id="dev-org", project_id="dev-project")
NOW = datetime.now(UTC)
HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"
HASH_C = f"sha256:{'c' * 64}"


def ref(resource_type: str, resource_id: str, *, revision: int = 1, content_hash: str = HASH_A):
    return {"resourceType": resource_type, "resourceId": resource_id, "revision": revision, "contentHash": content_hash}


def receipt_payload(**changes):
    value = {
        "schemaVersion": "aos.business-investigation.observation-receipt/v1",
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "receiptId": "receipt-1",
        "planRef": ref("ObservationPlanRevision", "plan-1", content_hash=HASH_B),
        "stepRef": ref("ObservationPlanStepRevision", "plan-1:step-1", content_hash=HASH_B),
        "capabilityRef": ref("CapabilityRevision", "browser-read"),
        "sessionRef": ref("ObservationSessionLeaseRevision", "lease-1"),
        "requirementRef": ref("DataRequirementRevision", "requirement-1"),
        "status": "succeeded",
        "semanticRoute": "/orders/**",
        "startedAt": NOW + timedelta(minutes=2),
        "cutoffAt": NOW + timedelta(minutes=3),
        "finishedAt": NOW + timedelta(minutes=4),
        "observedFieldSet": ["Order.paidAmount", "Order.paidAt"],
        "coverage": {"pagesExpected": 2, "pagesObserved": 2, "rowsExpected": 20, "rowsObserved": 18, "rowsUnknown": 2},
        "locationEvidenceRefs": [ref("DOMSnapshotArtifactRevision", "dom-1")],
        "factObservationRefs": [ref("PlatformObservation", "observation-1")],
        "pageFingerprint": HASH_C,
        "operatorRef": "operator-1",
        "humanIntervention": False,
        "nonClaims": ["DOM location evidence is not business fact authority"],
        "nextStep": "map-fields",
        "blockers": [],
        "contentHash": HASH_A,
        "idempotencyKey": "receipt-record-1",
        "requestHash": HASH_B,
        "createdBy": "adapter-test",
    }
    value.update(changes)
    return value


def _load_migration():
    spec = util.spec_from_file_location("biw3_002", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_receipt_keeps_location_evidence_and_business_facts_separate() -> None:
    receipt = ObservationReceiptRecord.model_validate(receipt_payload())
    assert receipt.location_evidence_refs[0].resource_type == "DOMSnapshotArtifactRevision"
    assert receipt.fact_observation_refs[0].resource_type == "PlatformObservation"

    bad_location = receipt_payload(locationEvidenceRefs=[ref("PlatformObservation", "obs")])
    with pytest.raises(ValidationError, match="locationEvidenceRefs"):
        ObservationReceiptRecord.model_validate(bad_location)

    bad_fact = receipt_payload(factObservationRefs=[ref("PageScreenshotArtifactRevision", "shot")])
    with pytest.raises(ValidationError, match="factObservationRefs"):
        ObservationReceiptRecord.model_validate(bad_fact)

    raw_value = receipt_payload(observedValues={"Order.paidAmount": "100.00"})
    with pytest.raises(ValidationError, match="Extra inputs"):
        ObservationReceiptRecord.model_validate(raw_value)


def test_receipt_timing_coverage_route_and_failure_states_fail_closed() -> None:
    with pytest.raises(ValidationError, match="semantic route"):
        ObservationReceiptRecord.model_validate(receipt_payload(semanticRoute="https://admin.test/orders?token=x"))
    with pytest.raises(ValidationError, match="timestamp"):
        ObservationReceiptRecord.model_validate(receipt_payload(finishedAt=NOW))
    with pytest.raises(ValidationError, match="coverage"):
        ObservationReceiptRecord.model_validate(
            receipt_payload(coverage={"pagesExpected": 1, "pagesObserved": 2, "rowsExpected": 10, "rowsObserved": 8, "rowsUnknown": 3})
        )
    with pytest.raises(ValidationError, match="blocker"):
        ObservationReceiptRecord.model_validate(
            receipt_payload(status="unknown", locationEvidenceRefs=[], factObservationRefs=[], blockers=[])
        )


def test_migration_is_append_only_tenant_scoped_and_validates_current_refs() -> None:
    module = _load_migration()
    assert module.revision == "biw3_002" and module.down_revision == "biw3_001"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert "CREATE TABLE business_investigation_observation_receipt" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql and "FORCE ROW LEVEL SECURITY" in sql
    assert "SECURITY DEFINER" in sql and "observation_receipt_record_biw3_002" in sql
    assert "ObservationPlanStepRevision" in sql and "CapabilityRevision" in sql
    assert "PageScreenshotArtifactRevision" in sql and "PlatformObservation" in sql
    assert "current_revision" in sql and "status<>'active'" in sql and "expires_at<=NOW()" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "GRANT INSERT ON business_investigation_observation_receipt" not in sql


def test_store_records_through_controlled_function_only() -> None:
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

    result = BusinessInvestigationObservationStore(connect).record_receipt(
        SCOPE, ObservationReceiptRecord.model_validate(receipt_payload())
    )
    assert not result.replayed and result.authority.receipt_id == "receipt-1"
    assert connection.commits == 1
    assert "observation_receipt_record_biw3_002" in connection.calls[0][0]


@pytest.mark.parametrize("defect", ["missing", "tenant", "hash", "plan", "payload", "revision", "type", "receipt"])
def test_exact_observation_read_rejects_invalid_identity_without_writes(defect):
    from tests.test_data_fulfillment_store import Connection
    item = ObservationReceiptRecord.model_validate(receipt_payload())
    exact = InvestigationExactRef(resource_type="ObservationReceipt", resource_id=item.receipt_id,
                                  revision=1, content_hash=item.content_hash)
    row = {"authority_data": item.model_dump(by_alias=True), "org_id": SCOPE.org_id,
           "project_id": SCOPE.project_id, "receipt_id": item.receipt_id,
           "plan_id": item.plan_ref.resource_id, "plan_revision": item.plan_ref.revision,
           "plan_content_hash": item.plan_ref.content_hash,
           "step_id": item.step_ref.resource_id.removeprefix(item.plan_ref.resource_id + ":"),
           "capability_id": item.capability_ref.resource_id, "lease_id": item.session_ref.resource_id,
           "lease_revision": item.session_ref.revision, "lease_content_hash": item.session_ref.content_hash,
           "requirement_id": item.requirement_ref.resource_id, "requirement_revision": item.requirement_ref.revision,
           "requirement_content_hash": item.requirement_ref.content_hash, "status": item.status.value,
           "semantic_route": item.semantic_route, "cutoff_at": item.cutoff_at, "content_hash": item.content_hash,
           "idempotency_key": item.idempotency_key, "request_hash": item.request_hash}
    if defect == "tenant": row["org_id"] = "dev-org"
    if defect == "hash": row["content_hash"] = HASH_C
    if defect == "plan": row["plan_revision"] = 99
    if defect == "payload": row["authority_data"]["tenant"]["orgId"] = "dev-org"
    if defect == "revision": exact = exact.model_copy(update={"revision": "1"})
    if defect == "type": exact = exact.model_copy(update={"resource_type": "PlatformObservation"})
    if defect == "receipt": exact = exact.model_copy(update={"receipt_id": "other"})
    conn = Connection(None if defect == "missing" else row)
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield conn
    store = BusinessInvestigationObservationStore(connect)
    if defect == "missing": assert store.read_receipt_exact(SCOPE, exact) is None
    else:
        with pytest.raises(BusinessInvestigationObservationValidationError):
            store.read_receipt_exact(SCOPE, exact)
    assert conn.commits == 0
    assert all(sql.startswith("SELECT") and "head" not in sql for sql, _ in conn.calls)


def test_disposable_database_idempotency_current_refs_isolation_and_rollback() -> None:
    with isolated_aip_migration_database(
        "biw3_observation_receipt", migration_target="biw3_002"
    ) as (config, dsn):
        command.downgrade(config, "biw3_001")
        command.upgrade(config, "biw3_002")
        with psycopg.connect(dsn) as conn:
            for org in ("org-org", "dev-org"):
                conn.execute(
                    "INSERT INTO data_requirement_head(org_id,project_id,requirement_id,current_revision,current_content_hash,status,version,created_by) VALUES(%s,'dev-project','requirement-1',1,%s,'accepted',1,'pytest')",
                    (org, "a" * 64),
                )
                conn.execute(
                    "INSERT INTO data_requirement_revision(org_id,project_id,requirement_id,revision,content_hash,status,operation,idempotency_key,request_hash,case_ref,run_ref,checkpoint_ref,payload,created_by) VALUES(%s,'dev-project','requirement-1',1,%s,'accepted','request','seed',%s,'{}','{}','{}','{}','pytest')",
                    (org, "a" * 64, "b" * 64),
                )
                lease_payload = {
                    "tenant": {"orgId": org, "projectId": "dev-project"}, "leaseId": "lease-1", "revision": 1,
                    "contentHash": HASH_A, "status": "active", "expiresAt": (NOW + timedelta(hours=1)).isoformat(),
                    "allowedDomains": ["admin.example.test"], "allowedRoutePatterns": ["/orders/**"],
                    "allowedReadActions": ["read"], "requirementRef": ref("DataRequirementRevision", "requirement-1"),
                }
                conn.execute(
                    "INSERT INTO business_investigation_observation_session_lease(org_id,project_id,lease_id,revision,state_version,content_hash,platform,requirement_id,requirement_revision,requirement_content_hash,status,expires_at,idempotency_key,request_hash,authority_data) VALUES(%s,'dev-project','lease-1',1,1,%s,'niushop','requirement-1',1,%s,'active',NOW()+INTERVAL '1 hour','seed-lease',%s,%s)",
                    (org, HASH_A, HASH_A, HASH_B, psycopg.types.json.Jsonb(lease_payload)),
                )
                plan_data = {
                    "tenant": {"orgId": org, "projectId": "dev-project"}, "planId": "plan-1", "revision": 1,
                    "contentHash": HASH_B, "leaseRef": ref("ObservationSessionLeaseRevision", "lease-1"),
                    "requirementRef": ref("DataRequirementRevision", "requirement-1"),
                    "steps": [{"stepId": "step-1", "action": "read", "domain": "admin.example.test", "routePattern": "/orders/**"}],
                }
                conn.execute(
                    "INSERT INTO business_investigation_observation_plan_head(org_id,project_id,plan_id,current_revision,current_content_hash,version) VALUES(%s,'dev-project','plan-1',1,%s,1)",
                    (org, HASH_B),
                )
                conn.execute(
                    "INSERT INTO business_investigation_observation_plan_revision(org_id,project_id,plan_id,revision,content_hash,lease_id,lease_revision,lease_content_hash,requirement_id,requirement_revision,requirement_content_hash,idempotency_key,request_hash,authority_data) VALUES(%s,'dev-project','plan-1',1,%s,'lease-1',1,%s,'requirement-1',1,%s,'seed-plan',%s,%s)",
                    (org, HASH_B, HASH_A, HASH_A, HASH_B, psycopg.types.json.Jsonb(plan_data)),
                )
            conn.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
                yield conn

        store = BusinessInvestigationObservationStore(runtime_connect)
        receipt = ObservationReceiptRecord.model_validate(receipt_payload())
        assert not store.record_receipt(SCOPE, receipt).replayed
        assert store.record_receipt(SCOPE, receipt).replayed
        exact_receipt = InvestigationExactRef(resource_type="ObservationReceipt", resource_id=receipt.receipt_id,
                                             revision=1, content_hash=receipt.content_hash)
        assert store.read_receipt_exact(SCOPE, exact_receipt) == receipt
        assert store.read_receipt_exact(OTHER_SCOPE, exact_receipt) is None
        with pytest.raises(BusinessInvestigationObservationConflict):
            store.record_receipt(
                SCOPE,
                ObservationReceiptRecord.model_validate(receipt_payload(requestHash=HASH_C)),
            )
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "UPDATE business_investigation_observation_plan_head SET current_revision=2,current_content_hash=%s,version=2 WHERE org_id='org-org' AND project_id='dev-project' AND plan_id='plan-1'",
                (HASH_C,),
            )
            conn.commit()
        with pytest.raises(BusinessInvestigationObservationConflict):
            store.record_receipt(
                SCOPE,
                ObservationReceiptRecord.model_validate(
                    receipt_payload(receiptId="receipt-old-plan", idempotencyKey="old-plan")
                ),
            )
        assert store.read_receipt_exact(SCOPE, exact_receipt) == receipt
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "UPDATE business_investigation_observation_plan_head SET current_revision=1,current_content_hash=%s,version=1 WHERE org_id='org-org' AND project_id='dev-project' AND plan_id='plan-1'",
                (HASH_B,),
            )
            conn.commit()
        with pytest.raises(BusinessInvestigationObservationConflict):
            store.record_receipt(
                SCOPE,
                ObservationReceiptRecord.model_validate(
                    receipt_payload(receiptId="receipt-step-missing", idempotencyKey="missing-step", stepRef=ref("ObservationPlanStepRevision", "plan-1:missing", content_hash=HASH_B))
                ),
            )

        other = ObservationReceiptRecord.model_validate(
            receipt_payload(tenant={"orgId": "dev-org", "projectId": "dev-project"}, receiptId="receipt-other", idempotencyKey="receipt-other")
        )
        assert not store.record_receipt(OTHER_SCOPE, other).replayed

        with psycopg.connect(dsn) as conn:
            conn.execute("UPDATE business_investigation_observation_session_lease SET status='revoked' WHERE org_id='org-org' AND project_id='dev-project' AND lease_id='lease-1'")
            conn.commit()
        with pytest.raises(BusinessInvestigationObservationConflict):
            store.record_receipt(
                SCOPE,
                ObservationReceiptRecord.model_validate(receipt_payload(receiptId="receipt-revoked", idempotencyKey="receipt-revoked")),
            )
        with psycopg.connect(dsn) as conn:
            conn.execute("UPDATE business_investigation_observation_session_lease SET status='active',expires_at=NOW()-INTERVAL '1 second' WHERE org_id='org-org' AND project_id='dev-project' AND lease_id='lease-1'")
            conn.commit()
        with pytest.raises(BusinessInvestigationObservationConflict):
            store.record_receipt(
                SCOPE,
                ObservationReceiptRecord.model_validate(receipt_payload(receiptId="receipt-expired", idempotencyKey="receipt-expired")),
            )

        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','org-org',true)")
            conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "INSERT INTO business_investigation_observation_receipt(org_id,project_id,receipt_id,plan_id,plan_revision,plan_content_hash,step_id,lease_id,lease_revision,lease_content_hash,requirement_id,requirement_revision,requirement_content_hash,status,semantic_route,idempotency_key,request_hash,authority_data) VALUES('org-org','dev-project','direct','plan-1',1,%s,'step-1','lease-1',1,%s,'requirement-1',1,%s,'succeeded','/orders/**','direct',%s,'{}')",
                    (HASH_B, HASH_A, HASH_A, HASH_B),
                )

        with pytest.raises(Exception, match="cannot downgrade biw3_002"):
            command.downgrade(config, "biw3_001")
