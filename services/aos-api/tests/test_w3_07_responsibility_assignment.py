"""W3-07 responsibility successor, takeover and fence control tests."""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from aos_api.aip_production_contracts import AssigneeKind, AssigneeRef, ExactRevisionRef
from aos_api.aip_responsibility_assignment import (
    AssertAssignmentFenceRequest,
    CreateResponsibilitySuccessorRequest,
    CreateTakeoverRequest,
    DecideTakeoverRequest,
    RuntimeAuthorityRef,
    TakeoverDecisionValue,
    TakeoverRequestStatus,
    TakeoverSafetyState,
)
from aos_api.aip_responsibility_assignment_store import (
    AipResponsibilityAssignmentStore,
    ResponsibilityAssignmentBlocked,
    ResponsibilityAssignmentConflict,
)
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 25, 0, 45, tzinfo=UTC)
HASH = "a" * 64


class _Result:
    def __init__(self, value: Any) -> None:
        self.value = value

    def fetchone(self) -> Any:
        return self.value

    def fetchall(self) -> Any:
        return self.value


class _ScriptedConnection:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.queries: list[tuple[str, tuple[Any, ...]]] = []
        self.commits = 0

    def __enter__(self) -> _ScriptedConnection:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> _Result:
        self.queries.append((" ".join(query.split()), params))
        if not self.responses:
            raise AssertionError(f"unexpected SQL: {query}")
        value = self.responses.pop(0)
        if callable(value):
            value = value(query, params)
        return _Result(value)

    def commit(self) -> None:
        self.commits += 1


def _factory(conn: _ScriptedConnection) -> Callable[[TenantScope], _ScriptedConnection]:
    return lambda scope: conn


def _assignee(resource_id: str) -> AssigneeRef:
    return AssigneeRef(kind=AssigneeKind.AGENT_INSTANCE, resource_id=resource_id, version=1)


def _source_ref() -> ExactRevisionRef:
    return ExactRevisionRef(resource_type="ResponsibilityPlanRevision", resource_id="plan-source", revision=2, content_hash=HASH)


def _successor_insert(_: str, params: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "successor_id": params[2], "task_id": params[3], "source_plan_ref": params[4],
        "successor_plan_ref": params[5], "slot_id": params[6], "source_assignee": params[7],
        "target_assignee": params[8], "resolution_receipt_id": params[9], "reason_code": params[10],
        "actor": params[11], "content_hash": params[14], "created_at": params[15],
    }


def test_pre_run_reassign_creates_new_frozen_exact_plan_without_task_run() -> None:
    source = {
        "content_hash": HASH, "lifecycle": "frozen", "profile": "standard",
        "template_ref": {"resourceType": "ResponsibilityTemplateRevision", "resourceId": "template-1", "revision": 1, "contentHash": HASH},
        "slots": [{"slotId": "operator", "responsibilityType": "execution", "requiredCapabilityIds": ["cap.execute"], "inputSchemaRef": {"resourceType": "Schema", "resourceId": "in"}, "outputSchemaRef": {"resourceType": "Schema", "resourceId": "out"}, "gateRefs": [], "returnStage": "execute", "assignee": _assignee("agent-old").model_dump(mode="json", by_alias=True)}],
        "merge_decisions": [],
    }
    conn = _ScriptedConnection([
        None, {"version": 3}, source, None,
        {"kind": "agent_instance", "resource_id": "agent-new", "version": 1, "status": "resolved"},
        None, None, _successor_insert,
    ])
    receipt = AipResponsibilityAssignmentStore(_factory(conn)).create_successor(
        SCOPE,
        CreateResponsibilitySuccessorRequest(task_id="task-1", source_plan_ref=_source_ref(), expected_source_version=3, slot_id="operator", target_assignee=_assignee("agent-new"), resolution_receipt_id="resolution-1", reason_code="OPERATOR_REASSIGNED"),
        actor="user:maker", idempotency_key="successor-key-1", now=NOW,
    )
    assert receipt.source_plan_ref.resource_id == "plan-source"
    assert receipt.successor_plan_ref.resource_id.startswith("responsibility-plan-successor-")
    assert receipt.successor_plan_ref.resource_id != receipt.source_plan_ref.resource_id
    assert receipt.source_assignee.resource_id == "agent-old"
    assert receipt.target_assignee.resource_id == "agent-new"
    assert conn.commits == 1
    assert any("'frozen'" in query and "aip_responsibility_plan_revision" in query for query, _ in conn.queries)


def test_pre_run_reassign_fails_closed_after_task_run_exists() -> None:
    conn = _ScriptedConnection([None, {"version": 3}, {"content_hash": HASH, "lifecycle": "frozen"}, {"run_id": "run-1"}])
    with pytest.raises(ResponsibilityAssignmentBlocked, match="USE_TAKEOVER"):
        AipResponsibilityAssignmentStore(_factory(conn)).create_successor(
            SCOPE,
            CreateResponsibilitySuccessorRequest(task_id="task-1", source_plan_ref=_source_ref(), expected_source_version=3, slot_id="operator", target_assignee=_assignee("agent-new"), resolution_receipt_id="resolution-1", reason_code="OPERATOR_REASSIGNED"),
            actor="user:maker", idempotency_key="successor-key-2", now=NOW,
        )
    assert conn.commits == 0


def _takeover_body(expected_fence: int = 0) -> CreateTakeoverRequest:
    return CreateTakeoverRequest(
        task_run_ref=RuntimeAuthorityRef(resource_type="TaskRun", resource_id="run-1", version=4),
        step_run_ref=RuntimeAuthorityRef(resource_type="StepRun", resource_id="step-1", version=2),
        attempt=2, source_owner=_assignee("agent-old"), target_owner=_assignee("agent-new"),
        resolution_receipt_id="resolution-1", expected_fence=expected_fence, reason_code="MANUAL_TAKEOVER",
    )


def _takeover_insert(_: str, params: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "request_id": params[2], "task_run_ref": params[3], "step_run_ref": params[4],
        "attempt": params[5], "source_owner": params[6], "target_owner": params[7],
        "resolution_receipt_id": params[8], "expected_fence": params[9], "reason_code": params[10],
        "safety_state": params[11], "status": params[12], "blockers": params[13],
        "maker": params[14], "content_hash": params[17], "created_at": params[18],
    }


def test_active_step_lease_creates_blocked_takeover_observation_not_false_ready() -> None:
    conn = _ScriptedConnection([
        None, {"run_id": "run-1", "version": 4},
        {"run_id": "run-1", "attempt": 2, "status": "running", "lease_expires_at": NOW + timedelta(minutes=5), "action_ref": None, "verify_ref": None},
        {"kind": "agent_instance", "resource_id": "agent-new", "version": 1, "status": "resolved"},
        None, _takeover_insert,
    ])
    receipt = AipResponsibilityAssignmentStore(_factory(conn)).create_takeover_request(
        SCOPE, _takeover_body(), actor="user:maker", idempotency_key="takeover-key-1", now=NOW,
    )
    assert receipt.status is TakeoverRequestStatus.BLOCKED
    assert receipt.safety_state is TakeoverSafetyState.ACTIVE_LEASE
    assert [item.code for item in receipt.blockers] == ["ACTIVE_EXECUTION_LEASE"]


def test_provider_unknown_blocks_takeover_and_never_advances_fence() -> None:
    conn = _ScriptedConnection([
        None, {"run_id": "run-1", "version": 4},
        {"run_id": "run-1", "attempt": 2, "status": "unknown", "lease_expires_at": None, "action_ref": {"provider": "opaque"}, "verify_ref": None},
        {"kind": "agent_instance", "resource_id": "agent-new", "version": 1, "status": "resolved"},
        None, _takeover_insert,
    ])
    receipt = AipResponsibilityAssignmentStore(_factory(conn)).create_takeover_request(
        SCOPE, _takeover_body(), actor="user:maker", idempotency_key="takeover-key-2", now=NOW,
    )
    assert receipt.safety_state is TakeoverSafetyState.PROVIDER_OUTCOME_UNKNOWN
    assert receipt.status is TakeoverRequestStatus.BLOCKED
    assert not any("aip_execution_assignment_head" in query and query.startswith(("INSERT", "UPDATE")) for query, _ in conn.queries)


def test_takeover_requires_maker_checker_and_exact_decision_version() -> None:
    request = {"request_id": "takeover-1", "maker": "user:maker", "status": "pending"}
    same_actor = _ScriptedConnection([None, request])
    store = AipResponsibilityAssignmentStore(_factory(same_actor))
    with pytest.raises(ResponsibilityAssignmentBlocked, match="MAKER_CHECKER"):
        store.decide_takeover(SCOPE, "takeover-1", DecideTakeoverRequest(expected_version=0, decision=TakeoverDecisionValue.REJECTED, reason_code="NOT_APPROVED"), actor="user:maker", idempotency_key="decision-key-1", now=NOW)
    stale = _ScriptedConnection([None, {**request, "maker": "user:maker"}, {"exists": 1}])
    with pytest.raises(ResponsibilityAssignmentConflict, match="version drifted"):
        AipResponsibilityAssignmentStore(_factory(stale)).decide_takeover(SCOPE, "takeover-1", DecideTakeoverRequest(expected_version=0, decision=TakeoverDecisionValue.REJECTED, reason_code="NOT_APPROVED"), actor="user:checker", idempotency_key="decision-key-2", now=NOW)


def _pending_takeover() -> dict[str, Any]:
    return {
        "request_id": "takeover-1",
        "maker": "user:maker",
        "status": "pending",
        "step_run_ref": RuntimeAuthorityRef(
            resource_type="StepRun", resource_id="step-1", version=2
        ).model_dump(mode="json", by_alias=True),
        "task_run_ref": RuntimeAuthorityRef(
            resource_type="TaskRun", resource_id="run-1", version=4
        ).model_dump(mode="json", by_alias=True),
        "target_owner": _assignee("agent-new").model_dump(mode="json", by_alias=True),
        "attempt": 2,
        "expected_fence": 0,
    }


def test_approval_rechecks_step_safety_and_blocks_new_provider_unknown() -> None:
    conn = _ScriptedConnection(
        [
            None,
            _pending_takeover(),
            None,
            {
                "status": "unknown",
                "lease_expires_at": None,
                "action_ref": {"provider": "opaque"},
                "verify_ref": None,
            },
        ]
    )
    with pytest.raises(ResponsibilityAssignmentBlocked, match="PROVIDER_OUTCOME_UNKNOWN"):
        AipResponsibilityAssignmentStore(_factory(conn)).decide_takeover(
            SCOPE,
            "takeover-1",
            DecideTakeoverRequest(
                expected_version=0,
                decision=TakeoverDecisionValue.APPROVED,
                reason_code="APPROVED",
                lease_expires_at=NOW + timedelta(minutes=5),
            ),
            actor="user:checker",
            idempotency_key="decision-key-provider-unknown",
            now=NOW,
        )
    assert not any(
        "aip_execution_assignment_head" in query
        and query.startswith(("INSERT", "UPDATE"))
        for query, _ in conn.queries
    )


def test_safe_approval_advances_fence_once_and_records_exact_lease() -> None:
    def decision_insert(_: str, params: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "decision_id": params[2],
            "request_id": params[3],
            "revision": 1,
            "decision": params[4],
            "reason_code": params[5],
            "checker": params[6],
            "assignment_lease": params[7],
            "content_hash": params[10],
            "created_at": params[11],
        }

    conn = _ScriptedConnection(
        [
            None,
            _pending_takeover(),
            None,
            {
                "status": "pending",
                "lease_expires_at": None,
                "action_ref": None,
                "verify_ref": None,
            },
            None,
            None,
            decision_insert,
        ]
    )
    receipt = AipResponsibilityAssignmentStore(_factory(conn)).decide_takeover(
        SCOPE,
        "takeover-1",
        DecideTakeoverRequest(
            expected_version=0,
            decision=TakeoverDecisionValue.APPROVED,
            reason_code="APPROVED",
            lease_expires_at=NOW + timedelta(minutes=5),
        ),
        actor="user:checker",
        idempotency_key="decision-key-approved",
        now=NOW,
    )
    assert receipt.assignment_lease is not None
    assert receipt.assignment_lease.task_run_ref.version == 4
    assert receipt.assignment_lease.fence == 1
    assert conn.commits == 1


def test_assignment_fence_accepts_only_current_owner_fence_and_unexpired_lease() -> None:
    current = {"run_id": "run-1", "run_version": 4, "lease_id": "lease-1", "owner": _assignee("agent-new").model_dump(mode="json", by_alias=True), "current_fence": 3, "lease_expires_at": NOW + timedelta(minutes=5)}
    body = AssertAssignmentFenceRequest(step_run_ref=RuntimeAuthorityRef(resource_type="StepRun", resource_id="step-1", version=2), attempt=2, owner=_assignee("agent-new"), fence=3)
    allowed = AipResponsibilityAssignmentStore(_factory(_ScriptedConnection([current]))).assert_fence(SCOPE, body, now=NOW)
    assert allowed.allowed is True
    assert allowed.lease is not None
    assert allowed.lease.task_run_ref.version == 4
    stale = AipResponsibilityAssignmentStore(_factory(_ScriptedConnection([current]))).assert_fence(SCOPE, body.model_copy(update={"fence": 2}), now=NOW)
    assert stale.allowed is False
    assert stale.blockers[0].code == "ASSIGNMENT_FENCE_STALE"


def test_run_observation_keeps_requests_decisions_and_current_leases_separate() -> None:
    request = {
        **_pending_takeover(),
        "source_owner": _assignee("agent-old").model_dump(mode="json", by_alias=True),
        "resolution_receipt_id": "resolution-1",
        "reason_code": "MANUAL_TAKEOVER",
        "safety_state": "safe_checkpoint",
        "blockers": [],
        "created_at": NOW,
        "content_hash": HASH,
    }
    decision = {
        "decision_id": "decision-1",
        "request_id": "takeover-1",
        "revision": 1,
        "decision": "approved",
        "reason_code": "APPROVED",
        "checker": "user:checker",
        "assignment_lease": {
            "leaseId": "lease-1",
            "taskRunRef": request["task_run_ref"],
            "stepRunRef": request["step_run_ref"],
            "attempt": 2,
            "owner": request["target_owner"],
            "fence": 1,
            "expiresAt": (NOW + timedelta(minutes=5)).isoformat(),
        },
        "created_at": NOW,
        "content_hash": HASH,
    }
    head = {
        "step_run_id": "step-1",
        "attempt": 2,
        "owner": request["target_owner"],
        "current_fence": 1,
        "lease_id": "lease-1",
        "lease_expires_at": NOW + timedelta(minutes=5),
    }
    observation = AipResponsibilityAssignmentStore(
        _factory(
            _ScriptedConnection(
                [{"run_id": "run-1", "version": 4}, [request], [decision], [head]]
            )
        )
    ).observe_run(SCOPE, "run-1", now=NOW)
    assert observation.run_ref.version == 4
    assert observation.takeover_requests[0].status is TakeoverRequestStatus.PENDING
    assert observation.takeover_decisions[0].decision is TakeoverDecisionValue.APPROVED
    assert observation.assignment_leases[0].fence == 1


def test_contracts_reject_same_owner_and_approved_without_lease_expiry() -> None:
    with pytest.raises(ValueError, match="differ"):
        CreateTakeoverRequest(task_run_ref=RuntimeAuthorityRef(resource_type="TaskRun", resource_id="run-1", version=1), step_run_ref=RuntimeAuthorityRef(resource_type="StepRun", resource_id="step-1", version=1), attempt=1, source_owner=_assignee("same"), target_owner=_assignee("same"), resolution_receipt_id="resolution-1", expected_fence=0, reason_code="MANUAL_TAKEOVER")
    with pytest.raises(ValueError, match="leaseExpiresAt"):
        DecideTakeoverRequest(expected_version=0, decision=TakeoverDecisionValue.APPROVED, reason_code="APPROVED")


def test_migration_is_linear_additive_rls_and_fail_closed_downgrade() -> None:
    migration = Path("alembic/versions/w3_016_responsibility_assignment.py").read_text()
    assert 'down_revision: str | Sequence[str] | None = "w3_015"' in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "guard_aip4_append_only" in migration
    assert "cannot downgrade w3_016 with canonical assignment authority data" in migration
    assert "aip_execution_assignment_head" in migration
