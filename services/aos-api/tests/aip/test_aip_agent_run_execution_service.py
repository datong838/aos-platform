from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_agent_run_execution_contracts import (
    AgentRunExecutionStatus,
    CreateAgentRunExecutionAttemptRequest,
    TransitionAgentRunExecutionAttemptRequest,
)
from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
from aos_api.aip_contracts import ArtifactRef, ResourceRef
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 17, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
HASH = "a" * 64


def asset(kind: str, value: str) -> VersionedAssetRef:
    return VersionedAssetRef(assetType=kind, assetId=value, revision=1, contentHash=HASH)


def create_request() -> CreateAgentRunExecutionAttemptRequest:
    return CreateAgentRunExecutionAttemptRequest(
        attemptId="attempt-1",
        agentRunRef=ResourceRef(resourceType="AgentRun", resourceId="run-1", revision="1", authority="postgresql"),
        attemptNo=1,
        routeRef=asset("ModelRouteRevision", "route-1"),
        policyRef=asset("RuntimePolicyRevision", "policy-1"),
        modelRef=asset("RegisteredModelRevision", "model-1"),
        providerRef=asset("ProviderInstanceRevision", "provider-1"),
        priceSnapshotRef=asset("ModelPriceSnapshotRevision", "price-1"),
        budgetRef=asset("BudgetRevision", "budget-1"),
        capacityReservationRef=ResourceRef(resourceType="CapacityReservation", resourceId="capacity-1", revision="1", authority="postgresql"),
        dataClassification="internal", lineageId="lineage-1", requestHash="b" * 64,
    )


def attempt_row(status: str = "prepared", version: int = 1):
    request = create_request()
    return {
        "attempt_id": "attempt-1", "agent_run_id": "run-1", "agent_run_version": 1,
        "attempt_no": 1, "route_ref": request.route_ref.model_dump(mode="json", by_alias=True),
        "policy_ref": request.policy_ref.model_dump(mode="json", by_alias=True),
        "model_ref": request.model_ref.model_dump(mode="json", by_alias=True),
        "provider_ref": request.provider_ref.model_dump(mode="json", by_alias=True),
        "price_snapshot_ref": request.price_snapshot_ref.model_dump(mode="json", by_alias=True),
        "budget_ref": request.budget_ref.model_dump(mode="json", by_alias=True),
        "capacity_reservation_ref": request.capacity_reservation_ref.model_dump(mode="json", by_alias=True),
        "data_classification": "internal", "lineage_id": "lineage-1", "request_hash": "b" * 64,
        "status": status, "provider_receipt_id": None, "usage_receipt_ids": [],
        "output_artifact_ref": None, "reason_code": None, "version": version,
        "prepared_at": NOW, "invoking_at": NOW if status != "prepared" else None,
        "completed_at": None, "created_by": "pytest", "updated_at": NOW,
    }


class Result:
    def __init__(self, row=None, rows=None): self.row=row; self.rows=rows or []
    def fetchone(self): return self.row
    def fetchall(self): return self.rows


class CreateConn:
    committed = False
    def execute(self, query, args=None):
        if "pg_advisory" in query: return Result()
        if "FROM aip_agent_registry_receipt" in query: return Result(None)
        if "FROM aip_agent_run WHERE" in query:
            req = create_request()
            return Result({"status":"running","version":1,
                "model_route_ref":req.route_ref.model_dump(mode="json",by_alias=True),
                "policy_ref":req.policy_ref.model_dump(mode="json",by_alias=True)})
        if "FROM aip_model_capacity_reservation" in query:
            req = create_request()
            return Result({"reservation_id":"capacity-1","status":"reserved","expires_at":NOW+timedelta(minutes=5),
                "route_ref":req.route_ref.model_dump(mode="json",by_alias=True),
                "model_ref":req.model_ref.model_dump(mode="json",by_alias=True),
                "provider_ref":req.provider_ref.model_dump(mode="json",by_alias=True)})
        if "FROM aip_model_price_snapshot_revision" in query:
            return Result({"lifecycle":"active","content_hash":HASH})
        if "FROM aip_budget_revision" in query:
            return Result({"lifecycle":"active","content_hash":HASH,"effective_from":NOW-timedelta(days=1),"effective_until":None})
        if "INSERT INTO aip_agent_run_execution_attempt" in query: return Result(attempt_row())
        if "INSERT INTO aip_agent_registry_receipt" in query:
            return Result({"receipt_id":"receipt-1","operation":"agent_run_execution_attempt.create",
                "idempotency_key":"idem-1","request_hash":AipAgentRunExecutionService._command_hash(create_request(),"pytest"),
                "resource_ref":{"resourceType":"AgentRun","resourceId":"run-1","revision":None,"authority":"postgresql"},
                "result_ref":{"resourceType":"AgentRunExecutionAttempt","resourceId":"attempt-1","revision":None,"authority":"postgresql"},
                "status":"applied","created_by":"pytest","created_at":NOW})
        raise AssertionError(query)
    def commit(self): self.committed=True


def factory(conn):
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield conn
    return connect


def test_create_persists_only_hashes_and_exact_refs() -> None:
    conn = CreateConn()
    attempt, receipt = AipAgentRunExecutionService(factory(conn)).create(
        SCOPE, create_request(), idempotency_key="idem-1", actor="pytest", occurred_at=NOW
    )
    assert attempt.status is AgentRunExecutionStatus.PREPARED
    assert attempt.request_hash == "b" * 64 and conn.committed
    assert receipt.receipt_id == "receipt-1"


def test_create_fails_closed_without_running_agent_run() -> None:
    conn = CreateConn()
    original = conn.execute
    def execute(query, args=None):
        result = original(query, args)
        if "FROM aip_agent_run WHERE" in query: result.row["status"] = "queued"
        return result
    conn.execute = execute
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="not running"):
        AipAgentRunExecutionService(factory(conn)).create(
            SCOPE, create_request(), idempotency_key="idem-1", actor="pytest", occurred_at=NOW
        )
    assert not conn.committed


@pytest.mark.parametrize(
    ("target", "field", "value", "error_type", "message"),
    [
        ("run", "version", 2, AipAgentRegistryConflict, "exact revision drifted"),
        ("run", "model_route_ref", {"drifted": True}, AipAgentRegistryConflict, "execution route differs"),
        ("run", "policy_ref", {"drifted": True}, AipAgentRegistryConflict, "execution policy differs"),
        ("capacity", "status", "released", AipAgentRegistryTransitionBlocked, "active capacity"),
        ("capacity", "expires_at", NOW, AipAgentRegistryTransitionBlocked, "capacity reservation expired"),
        ("capacity", "route_ref", {"drifted": True}, AipAgentRegistryConflict, "runtime refs drifted"),
        ("capacity", "model_ref", {"drifted": True}, AipAgentRegistryConflict, "runtime refs drifted"),
        ("capacity", "provider_ref", {"drifted": True}, AipAgentRegistryConflict, "runtime refs drifted"),
        ("price", "lifecycle", "suspended", AipAgentRegistryTransitionBlocked, "active exact price"),
        ("price", "content_hash", "0" * 64, AipAgentRegistryTransitionBlocked, "active exact price"),
        ("budget", "lifecycle", "suspended", AipAgentRegistryTransitionBlocked, "active exact budget"),
        ("budget", "content_hash", "0" * 64, AipAgentRegistryTransitionBlocked, "active exact budget"),
        ("budget", "effective_from", NOW + timedelta(seconds=1), AipAgentRegistryTransitionBlocked, "active exact budget"),
        ("budget", "effective_until", NOW, AipAgentRegistryTransitionBlocked, "active exact budget"),
    ],
)
def test_create_rejects_runtime_authority_drift_and_expiry_before_insert(
    target, field, value, error_type, message
) -> None:
    conn = CreateConn()
    original = conn.execute

    def execute(query, args=None):
        result = original(query, args)
        matched = (
            (target == "run" and "FROM aip_agent_run WHERE" in query)
            or (target == "capacity" and "FROM aip_model_capacity_reservation" in query)
            or (target == "price" and "FROM aip_model_price_snapshot_revision" in query)
            or (target == "budget" and "FROM aip_budget_revision" in query)
        )
        if matched:
            result.row[field] = value
        return result

    conn.execute = execute
    with pytest.raises(error_type, match=message):
        AipAgentRunExecutionService(factory(conn)).create(
            SCOPE,
            create_request(),
            idempotency_key="idem-1",
            actor="pytest",
            occurred_at=NOW,
        )
    assert not conn.committed


def test_contract_forbids_success_without_usage_lineage_artifact_chain() -> None:
    with pytest.raises(ValueError, match="provider, usage and artifact"):
        TransitionAgentRunExecutionAttemptRequest(
            expectedVersion=2, fromStatus="invoking", toStatus="succeeded",
            providerReceiptId="provider-1", usageReceiptIds=[],
        )


def test_contract_requires_reason_for_unknown_and_never_retries() -> None:
    body = TransitionAgentRunExecutionAttemptRequest(
        expectedVersion=2, fromStatus="invoking", toStatus="unknown",
        reasonCode="PROVIDER_RESULT_UNKNOWN",
    )
    assert body.reason_code == "PROVIDER_RESULT_UNKNOWN"
    with pytest.raises(ValueError, match="reason_code"):
        TransitionAgentRunExecutionAttemptRequest(
            expectedVersion=2, fromStatus="invoking", toStatus="unknown"
        )


def test_success_contract_accepts_complete_evidence_only() -> None:
    body = TransitionAgentRunExecutionAttemptRequest(
        expectedVersion=2, fromStatus="invoking", toStatus="succeeded",
        providerReceiptId="provider-1", usageReceiptIds=["usage-1"],
        outputArtifactRef=ArtifactRef(artifactId="artifact-1", artifactType="text", revision="1", contentHash=HASH),
    )
    assert body.to_status is AgentRunExecutionStatus.SUCCEEDED
