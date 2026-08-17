"""AIP-9 canonical MediaJob and AvatarSession authority API."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import Field

from aos_api.aip_content_contracts import (
    AvatarSessionOpenRequest,
    AvatarSessionSnapshot,
    AvatarSessionStatus,
    MediaJobCreateRequest,
    MediaJobSnapshot,
    MediaJobStatus,
)
from aos_api.aip_content_runtime_store import AipContentRuntimeStore
from aos_api.aip_contracts import AipContractModel, ArtifactRef, ResourceRef
from aos_api.aip_production_contracts import ContractBlocker, ExactRevisionRef
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/content", tags=["aip-content-runtime"])
_STORE = AipContentRuntimeStore()
_OPERATOR_ROLES = frozenset({"admin", "developer", "operator", "executor", "aip_executor"})
_EXECUTOR_ROLES = frozenset({"admin", "executor", "aip_executor"})


def get_aip_content_runtime_store() -> AipContentRuntimeStore:
    return _STORE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _require_role(principal: Principal, allowed: frozenset[str]) -> None:
    if not allowed.intersection(principal.roles):
        raise ApiError(
            code="CONTENT_RUNTIME_ROLE_REQUIRED",
            message="principal role is not allowed for this content runtime operation",
            status_code=403,
        )


class ExpectedVersionCommand(AipContractModel):
    expected_version: int = Field(ge=1)


class MediaClaimCommand(ExpectedVersionCommand):
    executor_lease_ref: ResourceRef
    heartbeat_at: datetime
    lease_expires_at: datetime


class MediaHeartbeatCommand(MediaClaimCommand):
    pass


class MediaCompleteCommand(ExpectedVersionCommand):
    output_artifact_refs: list[ArtifactRef] = Field(min_length=1, max_length=100)


class FailureCommand(ExpectedVersionCommand):
    reason_code: str = Field(min_length=1, max_length=160)


class UnknownCommand(ExpectedVersionCommand):
    blockers: list[ContractBlocker] = Field(min_length=1, max_length=100)


class MediaReconcileCommand(ExpectedVersionCommand):
    reconcile_status: MediaJobStatus
    reason_code: str | None = Field(default=None, min_length=1, max_length=160)


class AvatarLiveCommand(ExpectedVersionCommand):
    engine_session_ref: ExactRevisionRef
    heartbeat_at: datetime
    heartbeat_expires_at: datetime


class AvatarHeartbeatCommand(ExpectedVersionCommand):
    heartbeat_at: datetime
    heartbeat_expires_at: datetime


class AvatarReconcileCommand(ExpectedVersionCommand):
    reconcile_status: AvatarSessionStatus
    reason_code: str | None = Field(default=None, min_length=1, max_length=160)


def _media_command(
    job_id: str,
    operation: str,
    body: ExpectedVersionCommand,
    idempotency_key: str,
    principal: Principal,
    store: AipContentRuntimeStore,
) -> MediaJobSnapshot:
    _require_role(principal, _EXECUTOR_ROLES if operation in {
        "claim", "heartbeat", "succeed", "fail", "mark_unknown", "reconcile"
    } else _OPERATOR_ROLES)
    values = body.model_dump(exclude={"expected_version"}, exclude_none=True)
    return store.command_media_job(
        _scope(principal), job_id, operation,
        expected_version=body.expected_version,
        idempotency_key=idempotency_key,
        actor=principal.subject,
        **values,
    )


def _avatar_command(
    session_id: str,
    operation: str,
    body: ExpectedVersionCommand,
    idempotency_key: str,
    principal: Principal,
    store: AipContentRuntimeStore,
) -> AvatarSessionSnapshot:
    _require_role(principal, _EXECUTOR_ROLES if operation in {
        "ready", "live", "heartbeat", "fail", "mark_unknown", "reconcile"
    } else _OPERATOR_ROLES)
    values = body.model_dump(exclude={"expected_version"}, exclude_none=True)
    return store.command_avatar_session(
        _scope(principal), session_id, operation,
        expected_version=body.expected_version,
        idempotency_key=idempotency_key,
        actor=principal.subject,
        **values,
    )


@router.post("/media-jobs", response_model=MediaJobSnapshot, status_code=status.HTTP_201_CREATED)
def submit_media_job(
    body: MediaJobCreateRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120),
    principal: Principal = Depends(require_principal),
    store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store),
) -> MediaJobSnapshot:
    _require_role(principal, _OPERATOR_ROLES)
    return store.submit_media_job(
        _scope(principal), body, idempotency_key=idempotency_key, actor=principal.subject
    )


@router.get("/media-jobs", response_model=list[MediaJobSnapshot])
def list_media_jobs(
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store),
) -> list[MediaJobSnapshot]:
    return store.list_media_jobs(_scope(principal), limit=limit)


@router.get("/media-jobs/{job_id}", response_model=MediaJobSnapshot)
def get_media_job(
    job_id: str,
    principal: Principal = Depends(require_principal),
    store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store),
) -> MediaJobSnapshot:
    return store.get_media_job(_scope(principal), job_id)


@router.post("/media-jobs/{job_id}/claim", response_model=MediaJobSnapshot)
def claim_media_job(job_id: str, body: MediaClaimCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _media_command(job_id, "claim", body, idempotency_key, principal, store)


@router.post("/media-jobs/{job_id}/heartbeat", response_model=MediaJobSnapshot)
def heartbeat_media_job(job_id: str, body: MediaHeartbeatCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _media_command(job_id, "heartbeat", body, idempotency_key, principal, store)


@router.post("/media-jobs/{job_id}/complete", response_model=MediaJobSnapshot)
def complete_media_job(job_id: str, body: MediaCompleteCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _media_command(job_id, "succeed", body, idempotency_key, principal, store)


@router.post("/media-jobs/{job_id}/fail", response_model=MediaJobSnapshot)
def fail_media_job(job_id: str, body: FailureCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _media_command(job_id, "fail", body, idempotency_key, principal, store)


@router.post("/media-jobs/{job_id}/cancel", response_model=MediaJobSnapshot)
def cancel_media_job(job_id: str, body: FailureCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _media_command(job_id, "cancel", body, idempotency_key, principal, store)


@router.post("/media-jobs/{job_id}/mark-unknown", response_model=MediaJobSnapshot)
def mark_media_job_unknown(job_id: str, body: UnknownCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _media_command(job_id, "mark_unknown", body, idempotency_key, principal, store)


@router.post("/media-jobs/{job_id}/reconcile", response_model=MediaJobSnapshot)
def reconcile_media_job(job_id: str, body: MediaReconcileCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _media_command(job_id, "reconcile", body, idempotency_key, principal, store)


@router.post("/avatar-sessions", response_model=AvatarSessionSnapshot, status_code=status.HTTP_201_CREATED)
def open_avatar_session(
    body: AvatarSessionOpenRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120),
    principal: Principal = Depends(require_principal),
    store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store),
) -> AvatarSessionSnapshot:
    _require_role(principal, _OPERATOR_ROLES)
    return store.open_avatar_session(
        _scope(principal), body, idempotency_key=idempotency_key, actor=principal.subject
    )


@router.get("/avatar-sessions", response_model=list[AvatarSessionSnapshot])
def list_avatar_sessions(limit: int = Query(default=100, ge=1, le=200), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return store.list_avatar_sessions(_scope(principal), limit=limit)


@router.get("/avatar-sessions/{session_id}", response_model=AvatarSessionSnapshot)
def get_avatar_session(session_id: str, principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return store.get_avatar_session(_scope(principal), session_id)


@router.post("/avatar-sessions/{session_id}/ready", response_model=AvatarSessionSnapshot)
def ready_avatar_session(session_id: str, body: ExpectedVersionCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _avatar_command(session_id, "ready", body, idempotency_key, principal, store)


@router.post("/avatar-sessions/{session_id}/live", response_model=AvatarSessionSnapshot)
def live_avatar_session(session_id: str, body: AvatarLiveCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _avatar_command(session_id, "live", body, idempotency_key, principal, store)


@router.post("/avatar-sessions/{session_id}/heartbeat", response_model=AvatarSessionSnapshot)
def heartbeat_avatar_session(session_id: str, body: AvatarHeartbeatCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _avatar_command(session_id, "heartbeat", body, idempotency_key, principal, store)


@router.post("/avatar-sessions/{session_id}/pause", response_model=AvatarSessionSnapshot)
def pause_avatar_session(session_id: str, body: ExpectedVersionCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _avatar_command(session_id, "pause", body, idempotency_key, principal, store)


@router.post("/avatar-sessions/{session_id}/resume", response_model=AvatarSessionSnapshot)
def resume_avatar_session(session_id: str, body: AvatarLiveCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _avatar_command(session_id, "resume", body, idempotency_key, principal, store)


@router.post("/avatar-sessions/{session_id}/closing", response_model=AvatarSessionSnapshot)
def closing_avatar_session(session_id: str, body: ExpectedVersionCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _avatar_command(session_id, "closing", body, idempotency_key, principal, store)


@router.post("/avatar-sessions/{session_id}/close", response_model=AvatarSessionSnapshot)
def close_avatar_session(session_id: str, body: ExpectedVersionCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _avatar_command(session_id, "close", body, idempotency_key, principal, store)


@router.post("/avatar-sessions/{session_id}/fail", response_model=AvatarSessionSnapshot)
def fail_avatar_session(session_id: str, body: FailureCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _avatar_command(session_id, "fail", body, idempotency_key, principal, store)


@router.post("/avatar-sessions/{session_id}/kill", response_model=AvatarSessionSnapshot)
def kill_avatar_session(session_id: str, body: FailureCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _avatar_command(session_id, "kill", body, idempotency_key, principal, store)


@router.post("/avatar-sessions/{session_id}/mark-unknown", response_model=AvatarSessionSnapshot)
def mark_avatar_session_unknown(session_id: str, body: UnknownCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _avatar_command(session_id, "mark_unknown", body, idempotency_key, principal, store)


@router.post("/avatar-sessions/{session_id}/reconcile", response_model=AvatarSessionSnapshot)
def reconcile_avatar_session(session_id: str, body: AvatarReconcileCommand, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120), principal: Principal = Depends(require_principal), store: AipContentRuntimeStore = Depends(get_aip_content_runtime_store)):
    return _avatar_command(session_id, "reconcile", body, idempotency_key, principal, store)


__all__ = ["get_aip_content_runtime_store", "router"]
