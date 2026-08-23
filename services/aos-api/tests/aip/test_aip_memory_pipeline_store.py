from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from psycopg.errors import ObjectNotInPrerequisiteState

from aos_api.aip_contracts import ArtifactRef, ResourceRef
from aos_api.aip_memory_contracts import (
    KnowledgeScope,
    KnowledgeSourceRef,
    SubmitMemoryCandidateRequest,
)
from aos_api.aip_memory_pipeline_contracts import (
    ClaimKnowledgePipelineRunRequest,
    CompleteKnowledgePipelineRunRequest,
    CreateKnowledgePipelineScheduleRequest,
    StartKnowledgePipelineRunRequest,
    TransitionKnowledgePipelineRunRequest,
    TransitionKnowledgePipelineScheduleRequest,
)
from aos_api.aip_memory_pipeline_store import (
    AipMemoryPipelineConflict,
    AipMemoryPipelineNotFound,
    AipMemoryPipelinePersistenceError,
    AipMemoryPipelineStore,
    AipMemoryPipelineTransitionBlocked,
)
from aos_api.aip_memory_store import AipMemoryStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


PRIMARY = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 12, 16, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def artifact(identifier: str, content_hash: str = HASH_A) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=identifier,
        artifact_type="knowledge_pipeline_config",
        revision="1",
        content_hash=content_hash,
    )


def resource(kind: str, identifier: str, revision: str = "1") -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=identifier,
        revision=revision,
        authority="postgresql",
    )


@pytest.fixture()
def authority_chain() -> dict[str, str]:
    suffix = uuid.uuid4().hex[:12]
    task_id = f"pipeline-task-{suffix}"
    task_run_id = f"pipeline-task-run-{suffix}"
    plan_id = f"pipeline-plan-{suffix}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES ('org-org','栖月汇商贸有限公司') "
            "ON CONFLICT (id) DO NOTHING"
        )
        conn.execute(
            """INSERT INTO twa_workspace(org_id,project_id,name)
               VALUES ('org-org','dev-project','默认工作区')
               ON CONFLICT (org_id,project_id) DO NOTHING"""
        )
        conn.execute(
            """INSERT INTO aip_task (
               org_id,project_id,task_id,task_type,title,status,idempotency_key,
               request_hash,current_plan_revision_id,created_by)
               VALUES (%s,%s,%s,'memory_pipeline','pipeline','executing',%s,%s,%s,'pytest')""",
            (*PRIMARY.key, task_id, task_id, HASH_A, plan_id),
        )
        conn.execute(
            """INSERT INTO aip_plan_revision (
               org_id,project_id,plan_revision_id,task_id,revision,content_hash,
               steps,approval_status,idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,%s,1,%s,%s::jsonb,'approved',%s,%s,'pytest')""",
            (*PRIMARY.key, plan_id, task_id, HASH_A, json.dumps([]), plan_id, HASH_A),
        )
        conn.execute(
            """INSERT INTO aip_task_run (
               org_id,project_id,run_id,task_id,plan_revision_id,status,
               idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,%s,%s,'running',%s,%s,'pytest')""",
            (*PRIMARY.key, task_run_id, task_id, plan_id, task_run_id, HASH_A),
        )
        conn.commit()
    return {
        "suffix": suffix,
        "task_id": task_id,
        "task_run_id": task_run_id,
        "schedule_id": f"pipeline-schedule-{suffix}",
    }


def schedule_request(chain: dict[str, str], *, config_hash: str = HASH_A):
    return CreateKnowledgePipelineScheduleRequest(
        schedule_id=chain["schedule_id"],
        pipeline_kind="seed_import",
        trigger="manual",
        config=artifact(f"pipeline-config-{chain['suffix']}", config_hash),
        initial_status="paused",
    )


def start_request(
    chain: dict[str, str],
    pipeline_run_id: str,
    *,
    checkpoint_version: int = 0,
    retry_of_run_id: str | None = None,
    scheduled_for: datetime = NOW,
):
    return StartKnowledgePipelineRunRequest(
        pipeline_run_id=pipeline_run_id,
        schedule_id=chain["schedule_id"],
        task_id=chain["task_id"],
        run_id=chain["task_run_id"],
        trigger="manual",
        expected_checkpoint_version=checkpoint_version,
        scheduled_for=scheduled_for,
        retry_of_run_id=retry_of_run_id,
    )


def create_schedule(store: AipMemoryPipelineStore, chain: dict[str, str]):
    return store.create_schedule(
        PRIMARY,
        schedule_request(chain),
        idempotency_key=f"schedule-key-{chain['suffix']}",
        actor="pytest",
        occurred_at=NOW,
    )


def create_candidate(chain: dict[str, str], candidate_id: str) -> ResourceRef:
    memory = AipMemoryStore()
    source_id = f"source-{candidate_id}"
    source = KnowledgeSourceRef(
        source_kind="authorized_document",
        source_uri=f"urn:test:{candidate_id}",
        observed_at=NOW,
        freshness_expires_at=NOW + timedelta(days=30),
        license_id="internal-authorized",
        usage_policy="summary-and-citation",
        content_hash=HASH_B,
        provider="pytest",
        provider_version="1",
        applicability=["vertical:ecommerce"],
    )
    request = SubmitMemoryCandidateRequest(
        candidate_layer="semantic",
        task_id=chain["task_id"],
        run_id=chain["task_run_id"],
        subject=resource("ecom.product", "product-1"),
        payload=ArtifactRef(
            artifact_id=f"payload-{candidate_id}",
            artifact_type="memory_candidate",
            revision="1",
            content_hash=HASH_C,
        ),
        source=source,
        confidence=0.9,
        marking=["internal"],
    )
    memory.create_source_revision(PRIMARY, source_id, 1, source, actor="pytest")
    candidate = memory.submit_candidate(
        PRIMARY,
        candidate_id,
        request,
        source_id=source_id,
        source_revision=1,
        knowledge_scope=KnowledgeScope.WORKSPACE,
        actor="pytest",
        occurred_at=NOW,
    )
    return resource("aip.memory_candidate", candidate.candidate_id, str(candidate.version))


def test_schedule_hash_is_server_owned_idempotent_scoped_and_restart_safe(
    authority_chain,
) -> None:
    store = AipMemoryPipelineStore()
    created = create_schedule(store, authority_chain)
    assert created.status.value == "paused"
    assert created.version == 1
    replay = create_schedule(store, authority_chain)
    assert replay == created
    assert len(store.list_schedule_events(PRIMARY, created.schedule_id)) == 1
    assert AipMemoryPipelineStore().get_schedule(PRIMARY, created.schedule_id) == created
    with pytest.raises(AipMemoryPipelineConflict, match="idempotency"):
        store.create_schedule(
            PRIMARY,
            schedule_request(authority_chain),
            idempotency_key=f"schedule-key-{authority_chain['suffix']}",
            actor="different-actor",
            occurred_at=NOW,
        )
    with pytest.raises(AipMemoryPipelineNotFound):
        store.get_schedule(CANARY, created.schedule_id)
    changed = schedule_request(authority_chain, config_hash=HASH_C)
    with pytest.raises(AipMemoryPipelineConflict, match="idempotency"):
        store.create_schedule(
            PRIMARY,
            changed,
            idempotency_key=f"schedule-key-{authority_chain['suffix']}",
            actor="pytest",
            occurred_at=NOW,
        )


def test_activity_summary_is_unpaginated_and_tenant_scoped(authority_chain) -> None:
    store = AipMemoryPipelineStore()
    before = store.summarize_activity(PRIMARY)
    before_paused = next(
        (item.count for item in before["seed_import"].schedule_counts if item.status == "paused"),
        0,
    )
    created = create_schedule(store, authority_chain)

    primary = store.summarize_activity(PRIMARY)
    canary = store.summarize_activity(CANARY)

    seed = primary[created.pipeline_kind]
    assert next(item.count for item in seed.schedule_counts if item.status == "paused") == before_paused + 1
    assert seed.run_counts == []
    assert sum(item.count for snapshot in canary.values() for item in snapshot.schedule_counts) == 0


def test_schedule_transition_is_cas_audited_append_only_and_atomic(authority_chain) -> None:
    store = AipMemoryPipelineStore()
    schedule = create_schedule(store, authority_chain)
    disabled, event = store.transition_schedule(
        PRIMARY,
        schedule.schedule_id,
        TransitionKnowledgePipelineScheduleRequest(
            expected_version=1,
            from_status="paused",
            to_status="disabled",
            reason_code="dependency_unavailable",
        ),
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=1),
    )
    assert disabled.version == 2
    assert event.from_status.value == "paused"
    assert event.to_status.value == "disabled"
    assert [
        item.sequence
        for item in store.list_schedule_events(PRIMARY, schedule.schedule_id)
    ] == [1, 2]
    with pytest.raises(AipMemoryPipelineConflict):
        store.transition_schedule(
            PRIMARY,
            schedule.schedule_id,
            TransitionKnowledgePipelineScheduleRequest(
                expected_version=1,
                from_status="paused",
                to_status="disabled",
                reason_code="stale_writer",
            ),
            actor="reviewer",
            occurred_at=NOW + timedelta(minutes=2),
        )
    with connect(PRIMARY) as conn:
        with pytest.raises(ObjectNotInPrerequisiteState):
            conn.execute(
                """UPDATE aip_memory_pipeline_schedule_event SET reason_code='tampered'
                   WHERE org_id=%s AND project_id=%s AND schedule_id=%s""",
                (*PRIMARY.key, schedule.schedule_id),
            )
        conn.rollback()

    with connect() as conn:
        conn.execute(
            """CREATE OR REPLACE FUNCTION reject_test_pipeline_event() RETURNS trigger
               LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'event rejected'; END $$"""
        )
        conn.execute(
            """CREATE TRIGGER trg_test_reject_pipeline_event BEFORE INSERT
               ON aip_memory_pipeline_schedule_event FOR EACH ROW
               EXECUTE FUNCTION reject_test_pipeline_event()"""
        )
        conn.commit()
    try:
        with pytest.raises(AipMemoryPipelinePersistenceError):
            store.transition_schedule(
                PRIMARY,
                schedule.schedule_id,
                TransitionKnowledgePipelineScheduleRequest(
                    expected_version=2,
                    from_status="disabled",
                    to_status="paused",
                    reason_code="dependency_recovered",
                    dependency_review=resource("aip.eval_report", "review-1"),
                ),
                actor="reviewer",
                occurred_at=NOW + timedelta(minutes=3),
            )
    finally:
        with connect() as conn:
            conn.execute(
                "DROP TRIGGER IF EXISTS trg_test_reject_pipeline_event "
                "ON aip_memory_pipeline_schedule_event"
            )
            conn.execute("DROP FUNCTION IF EXISTS reject_test_pipeline_event()")
            conn.commit()
    assert store.get_schedule(PRIMARY, schedule.schedule_id) == disabled


def test_run_claim_pause_resume_failure_receipt_alert_and_retry(authority_chain) -> None:
    store = AipMemoryPipelineStore()
    create_schedule(store, authority_chain)
    first_id = f"pipeline-run-{authority_chain['suffix']}-1"
    started = store.start_run(
        PRIMARY,
        start_request(authority_chain, first_id),
        idempotency_key=f"run-key-{authority_chain['suffix']}-1",
        actor="pytest",
        occurred_at=NOW,
    )
    assert store.start_run(
        PRIMARY,
        start_request(authority_chain, first_id),
        idempotency_key=f"run-key-{authority_chain['suffix']}-1",
        actor="pytest",
        occurred_at=NOW,
    ) == started
    with pytest.raises(AipMemoryPipelineConflict, match="idempotency"):
        store.start_run(
            PRIMARY,
            start_request(
                authority_chain,
                first_id,
                scheduled_for=NOW + timedelta(minutes=1),
            ),
            idempotency_key=f"run-key-{authority_chain['suffix']}-1",
            actor="pytest",
            occurred_at=NOW,
        )
    claimed = store.claim_run(
        PRIMARY,
        first_id,
        ClaimKnowledgePipelineRunRequest(
            expected_version=1,
            lease_owner="worker-1",
            lease_seconds=120,
        ),
        occurred_at=NOW + timedelta(seconds=1),
    )
    assert claimed.status.value == "running"
    assert claimed.lease_owner == "worker-1"
    paused = store.transition_run(
        PRIMARY,
        first_id,
        TransitionKnowledgePipelineRunRequest(
            expected_version=2,
            from_status="running",
            to_status="paused",
            reason_code="operator_pause",
        ),
        actor="operator",
        occurred_at=NOW + timedelta(seconds=2),
    )
    queued = store.transition_run(
        PRIMARY,
        first_id,
        TransitionKnowledgePipelineRunRequest(
            expected_version=3,
            from_status="paused",
            to_status="queued",
            reason_code="operator_resume",
        ),
        actor="operator",
        occurred_at=NOW + timedelta(seconds=3),
    )
    assert paused.lease_owner is None and queued.status.value == "queued"
    claimed_again = store.claim_run(
        PRIMARY,
        first_id,
        ClaimKnowledgePipelineRunRequest(
            expected_version=4,
            lease_owner="worker-2",
            lease_seconds=120,
        ),
        occurred_at=NOW + timedelta(seconds=4),
    )
    receipt = store.complete_run(
        PRIMARY,
        first_id,
        CompleteKnowledgePipelineRunRequest(
            expected_run_version=claimed_again.version,
            status="failed",
            input_hash=HASH_A,
            output_hash=HASH_B,
            candidate_refs=[],
            checkpoint=None,
            produced_count=0,
            failed_count=1,
            error_codes=["source_blocked"],
        ),
        actor="worker-2",
        occurred_at=NOW + timedelta(seconds=5),
    )
    assert receipt.checkpoint_before_version == receipt.checkpoint_after_version == 0
    assert [item.code for item in store.list_alerts(PRIMARY, first_id)] == ["source_blocked"]
    assert [item.event_type for item in store.list_run_events(PRIMARY, first_id)] == [
        "enqueued",
        "claimed",
        "paused",
        "resumed",
        "claimed",
        "completed",
    ]
    with connect(PRIMARY) as conn:
        with pytest.raises(ObjectNotInPrerequisiteState):
            conn.execute(
                """UPDATE aip_memory_pipeline_run_event SET reason_code='tampered'
                   WHERE org_id=%s AND project_id=%s AND pipeline_run_id=%s""",
                (*PRIMARY.key, first_id),
            )
        conn.rollback()
    retry_id = f"pipeline-run-{authority_chain['suffix']}-2"
    retry = store.start_run(
        PRIMARY,
        start_request(authority_chain, retry_id, retry_of_run_id=first_id),
        idempotency_key=f"run-key-{authority_chain['suffix']}-2",
        actor="pytest",
        occurred_at=NOW + timedelta(seconds=6),
    )
    assert retry.attempt == 2
    assert retry.retry_of_run_id == first_id
    with pytest.raises(AipMemoryPipelineTransitionBlocked):
        store.claim_run(
            PRIMARY,
            first_id,
            ClaimKnowledgePipelineRunRequest(
                expected_version=claimed_again.version + 1,
                lease_owner="worker-3",
                lease_seconds=120,
            ),
            occurred_at=NOW + timedelta(seconds=7),
        )


def test_success_completion_binds_candidate_and_advances_checkpoint_atomically(
    authority_chain,
) -> None:
    store = AipMemoryPipelineStore()
    create_schedule(store, authority_chain)
    candidate_ref = create_candidate(
        authority_chain, f"pipeline-candidate-{authority_chain['suffix']}"
    )
    pipeline_run_id = f"pipeline-run-success-{authority_chain['suffix']}"
    store.start_run(
        PRIMARY,
        start_request(authority_chain, pipeline_run_id),
        idempotency_key=f"run-success-{authority_chain['suffix']}",
        actor="pytest",
        occurred_at=NOW,
    )
    running = store.claim_run(
        PRIMARY,
        pipeline_run_id,
        ClaimKnowledgePipelineRunRequest(
            expected_version=1,
            lease_owner="worker-success",
            lease_seconds=120,
        ),
        occurred_at=NOW + timedelta(seconds=1),
    )
    completion = CompleteKnowledgePipelineRunRequest(
        expected_run_version=running.version,
        status="succeeded",
        input_hash=HASH_A,
        output_hash=HASH_B,
        candidate_refs=[candidate_ref],
        checkpoint=artifact(f"checkpoint-{authority_chain['suffix']}", HASH_C),
        produced_count=1,
        failed_count=0,
        error_codes=[],
    )
    receipt = store.complete_run(
        PRIMARY,
        pipeline_run_id,
        completion,
        actor="worker-success",
        occurred_at=NOW + timedelta(seconds=2),
    )
    assert receipt.checkpoint_before_version == 0
    assert receipt.checkpoint_after_version == 1
    assert receipt.candidate_refs == [candidate_ref]
    checkpoint = store.get_checkpoint(PRIMARY, authority_chain["schedule_id"])
    assert checkpoint is not None and checkpoint.revision == 1
    restarted = AipMemoryPipelineStore()
    assert restarted.get_receipt_for_run(PRIMARY, pipeline_run_id) == receipt
    assert restarted.complete_run(
        PRIMARY,
        pipeline_run_id,
        completion,
        actor="worker-success",
        occurred_at=NOW + timedelta(minutes=10),
    ) == receipt
    with pytest.raises(AipMemoryPipelineConflict, match="different evidence"):
        restarted.complete_run(
            PRIMARY,
            pipeline_run_id,
            completion.model_copy(
                update={
                    "checkpoint": artifact(
                        f"checkpoint-{authority_chain['suffix']}", HASH_A
                    )
                }
            ),
            actor="worker-success",
            occurred_at=NOW + timedelta(minutes=11),
        )
    with pytest.raises(AipMemoryPipelineNotFound):
        restarted.get_receipt_for_run(CANARY, pipeline_run_id)


def test_candidate_drift_and_checkpoint_conflict_fail_closed(authority_chain) -> None:
    store = AipMemoryPipelineStore()
    create_schedule(store, authority_chain)
    candidate_ref = create_candidate(
        authority_chain, f"pipeline-candidate-drift-{authority_chain['suffix']}"
    )
    pipeline_run_id = f"pipeline-run-conflict-{authority_chain['suffix']}"
    store.start_run(
        PRIMARY,
        start_request(authority_chain, pipeline_run_id),
        idempotency_key=f"run-conflict-{authority_chain['suffix']}",
        actor="pytest",
        occurred_at=NOW,
    )
    running = store.claim_run(
        PRIMARY,
        pipeline_run_id,
        ClaimKnowledgePipelineRunRequest(
            expected_version=1,
            lease_owner="worker-conflict",
            lease_seconds=120,
        ),
        occurred_at=NOW + timedelta(seconds=1),
    )
    with pytest.raises(AipMemoryPipelineConflict, match="candidate"):
        store.complete_run(
            PRIMARY,
            pipeline_run_id,
            CompleteKnowledgePipelineRunRequest(
                expected_run_version=running.version,
                status="succeeded",
                input_hash=HASH_A,
                output_hash=HASH_B,
                candidate_refs=[candidate_ref.model_copy(update={"revision": "999"})],
                checkpoint=None,
                produced_count=1,
                failed_count=0,
                error_codes=[],
            ),
            actor="worker-conflict",
            occurred_at=NOW + timedelta(seconds=2),
        )
    with connect(PRIMARY) as conn:
        conn.execute(
            """UPDATE aip_memory_pipeline_schedule SET checkpoint_version=1
               WHERE org_id=%s AND project_id=%s AND schedule_id=%s""",
            (*PRIMARY.key, authority_chain["schedule_id"]),
        )
        conn.commit()
    with pytest.raises(AipMemoryPipelineConflict, match="checkpoint"):
        store.complete_run(
            PRIMARY,
            pipeline_run_id,
            CompleteKnowledgePipelineRunRequest(
                expected_run_version=running.version,
                status="succeeded",
                input_hash=HASH_A,
                output_hash=HASH_B,
                candidate_refs=[candidate_ref],
                checkpoint=artifact(f"checkpoint-conflict-{authority_chain['suffix']}", HASH_C),
                produced_count=1,
                failed_count=0,
                error_codes=[],
            ),
            actor="worker-conflict",
            occurred_at=NOW + timedelta(seconds=3),
        )
    assert [item.code for item in store.list_alerts(PRIMARY, pipeline_run_id)] == [
        "candidate_binding_conflict",
        "checkpoint_conflict",
    ]
    assert store.get_run(PRIMARY, pipeline_run_id).status.value == "running"
    assert store.get_receipt_for_run(PRIMARY, pipeline_run_id, required=False) is None


def test_expired_lease_becomes_unknown_with_receipt_and_alert(authority_chain) -> None:
    store = AipMemoryPipelineStore()
    create_schedule(store, authority_chain)
    pipeline_run_id = f"pipeline-run-expired-{authority_chain['suffix']}"
    store.start_run(
        PRIMARY,
        start_request(authority_chain, pipeline_run_id),
        idempotency_key=f"run-expired-{authority_chain['suffix']}",
        actor="pytest",
        occurred_at=NOW,
    )
    running = store.claim_run(
        PRIMARY,
        pipeline_run_id,
        ClaimKnowledgePipelineRunRequest(
            expected_version=1,
            lease_owner="expired-worker",
            lease_seconds=1,
        ),
        occurred_at=NOW + timedelta(seconds=1),
    )
    with pytest.raises(AipMemoryPipelineTransitionBlocked, match="not expired"):
        store.expire_run_lease(
            PRIMARY,
            pipeline_run_id,
            expected_version=running.version,
            occurred_at=NOW + timedelta(seconds=1),
        )
    with pytest.raises(AipMemoryPipelineTransitionBlocked, match="expired"):
        store.complete_run(
            PRIMARY,
            pipeline_run_id,
            CompleteKnowledgePipelineRunRequest(
                expected_run_version=running.version,
                status="failed",
                input_hash=HASH_A,
                output_hash=HASH_B,
                candidate_refs=[],
                checkpoint=None,
                produced_count=0,
                failed_count=1,
                error_codes=["late_result"],
            ),
            actor="expired-worker",
            occurred_at=NOW + timedelta(seconds=3),
        )
    receipt = store.expire_run_lease(
        PRIMARY,
        pipeline_run_id,
        expected_version=running.version,
        occurred_at=NOW + timedelta(seconds=3),
    )
    assert receipt.status.value == "unknown"
    assert receipt.checkpoint_before_version == receipt.checkpoint_after_version == 0
    assert receipt.error_codes == ["lease_expired"]
    assert store.get_run(PRIMARY, pipeline_run_id).status.value == "unknown"
    assert [item.code for item in store.list_alerts(PRIMARY, pipeline_run_id)] == [
        "lease_expired"
    ]


def test_run_cannot_be_claimed_before_scheduled_time(authority_chain) -> None:
    store = AipMemoryPipelineStore()
    create_schedule(store, authority_chain)
    pipeline_run_id = f"pipeline-run-future-{authority_chain['suffix']}"
    store.start_run(
        PRIMARY,
        start_request(
            authority_chain,
            pipeline_run_id,
            scheduled_for=NOW + timedelta(hours=1),
        ),
        idempotency_key=f"run-future-{authority_chain['suffix']}",
        actor="pytest",
        occurred_at=NOW,
    )
    with pytest.raises(AipMemoryPipelineTransitionBlocked, match="scheduled time"):
        store.claim_run(
            PRIMARY,
            pipeline_run_id,
            ClaimKnowledgePipelineRunRequest(
                expected_version=1,
                lease_owner="early-worker",
                lease_seconds=60,
            ),
            occurred_at=NOW + timedelta(minutes=59),
        )
    assert store.get_run(PRIMARY, pipeline_run_id).status.value == "queued"
