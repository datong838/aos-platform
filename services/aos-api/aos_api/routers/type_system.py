"""W2-O · 类型系统与视图配置路由：完整类型系统 + 视图配置 + 条件格式化."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.type_system import (
    ConditionalFormat,
    FormatError,
    TypeClass,
    TypeDefinition,
    TypeError_,
    ViewProfile,
    ViewTab,
    get_format_engine,
    get_type_system,
    get_view_profile_engine,
)

router = APIRouter(tags=["type-system"])
log = get_logger("aos-api.type-system")


def _map_type_error(err: TypeError_, status: int = 400) -> ApiError:
    if err.code == "TYPE_NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_vp_error(err: Exception, status: int = 400) -> ApiError:
    code = getattr(err, "code", "INTERNAL")
    msg = getattr(err, "message", str(err))
    if code == "NOT_FOUND":
        status = 404
    return ApiError(code=code, message=msg, status_code=status)


def _map_fmt_error(err: FormatError, status: int = 400) -> ApiError:
    if err.code in ("NOT_FOUND", "TYPE_CLASS_NOT_FOUND"):
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ─────────────── #52 完整类型系统 ───────────────

class TypeDefIn(BaseModel):
    name: str = Field(min_length=1)
    category: str = "scalar"
    base_type: str = "str"
    description: str = ""
    validators: list[str] = Field(default_factory=list)


class ValidateRequest(BaseModel):
    type_name: str
    value: Any


class CoerceRequest(BaseModel):
    type_name: str
    value: Any


@router.get("/v1/ontology/types")
def list_types(
    category: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#52 · 列出所有类型。"""
    _ = principal
    types = get_type_system().list_types(category=category)
    return {"items": [t.model_dump() for t in types], "count": len(types)}


@router.post("/v1/ontology/types")
def register_type(
    body: TypeDefIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#52 · 注册自定义类型。"""
    _ = principal
    td = get_type_system().register_type(TypeDefinition(**body.model_dump()))
    log.info("type_registered name=%s category=%s", td.name, td.category)
    return td.model_dump()


@router.get("/v1/ontology/types/{name}")
def get_type(
    name: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#52 · 获取类型详情。"""
    _ = principal
    try:
        return get_type_system().get_type(name).model_dump()
    except TypeError_ as err:
        raise _map_type_error(err) from err


@router.post("/v1/ontology/types/validate")
def validate_value(
    body: ValidateRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#52 · 验证值是否符合类型。"""
    _ = principal
    try:
        valid = get_type_system().validate(body.type_name, body.value)
        return {"type_name": body.type_name, "value": body.value, "valid": valid}
    except TypeError_ as err:
        raise _map_type_error(err) from err


@router.post("/v1/ontology/types/coerce")
def coerce_value(
    body: CoerceRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#52 · 强制转换值到类型。"""
    _ = principal
    try:
        coerced = get_type_system().coerce(body.type_name, body.value)
        return {"type_name": body.type_name, "original": body.value, "coerced": coerced}
    except TypeError_ as err:
        raise _map_type_error(err) from err


# ─────────────── #51 Object Views 配置文件 ───────────────

class ViewTabIn(BaseModel):
    name: str = Field(min_length=1)
    widgets: list[str] = Field(default_factory=list)
    visible: bool = True


class ViewProfileIn(BaseModel):
    name: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    user_groups: list[str] = Field(default_factory=list)
    tabs: list[ViewTabIn] = Field(default_factory=list)
    is_default: bool = False


class ViewProfileUpdateIn(BaseModel):
    name: str | None = None
    user_groups: list[str] | None = None
    tabs: list[ViewTabIn] | None = None
    is_default: bool | None = None


class ActivateRequest(BaseModel):
    user_group: str = Field(min_length=1)


@router.get("/v1/ontology/view-profiles")
def list_view_profiles(
    object_type: str | None = None,
    user_group: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#51 · 列出视图配置。"""
    _ = principal
    items = get_view_profile_engine().list(object_type=object_type, user_group=user_group)
    return {"items": [p.model_dump() for p in items], "count": len(items)}


@router.post("/v1/ontology/view-profiles")
def create_view_profile(
    body: ViewProfileIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#51 · 创建视图配置。"""
    _ = principal
    profile = ViewProfile(
        name=body.name,
        object_type=body.object_type,
        user_groups=body.user_groups,
        tabs=[ViewTab(**t.model_dump()) for t in body.tabs],
        is_default=body.is_default,
    )
    get_view_profile_engine().create(profile)
    log.info("view_profile_created id=%s ot=%s", profile.id, profile.object_type)
    return profile.model_dump()


@router.get("/v1/ontology/view-profiles/{profile_id}")
def get_view_profile(
    profile_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#51 · 获取视图配置。"""
    _ = principal
    try:
        return get_view_profile_engine().get(profile_id).model_dump()
    except Exception as err:
        raise _map_vp_error(err) from err


@router.put("/v1/ontology/view-profiles/{profile_id}")
def update_view_profile(
    profile_id: str,
    body: ViewProfileUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#51 · 更新视图配置。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "tabs" in updates and updates["tabs"] is not None:
        updates["tabs"] = [ViewTab(**t) for t in updates["tabs"]]
    try:
        profile = get_view_profile_engine().update(profile_id, updates)
        log.info("view_profile_updated id=%s", profile_id)
        return profile.model_dump()
    except Exception as err:
        raise _map_vp_error(err) from err


@router.delete("/v1/ontology/view-profiles/{profile_id}")
def delete_view_profile(
    profile_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#51 · 删除视图配置。"""
    _ = principal
    try:
        get_view_profile_engine().delete(profile_id)
        log.info("view_profile_deleted id=%s", profile_id)
        return {"deleted": True, "id": profile_id}
    except Exception as err:
        raise _map_vp_error(err) from err


@router.post("/v1/ontology/view-profiles/{profile_id}/activate")
def activate_view_profile(
    profile_id: str,
    body: ActivateRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#51 · 为用户组激活配置。"""
    _ = principal
    try:
        profile = get_view_profile_engine().activate(profile_id, body.user_group)
        log.info("view_profile_activated id=%s group=%s", profile_id, body.user_group)
        return {"activated": True, "profile_id": profile_id, "user_group": body.user_group}
    except Exception as err:
        raise _map_vp_error(err) from err


@router.get("/v1/ontology/view-profiles/active/{object_type}")
def get_active_view_profile(
    object_type: str,
    user_group: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#51 · 获取指定用户组的激活配置。"""
    _ = principal
    profile = get_view_profile_engine().get_active(object_type, user_group)
    if profile is None:
        return {"object_type": object_type, "user_group": user_group, "profile": None}
    return {"object_type": object_type, "user_group": user_group, "profile": profile.model_dump()}


# ─────────────── #53 值类型/条件格式化/类型类 ───────────────

class TypeClassIn(BaseModel):
    name: str = Field(min_length=1)
    base_type: str = "String"
    description: str = ""
    render_hint: str = ""


class ConditionalFormatIn(BaseModel):
    object_type: str = Field(min_length=1)
    field: str = Field(min_length=1)
    condition: str = Field(min_length=1)
    style: dict[str, Any] = Field(default_factory=dict)


class RenderRequest(BaseModel):
    type_class: str
    value: Any


class EvaluateFormatRequest(BaseModel):
    value: Any


@router.get("/v1/ontology/type-classes")
def list_type_classes(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#53 · 列出所有类型类。"""
    _ = principal
    items = get_format_engine().list_type_classes()
    return {"items": [t.model_dump() for t in items], "count": len(items)}


@router.post("/v1/ontology/type-classes")
def register_type_class(
    body: TypeClassIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#53 · 注册类型类。"""
    _ = principal
    tc = get_format_engine().register_type_class(TypeClass(**body.model_dump()))
    log.info("type_class_registered name=%s", tc.name)
    return tc.model_dump()


@router.get("/v1/ontology/type-classes/{name}")
def get_type_class(
    name: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#53 · 获取类型类详情。"""
    _ = principal
    try:
        return get_format_engine().get_type_class(name).model_dump()
    except FormatError as err:
        raise _map_fmt_error(err) from err


@router.post("/v1/ontology/type-classes/render")
def render_value(
    body: RenderRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#53 · 渲染值。"""
    _ = principal
    try:
        return get_format_engine().render(body.type_class, body.value)
    except FormatError as err:
        raise _map_fmt_error(err) from err


@router.post("/v1/ontology/conditional-formats")
def create_conditional_format(
    body: ConditionalFormatIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#53 · 创建条件格式。"""
    _ = principal
    cf = ConditionalFormat(**body.model_dump())
    get_format_engine().add_conditional_format(cf)
    log.info("conditional_format_created id=%s ot=%s field=%s", cf.id, cf.object_type, cf.field)
    return cf.model_dump()


@router.get("/v1/ontology/conditional-formats")
def list_conditional_formats(
    object_type: str | None = None,
    field: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#53 · 列出条件格式。"""
    _ = principal
    items = get_format_engine().list_conditional_formats(object_type=object_type, field=field)
    return {"items": [c.model_dump() for c in items], "count": len(items)}


@router.get("/v1/ontology/conditional-formats/{cf_id}")
def get_conditional_format(
    cf_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#53 · 获取条件格式。"""
    _ = principal
    try:
        return get_format_engine().get_conditional_format(cf_id).model_dump()
    except FormatError as err:
        raise _map_fmt_error(err) from err


@router.delete("/v1/ontology/conditional-formats/{cf_id}")
def delete_conditional_format(
    cf_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#53 · 删除条件格式。"""
    _ = principal
    try:
        get_format_engine().delete_conditional_format(cf_id)
        log.info("conditional_format_deleted id=%s", cf_id)
        return {"deleted": True, "id": cf_id}
    except FormatError as err:
        raise _map_fmt_error(err) from err


@router.post("/v1/ontology/conditional-formats/{cf_id}/evaluate")
def evaluate_conditional_format(
    cf_id: str,
    body: EvaluateFormatRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#53 · 评估条件格式是否匹配。"""
    _ = principal
    try:
        return get_format_engine().evaluate(cf_id, body.value)
    except FormatError as err:
        raise _map_fmt_error(err) from err
