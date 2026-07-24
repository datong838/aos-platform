"""W2-V · AIP 智能层扩展组路由：#78 调试器 + #79 Automate + #80 四层成熟度."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.aip_extras import (
    AIPExtrasError,
    AutomateEngine,
    AutomateRun,
    AutomateTrigger,
    DebugSession,
    DebugStep,
    DebuggerEngine,
    MaturityAssessment,
    MaturityLevel,
    MaturityEngine,
    ProposedChange,
    ProposalPreview,
    get_automate_engine,
    get_debugger_engine,
    get_maturity_engine,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["aip-extras"])
log = get_logger("aos-api.aip-extras")


def _map_err(err: AIPExtrasError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    if err.code == "ALREADY_APPLIED":
        status = 409
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #78 调试器 ════════════════════

class CreateSessionIn(BaseModel):
    logic_id: str = Field(min_length=1)
    inputs: dict[str, Any] = Field(default_factory=dict)


class PreviewProposalIn(BaseModel):
    changes: list[ProposedChange] = Field(default_factory=list)


@router.post("/v1/aip/debugger/sessions")
def create_debug_session(
    body: CreateSessionIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#78 · 创建调试会话。"""
    _ = principal
    try:
        s = get_debugger_engine().create_session(body.logic_id, body.inputs)
        log.info("debug_session_created id=%s logic=%s", s.id, s.logic_id)
        return s.model_dump()
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.get("/v1/aip/debugger/sessions")
def list_debug_sessions(
    logic_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#78 · 列出调试会话。"""
    _ = principal
    items = get_debugger_engine().list_sessions(logic_id=logic_id)
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/v1/aip/debugger/sessions/{session_id}")
def get_debug_session(
    session_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#78 · 单条调试会话。"""
    _ = principal
    try:
        return get_debugger_engine().get_session(session_id).model_dump()
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/debugger/sessions/{session_id}/step-forward")
def debug_step_forward(
    session_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#78 · 前进一步。"""
    _ = principal
    try:
        step = get_debugger_engine().step_forward(session_id)
        return step.model_dump()
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/debugger/sessions/{session_id}/step-backward")
def debug_step_backward(
    session_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#78 · 后退一步。"""
    _ = principal
    try:
        step = get_debugger_engine().step_backward(session_id)
        return step.model_dump()
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/debugger/sessions/{session_id}/run")
def debug_run_to_completion(
    session_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#78 · 连续执行到完成。"""
    _ = principal
    try:
        s = get_debugger_engine().run_to_completion(session_id)
        log.info("debug_session_completed id=%s status=%s", session_id, s.status)
        return s.model_dump()
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/debugger/sessions/{session_id}/preview")
def preview_proposal(
    session_id: str,
    body: PreviewProposalIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#78 · 生成提议预览（不应用）。"""
    _ = principal
    try:
        p = get_debugger_engine().preview_proposal(session_id, body.changes)
        log.info("proposal_previewed id=%s session=%s", p.id, session_id)
        return p.model_dump()
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.get("/v1/aip/debugger/proposals")
def list_proposals(
    session_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#78 · 列出提议预览。"""
    _ = principal
    items = get_debugger_engine().list_proposals(session_id=session_id)
    return {"items": [p.model_dump() for p in items], "count": len(items)}


@router.post("/v1/aip/debugger/proposals/{proposal_id}/apply")
def apply_proposal(
    proposal_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#78 · 应用提议。"""
    _ = principal
    try:
        p = get_debugger_engine().apply_proposal(proposal_id)
        log.info("proposal_applied id=%s", proposal_id)
        return p.model_dump()
    except AIPExtrasError as err:
        raise _map_err(err) from err


# ════════════════════ #79 Automate ════════════════════

class UpsertTriggerIn(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1)
    logic_id: str = Field(min_length=1)
    event_type: str = "manual"
    condition: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    cooldown_seconds: float = 0.0
    description: str = ""


class EvaluateTriggerIn(BaseModel):
    event: dict[str, Any] = Field(default_factory=dict)


class FireTriggerIn(BaseModel):
    event: dict[str, Any] = Field(default_factory=dict)


@router.get("/v1/aip/automate/triggers")
def list_automate_triggers(
    enabled_only: bool = False,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#79 · 列出触发器。"""
    _ = principal
    items = get_automate_engine().list_triggers(enabled_only=enabled_only)
    return {"items": [t.model_dump() for t in items], "count": len(items)}


@router.post("/v1/aip/automate/triggers")
def upsert_automate_trigger(
    body: UpsertTriggerIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#79 · 新增/更新触发器。"""
    _ = principal
    trigger = AutomateTrigger(
        id=body.id or "",
        name=body.name,
        logic_id=body.logic_id,
        event_type=body.event_type,
        condition=body.condition,
        enabled=body.enabled,
        cooldown_seconds=body.cooldown_seconds,
        description=body.description,
    )
    try:
        created = get_automate_engine().upsert_trigger(trigger)
        log.info("automate_trigger_upserted id=%s name=%s", created.id, created.name)
        return created.model_dump()
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.get("/v1/aip/automate/triggers/{trigger_id}")
def get_automate_trigger(
    trigger_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#79 · 单条触发器。"""
    _ = principal
    try:
        return get_automate_engine().get_trigger(trigger_id).model_dump()
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.delete("/v1/aip/automate/triggers/{trigger_id}")
def delete_automate_trigger(
    trigger_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#79 · 删除触发器。"""
    _ = principal
    try:
        get_automate_engine().delete_trigger(trigger_id)
        log.info("automate_trigger_deleted id=%s", trigger_id)
        return {"deleted": True, "id": trigger_id}
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/automate/triggers/{trigger_id}/evaluate")
def evaluate_automate_trigger(
    trigger_id: str,
    body: EvaluateTriggerIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#79 · 评估触发条件。"""
    _ = principal
    try:
        matched = get_automate_engine().evaluate(trigger_id, body.event)
        return {"trigger_id": trigger_id, "matched": matched}
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/automate/triggers/{trigger_id}/fire")
def fire_automate_trigger(
    trigger_id: str,
    body: FireTriggerIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#79 · 触发执行。"""
    _ = principal
    try:
        run = get_automate_engine().fire(trigger_id, body.event)
        log.info("automate_fired trigger=%s run=%s status=%s",
                 trigger_id, run.id, run.status)
        return run.model_dump()
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.get("/v1/aip/automate/runs")
def list_automate_runs(
    trigger_id: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#79 · 列出执行记录。"""
    _ = principal
    items = get_automate_engine().list_runs(trigger_id=trigger_id, limit=limit)
    return {"items": [r.model_dump() for r in items], "count": len(items)}


@router.get("/v1/aip/automate/runs/{run_id}")
def get_automate_run(
    run_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#79 · 单条执行记录。"""
    _ = principal
    try:
        return get_automate_engine().get_run(run_id).model_dump()
    except AIPExtrasError as err:
        raise _map_err(err) from err


# ════════════════════ #80 四层成熟度 ════════════════════

class UpsertLevelIn(BaseModel):
    level: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    required_capabilities: list[str] = Field(default_factory=list)


class RegisterCapabilityIn(BaseModel):
    name: str = Field(min_length=1)
    satisfied: bool


class SetTargetIn(BaseModel):
    level: str = Field(min_length=1)


@router.get("/v1/aip/maturity/levels")
def list_maturity_levels(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#80 · 列出 L1~L4 定义。"""
    _ = principal
    items = get_maturity_engine().list_levels()
    return {"items": [lv.model_dump() for lv in items], "count": len(items)}


@router.get("/v1/aip/maturity/levels/{level}")
def get_maturity_level(
    level: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#80 · 单条等级定义。"""
    _ = principal
    try:
        return get_maturity_engine().get_level(level).model_dump()
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/maturity/levels")
def upsert_maturity_level(
    body: UpsertLevelIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#80 · 更新等级定义。"""
    _ = principal
    level = MaturityLevel(
        level=body.level,
        name=body.name,
        description=body.description,
        required_capabilities=body.required_capabilities,
    )
    try:
        created = get_maturity_engine().upsert_level(level)
        log.info("maturity_level_upserted level=%s", created.level)
        return created.model_dump()
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.get("/v1/aip/maturity/capabilities")
def list_capabilities(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#80 · 列出能力满足情况。"""
    _ = principal
    caps = get_maturity_engine().list_capabilities()
    return {"capabilities": caps, "count": len(caps)}


@router.post("/v1/aip/maturity/capabilities")
def register_capability(
    body: RegisterCapabilityIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#80 · 注册/更新能力。"""
    _ = principal
    try:
        get_maturity_engine().register_capability(body.name, body.satisfied)
        log.info("capability_registered name=%s satisfied=%s", body.name, body.satisfied)
        return {"name": body.name, "satisfied": body.satisfied}
    except AIPExtrasError as err:
        raise _map_err(err) from err


@router.post("/v1/aip/maturity/assess")
def assess_maturity(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#80 · 触发评估。"""
    _ = principal
    asmt = get_maturity_engine().assess()
    log.info("maturity_assessed id=%s current=%s score=%.2f",
             asmt.id, asmt.current_level, asmt.score)
    return asmt.model_dump()


@router.get("/v1/aip/maturity/assessments")
def list_maturity_assessments(
    limit: int = 20,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#80 · 历史评估列表。"""
    _ = principal
    items = get_maturity_engine().list_assessments(limit=limit)
    return {"items": [a.model_dump() for a in items], "count": len(items)}


@router.get("/v1/aip/maturity/target")
def get_target_level(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#80 · 当前目标等级。"""
    _ = principal
    return {"target_level": get_maturity_engine().get_target_level()}


@router.post("/v1/aip/maturity/target")
def set_target_level(
    body: SetTargetIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#80 · 设置目标等级。"""
    _ = principal
    try:
        get_maturity_engine().set_target_level(body.level)
        log.info("maturity_target_set level=%s", body.level)
        return {"target_level": body.level}
    except AIPExtrasError as err:
        raise _map_err(err) from err
