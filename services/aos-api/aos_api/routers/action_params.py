"""W2-P · Action 参数增强路由：参数约束 + 默认值 + 条件覆盖."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.action_params import (
    ConstraintError,
    DefaultError,
    OverrideError,
    ParameterConstraint,
    ParameterDefault,
    ParameterOverride,
    get_constraint_engine,
    get_default_engine,
    get_override_engine,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["action-params"])
log = get_logger("aos-api.action-params")


def _map_constraint_error(err: ConstraintError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_default_error(err: DefaultError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_override_error(err: OverrideError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ─────────────── #58 参数约束 ───────────────

class ConstraintIn(BaseModel):
    action_id: str
    param_name: str
    constraint_type: str  # user_input / multiple_choice / object_set
    config: dict[str, Any] = Field(default_factory=dict)


class ConstraintUpdateIn(BaseModel):
    action_id: str | None = None
    param_name: str | None = None
    constraint_type: str | None = None
    config: dict[str, Any] | None = None


class ObjectSetRegisterIn(BaseModel):
    set_id: str
    objects: list[dict[str, Any]]


class ValidateValueIn(BaseModel):
    value: Any


@router.get("/v1/actions/parameter-constraints")
def list_constraints(
    action_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#58 · 列出参数约束。"""
    _ = principal
    eng = get_constraint_engine()
    items = eng.list(action_id=action_id)
    return {"constraints": [c.model_dump() for c in items], "count": len(items)}


@router.post("/v1/actions/parameter-constraints")
def create_constraint(
    body: ConstraintIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#58 · 创建参数约束。"""
    _ = principal
    eng = get_constraint_engine()
    constraint = ParameterConstraint(**body.model_dump())
    try:
        created = eng.create(constraint)
    except ConstraintError as err:
        raise _map_constraint_error(err) from err
    log.info("constraint_created id=%s action=%s param=%s type=%s",
             created.id, created.action_id, created.param_name, created.constraint_type)
    return created.model_dump()


@router.get("/v1/actions/parameter-constraints/{constraint_id}")
def get_constraint(
    constraint_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#58 · 获取参数约束详情。"""
    _ = principal
    eng = get_constraint_engine()
    try:
        return eng.get(constraint_id).model_dump()
    except ConstraintError as err:
        raise _map_constraint_error(err) from err


@router.put("/v1/actions/parameter-constraints/{constraint_id}")
def update_constraint(
    constraint_id: str,
    body: ConstraintUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#58 · 更新参数约束。"""
    _ = principal
    eng = get_constraint_engine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        updated = eng.update(constraint_id, updates)
    except ConstraintError as err:
        raise _map_constraint_error(err) from err
    log.info("constraint_updated id=%s", constraint_id)
    return updated.model_dump()


@router.delete("/v1/actions/parameter-constraints/{constraint_id}")
def delete_constraint(
    constraint_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#58 · 删除参数约束。"""
    _ = principal
    eng = get_constraint_engine()
    try:
        eng.delete(constraint_id)
    except ConstraintError as err:
        raise _map_constraint_error(err) from err
    log.info("constraint_deleted id=%s", constraint_id)
    return {"ok": True}


@router.post("/v1/actions/parameter-constraints/{constraint_id}/validate")
def validate_value(
    constraint_id: str,
    body: ValidateValueIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#58 · 校验值是否符合约束。"""
    _ = principal
    eng = get_constraint_engine()
    try:
        return eng.validate_value(constraint_id, body.value)
    except ConstraintError as err:
        raise _map_constraint_error(err) from err


@router.get("/v1/actions/parameter-constraints/{constraint_id}/options")
def get_constraint_options(
    constraint_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#58 · 获取约束的候选选项（多选/对象集合）。"""
    _ = principal
    eng = get_constraint_engine()
    try:
        options = eng.get_options(constraint_id)
    except ConstraintError as err:
        raise _map_constraint_error(err) from err
    return {"options": options}


@router.post("/v1/actions/object-sets")
def register_object_set(
    body: ObjectSetRegisterIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#58 · 注册 Object Set（供 object_set 类型约束取选项）。"""
    _ = principal
    eng = get_constraint_engine()
    eng.register_object_set(body.set_id, body.objects)
    log.info("object_set_registered id=%s count=%s", body.set_id, len(body.objects))
    return {"ok": True, "set_id": body.set_id, "count": len(body.objects)}


# ─────────────── #59 参数默认值 ───────────────

class DefaultIn(BaseModel):
    action_id: str
    param_name: str
    source: str  # static / object_property / type_class / environment
    value: Any = None
    fallback: Any = None


class DefaultUpdateIn(BaseModel):
    action_id: str | None = None
    param_name: str | None = None
    source: str | None = None
    value: Any = None
    fallback: Any = None


class ObjectRegisterIn(BaseModel):
    object_type: str
    obj: dict[str, Any]


class ResolveIn(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


@router.get("/v1/actions/parameter-defaults")
def list_defaults(
    action_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#59 · 列出参数默认值。"""
    _ = principal
    eng = get_default_engine()
    items = eng.list(action_id=action_id)
    return {"defaults": [d.model_dump() for d in items], "count": len(items)}


@router.post("/v1/actions/parameter-defaults")
def create_default(
    body: DefaultIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#59 · 创建参数默认值。"""
    _ = principal
    eng = get_default_engine()
    default = ParameterDefault(**body.model_dump())
    try:
        created = eng.create(default)
    except DefaultError as err:
        raise _map_default_error(err) from err
    log.info("default_created id=%s action=%s param=%s source=%s",
             created.id, created.action_id, created.param_name, created.source)
    return created.model_dump()


@router.get("/v1/actions/parameter-defaults/{default_id}")
def get_default(
    default_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#59 · 获取默认值详情。"""
    _ = principal
    eng = get_default_engine()
    try:
        return eng.get(default_id).model_dump()
    except DefaultError as err:
        raise _map_default_error(err) from err


@router.put("/v1/actions/parameter-defaults/{default_id}")
def update_default(
    default_id: str,
    body: DefaultUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#59 · 更新默认值。"""
    _ = principal
    eng = get_default_engine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        updated = eng.update(default_id, updates)
    except DefaultError as err:
        raise _map_default_error(err) from err
    log.info("default_updated id=%s", default_id)
    return updated.model_dump()


@router.delete("/v1/actions/parameter-defaults/{default_id}")
def delete_default(
    default_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#59 · 删除默认值。"""
    _ = principal
    eng = get_default_engine()
    try:
        eng.delete(default_id)
    except DefaultError as err:
        raise _map_default_error(err) from err
    log.info("default_deleted id=%s", default_id)
    return {"ok": True}


@router.post("/v1/actions/parameter-defaults/{default_id}/resolve")
def resolve_default(
    default_id: str,
    body: ResolveIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#59 · 解析默认值（按来源动态求值）。"""
    _ = principal
    eng = get_default_engine()
    try:
        return eng.resolve(default_id, body.context)
    except DefaultError as err:
        raise _map_default_error(err) from err


@router.post("/v1/actions/parameter-default-objects")
def register_default_object(
    body: ObjectRegisterIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#59 · 注册对象供 object_property 来源引用。"""
    _ = principal
    eng = get_default_engine()
    eng.register_object(body.object_type, body.obj)
    log.info("default_object_registered type=%s id=%s",
             body.object_type, body.obj.get("id"))
    return {"ok": True}


# ─────────────── #60 参数覆盖 ───────────────

class OverrideIn(BaseModel):
    action_id: str
    param_name: str
    condition: str
    overrides: dict[str, Any] = Field(default_factory=dict)


class OverrideUpdateIn(BaseModel):
    action_id: str | None = None
    param_name: str | None = None
    condition: str | None = None
    overrides: dict[str, Any] | None = None


class EvaluateIn(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


@router.get("/v1/actions/parameter-overrides")
def list_overrides(
    action_id: str | None = None,
    param_name: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#60 · 列出参数覆盖。"""
    _ = principal
    eng = get_override_engine()
    items = eng.list(action_id=action_id, param_name=param_name)
    return {"overrides": [o.model_dump() for o in items], "count": len(items)}


@router.post("/v1/actions/parameter-overrides")
def create_override(
    body: OverrideIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#60 · 创建参数覆盖。"""
    _ = principal
    eng = get_override_engine()
    override = ParameterOverride(**body.model_dump())
    created = eng.create(override)
    log.info("override_created id=%s action=%s param=%s",
             created.id, created.action_id, created.param_name)
    return created.model_dump()


@router.get("/v1/actions/parameter-overrides/{override_id}")
def get_override(
    override_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#60 · 获取覆盖详情。"""
    _ = principal
    eng = get_override_engine()
    try:
        return eng.get(override_id).model_dump()
    except OverrideError as err:
        raise _map_override_error(err) from err


@router.put("/v1/actions/parameter-overrides/{override_id}")
def update_override(
    override_id: str,
    body: OverrideUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#60 · 更新覆盖。"""
    _ = principal
    eng = get_override_engine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        updated = eng.update(override_id, updates)
    except OverrideError as err:
        raise _map_override_error(err) from err
    log.info("override_updated id=%s", override_id)
    return updated.model_dump()


@router.delete("/v1/actions/parameter-overrides/{override_id}")
def delete_override(
    override_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#60 · 删除覆盖。"""
    _ = principal
    eng = get_override_engine()
    try:
        eng.delete(override_id)
    except OverrideError as err:
        raise _map_override_error(err) from err
    log.info("override_deleted id=%s", override_id)
    return {"ok": True}


@router.post("/v1/actions/parameter-overrides/evaluate")
def evaluate_overrides(
    body: EvaluateIn,
    action_id: str,
    param_name: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#60 · 评估参数的覆盖状态（合并所有匹配块）。"""
    _ = principal
    eng = get_override_engine()
    return eng.evaluate(action_id, param_name, body.context)
