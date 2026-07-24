"""W2-M · Object Explorer 增强路由：高级搜索 + 保存探索 + 批量导出."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.oe_enhancements import (
    ExportError,
    ExplorationError,
    SavedExploration,
    SearchError,
    get_exploration_engine,
    get_export_engine,
    get_search_engine,
)

router = APIRouter(tags=["oe-enhancements"])
log = get_logger("aos-api.oe-enhancements")


def _map_search_error(err: SearchError, status: int = 400) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_exp_error(err: ExplorationError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    elif err.code == "NOT_DYNAMIC":
        status = 409
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_export_error(err: ExportError, status: int = 400) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=status)


# ─────────────── #48 高级搜索 ───────────────

class IndexRequest(BaseModel):
    object_type: str = Field(min_length=1)
    objects: list[dict[str, Any]] = Field(default_factory=list)


class AddLinkRequest(BaseModel):
    src_id: str
    dst_id: str
    dst_obj: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    object_type: str = Field(min_length=1)
    expression: str = Field(min_length=1)
    limit: int = 100
    offset: int = 0


@router.post("/v1/ontology/object-explorer/index")
def index_objects(
    body: IndexRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#48 · 索引对象供搜索（测试/管理用）。"""
    _ = principal
    get_search_engine().index(body.object_type, body.objects)
    log.info("oe_indexed ot=%s count=%s", body.object_type, len(body.objects))
    return {"indexed": True, "object_type": body.object_type, "count": len(body.objects)}


@router.post("/v1/ontology/object-explorer/links")
def add_link(
    body: AddLinkRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#48 · 添加链接关系（供 LINKS 筛选用）。"""
    _ = principal
    get_search_engine().add_link(body.src_id, body.dst_id, body.dst_obj)
    return {"added": True, "src_id": body.src_id, "dst_id": body.dst_id}


@router.post("/v1/ontology/object-explorer/search")
def search_objects(
    body: SearchRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#48 · 高级搜索。"""
    _ = principal
    try:
        result = get_search_engine().search(
            body.object_type, body.expression,
            limit=body.limit, offset=body.offset,
        )
        log.info("oe_search ot=%s total=%s", body.object_type, result["total"])
        return result
    except SearchError as err:
        raise _map_search_error(err) from err


# ─────────────── #49 保存探索 ───────────────

class ExplorationIn(BaseModel):
    name: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    kind: str = "dynamic"
    visibility: str = "private"
    owner: str = ""
    query: dict[str, Any] = Field(default_factory=dict)
    object_ids: list[str] = Field(default_factory=list)


class ExplorationUpdateIn(BaseModel):
    name: str | None = None
    kind: str | None = None
    visibility: str | None = None
    query: dict[str, Any] | None = None
    object_ids: list[str] | None = None


@router.get("/v1/ontology/explorations")
def list_explorations(
    owner: str | None = None,
    object_type: str | None = None,
    kind: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#49 · 列出保存的探索。"""
    _ = principal
    items = get_exploration_engine().list(
        owner=owner, object_type=object_type, kind=kind,
    )
    return {"items": [e.model_dump() for e in items], "count": len(items)}


@router.post("/v1/ontology/explorations")
def create_exploration(
    body: ExplorationIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#49 · 创建保存的探索。"""
    _ = principal
    exp = SavedExploration(**body.model_dump())
    get_exploration_engine().create(exp)
    log.info("exploration_created id=%s name=%s kind=%s", exp.id, exp.name, exp.kind)
    return exp.model_dump()


@router.get("/v1/ontology/explorations/{exp_id}")
def get_exploration(
    exp_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#49 · 获取探索详情。"""
    _ = principal
    try:
        return get_exploration_engine().get(exp_id).model_dump()
    except ExplorationError as err:
        raise _map_exp_error(err) from err


@router.put("/v1/ontology/explorations/{exp_id}")
def update_exploration(
    exp_id: str,
    body: ExplorationUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#49 · 更新探索。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        exp = get_exploration_engine().update(exp_id, updates)
        log.info("exploration_updated id=%s", exp_id)
        return exp.model_dump()
    except ExplorationError as err:
        raise _map_exp_error(err) from err


@router.delete("/v1/ontology/explorations/{exp_id}")
def delete_exploration(
    exp_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#49 · 删除探索。"""
    _ = principal
    try:
        get_exploration_engine().delete(exp_id)
        log.info("exploration_deleted id=%s", exp_id)
        return {"deleted": True, "id": exp_id}
    except ExplorationError as err:
        raise _map_exp_error(err) from err


@router.post("/v1/ontology/explorations/{exp_id}/execute")
def execute_exploration(
    exp_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#49 · 执行动态探索。"""
    _ = principal
    try:
        result = get_exploration_engine().execute(exp_id, get_search_engine())
        log.info("exploration_executed id=%s total=%s", exp_id, result["total"])
        return result
    except ExplorationError as err:
        raise _map_exp_error(err) from err
    except SearchError as err:
        raise _map_search_error(err) from err


# ─────────────── #50 批量导出 ───────────────

class ExportRequest(BaseModel):
    object_type: str = Field(min_length=1)
    objects: list[dict[str, Any]] = Field(default_factory=list)
    fmt: str = "csv"
    columns: list[str] = Field(default_factory=list)
    object_ids: list[str] = Field(default_factory=list)


class BulkUpdateRequest(BaseModel):
    objects: list[dict[str, Any]] = Field(default_factory=list)
    updates: dict[str, Any] = Field(default_factory=dict)
    object_ids: list[str] = Field(default_factory=list)


class BulkDeleteRequest(BaseModel):
    objects: list[dict[str, Any]] = Field(default_factory=list)
    object_ids: list[str] = Field(default_factory=list)


@router.post("/v1/ontology/object-explorer/export")
def export_objects(
    body: ExportRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#50 · 导出对象数据。"""
    _ = principal
    try:
        result = get_export_engine().export(
            body.object_type, body.objects,
            fmt=body.fmt,
            columns=body.columns or None,
            object_ids=body.object_ids or None,
        )
        log.info("oe_export ot=%s fmt=%s rows=%s", body.object_type, body.fmt, result["total_rows"])
        return result
    except ExportError as err:
        raise _map_export_error(err) from err


@router.post("/v1/ontology/object-explorer/bulk-update")
def bulk_update(
    body: BulkUpdateRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#50 · 批量更新对象。"""
    _ = principal
    result = get_export_engine().bulk_update(
        body.objects, body.updates,
        object_ids=body.object_ids or None,
    )
    log.info("oe_bulk_update updated=%s", result["updated"])
    return result


@router.post("/v1/ontology/object-explorer/bulk-delete")
def bulk_delete(
    body: BulkDeleteRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#50 · 批量删除对象。"""
    _ = principal
    result = get_export_engine().bulk_delete(
        body.objects,
        object_ids=body.object_ids or None,
    )
    log.info("oe_bulk_delete deleted=%s remaining=%s", result["deleted"], result["remaining"])
    return result
