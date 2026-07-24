"""W2-L · Object 数据层增强路由：Shared Property + Type Coherence + L1 Join + Computed Property."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.ontology_data_layer import (
    ComputedProperty,
    L1JoinConfig,
    L1JoinError,
    JoinSpec,
    SharedProperty,
    SharedPropertyError,
    get_l1_engine,
    get_sp_engine,
    get_tc_engine,
)

router = APIRouter(tags=["ontology-data-layer"])
log = get_logger("aos-api.ontology-data-layer")


def _map_sp_error(err: SharedPropertyError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    elif err.code == "STILL_REFERENCED":
        status = 409
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_l1_error(err: L1JoinError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ─────────────── #33 Shared Property ───────────────

class SharedPropertyIn(BaseModel):
    name: str = Field(min_length=1)
    data_type: str = "string"
    description: str = ""
    backing_column: str = ""
    nullable: bool = True


class SharedPropertyUpdateIn(BaseModel):
    name: str | None = None
    data_type: str | None = None
    description: str | None = None
    backing_column: str | None = None
    nullable: bool | None = None


class AttachRequest(BaseModel):
    object_type: str = Field(min_length=1)


@router.get("/v1/ontology/shared-properties")
def list_shared_properties(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#33 · 列出共享属性。"""
    _ = principal
    props = get_sp_engine().list()
    return {"items": [p.model_dump() for p in props], "count": len(props)}


@router.post("/v1/ontology/shared-properties")
def create_shared_property(
    body: SharedPropertyIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#33 · 创建共享属性。"""
    _ = principal
    prop = SharedProperty(**body.model_dump())
    get_sp_engine().create(prop)
    log.info("shared_property_created id=%s name=%s", prop.id, prop.name)
    return prop.model_dump()


@router.get("/v1/ontology/shared-properties/{prop_id}")
def get_shared_property(
    prop_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#33 · 获取共享属性详情。"""
    _ = principal
    try:
        return get_sp_engine().get(prop_id).model_dump()
    except SharedPropertyError as err:
        raise _map_sp_error(err) from err


@router.put("/v1/ontology/shared-properties/{prop_id}")
def update_shared_property(
    prop_id: str,
    body: SharedPropertyUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#33 · 更新共享属性。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        prop = get_sp_engine().update(prop_id, updates)
        log.info("shared_property_updated id=%s", prop_id)
        return prop.model_dump()
    except SharedPropertyError as err:
        raise _map_sp_error(err) from err


@router.delete("/v1/ontology/shared-properties/{prop_id}")
def delete_shared_property(
    prop_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#33 · 删除共享属性（被引用时禁止）。"""
    _ = principal
    try:
        get_sp_engine().delete(prop_id)
        log.info("shared_property_deleted id=%s", prop_id)
        return {"deleted": True, "id": prop_id}
    except SharedPropertyError as err:
        raise _map_sp_error(err) from err


@router.post("/v1/ontology/shared-properties/{prop_id}/attach")
def attach_shared_property(
    prop_id: str,
    body: AttachRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#33 · 绑定共享属性到 Object Type。"""
    _ = principal
    try:
        prop = get_sp_engine().attach(prop_id, body.object_type)
        log.info("shared_property_attached id=%s ot=%s", prop_id, body.object_type)
        return prop.model_dump()
    except SharedPropertyError as err:
        raise _map_sp_error(err) from err


@router.post("/v1/ontology/shared-properties/{prop_id}/detach")
def detach_shared_property(
    prop_id: str,
    body: AttachRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#33 · 从 Object Type 解绑共享属性。"""
    _ = principal
    try:
        prop = get_sp_engine().detach(prop_id, body.object_type)
        log.info("shared_property_detached id=%s ot=%s", prop_id, body.object_type)
        return prop.model_dump()
    except SharedPropertyError as err:
        raise _map_sp_error(err) from err


# ─────────────── #29 Type Coherence ───────────────

class SchemaPropertyIn(BaseModel):
    name: str
    data_type: str = "string"
    backing_column: str = ""
    nullable: bool = True


class DatasetColumnIn(BaseModel):
    name: str
    data_type: str = "string"
    nullable: bool = True


class RegisterSchemaIn(BaseModel):
    object_type: str = Field(min_length=1)
    properties: list[SchemaPropertyIn] = Field(default_factory=list)
    dataset_columns: list[DatasetColumnIn] = Field(default_factory=list)


class CheckOneIn(BaseModel):
    object_type: str = Field(min_length=1)


@router.post("/v1/ontology/type-coherence/schemas")
def register_schema(
    body: RegisterSchemaIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#29 · 注册 OT 的 schema 快照（properties + dataset columns）。"""
    _ = principal
    get_tc_engine().register_schema(
        body.object_type,
        properties=[p.model_dump() for p in body.properties],
        dataset_columns=[c.model_dump() for c in body.dataset_columns],
    )
    log.info("schema_registered ot=%s props=%s cols=%s",
             body.object_type, len(body.properties), len(body.dataset_columns))
    return {
        "registered": True,
        "object_type": body.object_type,
        "properties": len(body.properties),
        "dataset_columns": len(body.dataset_columns),
    }


@router.post("/v1/ontology/type-coherence/check")
def check_coherence(
    body: CheckOneIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#29 · 检查指定 OT 的 Schema 一致性。"""
    _ = principal
    conflicts = get_tc_engine().check(body.object_type)
    return {
        "object_type": body.object_type,
        "conflicts": [c.model_dump() for c in conflicts],
        "count": len(conflicts),
    }


@router.get("/v1/ontology/type-coherence/conflicts")
def list_all_conflicts(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#29 · 列出所有 OT 的冲突。"""
    _ = principal
    conflicts = get_tc_engine().check_all()
    return {
        "conflicts": [c.model_dump() for c in conflicts],
        "count": len(conflicts),
    }


# ─────────────── #30 L1 Join + Computed Property ───────────────

class JoinSpecIn(BaseModel):
    dataset: str = Field(min_length=1)
    join_type: str = "left"
    left_key: str
    right_key: str
    columns: list[str] = Field(default_factory=list)


class L1JoinIn(BaseModel):
    object_type: str = Field(min_length=1)
    primary_dataset: str = Field(min_length=1)
    primary_key: str
    joins: list[JoinSpecIn] = Field(default_factory=list)


class ComputedPropertyIn(BaseModel):
    object_type: str = Field(min_length=1)
    property_name: str = Field(min_length=1)
    function_name: str = Field(min_length=1)
    input_mapping: dict[str, str] = Field(default_factory=dict)
    output_type: str = "string"


@router.post("/v1/ontology/l1-joins")
def create_l1_join(
    body: L1JoinIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#30 · 解法 A：创建 L1 Join 宽表配置。"""
    _ = principal
    config = L1JoinConfig(
        object_type=body.object_type,
        primary_dataset=body.primary_dataset,
        primary_key=body.primary_key,
        joins=[JoinSpec(**j.model_dump()) for j in body.joins],
    )
    get_l1_engine().create_join(config)
    log.info("l1_join_created id=%s ot=%s joins=%s", config.id, config.object_type, len(config.joins))
    return config.model_dump()


@router.get("/v1/ontology/l1-joins")
def list_l1_joins(
    object_type: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#30 · 列出 L1 Join 配置。"""
    _ = principal
    joins = get_l1_engine().list_joins(object_type=object_type)
    return {"items": [j.model_dump() for j in joins], "count": len(joins)}


@router.get("/v1/ontology/l1-joins/{join_id}")
def get_l1_join(
    join_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#30 · 获取 L1 Join 配置详情。"""
    _ = principal
    try:
        return get_l1_engine().get_join(join_id).model_dump()
    except L1JoinError as err:
        raise _map_l1_error(err) from err


@router.post("/v1/ontology/l1-joins/{join_id}/preview")
def preview_l1_join(
    join_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#30 · 预览 join 结果列。"""
    _ = principal
    try:
        return get_l1_engine().preview_join(join_id)
    except L1JoinError as err:
        raise _map_l1_error(err) from err


@router.delete("/v1/ontology/l1-joins/{join_id}")
def delete_l1_join(
    join_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#30 · 删除 L1 Join 配置。"""
    _ = principal
    try:
        get_l1_engine().delete_join(join_id)
        log.info("l1_join_deleted id=%s", join_id)
        return {"deleted": True, "id": join_id}
    except L1JoinError as err:
        raise _map_l1_error(err) from err


@router.post("/v1/ontology/computed-properties")
def create_computed_property(
    body: ComputedPropertyIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#30 · 解法 C：创建计算属性。"""
    _ = principal
    prop = ComputedProperty(**body.model_dump())
    get_l1_engine().create_computed(prop)
    log.info("computed_property_created id=%s ot=%s name=%s",
             prop.id, prop.object_type, prop.property_name)
    return prop.model_dump()


@router.get("/v1/ontology/computed-properties")
def list_computed_properties(
    object_type: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#30 · 列出计算属性。"""
    _ = principal
    props = get_l1_engine().list_computed(object_type=object_type)
    return {"items": [p.model_dump() for p in props], "count": len(props)}


@router.get("/v1/ontology/computed-properties/{prop_id}")
def get_computed_property(
    prop_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#30 · 获取计算属性详情。"""
    _ = principal
    try:
        return get_l1_engine().get_computed(prop_id).model_dump()
    except L1JoinError as err:
        raise _map_l1_error(err) from err


@router.delete("/v1/ontology/computed-properties/{prop_id}")
def delete_computed_property(
    prop_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#30 · 删除计算属性。"""
    _ = principal
    try:
        get_l1_engine().delete_computed(prop_id)
        log.info("computed_property_deleted id=%s", prop_id)
        return {"deleted": True, "id": prop_id}
    except L1JoinError as err:
        raise _map_l1_error(err) from err
