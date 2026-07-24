"""W2-S · Action 收尾组路由：#67 日志对象类型 + #68 平台集成 + #70 Saga 事务回滚."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.action_finale import (
    ActionBinding,
    ActionBindingError,
    ActionLog,
    ActionLogError,
    CompensationStep,
    SagaError,
    SagaStepRecord,
    SagaTransaction,
    WorkshopButtonGroup,
    get_action_binding_engine,
    get_action_log_engine,
    get_saga_engine,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["action-finale"])
log = get_logger("aos-api.action-finale")


def _map_log_error(err: ActionLogError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_binding_error(err: ActionBindingError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_saga_error(err: SagaError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ─────────────── #67 Action 日志对象类型 ───────────────

class ActionLogIn(BaseModel):
    action_id: str = Field(min_length=1)
    operation_rid: str = ""
    version: int = 0
    actor: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    submission_id: str = ""
    status: str = "submitted"
    metadata: dict[str, Any] = Field(default_factory=dict)


class LogStatusUpdateIn(BaseModel):
    status: str = Field(min_length=1)


@router.get("/v1/actions/logs")
def list_action_logs(
    action_id: str | None = None,
    status: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#67 · 列出 Action 日志。"""
    _ = principal
    items = get_action_log_engine().list(action_id=action_id, status=status)
    return {"items": [l.model_dump() for l in items], "count": len(items)}


@router.post("/v1/actions/logs")
def create_action_log(
    body: ActionLogIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#67 · 创建 Action 日志。"""
    _ = principal
    log_obj = ActionLog(**body.model_dump())
    try:
        created = get_action_log_engine().create(log_obj)
        log.info("action_log_created id=%s action=%s version=%s",
                 created.id, created.action_id, created.version)
        return created.model_dump()
    except ActionLogError as err:
        raise _map_log_error(err) from err


@router.get("/v1/actions/logs/{log_id}")
def get_action_log(
    log_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#67 · 获取日志详情。"""
    _ = principal
    try:
        return get_action_log_engine().get(log_id).model_dump()
    except ActionLogError as err:
        raise _map_log_error(err) from err


@router.get("/v1/actions/{action_id}/logs")
def list_logs_by_action(
    action_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#67 · 按 action 列出日志。"""
    _ = principal
    items = get_action_log_engine().list(action_id=action_id)
    return {"items": [l.model_dump() for l in items], "count": len(items)}


@router.post("/v1/actions/logs/{log_id}/status")
def update_log_status(
    log_id: str,
    body: LogStatusUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#67 · 更新日志状态。"""
    _ = principal
    try:
        updated = get_action_log_engine().update_status(log_id, body.status)
        log.info("action_log_status_updated id=%s status=%s", log_id, body.status)
        return updated.model_dump()
    except ActionLogError as err:
        raise _map_log_error(err) from err


@router.get("/v1/actions/{action_id}/log-type")
def get_action_log_type(
    action_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#67 · 获取/生成日志对象类型定义。"""
    _ = principal
    return get_action_log_engine().get_log_type(action_id)


# ─────────────── #68 Action 平台集成 ───────────────

class ActionBindingIn(BaseModel):
    action_id: str = Field(min_length=1)
    integration_type: str = "object_view"
    target_type: str = "object_type"
    target_id: str = Field(min_length=1)
    button_label: str = Field(min_length=1)
    button_location: str = "primary"
    visibility_condition: str = ""
    order: int = 0
    enabled: bool = True


class ActionBindingUpdateIn(BaseModel):
    integration_type: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    button_label: str | None = None
    button_location: str | None = None
    visibility_condition: str | None = None
    order: int | None = None
    enabled: bool | None = None


class EvaluateBindingIn(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


class WorkshopButtonGroupIn(BaseModel):
    workshop_module: str = Field(min_length=1)
    name: str = Field(min_length=1)
    action_bindings: list[str] = Field(default_factory=list)
    layout: str = "horizontal"
    order: int = 0


class WorkshopButtonGroupUpdateIn(BaseModel):
    name: str | None = None
    action_bindings: list[str] | None = None
    layout: str | None = None
    order: int | None = None


class AttachBindingIn(BaseModel):
    binding_id: str = Field(min_length=1)


@router.get("/v1/actions/bindings")
def list_bindings(
    action_id: str | None = None,
    integration_type: str | None = None,
    target_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 列出绑定。"""
    _ = principal
    items = get_action_binding_engine().list_bindings(
        action_id=action_id, integration_type=integration_type, target_id=target_id,
    )
    return {"items": [b.model_dump() for b in items], "count": len(items)}


@router.post("/v1/actions/bindings")
def create_binding(
    body: ActionBindingIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 创建绑定。"""
    _ = principal
    binding = ActionBinding(**body.model_dump())
    try:
        created = get_action_binding_engine().create_binding(binding)
        log.info("action_binding_created id=%s action=%s target=%s",
                 created.id, created.action_id, created.target_id)
        return created.model_dump()
    except ActionBindingError as err:
        raise _map_binding_error(err) from err


@router.get("/v1/actions/bindings/{binding_id}")
def get_binding(
    binding_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 获取绑定详情。"""
    _ = principal
    try:
        return get_action_binding_engine().get_binding(binding_id).model_dump()
    except ActionBindingError as err:
        raise _map_binding_error(err) from err


@router.put("/v1/actions/bindings/{binding_id}")
def update_binding(
    binding_id: str,
    body: ActionBindingUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 更新绑定。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        binding = get_action_binding_engine().update_binding(binding_id, updates)
        log.info("action_binding_updated id=%s", binding_id)
        return binding.model_dump()
    except ActionBindingError as err:
        raise _map_binding_error(err) from err


@router.delete("/v1/actions/bindings/{binding_id}")
def delete_binding(
    binding_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 删除绑定。"""
    _ = principal
    try:
        get_action_binding_engine().delete_binding(binding_id)
        log.info("action_binding_deleted id=%s", binding_id)
        return {"deleted": True, "id": binding_id}
    except ActionBindingError as err:
        raise _map_binding_error(err) from err


@router.post("/v1/actions/bindings/{binding_id}/evaluate")
def evaluate_binding(
    binding_id: str,
    body: EvaluateBindingIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 评估绑定可见性。"""
    _ = principal
    try:
        return get_action_binding_engine().evaluate_binding(binding_id, body.context)
    except ActionBindingError as err:
        raise _map_binding_error(err) from err


@router.get("/v1/actions/workshop-button-groups")
def list_button_groups(
    workshop_module: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 列出按钮组。"""
    _ = principal
    items = get_action_binding_engine().list_button_groups(workshop_module=workshop_module)
    return {"items": [g.model_dump() for g in items], "count": len(items)}


@router.post("/v1/actions/workshop-button-groups")
def create_button_group(
    body: WorkshopButtonGroupIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 创建按钮组。"""
    _ = principal
    group = WorkshopButtonGroup(**body.model_dump())
    try:
        created = get_action_binding_engine().create_button_group(group)
        log.info("button_group_created id=%s module=%s", created.id, created.workshop_module)
        return created.model_dump()
    except ActionBindingError as err:
        raise _map_binding_error(err) from err


@router.get("/v1/actions/workshop-button-groups/{group_id}")
def get_button_group(
    group_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 获取按钮组详情。"""
    _ = principal
    try:
        return get_action_binding_engine().get_button_group(group_id).model_dump()
    except ActionBindingError as err:
        raise _map_binding_error(err) from err


@router.put("/v1/actions/workshop-button-groups/{group_id}")
def update_button_group(
    group_id: str,
    body: WorkshopButtonGroupUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 更新按钮组。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        group = get_action_binding_engine().update_button_group(group_id, updates)
        log.info("button_group_updated id=%s", group_id)
        return group.model_dump()
    except ActionBindingError as err:
        raise _map_binding_error(err) from err


@router.delete("/v1/actions/workshop-button-groups/{group_id}")
def delete_button_group(
    group_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 删除按钮组。"""
    _ = principal
    try:
        get_action_binding_engine().delete_button_group(group_id)
        log.info("button_group_deleted id=%s", group_id)
        return {"deleted": True, "id": group_id}
    except ActionBindingError as err:
        raise _map_binding_error(err) from err


@router.get("/v1/actions/workshop-button-groups/by-module/{module}")
def list_button_groups_by_module(
    module: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 按模块列出按钮组。"""
    _ = principal
    items = get_action_binding_engine().list_button_groups(workshop_module=module)
    return {"items": [g.model_dump() for g in items], "count": len(items)}


@router.post("/v1/actions/workshop-button-groups/{group_id}/attach")
def attach_binding(
    group_id: str,
    body: AttachBindingIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 绑定 Action 到按钮组。"""
    _ = principal
    try:
        group = get_action_binding_engine().attach_binding(group_id, body.binding_id)
        log.info("binding_attached group=%s binding=%s", group_id, body.binding_id)
        return group.model_dump()
    except ActionBindingError as err:
        raise _map_binding_error(err) from err


@router.post("/v1/actions/workshop-button-groups/{group_id}/detach")
def detach_binding(
    group_id: str,
    body: AttachBindingIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#68 · 从按钮组解绑 Action。"""
    _ = principal
    try:
        group = get_action_binding_engine().detach_binding(group_id, body.binding_id)
        log.info("binding_detached group=%s binding=%s", group_id, body.binding_id)
        return group.model_dump()
    except ActionBindingError as err:
        raise _map_binding_error(err) from err


# ─────────────── #70 Action 事务回滚（Saga） ───────────────

class CompensationStepIn(BaseModel):
    step_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    order: int
    parameters: dict[str, Any] = Field(default_factory=dict)


class SagaIn(BaseModel):
    name: str = Field(min_length=1)
    forward_steps: list[dict[str, Any]] = Field(default_factory=list)
    compensation_steps: list[CompensationStepIn] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class SagaUpdateIn(BaseModel):
    name: str | None = None
    forward_steps: list[dict[str, Any]] | None = None
    compensation_steps: list[CompensationStepIn] | None = None
    context: dict[str, Any] | None = None


class StepStatusUpdateIn(BaseModel):
    status: str = Field(min_length=1)


@router.get("/v1/actions/sagas")
def list_sagas(
    status: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#70 · 列出 Saga。"""
    _ = principal
    items = get_saga_engine().list(status=status)
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.post("/v1/actions/sagas")
def create_saga(
    body: SagaIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#70 · 创建 Saga。"""
    _ = principal
    saga = SagaTransaction(
        name=body.name,
        forward_steps=body.forward_steps,
        compensation_steps=[
            CompensationStep(**c.model_dump()) for c in body.compensation_steps
        ],
        context=body.context,
    )
    try:
        created = get_saga_engine().create(saga)
        log.info("saga_created id=%s name=%s", created.id, created.name)
        return created.model_dump()
    except SagaError as err:
        raise _map_saga_error(err) from err


@router.get("/v1/actions/sagas/{saga_id}")
def get_saga(
    saga_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#70 · 获取 Saga 详情。"""
    _ = principal
    try:
        return get_saga_engine().get(saga_id).model_dump()
    except SagaError as err:
        raise _map_saga_error(err) from err


@router.put("/v1/actions/sagas/{saga_id}")
def update_saga(
    saga_id: str,
    body: SagaUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#70 · 更新 Saga。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "compensation_steps" in updates and updates["compensation_steps"] is not None:
        updates["compensation_steps"] = [
            CompensationStep(**c.model_dump()) if hasattr(c, "model_dump")
            else CompensationStep(**c)
            for c in updates["compensation_steps"]
        ]
    try:
        saga = get_saga_engine().update(saga_id, updates)
        log.info("saga_updated id=%s", saga_id)
        return saga.model_dump()
    except SagaError as err:
        raise _map_saga_error(err) from err


@router.delete("/v1/actions/sagas/{saga_id}")
def delete_saga(
    saga_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#70 · 删除 Saga。"""
    _ = principal
    try:
        get_saga_engine().delete(saga_id)
        log.info("saga_deleted id=%s", saga_id)
        return {"deleted": True, "id": saga_id}
    except SagaError as err:
        raise _map_saga_error(err) from err


@router.post("/v1/actions/sagas/{saga_id}/start")
def start_saga(
    saga_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#70 · 启动 Saga。"""
    _ = principal
    try:
        saga = get_saga_engine().start(saga_id)
        log.info("saga_started id=%s", saga_id)
        return saga.model_dump()
    except SagaError as err:
        raise _map_saga_error(err) from err


@router.post("/v1/actions/sagas/{saga_id}/compensate")
def compensate_saga(
    saga_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#70 · 触发 Saga 补偿。"""
    _ = principal
    try:
        saga = get_saga_engine().compensate(saga_id)
        log.info("saga_compensating id=%s", saga_id)
        return saga.model_dump()
    except SagaError as err:
        raise _map_saga_error(err) from err


@router.get("/v1/actions/sagas/{saga_id}/records")
def list_saga_records(
    saga_id: str,
    direction: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#70 · 列出 Saga 步骤记录。"""
    _ = principal
    items = get_saga_engine().list_records(saga_id, direction=direction)
    return {"items": [r.model_dump() for r in items], "count": len(items)}


@router.post("/v1/actions/sagas/{saga_id}/records/{record_id}/status")
def update_saga_record_status(
    saga_id: str,
    record_id: str,
    body: StepStatusUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#70 · 更新 Saga 步骤状态。"""
    _ = principal
    try:
        rec = get_saga_engine().update_record_status(saga_id, record_id, body.status)
        log.info("saga_record_status_updated saga=%s record=%s status=%s",
                 saga_id, record_id, body.status)
        return rec.model_dump()
    except SagaError as err:
        raise _map_saga_error(err) from err


@router.get("/v1/actions/sagas/{saga_id}/state")
def get_saga_state(
    saga_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#70 · 获取 Saga 当前状态快照。"""
    _ = principal
    try:
        return get_saga_engine().get_state(saga_id)
    except SagaError as err:
        raise _map_saga_error(err) from err
