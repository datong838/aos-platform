"""W-L12 HandoffDecisionRevision layered on consumed Envelope."""
from __future__ import annotations

from datetime import timedelta

import pytest

from aos_api.aip_agent_registry_contracts import (
    CreateHandoffDecisionRequest,
    HandoffDecisionKind,
    HandoffEnvelopeRequest,
    IssueHandoffRequest,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_handoff_service import AipHandoffService
from aos_api.db import connect

from test_aip6_capability_run_handoff import (
    CANARY,
    NOW,
    PRIMARY,
    _active_instance,
    resource,
)

pytest_plugins = ("test_aip6_capability_run_handoff",)


def test_decision_requires_consumed_and_does_not_reopen_envelope(ids):
    sender = _active_instance(ids, "sender")
    receiver = _active_instance(ids, "receiver")
    service = AipHandoffService(ref_authorizer=lambda scope, ref, instance: True)
    issued = service.issue(
        PRIMARY,
        IssueHandoffRequest(
            handoff_id=ids["handoff"],
            envelope=HandoffEnvelopeRequest(
                task_ref=resource("Task", ids["task"]),
                run_ref=resource("TaskRun", ids["task_run"]),
                sender_instance=sender.instance_ref,
                receiver_instance=receiver.instance_ref,
                object_refs=[],
                context={"intent": "w-l12"},
                allowed_context_fields=["intent"],
                markings=["internal"],
                expires_at=NOW + timedelta(minutes=10),
            ),
        ),
        idempotency_key=f"issue-{ids['handoff']}",
        actor="pytest",
        occurred_at=NOW,
    )
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="consumed"):
        service.decide(
            PRIMARY,
            ids["handoff"],
            CreateHandoffDecisionRequest(
                decision=HandoffDecisionKind.ACCEPTED,
                expected_head_version=0,
                receiver_instance=receiver.instance_ref,
            ),
            idempotency_key=f"decide-{ids['handoff']}",
            actor="pytest-receiver",
            occurred_at=NOW + timedelta(minutes=1),
        )
    service.consume(
        PRIMARY,
        ids["handoff"],
        bearer_token=issued.bearer_token,
        receiver_instance=receiver.instance_ref,
        actor="pytest-receiver",
        occurred_at=NOW + timedelta(minutes=1),
    )
    decided = service.decide(
        PRIMARY,
        ids["handoff"],
        CreateHandoffDecisionRequest(
            decision=HandoffDecisionKind.ACCEPTED,
            expected_head_version=0,
            receiver_instance=receiver.instance_ref,
        ),
        idempotency_key=f"decide-{ids['handoff']}",
        actor="pytest-receiver",
        occurred_at=NOW + timedelta(minutes=2),
    )
    assert decided.decision.decision is HandoffDecisionKind.ACCEPTED
    envelope = service.get(PRIMARY, ids["handoff"])
    assert envelope.status == "consumed"
    replay = service.decide(
        PRIMARY,
        ids["handoff"],
        CreateHandoffDecisionRequest(
            decision=HandoffDecisionKind.ACCEPTED,
            expected_head_version=0,
            receiver_instance=receiver.instance_ref,
        ),
        idempotency_key=f"decide-{ids['handoff']}",
        actor="pytest-receiver",
        occurred_at=NOW + timedelta(minutes=3),
    )
    assert replay.decision.decision_id == decided.decision.decision_id
    with pytest.raises(AipAgentRegistryConflict):
        service.decide(
            PRIMARY,
            ids["handoff"],
            CreateHandoffDecisionRequest(
                decision=HandoffDecisionKind.REJECTED,
                expected_head_version=1,
                reason_code="NOT_NEEDED",
                receiver_instance=receiver.instance_ref,
            ),
            idempotency_key=f"decide-again-{ids['handoff']}",
            actor="pytest-receiver",
            occurred_at=NOW + timedelta(minutes=4),
        )
    with connect(PRIMARY) as conn:
        task = conn.execute(
            """SELECT status FROM aip_task
               WHERE org_id=%s AND project_id=%s AND task_id=%s""",
            (*PRIMARY.key, ids["task"]),
        ).fetchone()
    assert task is not None
    listing = service.list_decisions(PRIMARY, ids["handoff"])
    assert listing.count == 1 and listing.head_version == 1
    with pytest.raises(AipAgentRegistryNotFound):
        service.list_decisions(CANARY, ids["handoff"])


def test_request_more_then_returned(ids):
    sender = _active_instance(ids, "sender")
    receiver = _active_instance(ids, "receiver")
    service = AipHandoffService(ref_authorizer=lambda scope, ref, instance: True)
    issued = service.issue(
        PRIMARY,
        IssueHandoffRequest(
            handoff_id=ids["handoff"],
            envelope=HandoffEnvelopeRequest(
                task_ref=resource("Task", ids["task"]),
                run_ref=resource("TaskRun", ids["task_run"]),
                sender_instance=sender.instance_ref,
                receiver_instance=receiver.instance_ref,
                object_refs=[],
                context={"intent": "need-more"},
                allowed_context_fields=["intent"],
                markings=["internal"],
                expires_at=NOW + timedelta(minutes=10),
            ),
        ),
        idempotency_key=f"issue-more-{ids['handoff']}",
        actor="pytest",
        occurred_at=NOW,
    )
    service.consume(
        PRIMARY,
        ids["handoff"],
        bearer_token=issued.bearer_token,
        receiver_instance=receiver.instance_ref,
        actor="pytest-receiver",
        occurred_at=NOW + timedelta(minutes=1),
    )
    more = service.decide(
        PRIMARY,
        ids["handoff"],
        CreateHandoffDecisionRequest(
            decision=HandoffDecisionKind.REQUEST_MORE,
            expected_head_version=0,
            gap_codes=["EVIDENCE_MISSING"],
            receiver_instance=receiver.instance_ref,
        ),
        idempotency_key=f"more-{ids['handoff']}",
        actor="pytest-receiver",
        occurred_at=NOW + timedelta(minutes=2),
    )
    assert more.decision.decision is HandoffDecisionKind.REQUEST_MORE
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="returned"):
        service.decide(
            PRIMARY,
            ids["handoff"],
            CreateHandoffDecisionRequest(
                decision=HandoffDecisionKind.ACCEPTED,
                expected_head_version=1,
                receiver_instance=receiver.instance_ref,
            ),
            idempotency_key=f"bad-{ids['handoff']}",
            actor="pytest-receiver",
            occurred_at=NOW + timedelta(minutes=3),
        )
    returned = service.decide(
        PRIMARY,
        ids["handoff"],
        CreateHandoffDecisionRequest(
            decision=HandoffDecisionKind.RETURNED,
            expected_head_version=1,
            return_refs=[
                ResourceRef(
                    resource_type="Observation",
                    resource_id="obs-1",
                    revision="1",
                    authority="aip",
                )
            ],
            receiver_instance=receiver.instance_ref,
        ),
        idempotency_key=f"return-{ids['handoff']}",
        actor="pytest-receiver",
        occurred_at=NOW + timedelta(minutes=4),
    )
    assert returned.decision.decision is HandoffDecisionKind.RETURNED
    assert service.get(PRIMARY, ids["handoff"]).status == "consumed"
    assert service.list_decisions(PRIMARY, ids["handoff"]).count == 2
