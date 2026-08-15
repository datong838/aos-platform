from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest

from aos_api.aip_assist_contracts import (
    AssistEventType,
    AssistStreamEvent,
    AssistThreadStatus,
    CreateAssistThreadRequest,
    CreateAssistTurnRequest,
)
from aos_api.aip_assist_store import AipAssistStore
from aos_api.aip_contracts import ResourceRef
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def ref(kind: str, value: str) -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=value,
        revision="1",
        authority="test-authority",
    )


def thread_request() -> CreateAssistThreadRequest:
    return CreateAssistThreadRequest(
        task_ref=ref("Task", "task-1"),
        task_run_ref=ref("TaskRun", "run-1"),
        agent_run_ref=ref("AgentRun", "agent-run-1"),
        selection_refs=[ref("SelectionRevision", "selection-1")],
        cutoff_at=datetime.now(UTC),
        title="订单风险核查",
    )


def key(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def test_store_create_replay_turn_cas_and_tenant_isolation() -> None:
    store = AipAssistStore()
    request = thread_request()
    create_key = key("thread")
    created = store.create_thread(
        SCOPE,
        request,
        idempotency_key=create_key,
        actor="user:dev",
    )
    assert created.status == AssistThreadStatus.OPEN and created.version == 1
    assert store.create_thread(
        SCOPE,
        request,
        idempotency_key=create_key,
        actor="user:dev",
    ) == created

    with pytest.raises(ApiError) as hidden:
        store.get_thread(
            TenantScope("dev-org", "dev-project"),
            created.thread_id,
        )
    assert hidden.value.status_code == 404

    turn_key = key("turn")
    turn = CreateAssistTurnRequest(
        message="核查当前订单风险",
        expected_thread_version=1,
        cutoff_at=request.cutoff_at,
    )
    outcome = store.create_blocked_turn(
        SCOPE,
        created.thread_id,
        turn,
        idempotency_key=turn_key,
        actor="user:dev",
    )
    assert outcome.thread.version == 2
    assert [event.event_type for event in outcome.events] == [
        AssistEventType.START,
        AssistEventType.BLOCKED,
    ]
    assert outcome.events[-1].blocker
    assert outcome.events[-1].blocker.code == "ASSIST_RUNTIME_NOT_INSTALLED"
    assert store.create_blocked_turn(
        SCOPE,
        created.thread_id,
        turn,
        idempotency_key=turn_key,
        actor="user:dev",
    ) == outcome

    with pytest.raises(ApiError) as stale:
        store.create_blocked_turn(
            SCOPE,
            created.thread_id,
            turn.model_copy(update={"message": "另一个问题"}),
            idempotency_key=key("stale"),
            actor="user:dev",
        )
    assert stale.value.status_code == 412


def test_store_rejects_idempotency_payload_drift() -> None:
    store = AipAssistStore()
    request = thread_request()
    reused = key("drift")
    store.create_thread(SCOPE, request, idempotency_key=reused, actor="user:dev")
    with pytest.raises(ApiError) as drift:
        store.create_thread(
            SCOPE,
            request.model_copy(update={"title": "不同标题"}),
            idempotency_key=reused,
            actor="user:dev",
        )
    assert drift.value.code == "IDEMPOTENCY_CONFLICT"


def test_assist_tables_force_rls_and_reject_mutation() -> None:
    tables = [
        "aip_assist_thread",
        "aip_assist_turn",
        "aip_assist_event",
        "aip_assist_receipt",
    ]
    with connect(SCOPE) as conn:
        rows = conn.execute(
            """SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class
            WHERE relname=ANY(%s) ORDER BY relname""",
            (tables,),
        ).fetchall()
        assert len(rows) == 4
        assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rows)

    created = AipAssistStore().create_thread(
        SCOPE,
        thread_request(),
        idempotency_key=key("immutable"),
        actor="user:dev",
    )
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        with connect(SCOPE) as conn:
            conn.execute(
                """UPDATE aip_assist_thread SET created_by='forged'
                WHERE org_id=%s AND project_id=%s AND thread_id=%s""",
                (*SCOPE.key, created.thread_id),
            )


def test_prepare_finalize_replay_and_interrupted_turn_recovery() -> None:
    store = AipAssistStore(recovery_after=timedelta(0))
    request = thread_request()
    created = store.create_thread(
        SCOPE,
        request,
        idempotency_key=key("runtime-thread"),
        actor="user:dev",
    )
    turn_key = key("runtime-turn")
    turn = CreateAssistTurnRequest(
        message="核查当前订单风险",
        expected_thread_version=1,
        cutoff_at=request.cutoff_at,
    )
    prepared = store.prepare_turn(
        SCOPE,
        created.thread_id,
        turn,
        idempotency_key=turn_key,
        actor="user:dev",
    )
    assert [event.event_type for event in prepared.events] == [AssistEventType.START]
    resumed = store.prepare_turn(
        SCOPE,
        created.thread_id,
        turn,
        idempotency_key=turn_key,
        actor="user:dev",
    )
    assert resumed.resumed is True
    blocked = AssistStreamEvent(
        event_type=AssistEventType.BLOCKED,
        thread_id=created.thread_id,
        turn_id=resumed.turn_id,
        sequence=2,
        occurred_at=datetime.now(UTC),
        blocker={
            "code": "ASSIST_TURN_RECOVERY_REQUIRED",
            "message": "interrupted turn",
            "retryable": True,
        },
    )
    record = store.finalize_turn(
        SCOPE,
        resumed,
        [blocked],
        idempotency_key=turn_key,
        actor="user:dev",
    )
    assert record.events[-1].blocker.code == "ASSIST_TURN_RECOVERY_REQUIRED"
    replay = store.prepare_turn(
        SCOPE,
        created.thread_id,
        turn,
        idempotency_key=turn_key,
        actor="user:dev",
    )
    assert replay.replay == record
