"""W3-08 dispatch intent, priority CAS and migration tests."""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from aos_api.aip_dispatch_control import (
    ConfirmDispatchIntentRequest,
    CreateDispatchIntentRequest,
    DecideTaskPriorityRequest,
    DispatchIntentStatus,
)
from aos_api.aip_dispatch_control_store import (
    AipDispatchControlStore,
    DispatchControlBlocked,
    DispatchControlConflict,
)
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_responsibility_assignment import RuntimeAuthorityRef
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 25, 1, 30, tzinfo=UTC)
HASH = "a" * 64
FROZEN_PLAN = {"content_hash": HASH, "lifecycle": "frozen"}


class _Result:
    def __init__(self, value: Any) -> None:
        self.value = value

    def fetchone(self) -> Any:
        return self.value

    def fetchall(self) -> Any:
        return self.value


class _Connection:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.queries: list[tuple[str, tuple[Any, ...]]] = []
        self.commits = 0

    def __enter__(self) -> "_Connection":
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


def _factory(conn: _Connection) -> Callable[[TenantScope], _Connection]:
    return lambda scope: conn


def _ref(resource_type: str, resource_id: str, version: int = 1) -> RuntimeAuthorityRef:
    return RuntimeAuthorityRef(resourceType=resource_type, resourceId=resource_id, version=version)


def _exact(resource_type: str, resource_id: str) -> ExactRevisionRef:
    return ExactRevisionRef(resourceType=resource_type, resourceId=resource_id, revision=1, contentHash=HASH)


def _successor_intent() -> CreateDispatchIntentRequest:
    return CreateDispatchIntentRequest(
        taskRef=_ref("Task", "task-1", 3),
        responsibilityPlanRef=_exact("ResponsibilityPlanRevision", "responsibility-1"),
        commandKind="responsibility_successor",
        sourceIdentity="agent-old",
        targetIdentity="agent-new",
        sourceSlotId="operator",
        reasonCode="OPERATOR_REASSIGNED",
        policyRef=_exact("PolicyRevision", "dispatch-policy-1"),
        impact={"affectedSlots": 1},
    )


def _intent_insert(_: str, params: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "intent_id": params[2], "revision": 1, "task_ref": params[3],
        "task_run_ref": params[4], "step_run_ref": params[5],
        "responsibility_plan_ref": params[6], "command_kind": params[7],
        "source_identity": params[8], "target_identity": params[9],
        "source_slot_id": params[10], "target_slot_id": params[11],
        "expected_fence": params[12], "reason_code": params[13],
        "policy_ref": params[14], "diff": params[15], "impact": params[16],
        "readiness": params[17], "blockers": params[18], "maker": params[19],
        "content_hash": params[22], "created_at": params[23],
    }


def test_dispatch_suggestion_is_immutable_ready_and_has_server_owned_command() -> None:
    conn = _Connection([None, {"version": 3, "status": "planning"}, FROZEN_PLAN, _intent_insert])
    result = AipDispatchControlStore(_factory(conn)).create_intent(
        SCOPE, _successor_intent(), actor="user:maker", idempotency_key="dispatch-intent-1", now=NOW
    )
    assert result.readiness is DispatchIntentStatus.READY
    assert result.command.route_identity == "aip.responsibility.successor"
    assert result.diff["identity"] == {"from": "agent-old", "to": "agent-new"}
    assert conn.commits == 1
    assert not any(query.startswith("UPDATE aip_task") for query, _ in conn.queries)


def test_terminal_task_creates_blocked_intent_instead_of_false_ready() -> None:
    conn = _Connection([None, {"version": 3, "status": "completed"}, FROZEN_PLAN, _intent_insert])
    result = AipDispatchControlStore(_factory(conn)).create_intent(
        SCOPE, _successor_intent(), actor="user:maker", idempotency_key="dispatch-intent-2", now=NOW
    )
    assert result.readiness is DispatchIntentStatus.BLOCKED
    assert [item.code for item in result.blockers] == ["TASK_TERMINAL"]


def test_runtime_takeover_fails_closed_on_active_lease_and_provider_unknown() -> None:
    body = CreateDispatchIntentRequest(
        taskRef=_ref("Task", "task-1", 3), taskRunRef=_ref("TaskRun", "run-1", 4),
        stepRunRef=_ref("StepRun", "step-1", 2), commandKind="runtime_takeover",
        sourceIdentity="agent-old", targetIdentity="agent-new", expectedFence=2,
        reasonCode="MANUAL_TAKEOVER", policyRef=_exact("PolicyRevision", "dispatch-policy-1"),
    )
    conn = _Connection([
        None, {"version": 3, "status": "paused"}, {"task_id": "task-1", "version": 4},
        {"run_id": "run-1", "attempt": 2, "status": "unknown", "action_ref": {"provider": "opaque"}, "verify_ref": None, "lease_expires_at": NOW + timedelta(minutes=3)},
        {"current_fence": 2},
        _intent_insert,
    ])
    result = AipDispatchControlStore(_factory(conn)).create_intent(
        SCOPE, body, actor="user:maker", idempotency_key="dispatch-intent-3", now=NOW
    )
    assert result.readiness is DispatchIntentStatus.BLOCKED
    assert {item.code for item in result.blockers} == {"PROVIDER_OUTCOME_UNKNOWN", "ACTIVE_EXECUTION_LEASE"}


def _ready_intent_row() -> dict[str, Any]:
    body = _successor_intent().model_dump(mode="json", by_alias=True)
    return {
        "intent_id": "dispatch-intent-1", "revision": 1, "task_ref": body["taskRef"],
        "task_run_ref": None, "step_run_ref": None, "responsibility_plan_ref": body["responsibilityPlanRef"],
        "command_kind": "responsibility_successor", "source_identity": "agent-old",
        "target_identity": "agent-new", "source_slot_id": "operator", "target_slot_id": None,
        "expected_fence": None, "reason_code": "OPERATOR_REASSIGNED", "policy_ref": body["policyRef"],
        "diff": {}, "impact": {}, "readiness": "ready", "blockers": [], "maker": "user:maker",
        "content_hash": HASH, "created_at": NOW,
    }


def _confirmation_insert(_: str, params: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "confirmation_id": params[2], "intent_id": params[3], "intent_revision": params[4],
        "intent_content_hash": params[5], "command_kind": params[6],
        "invocation_state": "canonical_command_required", "checker": params[7],
        "content_hash": params[10], "created_at": params[11],
    }


def test_confirmation_requires_maker_checker_and_revalidates_task() -> None:
    body = ConfirmDispatchIntentRequest(expectedRevision=1, expectedContentHash=HASH)
    same = _Connection([None, _ready_intent_row()])
    with pytest.raises(DispatchControlBlocked, match="maker-checker"):
        AipDispatchControlStore(_factory(same)).confirm_intent(SCOPE, "dispatch-intent-1", body, actor="user:maker", idempotency_key="dispatch-confirm-1", now=NOW)
    drift = _Connection([None, _ready_intent_row(), {"version": 4, "status": "planning"}])
    with pytest.raises(DispatchControlConflict, match="drifted"):
        AipDispatchControlStore(_factory(drift)).confirm_intent(SCOPE, "dispatch-intent-1", body, actor="user:checker", idempotency_key="dispatch-confirm-2", now=NOW)
    ready = _Connection([None, _ready_intent_row(), {"version": 3, "status": "planning"}, FROZEN_PLAN, _confirmation_insert])
    receipt = AipDispatchControlStore(_factory(ready)).confirm_intent(SCOPE, "dispatch-intent-1", body, actor="user:checker", idempotency_key="dispatch-confirm-3", now=NOW)
    assert receipt.invocation_state == "canonical_command_required"
    assert receipt.command.route_path == "/v1/aip/responsibility-assignments/successors"


def test_confirmation_fails_closed_when_runtime_safety_or_fence_changes() -> None:
    body = ConfirmDispatchIntentRequest(expectedRevision=1, expectedContentHash=HASH)
    intent = _ready_intent_row()
    intent.update({
        "command_kind": "runtime_takeover",
        "task_run_ref": _ref("TaskRun", "run-1", 4).model_dump(mode="json", by_alias=True),
        "step_run_ref": _ref("StepRun", "step-1", 2).model_dump(mode="json", by_alias=True),
        "responsibility_plan_ref": None,
        "expected_fence": 2,
    })
    unsafe = _Connection([
        None,
        intent,
        {"version": 3, "status": "paused"},
        {"task_id": "task-1", "version": 4},
        {"run_id": "run-1", "attempt": 2, "status": "unknown", "action_ref": {}, "verify_ref": None, "lease_expires_at": NOW + timedelta(minutes=1)},
        {"current_fence": 2},
    ])
    with pytest.raises(DispatchControlBlocked, match="safety state changed"):
        AipDispatchControlStore(_factory(unsafe)).confirm_intent(
            SCOPE, "dispatch-intent-1", body, actor="user:checker", idempotency_key="dispatch-confirm-unsafe", now=NOW
        )

    fence_drift = _Connection([
        None,
        intent,
        {"version": 3, "status": "paused"},
        {"task_id": "task-1", "version": 4},
        {"run_id": "run-1", "attempt": 2, "status": "paused", "action_ref": None, "verify_ref": None, "lease_expires_at": None},
        {"current_fence": 3},
    ])
    with pytest.raises(DispatchControlConflict, match="dependency drifted"):
        AipDispatchControlStore(_factory(fence_drift)).confirm_intent(
            SCOPE, "dispatch-intent-1", body, actor="user:checker", idempotency_key="dispatch-confirm-fence", now=NOW
        )


def _priority_insert(_: str, params: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "decision_id": params[2], "revision": 1, "task_ref_before": params[3],
        "task_ref_after": params[4], "old_priority": params[5], "new_priority": params[6],
        "reason_code": params[7], "policy_ref": params[8], "actor": params[9],
        "content_hash": params[12], "created_at": params[13],
    }


def _priority_body() -> DecideTaskPriorityRequest:
    return DecideTaskPriorityRequest(taskRef=_ref("Task", "task-1", 3), oldPriority=50, newPriority=80, reasonCode="SLA_ESCALATION", policyRef=_exact("PolicyRevision", "priority-policy-1"))


def test_priority_decision_appends_receipt_and_cas_updates_task_once() -> None:
    conn = _Connection([None, {"version": 3, "priority": 50, "status": "planning"}, _priority_insert, {"version": 4}])
    result = AipDispatchControlStore(_factory(conn)).decide_priority(SCOPE, _priority_body(), actor="user:operator", idempotency_key="priority-decision-1", now=NOW)
    assert result.task_ref_before.version == 3
    assert result.task_ref_after.version == 4
    assert result.old_priority == 50 and result.new_priority == 80
    updates = [query for query, _ in conn.queries if query.startswith("UPDATE aip_task SET priority")]
    assert len(updates) == 1
    assert conn.commits == 1


@pytest.mark.parametrize("task", [
    {"version": 4, "priority": 50, "status": "planning"},
    {"version": 3, "priority": 40, "status": "planning"},
])
def test_priority_decision_rejects_version_or_old_value_drift(task: dict[str, Any]) -> None:
    conn = _Connection([None, task])
    with pytest.raises(DispatchControlConflict):
        AipDispatchControlStore(_factory(conn)).decide_priority(SCOPE, _priority_body(), actor="user:operator", idempotency_key=f"priority-drift-{task['version']}-{task['priority']}", now=NOW)
    assert conn.commits == 0


def test_priority_decision_blocks_terminal_task() -> None:
    conn = _Connection([None, {"version": 3, "priority": 50, "status": "completed"}])
    with pytest.raises(DispatchControlBlocked, match="terminal"):
        AipDispatchControlStore(_factory(conn)).decide_priority(SCOPE, _priority_body(), actor="user:operator", idempotency_key="priority-terminal-1", now=NOW)


def test_task_observation_keeps_intent_confirmation_and_priority_ledgers_separate() -> None:
    intent = _ready_intent_row()
    confirmation = {
        "confirmation_id": "confirmation-1", "intent_id": intent["intent_id"],
        "intent_revision": 1, "intent_content_hash": HASH,
        "command_kind": "responsibility_successor", "invocation_state": "canonical_command_required",
        "checker": "user:checker", "created_at": NOW, "content_hash": "b" * 64,
    }
    priority_body = _priority_body().model_dump(mode="json", by_alias=True)
    priority = {
        "decision_id": "priority-1", "revision": 1,
        "task_ref_before": priority_body["taskRef"],
        "task_ref_after": {**priority_body["taskRef"], "version": 4},
        "old_priority": 50, "new_priority": 80, "reason_code": "SLA_ESCALATION",
        "policy_ref": priority_body["policyRef"], "actor": "user:operator",
        "created_at": NOW, "content_hash": "c" * 64,
    }
    conn = _Connection([{"task_id": "task-1", "version": 4}, [intent], [confirmation], [priority]])
    observed = AipDispatchControlStore(_factory(conn)).observe_task(SCOPE, "task-1", now=NOW)
    assert observed.task_ref.version == 4
    assert [item.intent_id for item in observed.dispatch_intents] == ["dispatch-intent-1"]
    assert [item.confirmation_id for item in observed.confirmations] == ["confirmation-1"]
    assert observed.priority_decisions[0].new_priority == 80


def test_w3_017_migration_is_tenant_scoped_append_only_and_chain_head() -> None:
    path = Path(__file__).parents[1] / "alembic/versions/w3_017_dispatch_control.py"
    text = path.read_text()
    assert 'down_revision: str | Sequence[str] | None = "w3_016"' in text
    for table in ("aip_dispatch_intent_revision", "aip_dispatch_confirmation_receipt", "aip_task_priority_decision_revision"):
        assert f"CREATE TABLE {table}" in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "REVOKE UPDATE,DELETE,TRUNCATE" in text
    assert "guard_aip4_append_only" in text
