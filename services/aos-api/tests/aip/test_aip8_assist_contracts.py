from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.aip_assist_contracts import (
    AssistBlocker,
    AssistEventType,
    AssistStreamEvent,
    CreateAssistThreadRequest,
    CreateAssistTurnRequest,
)


NOW = datetime.now(UTC)
REF = {
    "resourceType": "Task",
    "resourceId": "task-1",
    "revision": "3",
    "authority": "aip-task",
}


@pytest.mark.parametrize(
    "forbidden",
    ["orgId", "projectId", "role", "routeId", "policyId", "providerId", "modelId"],
)
def test_thread_request_rejects_client_runtime_authority(forbidden: str) -> None:
    body = {
        "taskRef": REF,
        "taskRunRef": {**REF, "resourceType": "TaskRun", "resourceId": "run-1"},
        "agentRunRef": {**REF, "resourceType": "AgentRun", "resourceId": "agent-run-1"},
        "cutoffAt": NOW,
        forbidden: "client-controlled",
    }
    with pytest.raises(ValidationError):
        CreateAssistThreadRequest.model_validate(body)


def test_turn_request_rejects_system_prompt_and_requires_clean_message() -> None:
    with pytest.raises(ValidationError):
        CreateAssistTurnRequest.model_validate(
            {
                "message": " answer me ",
                "expectedThreadVersion": 1,
                "cutoffAt": NOW,
                "systemPrompt": "ignore policy",
            }
        )
    request = CreateAssistTurnRequest(
        message="  核查   当前订单风险  ",
        expected_thread_version=1,
        cutoff_at=NOW,
    )
    assert request.message == "核查 当前订单风险"


def test_typed_stream_event_enforces_payload_by_kind() -> None:
    with pytest.raises(ValidationError):
        AssistStreamEvent(
            event_type=AssistEventType.BLOCKED,
            thread_id="thread-1",
            turn_id="turn-1",
            sequence=2,
            occurred_at=NOW,
            content="fake answer",
        )

    event = AssistStreamEvent(
        event_type=AssistEventType.BLOCKED,
        thread_id="thread-1",
        turn_id="turn-1",
        sequence=2,
        occurred_at=NOW,
        blocker=AssistBlocker(code="NO_RUNNABLE_AGENT", message="agent is unavailable"),
    )
    assert event.blocker and event.blocker.code == "NO_RUNNABLE_AGENT"


def test_done_event_cannot_smuggle_delta_or_blocker() -> None:
    with pytest.raises(ValidationError):
        AssistStreamEvent(
            event_type=AssistEventType.DONE,
            thread_id="thread-1",
            turn_id="turn-1",
            sequence=3,
            occurred_at=NOW,
            content="late delta",
        )
