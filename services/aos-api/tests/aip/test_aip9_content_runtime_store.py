from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from aos_api.aip_content_contracts import (
    AvatarSessionOpenRequest,
    AvatarSessionStatus,
    MediaAssetRef,
    MediaJobCreateRequest,
    MediaJobKind,
    MediaJobStatus,
    MediaType,
    MediaUsage,
)
from aos_api.aip_content_runtime_store import AipContentRuntimeStore
from aos_api.aip_contracts import ArtifactRef, ResourceRef
from aos_api.aip_production_contracts import (
    ContractBlocker,
    ExactRevisionRef,
    MutableAuthorityRef,
)
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database

HASH = "a" * 64
SCOPE = TenantScope("pytest-content-org", "pytest-content-project")
CANARY = TenantScope("pytest-content-canary", "pytest-content-project")
RUN_ID = "content-run-1"
STEP_ID = "content-step-1"


def resource(kind: str, value: str) -> ResourceRef:
    return ResourceRef(resourceType=kind, resourceId=value, revision="1", authority="pytest")


def exact(kind: str, value: str) -> ExactRevisionRef:
    return ExactRevisionRef(resourceType=kind, resourceId=value, revision=1, contentHash=HASH)


@pytest.fixture(scope="module", autouse=True)
def content_database():
    with isolated_aip_migration_database("content_store"):
        with connect() as conn:
            for scope in (SCOPE, CANARY):
                conn.execute("INSERT INTO twa_org(id,name) VALUES (%s,%s)", (scope.org_id, scope.org_id))
                conn.execute(
                    "INSERT INTO twa_workspace(org_id,project_id,name) VALUES (%s,%s,%s)",
                    (*scope.key, scope.project_id),
                )
            conn.execute(
                """INSERT INTO aip_task(org_id,project_id,task_id,task_type,title,status,
                   idempotency_key,request_hash,created_by)
                   VALUES (%s,%s,'content-task-1','content_campaign','Content test','executing',
                     'content-task-key',%s,'pytest')""", (*SCOPE.key, HASH),
            )
            conn.execute(
                """INSERT INTO aip_plan_revision(org_id,project_id,plan_revision_id,task_id,
                   revision,content_hash,steps,approval_status,idempotency_key,request_hash,created_by)
                   VALUES (%s,%s,'content-plan-1','content-task-1',1,%s,'[]'::jsonb,'approved',
                     'content-plan-key',%s,'pytest')""", (*SCOPE.key, HASH, HASH),
            )
            conn.execute(
                """UPDATE aip_task SET current_plan_revision_id='content-plan-1'
                   WHERE org_id=%s AND project_id=%s AND task_id='content-task-1'""", SCOPE.key,
            )
            conn.execute(
                """INSERT INTO aip_task_run(org_id,project_id,run_id,task_id,plan_revision_id,
                   status,idempotency_key,request_hash,created_by)
                   VALUES (%s,%s,%s,'content-task-1','content-plan-1','running',
                     'content-run-key',%s,'pytest')""", (*SCOPE.key, RUN_ID, HASH),
            )
            conn.execute(
                """INSERT INTO aip_step_run(org_id,project_id,step_run_id,run_id,step_key,
                   attempt,status) VALUES (%s,%s,%s,%s,'render',1,'running')""",
                (*SCOPE.key, STEP_ID, RUN_ID),
            )
            conn.commit()
        yield


def media_request() -> MediaJobCreateRequest:
    asset = MediaAssetRef(
        artifactRef=ArtifactRef(artifactId="product-image-1", artifactType="image",
                                revision="1", contentHash=HASH),
        mediaType=MediaType.IMAGE,
        usage=MediaUsage.INPUT,
        provenanceRef=exact("AssetProvenanceRevision", "provenance-1"),
        licenseRef=exact("AssetLicenseRevision", "license-1"),
        evidenceBundleRef=exact("EvidenceBundleRevision", "evidence-1"),
        withdrawalPolicyRef=exact("AssetWithdrawalPolicyRevision", "withdrawal-1"),
    )
    return MediaJobCreateRequest(
        taskRunRef=resource("TaskRun", RUN_ID),
        stepRunRef=resource("StepRun", STEP_ID),
        jobKind=MediaJobKind.VIDEO_RENDER,
        inputAssets=[asset],
        outputSchemaRef=resource("JsonSchemaRevision", "video-output-v1"),
        capabilityRef=exact("CapabilityRevision", "video-render"),
        capabilityBindingRef=MutableAuthorityRef(
            resourceType="CapabilityBinding", resourceId="video-render-binding", version=1
        ),
        budgetRef=exact("BudgetRevision", "content-budget"),
        deadlineAt=datetime.now(UTC) + timedelta(hours=1),
    )


def avatar_request() -> AvatarSessionOpenRequest:
    return AvatarSessionOpenRequest(
        taskRunRef=resource("TaskRun", RUN_ID),
        stepRunRef=resource("StepRun", STEP_ID),
        capabilityRef=exact("CapabilityRevision", "avatar-live"),
        capabilityBindingRef=MutableAuthorityRef(
            resourceType="CapabilityBinding", resourceId="avatar-binding", version=1
        ),
        budgetRef=exact("BudgetRevision", "avatar-budget"),
        killPolicyRef=exact("KillPolicyRevision", "avatar-kill"),
        livePlanRef=ArtifactRef(artifactId="live-plan-1", artifactType="live_plan",
                                revision="1", contentHash=HASH),
        maxDurationSeconds=300,
    )


def key(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def test_media_job_cas_replay_restart_tenant_and_terminal_guards() -> None:
    store = AipContentRuntimeStore()
    submit_key = key("media-submit")
    request = media_request()
    created = store.submit_media_job(SCOPE, request, idempotency_key=submit_key, actor="pytest")
    assert created.status is MediaJobStatus.QUEUED and created.latest_sequence == 1
    assert store.submit_media_job(SCOPE, request, idempotency_key=submit_key, actor="pytest") == created
    with pytest.raises(ApiError) as hidden:
        store.get_media_job(CANARY, created.job_id)
    assert hidden.value.status_code == 404

    now = datetime.now(UTC)
    lease = resource("ExecutorLease", "media-lease-1")
    running = store.command_media_job(
        SCOPE, created.job_id, "claim", expected_version=1,
        idempotency_key=key("claim"), actor="pytest", executor_lease_ref=lease,
        heartbeat_at=now, lease_expires_at=now + timedelta(minutes=5), occurred_at=now,
    )
    assert running.status is MediaJobStatus.RUNNING and running.latest_sequence == 2
    heartbeat = store.command_media_job(
        SCOPE, created.job_id, "heartbeat", expected_version=2,
        idempotency_key=key("heartbeat"), actor="pytest", executor_lease_ref=lease,
        heartbeat_at=now + timedelta(minutes=1),
        lease_expires_at=now + timedelta(minutes=6), occurred_at=now + timedelta(minutes=1),
    )
    assert heartbeat.latest_sequence == 3
    output = ArtifactRef(artifactId="video-1", artifactType="video", revision="1", contentHash=HASH)
    succeeded = store.command_media_job(
        SCOPE, created.job_id, "succeed", expected_version=3,
        idempotency_key=key("succeed"), actor="pytest", output_artifact_refs=[output],
        occurred_at=now + timedelta(minutes=2),
    )
    assert succeeded.status is MediaJobStatus.SUCCEEDED
    assert AipContentRuntimeStore().get_media_job(SCOPE, created.job_id) == succeeded
    with connect(SCOPE) as conn:
        receipt = conn.execute(
            """SELECT receipt_id FROM aip_media_job_receipt
               WHERE org_id=%s AND project_id=%s AND job_id=%s AND operation='succeed'""",
            (*SCOPE.key, created.job_id),
        ).fetchone()
    assert receipt["receipt_id"] == succeeded.completion_receipt_ref.resource_id
    with pytest.raises(ApiError) as terminal:
        store.command_media_job(SCOPE, created.job_id, "cancel", expected_version=4,
                                idempotency_key=key("late-cancel"), actor="pytest",
                                reason_code="too_late")
    assert terminal.value.code == "CONTENT_RUNTIME_TRANSITION_BLOCKED"


def test_media_unknown_reconcile_is_explicit_and_cannot_forge_success() -> None:
    store = AipContentRuntimeStore()
    created = store.submit_media_job(
        SCOPE, media_request(), idempotency_key=key("unknown-submit"), actor="pytest"
    )
    unknown = store.command_media_job(
        SCOPE, created.job_id, "mark_unknown", expected_version=1,
        idempotency_key=key("unknown"), actor="pytest",
        blockers=[ContractBlocker(code="EXECUTOR_LOST", message="executor heartbeat expired")],
    )
    assert unknown.status is MediaJobStatus.UNKNOWN and unknown.finished_at is None
    with pytest.raises(ApiError):
        store.command_media_job(
            SCOPE, created.job_id, "reconcile", expected_version=2,
            idempotency_key=key("forge"), actor="pytest",
            reconcile_status=MediaJobStatus.SUCCEEDED,
        )
    queued = store.command_media_job(
        SCOPE, created.job_id, "reconcile", expected_version=2,
        idempotency_key=key("requeue"), actor="pytest",
        reconcile_status=MediaJobStatus.QUEUED,
    )
    assert queued.status is MediaJobStatus.QUEUED and not queued.blockers


def test_content_runtime_lists_are_tenant_scoped_bounded_and_stably_sorted() -> None:
    store = AipContentRuntimeStore()
    first_at = datetime.now(UTC) + timedelta(days=2)
    first = store.submit_media_job(
        SCOPE, media_request(), idempotency_key=key("list-first"), actor="pytest",
        occurred_at=first_at,
    )
    second = store.submit_media_job(
        SCOPE, media_request(), idempotency_key=key("list-second"), actor="pytest",
        occurred_at=first_at + timedelta(seconds=1),
    )
    assert [item.job_id for item in store.list_media_jobs(SCOPE, limit=2)] == [
        second.job_id,
        first.job_id,
    ]
    assert store.list_media_jobs(CANARY, limit=2) == []

    avatar_first = store.open_avatar_session(
        SCOPE, avatar_request(), idempotency_key=key("avatar-list-first"), actor="pytest",
        occurred_at=first_at,
    )
    avatar_second = store.open_avatar_session(
        SCOPE, avatar_request(), idempotency_key=key("avatar-list-second"), actor="pytest",
        occurred_at=first_at + timedelta(seconds=1),
    )
    assert [item.session_id for item in store.list_avatar_sessions(SCOPE, limit=2)] == [
        avatar_second.session_id,
        avatar_first.session_id,
    ]
    assert store.list_avatar_sessions(CANARY, limit=2) == []
    with pytest.raises(ValueError):
        store.list_media_jobs(SCOPE, limit=0)
    with pytest.raises(ValueError):
        store.list_avatar_sessions(SCOPE, limit=201)


def test_avatar_session_full_control_path_and_terminal_guard() -> None:
    store = AipContentRuntimeStore()
    opened = store.open_avatar_session(
        SCOPE, avatar_request(), idempotency_key=key("avatar-open"), actor="pytest"
    )
    ready = store.command_avatar_session(
        SCOPE, opened.session_id, "ready", expected_version=1,
        idempotency_key=key("ready"), actor="pytest",
    )
    now = datetime.now(UTC)
    engine = exact("OpaqueAvatarEngineSessionRef", "engine-session-1")
    live = store.command_avatar_session(
        SCOPE, opened.session_id, "live", expected_version=2,
        idempotency_key=key("live"), actor="pytest", engine_session_ref=engine,
        heartbeat_at=now, heartbeat_expires_at=now + timedelta(minutes=1), occurred_at=now,
    )
    assert live.status is AvatarSessionStatus.LIVE
    paused = store.command_avatar_session(
        SCOPE, opened.session_id, "pause", expected_version=3,
        idempotency_key=key("pause"), actor="pytest",
    )
    resumed = store.command_avatar_session(
        SCOPE, opened.session_id, "resume", expected_version=4,
        idempotency_key=key("resume"), actor="pytest", engine_session_ref=engine,
        heartbeat_at=now + timedelta(seconds=20),
        heartbeat_expires_at=now + timedelta(minutes=2), occurred_at=now + timedelta(seconds=20),
    )
    assert resumed.status is AvatarSessionStatus.LIVE
    closing = store.command_avatar_session(
        SCOPE, opened.session_id, "closing", expected_version=5,
        idempotency_key=key("closing"), actor="pytest",
    )
    closed = store.command_avatar_session(
        SCOPE, opened.session_id, "close", expected_version=6,
        idempotency_key=key("close"), actor="pytest",
    )
    assert paused.status is AvatarSessionStatus.PAUSED
    assert closing.status is AvatarSessionStatus.CLOSING
    assert closed.status is AvatarSessionStatus.CLOSED and closed.completion_receipt_ref
    with connect(SCOPE) as conn:
        receipt = conn.execute(
            """SELECT receipt_id FROM aip_avatar_session_receipt
               WHERE org_id=%s AND project_id=%s AND session_id=%s AND operation='close'""",
            (*SCOPE.key, opened.session_id),
        ).fetchone()
    assert receipt["receipt_id"] == closed.completion_receipt_ref.resource_id
    with pytest.raises(ApiError):
        store.command_avatar_session(
            SCOPE, opened.session_id, "ready", expected_version=7,
            idempotency_key=key("terminal-ready"), actor="pytest",
        )


def test_idempotency_payload_drift_and_stale_version_fail_closed() -> None:
    store = AipContentRuntimeStore()
    reused = key("drift")
    store.submit_media_job(SCOPE, media_request(), idempotency_key=reused, actor="pytest")
    with pytest.raises(ApiError) as drift:
        store.submit_media_job(
            SCOPE,
            media_request().model_copy(update={"deadline_at": datetime.now(UTC) + timedelta(days=1)}),
            idempotency_key=reused,
            actor="pytest",
        )
    assert drift.value.code == "IDEMPOTENCY_CONFLICT"

    created = store.submit_media_job(
        SCOPE, media_request(), idempotency_key=key("stale-submit"), actor="pytest"
    )
    with pytest.raises(ApiError) as stale:
        store.command_media_job(
            SCOPE, created.job_id, "cancel", expected_version=99,
            idempotency_key=key("stale"), actor="pytest", reason_code="cancelled",
        )
    assert stale.value.code == "REVISION_CONFLICT"
