"""W2-X · AIP 决策审计组路由：#84 Decision Lineage + #85 Insight Backfill + #87 Capability Adapter."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.decision_audit import (
    AdapterManifest,
    BackfillConfig,
    DecisionAuditError,
    DecisionRecord,
    InsightObject,
    get_capability_adapter_engine,
    get_decision_lineage_engine,
    get_insight_backfill_engine,
)
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["decision-audit"])
log = get_logger("aos-api.decision-audit")


def _map_err(err: DecisionAuditError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #84 Decision Lineage ════════════════════

class DecisionRecordIn(BaseModel):
    logic_id: str = Field(min_length=1)
    proposal_id: str = ""
    model_id: str = ""
    prompt_version: str = ""
    object_refs: list[str] = Field(default_factory=list)
    wiki_fields: list[str] = Field(default_factory=list)
    cot: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    draft_params: dict[str, Any] = Field(default_factory=dict)
    approval_result: str = ""
    actor: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/v1/aip/decisions")
def record_decision(
    body: DecisionRecordIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#84 · 记录决策。"""
    _ = principal
    rec = DecisionRecord(**body.model_dump())
    return {"item": get_decision_lineage_engine().record(rec).model_dump()}


@router.get("/v1/aip/decisions")
def list_decisions(
    logic_id: str | None = None,
    proposal_id: str | None = None,
    actor: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#84 · 决策列表。"""
    _ = principal
    items = get_decision_lineage_engine().list(
        logic_id=logic_id, proposal_id=proposal_id, actor=actor, limit=limit,
    )
    return {"items": [r.model_dump() for r in items], "count": len(items)}


@router.get("/v1/aip/decisions/{decision_id}")
def get_decision(
    decision_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#84 · 单条决策。"""
    _ = principal
    try:
        return {"item": get_decision_lineage_engine().get(decision_id).model_dump()}
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc


@router.get("/v1/aip/decisions/{decision_id}/timeline")
def get_decision_timeline(
    decision_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#84 · 决策时间线。"""
    _ = principal
    try:
        return {"item": get_decision_lineage_engine().get_timeline(decision_id)}
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc


@router.get("/v1/aip/decisions/by-proposal/{proposal_id}")
def trace_by_proposal(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#84 · 按提案溯源。"""
    _ = principal
    items = get_decision_lineage_engine().trace(proposal_id)
    return {"items": [r.model_dump() for r in items], "count": len(items)}


# ════════════════════ #85 Insight Backfill ════════════════════

class BackfillConfigIn(BaseModel):
    confidence_threshold: float = 0.85
    auto_backfill: bool = False
    max_daily_backfill: int = 100


class InsightIn(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    confidence: float
    source_decision_id: str = Field(min_length=1)
    object_type: str = "Insight"
    object_id: str = ""
    links: list[str] = Field(default_factory=list)


class EvaluateIn(BaseModel):
    decision_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    confidence: float
    links: list[str] = Field(default_factory=list)


@router.get("/v1/aip/insights/config")
def get_backfill_config(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#85 · 获取回填配置。"""
    _ = principal
    return {"item": get_insight_backfill_engine().get_config().model_dump()}


@router.post("/v1/aip/insights/config")
def update_backfill_config(
    body: BackfillConfigIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#85 · 更新回填配置。"""
    _ = principal
    try:
        cfg = get_insight_backfill_engine().update_config(BackfillConfig(**body.model_dump()))
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc
    return {"item": cfg.model_dump()}


@router.post("/v1/aip/insights")
def register_insight(
    body: InsightIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#85 · 注册 Insight。"""
    _ = principal
    try:
        ins = get_insight_backfill_engine().register_insight(
            InsightObject(**body.model_dump()),
        )
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc
    return {"item": ins.model_dump()}


@router.get("/v1/aip/insights")
def list_insights(
    source_decision_id: str | None = None,
    backfill_status: str | None = None,
    min_confidence: float = 0.0,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#85 · Insight 列表。"""
    _ = principal
    items = get_insight_backfill_engine().list_insights(
        source_decision_id=source_decision_id,
        backfill_status=backfill_status,
        min_confidence=min_confidence,
        limit=limit,
    )
    return {"items": [i.model_dump() for i in items], "count": len(items)}


@router.get("/v1/aip/insights/pending")
def list_pending_insights(
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#85 · 待回填列表。"""
    _ = principal
    items = get_insight_backfill_engine().list_pending(limit=limit)
    return {"items": [i.model_dump() for i in items], "count": len(items)}


@router.get("/v1/aip/insights/{insight_id}")
def get_insight(
    insight_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#85 · 单条 Insight。"""
    _ = principal
    try:
        return {"item": get_insight_backfill_engine().get_insight(insight_id).model_dump()}
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc


@router.post("/v1/aip/insights/{insight_id}/backfill")
def backfill_insight(
    insight_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#85 · 执行回填。"""
    _ = principal
    try:
        ins = get_insight_backfill_engine().backfill(insight_id)
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc
    return {"item": ins.model_dump()}


@router.post("/v1/aip/insights/evaluate")
def evaluate_and_register_insight(
    body: EvaluateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#85 · 评估置信度并注册 Insight。"""
    _ = principal
    try:
        ins = get_insight_backfill_engine().evaluate_and_register(
            decision_id=body.decision_id,
            title=body.title,
            content=body.content,
            confidence=body.confidence,
            links=body.links,
        )
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc
    return {"item": ins.model_dump()}


@router.post("/v1/aip/insights/cleanup")
def cleanup_insights(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#85 · 清理失败的 Insight 记录。"""
    _ = principal
    n = get_insight_backfill_engine().cleanup()
    return {"cleaned": n}


# ════════════════════ #87 Capability Adapter ════════════════════

class AdapterManifestIn(BaseModel):
    id: str = Field(min_length=1)
    name: str
    capability_class: str
    version: str = "1.0.0"
    description: str = ""
    invoke_endpoint: str = ""
    submit_endpoint: str = ""
    status_endpoint: str = ""
    cancel_endpoint: str = ""
    artifact_endpoint: str = ""
    session_open_endpoint: str = ""
    session_close_endpoint: str = ""
    auth_type: str = "none"
    enabled: bool = True


class AdapterUpdateIn(BaseModel):
    name: str | None = None
    version: str | None = None
    description: str | None = None
    invoke_endpoint: str | None = None
    submit_endpoint: str | None = None
    status_endpoint: str | None = None
    cancel_endpoint: str | None = None
    artifact_endpoint: str | None = None
    session_open_endpoint: str | None = None
    session_close_endpoint: str | None = None
    auth_type: str | None = None
    enabled: bool | None = None


class InvokeIn(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    invoke_endpoint: str | None = None  # 可选覆盖（仅测试用，生产层走 callable 注入）


class SubmitIn(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


class SessionOpenIn(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


@router.post("/v1/aip/capabilities/adapters")
def register_adapter(
    body: AdapterManifestIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#87 · 注册 Adapter。"""
    _ = principal
    try:
        m = get_capability_adapter_engine().register(
            AdapterManifest(**body.model_dump()),
        )
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc
    return {"item": m.model_dump()}


@router.get("/v1/aip/capabilities/adapters")
def list_adapters(
    capability_class: str | None = None,
    enabled_only: bool = False,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#87 · Adapter 列表。"""
    _ = principal
    items = get_capability_adapter_engine().list(
        capability_class=capability_class, enabled_only=enabled_only,
    )
    return {"items": [m.model_dump() for m in items], "count": len(items)}


@router.get("/v1/aip/capabilities/adapters/{adapter_id}")
def get_adapter(
    adapter_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#87 · 单条 Adapter。"""
    _ = principal
    try:
        return {"item": get_capability_adapter_engine().get(adapter_id).model_dump()}
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/aip/capabilities/adapters/{adapter_id}")
def update_adapter(
    adapter_id: str,
    body: AdapterUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#87 · 更新 Adapter。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        m = get_capability_adapter_engine().update(adapter_id, updates)
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc
    return {"item": m.model_dump()}


@router.delete("/v1/aip/capabilities/adapters/{adapter_id}")
def delete_adapter(
    adapter_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#87 · 删除 Adapter。"""
    _ = principal
    ok = get_capability_adapter_engine().delete(adapter_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"Adapter {adapter_id} 不存在", status_code=404)
    return {"id": adapter_id, "deleted": True}


@router.post("/v1/aip/capabilities/adapters/{adapter_id}/invoke")
def invoke_adapter(
    adapter_id: str,
    body: InvokeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#87 · C0 同步调用。"""
    _ = principal
    try:
        inv = get_capability_adapter_engine().invoke(
            adapter_id, body.inputs, invoke_callable=None,
        )
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc
    return {"item": inv.model_dump()}


@router.post("/v1/aip/capabilities/adapters/{adapter_id}/submit")
def submit_job(
    adapter_id: str,
    body: SubmitIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#87 · C1 异步提交。"""
    _ = principal
    try:
        inv = get_capability_adapter_engine().submit(
            adapter_id, body.inputs, submit_callable=None,
        )
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc
    return {"item": inv.model_dump()}


@router.get("/v1/aip/capabilities/adapters/{adapter_id}/jobs/{job_id}/status")
def job_status(
    adapter_id: str,
    job_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#87 · C1 查询 job 状态。"""
    _ = principal
    try:
        inv = get_capability_adapter_engine().status(
            adapter_id, job_id, status_callable=None,
        )
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc
    return {"item": inv.model_dump()}


@router.post("/v1/aip/capabilities/adapters/{adapter_id}/jobs/{job_id}/cancel")
def cancel_job(
    adapter_id: str,
    job_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#87 · C1 取消 job。"""
    _ = principal
    try:
        inv = get_capability_adapter_engine().cancel(adapter_id, job_id)
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc
    return {"item": inv.model_dump()}


@router.get("/v1/aip/capabilities/adapters/{adapter_id}/jobs/{job_id}/artifact")
def job_artifact(
    adapter_id: str,
    job_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#87 · C1 获取 job 产物。"""
    _ = principal
    try:
        inv = get_capability_adapter_engine().artifact(
            adapter_id, job_id, artifact_callable=None,
        )
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc
    return {"item": inv.model_dump()}


@router.post("/v1/aip/capabilities/adapters/{adapter_id}/sessions/open")
def open_session(
    adapter_id: str,
    body: SessionOpenIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#87 · C2 开启会话。"""
    _ = principal
    try:
        inv = get_capability_adapter_engine().session_open(
            adapter_id, body.inputs, open_callable=None,
        )
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc
    return {"item": inv.model_dump()}


@router.post("/v1/aip/capabilities/adapters/{adapter_id}/sessions/{session_id}/close")
def close_session(
    adapter_id: str,
    session_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#87 · C2 关闭会话。"""
    _ = principal
    try:
        inv = get_capability_adapter_engine().session_close(adapter_id, session_id)
    except DecisionAuditError as exc:
        raise _map_err(exc) from exc
    return {"item": inv.model_dump()}


@router.get("/v1/aip/capabilities/invocations")
def list_invocations(
    adapter_id: str | None = None,
    job_id: str | None = None,
    session_id: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#87 · 调用记录列表。"""
    _ = principal
    items = get_capability_adapter_engine().list_invocations(
        adapter_id=adapter_id, job_id=job_id, session_id=session_id, limit=limit,
    )
    return {"items": [i.model_dump() for i in items], "count": len(items)}
