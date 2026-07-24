"""W2-W · L4 自动化收尾组路由：#82 L4 熔断 + #83 模型预热 + #86 三种提案通道."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.l4_automation import (
    L4Alert,
    L4AutomationError,
    L4CircuitConfig,
    L4CircuitEngine,
    L4CircuitState,
    ModelWarmupEngine,
    ProposalChannel,
    ProposalChannelEngine,
    ProposalSubmission,
    WarmupProbeResult,
    WarmupState,
    get_l4_circuit_engine,
    get_model_warmup_engine,
    get_proposal_channel_engine,
)
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["l4-automation"])
log = get_logger("aos-api.l4-automation")


def _map_err(err: L4AutomationError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    if err.code in ("ALREADY_APPROVED", "ALREADY_REJECTED", "ALREADY_DECIDED",
                    "SUBMISSION_CANCELLED", "SUBMISSION_FINAL"):
        status = 409
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #82 L4 熔断 ════════════════════

class UpdateConfigIn(BaseModel):
    window_size: int = 100
    failure_threshold: float = 0.05
    recovery_threshold: float = 0.025
    cooldown_seconds: float = 60.0
    auto_degrade_to: str = "L3"


class RecordCallIn(BaseModel):
    success: bool


class ForceDegradeIn(BaseModel):
    reason: str = "manual"


@router.get("/v1/aip/l4-circuit/config")
def get_l4_config(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#82 · 获取 L4 熔断配置。"""
    _ = principal
    return get_l4_circuit_engine().get_config().model_dump()


@router.post("/v1/aip/l4-circuit/config")
def update_l4_config(
    body: UpdateConfigIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#82 · 更新 L4 熔断配置。"""
    _ = principal
    cfg = L4CircuitConfig(**body.model_dump())
    try:
        updated = get_l4_circuit_engine().update_config(cfg)
        log.info("l4_config_updated window=%s threshold=%.3f",
                 updated.window_size, updated.failure_threshold)
        return updated.model_dump()
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.get("/v1/aip/l4-circuit/state")
def get_l4_state(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#82 · 当前 L4 熔断状态。"""
    _ = principal
    return get_l4_circuit_engine().get_state().model_dump()


@router.post("/v1/aip/l4-circuit/record-call")
def record_l4_call(
    body: RecordCallIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#82 · 记录一次调用结果。"""
    _ = principal
    state = get_l4_circuit_engine().record_call(body.success)
    return state.model_dump()


@router.post("/v1/aip/l4-circuit/force-degrade")
def force_l4_degrade(
    body: ForceDegradeIn | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#82 · 手动强制降级（演练）。"""
    _ = principal
    reason = body.reason if body else "manual"
    alert = get_l4_circuit_engine().force_degrade(reason)
    log.info("l4_force_degraded reason=%s", reason)
    return alert.model_dump()


@router.post("/v1/aip/l4-circuit/force-recover")
def force_l4_recover(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#82 · 手动恢复。"""
    _ = principal
    alert = get_l4_circuit_engine().force_recover()
    log.info("l4_force_recovered")
    return alert.model_dump()


@router.get("/v1/aip/l4-circuit/alerts")
def list_l4_alerts(
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#82 · 告警历史。"""
    _ = principal
    items = get_l4_circuit_engine().list_alerts(limit=limit)
    return {"items": [a.model_dump() for a in items], "count": len(items)}


# ════════════════════ #83 模型预热 ════════════════════

class RegisterModelIn(BaseModel):
    model_id: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarkFailedIn(BaseModel):
    error: str = ""


class WarmupIn(BaseModel):
    # 客户端可传 probe_url 等，服务端简化忽略；probe 由后端注入
    pass


@router.post("/v1/aip/warmup/models")
def register_warmup_model(
    body: RegisterModelIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#83 · 注册模型预热。"""
    _ = principal
    try:
        s = get_model_warmup_engine().register_model(body.model_id, body.metadata)
        log.info("warmup_model_registered id=%s", body.model_id)
        return s.model_dump()
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.get("/v1/aip/warmup/models")
def list_warmup_models(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#83 · 列出预热状态。"""
    _ = principal
    items = get_model_warmup_engine().list_states()
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/v1/aip/warmup/models/{model_id}")
def get_warmup_state(
    model_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#83 · 单条预热状态。"""
    _ = principal
    try:
        return get_model_warmup_engine().get_state(model_id).model_dump()
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/warmup/models/{model_id}/warmup")
def trigger_warmup(
    model_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#83 · 执行预热探测（默认 probe 返回 True）。"""
    _ = principal
    try:
        result = get_model_warmup_engine().warmup(model_id)
        log.info("warmup_triggered id=%s success=%s", model_id, result.success)
        return result.model_dump()
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/warmup/models/{model_id}/mark-ready")
def mark_warmup_ready(
    model_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#83 · 标记就绪（外部探测器）。"""
    _ = principal
    try:
        s = get_model_warmup_engine().mark_ready(model_id)
        log.info("warmup_marked_ready id=%s", model_id)
        return s.model_dump()
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/warmup/models/{model_id}/mark-failed")
def mark_warmup_failed(
    model_id: str,
    body: MarkFailedIn | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#83 · 标记失败。"""
    _ = principal
    error = body.error if body else ""
    try:
        s = get_model_warmup_engine().mark_failed(model_id, error)
        log.info("warmup_marked_failed id=%s error=%s", model_id, error)
        return s.model_dump()
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.delete("/v1/aip/warmup/models/{model_id}")
def remove_warmup_model(
    model_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#83 · 移除模型。"""
    _ = principal
    try:
        get_model_warmup_engine().remove_model(model_id)
        log.info("warmup_model_removed id=%s", model_id)
        return {"deleted": True, "id": model_id}
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.get("/v1/aip/warmup/probe-results")
def list_warmup_probe_results(
    model_id: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#83 · 探测历史。"""
    _ = principal
    items = get_model_warmup_engine().list_probe_results(
        model_id=model_id, limit=limit,
    )
    return {"items": [r.model_dump() for r in items], "count": len(items)}


# ════════════════════ #86 三种提案通道 ════════════════════

class UpsertChannelIn(BaseModel):
    type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    enabled: bool = True


class SubmitProposalIn(BaseModel):
    channel: str = Field(min_length=1)
    logic_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    submitted_by: str = ""
    visibility_hours: float = 24.0


class ApproveIn(BaseModel):
    approver: str = Field(min_length=1)


class RejectIn(BaseModel):
    approver: str = Field(min_length=1)
    reason: str = ""


@router.get("/v1/aip/proposal-channels")
def list_proposal_channels(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#86 · 列出通道。"""
    _ = principal
    items = get_proposal_channel_engine().list_channels()
    return {"items": [c.model_dump() for c in items], "count": len(items)}


@router.get("/v1/aip/proposal-channels/{channel_type}")
def get_proposal_channel(
    channel_type: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#86 · 单条通道。"""
    _ = principal
    try:
        return get_proposal_channel_engine().get_channel(channel_type).model_dump()
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/proposal-channels")
def upsert_proposal_channel(
    body: UpsertChannelIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#86 · 新增/更新通道。"""
    _ = principal
    ch = ProposalChannel(**body.model_dump())
    try:
        created = get_proposal_channel_engine().upsert_channel(ch)
        log.info("proposal_channel_upserted type=%s", created.type)
        return created.model_dump()
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/proposals")
def submit_proposal(
    body: SubmitProposalIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#86 · 提交提案。"""
    _ = principal
    try:
        s = get_proposal_channel_engine().submit(
            channel=body.channel,
            logic_id=body.logic_id,
            payload=body.payload,
            submitted_by=body.submitted_by,
            visibility_hours=body.visibility_hours,
        )
        log.info("proposal_submitted id=%s channel=%s logic=%s",
                 s.id, s.channel, s.logic_id)
        return s.model_dump()
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.get("/v1/aip/proposals")
def list_proposals(
    channel: str | None = None,
    status: str | None = None,
    approval_status: str | None = None,
    include_expired: bool = False,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#86 · 列出提案。"""
    _ = principal
    items = get_proposal_channel_engine().list_submissions(
        channel=channel,
        status=status,
        approval_status=approval_status,
        include_expired=include_expired,
    )
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/v1/aip/proposals/{proposal_id}")
def get_proposal(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#86 · 单条提案。"""
    _ = principal
    try:
        return get_proposal_channel_engine().get_submission(proposal_id).model_dump()
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/proposals/{proposal_id}/approve")
def approve_proposal(
    proposal_id: str,
    body: ApproveIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#86 · 审批通过。"""
    _ = principal
    try:
        s = get_proposal_channel_engine().approve(proposal_id, body.approver)
        log.info("proposal_approved id=%s approver=%s", proposal_id, body.approver)
        return s.model_dump()
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/proposals/{proposal_id}/reject")
def reject_proposal(
    proposal_id: str,
    body: RejectIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#86 · 审批驳回。"""
    _ = principal
    try:
        s = get_proposal_channel_engine().reject(
            proposal_id, body.approver, body.reason,
        )
        log.info("proposal_rejected id=%s approver=%s", proposal_id, body.approver)
        return s.model_dump()
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/proposals/{proposal_id}/cancel")
def cancel_proposal(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#86 · 取消提案。"""
    _ = principal
    try:
        s = get_proposal_channel_engine().cancel(proposal_id)
        log.info("proposal_cancelled id=%s", proposal_id)
        return s.model_dump()
    except L4AutomationError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/proposals/cleanup-expired")
def cleanup_expired_proposals(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#86 · 清理过期未审批提案。"""
    _ = principal
    count = get_proposal_channel_engine().cleanup_expired()
    log.info("proposals_cleanup_expired count=%s", count)
    return {"cancelled_count": count}
