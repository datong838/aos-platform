"""W2-Q · Action 增强延伸路由：参数筛选 + 提交标准 + 通知副作用."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.action_further import (
    CriteriaError,
    FilterError,
    NotificationError,
    NotificationSideEffect,
    ParameterFilter,
    SubmissionCriteria,
    get_criteria_engine,
    get_filter_engine,
    get_notification_engine,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["action-further"])
log = get_logger("aos-api.action-further")


def _map_filter_error(err: FilterError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_criteria_error(err: CriteriaError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_notification_error(err: NotificationError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ─────────────── #61 参数筛选 ───────────────

class FilterIn(BaseModel):
    action_id: str
    param_name: str
    target_object_type: str = ""
    base_set: str = ""
    search_scope: dict[str, Any] = Field(default_factory=dict)
    security_filter: str = ""
    ordering: list[dict[str, Any]] = Field(default_factory=list)


class FilterUpdateIn(BaseModel):
    action_id: str | None = None
    param_name: str | None = None
    target_object_type: str | None = None
    base_set: str | None = None
    search_scope: dict[str, Any] | None = None
    security_filter: str | None = None
    ordering: list[dict[str, Any]] | None = None


class ObjectPoolRegisterIn(BaseModel):
    object_type: str
    objects: list[dict[str, Any]]


class ObjectSetRegisterIn(BaseModel):
    set_id: str
    objects: list[dict[str, Any]]


class ApplyIn(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


@router.get("/v1/actions/parameter-filters")
def list_filters(
    action_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#61 · 列出参数筛选。"""
    _ = principal
    eng = get_filter_engine()
    items = eng.list(action_id=action_id)
    return {"filters": [f.model_dump() for f in items], "count": len(items)}


@router.post("/v1/actions/parameter-filters")
def create_filter(
    body: FilterIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#61 · 创建参数筛选。"""
    _ = principal
    eng = get_filter_engine()
    flt = ParameterFilter(**body.model_dump())
    created = eng.create(flt)
    log.info("filter_created id=%s action=%s param=%s",
             created.id, created.action_id, created.param_name)
    return created.model_dump()


@router.get("/v1/actions/parameter-filters/{filter_id}")
def get_filter(
    filter_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#61 · 获取筛选详情。"""
    _ = principal
    eng = get_filter_engine()
    try:
        return eng.get(filter_id).model_dump()
    except FilterError as err:
        raise _map_filter_error(err) from err


@router.put("/v1/actions/parameter-filters/{filter_id}")
def update_filter(
    filter_id: str,
    body: FilterUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#61 · 更新筛选。"""
    _ = principal
    eng = get_filter_engine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        updated = eng.update(filter_id, updates)
    except FilterError as err:
        raise _map_filter_error(err) from err
    log.info("filter_updated id=%s", filter_id)
    return updated.model_dump()


@router.delete("/v1/actions/parameter-filters/{filter_id}")
def delete_filter(
    filter_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#61 · 删除筛选。"""
    _ = principal
    eng = get_filter_engine()
    try:
        eng.delete(filter_id)
    except FilterError as err:
        raise _map_filter_error(err) from err
    log.info("filter_deleted id=%s", filter_id)
    return {"ok": True}


@router.post("/v1/actions/parameter-filters/{filter_id}/apply")
def apply_filter(
    filter_id: str,
    body: ApplyIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#61 · 应用筛选，返回符合条件的对象列表。"""
    _ = principal
    eng = get_filter_engine()
    try:
        return eng.apply(filter_id, body.context)
    except FilterError as err:
        raise _map_filter_error(err) from err


@router.post("/v1/actions/parameter-filter-object-pools")
def register_object_pool(
    body: ObjectPoolRegisterIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#61 · 注册对象池供筛选起始集。"""
    _ = principal
    eng = get_filter_engine()
    eng.register_object_pool(body.object_type, body.objects)
    log.info("object_pool_registered type=%s count=%s", body.object_type, len(body.objects))
    return {"ok": True}


@router.post("/v1/actions/parameter-filter-object-sets")
def register_filter_object_set(
    body: ObjectSetRegisterIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#61 · 注册 Object Set 作为筛选起始集。"""
    _ = principal
    eng = get_filter_engine()
    eng.register_object_set(body.set_id, body.objects)
    log.info("filter_object_set_registered id=%s count=%s", body.set_id, len(body.objects))
    return {"ok": True}


# ─────────────── #62 提交标准可视化 ───────────────

class CriteriaIn(BaseModel):
    action_id: str
    name: str
    condition_tree: dict[str, Any]
    failure_message: str = ""
    severity: str = "error"


class CriteriaUpdateIn(BaseModel):
    action_id: str | None = None
    name: str | None = None
    condition_tree: dict[str, Any] | None = None
    failure_message: str | None = None
    severity: str | None = None


class EvaluateCriteriaIn(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


@router.get("/v1/actions/submission-criteria")
def list_criteria(
    action_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#62 · 列出提交标准。"""
    _ = principal
    eng = get_criteria_engine()
    items = eng.list(action_id=action_id)
    return {"criteria": [c.model_dump() for c in items], "count": len(items)}


@router.post("/v1/actions/submission-criteria")
def create_criteria(
    body: CriteriaIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#62 · 创建提交标准。"""
    _ = principal
    eng = get_criteria_engine()
    criteria = SubmissionCriteria(**body.model_dump())
    try:
        created = eng.create(criteria)
    except CriteriaError as err:
        raise _map_criteria_error(err) from err
    log.info("criteria_created id=%s action=%s name=%s",
             created.id, created.action_id, created.name)
    return created.model_dump()


@router.get("/v1/actions/submission-criteria/{criteria_id}")
def get_criteria(
    criteria_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#62 · 获取提交标准详情。"""
    _ = principal
    eng = get_criteria_engine()
    try:
        return eng.get(criteria_id).model_dump()
    except CriteriaError as err:
        raise _map_criteria_error(err) from err


@router.put("/v1/actions/submission-criteria/{criteria_id}")
def update_criteria(
    criteria_id: str,
    body: CriteriaUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#62 · 更新提交标准。"""
    _ = principal
    eng = get_criteria_engine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        updated = eng.update(criteria_id, updates)
    except CriteriaError as err:
        raise _map_criteria_error(err) from err
    log.info("criteria_updated id=%s", criteria_id)
    return updated.model_dump()


@router.delete("/v1/actions/submission-criteria/{criteria_id}")
def delete_criteria(
    criteria_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#62 · 删除提交标准。"""
    _ = principal
    eng = get_criteria_engine()
    try:
        eng.delete(criteria_id)
    except CriteriaError as err:
        raise _map_criteria_error(err) from err
    log.info("criteria_deleted id=%s", criteria_id)
    return {"ok": True}


@router.post("/v1/actions/submission-criteria/{criteria_id}/evaluate")
def evaluate_criteria(
    criteria_id: str,
    body: EvaluateCriteriaIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#62 · 评估条件树。"""
    _ = principal
    eng = get_criteria_engine()
    try:
        return eng.evaluate(criteria_id, body.context)
    except CriteriaError as err:
        raise _map_criteria_error(err) from err


# ─────────────── #63 通知副作用 ───────────────

class NotificationIn(BaseModel):
    action_id: str
    name: str
    recipient_source: str = "static"
    recipients: list[str] = Field(default_factory=list)
    recipient_ref: str = ""
    subject_template: str = ""
    body_template: str = ""
    channel: str = "email"


class NotificationUpdateIn(BaseModel):
    action_id: str | None = None
    name: str | None = None
    recipient_source: str | None = None
    recipients: list[str] | None = None
    recipient_ref: str | None = None
    subject_template: str | None = None
    body_template: str | None = None
    channel: str | None = None


class NotificationObjectIn(BaseModel):
    object_type: str
    obj: dict[str, Any]


class NotificationFunctionIn(BaseModel):
    func_name: str
    # 函数体存疑：API 不直接传 callable，仅做注册占位
    description: str = ""


class RenderIn(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


@router.get("/v1/actions/notification-effects")
def list_notifications(
    action_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#63 · 列出通知副作用。"""
    _ = principal
    eng = get_notification_engine()
    items = eng.list(action_id=action_id)
    return {"effects": [e.model_dump() for e in items], "count": len(items)}


@router.post("/v1/actions/notification-effects")
def create_notification(
    body: NotificationIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#63 · 创建通知副作用。"""
    _ = principal
    eng = get_notification_engine()
    effect = NotificationSideEffect(**body.model_dump())
    try:
        created = eng.create(effect)
    except NotificationError as err:
        raise _map_notification_error(err) from err
    log.info("notification_created id=%s action=%s name=%s source=%s channel=%s",
             created.id, created.action_id, created.name,
             created.recipient_source, created.channel)
    return created.model_dump()


@router.get("/v1/actions/notification-effects/{effect_id}")
def get_notification(
    effect_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#63 · 获取通知副作用详情。"""
    _ = principal
    eng = get_notification_engine()
    try:
        return eng.get(effect_id).model_dump()
    except NotificationError as err:
        raise _map_notification_error(err) from err


@router.put("/v1/actions/notification-effects/{effect_id}")
def update_notification(
    effect_id: str,
    body: NotificationUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#63 · 更新通知副作用。"""
    _ = principal
    eng = get_notification_engine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        updated = eng.update(effect_id, updates)
    except NotificationError as err:
        raise _map_notification_error(err) from err
    log.info("notification_updated id=%s", effect_id)
    return updated.model_dump()


@router.delete("/v1/actions/notification-effects/{effect_id}")
def delete_notification(
    effect_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#63 · 删除通知副作用。"""
    _ = principal
    eng = get_notification_engine()
    try:
        eng.delete(effect_id)
    except NotificationError as err:
        raise _map_notification_error(err) from err
    log.info("notification_deleted id=%s", effect_id)
    return {"ok": True}


@router.post("/v1/actions/notification-effects/{effect_id}/render")
def render_notification(
    effect_id: str,
    body: RenderIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#63 · 渲染通知（subject/body/recipients）。"""
    _ = principal
    eng = get_notification_engine()
    try:
        return eng.render(effect_id, body.context)
    except NotificationError as err:
        raise _map_notification_error(err) from err


@router.post("/v1/actions/notification-effects/{effect_id}/dispatch")
def dispatch_notification(
    effect_id: str,
    body: RenderIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#63 · 派发通知到队列。"""
    _ = principal
    eng = get_notification_engine()
    try:
        record = eng.dispatch(effect_id, body.context)
    except NotificationError as err:
        raise _map_notification_error(err) from err
    log.info("notification_dispatched id=%s dispatch=%s recipients=%s",
             effect_id, record["dispatch_id"], len(record["recipients"]))
    return record


@router.get("/v1/actions/notification-effects/dispatches")
def list_dispatches(
    effect_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#63 · 列出派发记录。"""
    _ = principal
    eng = get_notification_engine()
    items = eng.list_dispatches(effect_id=effect_id)
    return {"dispatches": items, "count": len(items)}


@router.post("/v1/actions/notification-objects")
def register_notification_object(
    body: NotificationObjectIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#63 · 注册对象供 object_property 来源引用。"""
    _ = principal
    eng = get_notification_engine()
    eng.register_object(body.object_type, body.obj)
    log.info("notification_object_registered type=%s id=%s",
             body.object_type, body.obj.get("id"))
    return {"ok": True}
