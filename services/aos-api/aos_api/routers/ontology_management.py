"""W2-K · Ontology 管理增强路由：Edit History + Cleanup + Interface."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.ontology_management import (
    CleanupItem,
    EditEvent,
    InterfaceError,
    OntologyInterface,
    get_cleanup_engine,
    get_edit_engine,
    get_iface_engine,
)

router = APIRouter(tags=["ontology-management"])
log = get_logger("aos-api.ontology-management")


# ─────────────── #36 Edit History ───────────────

class EditEventIn(BaseModel):
    target_type: str
    target_id: str
    action: str
    author: str = ""
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class RollbackByAuthorIn(BaseModel):
    author: str


@router.get("/v1/ontology/edit-history")
def list_edit_history(
    target_type: str | None = None,
    author: str | None = None,
    target_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#36 · 全局编辑时间线。"""
    _ = principal
    eng = get_edit_engine()
    events = eng.list(target_type=target_type, author=author, target_id=target_id)
    return {"events": [e.model_dump() for e in events], "count": len(events)}


@router.post("/v1/ontology/edit-history")
def record_edit_event(
    body: EditEventIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#36 · 记录编辑事件。"""
    _ = principal
    eng = get_edit_engine()
    event = EditEvent(**body.model_dump())
    eng.record(event)
    log.info("edit_event_recorded id=%s target=%s/%s action=%s",
             event.id, event.target_type, event.target_id, event.action)
    return event.model_dump()


@router.get("/v1/ontology/edit-history/{event_id}")
def get_edit_event(
    event_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#36 · 获取事件详情。"""
    _ = principal
    eng = get_edit_engine()
    try:
        return eng.get(event_id).model_dump()
    except KeyError as err:
        raise ApiError(code="NOT_FOUND", message=str(err), status_code=404) from err


@router.post("/v1/ontology/edit-history/{event_id}/rollback")
def rollback_event(
    event_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#36 · 回退单个事件。"""
    _ = principal
    eng = get_edit_engine()
    try:
        event = eng.rollback(event_id)
    except KeyError as err:
        raise ApiError(code="NOT_FOUND", message=str(err), status_code=404) from err
    log.info("edit_event_rolled_back id=%s", event_id)
    return event.model_dump()


@router.post("/v1/ontology/edit-history/rollback-by-author")
def rollback_by_author(
    body: RollbackByAuthorIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#36 · 按作者批量回退。"""
    _ = principal
    eng = get_edit_engine()
    rolled = eng.rollback_by_author(body.author)
    log.info("rollback_by_author author=%s count=%s", body.author, len(rolled))
    return {"rolledBack": len(rolled), "events": [e.model_dump() for e in rolled]}


@router.get("/v1/ontology/edit-history/timeline")
def edit_timeline(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#36 · 按作者合并的时间线视图。"""
    _ = principal
    eng = get_edit_engine()
    return {"timeline": eng.timeline_merged_by_author()}


# ─────────────── #37 Cleanup ───────────────

class CleanupRegisterIn(BaseModel):
    resource_type: str
    resource_id: str
    name: str
    description: str = ""
    updated_at: str = ""
    deprecated_date: str | None = None
    is_recycle_bin: bool = False
    is_indexed: bool = True


class CleanupApplyIn(BaseModel):
    resource_type: str
    resource_id: str
    action: str  # delay / deprecate / delete


class CleanupBatchIn(BaseModel):
    tag: str | None = None
    action: str = "delay"


@router.get("/v1/ontology/cleanup/scan")
def cleanup_scan(
    tags: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#37 · 扫描并返回带清理标记的资源。"""
    _ = principal
    eng = get_cleanup_engine()
    tag_list = tags.split(",") if tags else None
    items = eng.scan(tags=tag_list)
    return {"items": [i.model_dump() for i in items], "count": len(items)}


@router.post("/v1/ontology/cleanup/register")
def cleanup_register(
    body: CleanupRegisterIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#37 · 注册资源到清理扫描池。"""
    _ = principal
    eng = get_cleanup_engine()
    item = CleanupItem(**body.model_dump())
    eng.register(item)
    return item.model_dump()


@router.post("/v1/ontology/cleanup/apply")
def cleanup_apply(
    body: CleanupApplyIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#37 · 对指定资源执行延迟/弃用/删除。"""
    _ = principal
    eng = get_cleanup_engine()
    try:
        item = eng.apply(body.resource_type, body.resource_id, body.action)
    except KeyError as err:
        raise ApiError(code="NOT_FOUND", message=str(err), status_code=404) from err
    except ValueError as err:
        raise ApiError(code="VALIDATION", message=str(err), status_code=400) from err
    log.info("cleanup_apply %s/%s action=%s", body.resource_type, body.resource_id, body.action)
    return item.model_dump() if body.action != "delete" else {"ok": True, "deleted": body.resource_id}


@router.post("/v1/ontology/cleanup/batch")
def cleanup_batch(
    body: CleanupBatchIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#37 · 批量操作（按标记筛选）。"""
    _ = principal
    eng = get_cleanup_engine()
    results = eng.batch_apply(tag=body.tag, action=body.action)
    log.info("cleanup_batch tag=%s action=%s count=%s", body.tag, body.action, len(results))
    return {"applied": len(results), "items": [r.model_dump() for r in results]}


# ─────────────── #32 Interface ───────────────

class InterfaceCreateIn(BaseModel):
    name: str
    description: str = ""
    properties: list[dict[str, Any]] = Field(default_factory=list)
    extends: list[str] = Field(default_factory=list)
    owner: str = ""


class InterfaceUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    properties: list[dict[str, Any]] | None = None
    extends: list[str] | None = None
    owner: str | None = None
    version: int | None = None


class ImplementIn(BaseModel):
    object_type: str


def _map_iface_error(err: InterfaceError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


@router.get("/v1/ontology/interfaces")
def list_interfaces(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#32 · 列出接口。"""
    _ = principal
    eng = get_iface_engine()
    ifaces = eng.list()
    return {"interfaces": [i.model_dump() for i in ifaces], "count": len(ifaces)}


@router.post("/v1/ontology/interfaces")
def create_interface(
    body: InterfaceCreateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#32 · 创建接口。"""
    _ = principal
    eng = get_iface_engine()
    iface = OntologyInterface(**body.model_dump())
    try:
        created = eng.create(iface)
    except InterfaceError as err:
        raise _map_iface_error(err) from err
    log.info("interface_created id=%s name=%s", created.id, created.name)
    return created.model_dump()


@router.get("/v1/ontology/interfaces/{interface_id}")
def get_interface(
    interface_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#32 · 获取接口详情。"""
    _ = principal
    eng = get_iface_engine()
    try:
        iface = eng.get(interface_id)
    except InterfaceError as err:
        raise _map_iface_error(err) from err
    result = iface.model_dump()
    result["effectiveProperties"] = eng.get_effective_properties(interface_id)
    return result


@router.put("/v1/ontology/interfaces/{interface_id}")
def update_interface(
    interface_id: str,
    body: InterfaceUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#32 · 更新接口。"""
    _ = principal
    eng = get_iface_engine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        updated = eng.update(interface_id, updates)
    except InterfaceError as err:
        raise _map_iface_error(err) from err
    log.info("interface_updated id=%s", interface_id)
    return updated.model_dump()


@router.delete("/v1/ontology/interfaces/{interface_id}")
def delete_interface(
    interface_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#32 · 删除接口。"""
    _ = principal
    eng = get_iface_engine()
    try:
        eng.delete(interface_id)
    except InterfaceError as err:
        raise _map_iface_error(err) from err
    log.info("interface_deleted id=%s", interface_id)
    return {"ok": True}


@router.post("/v1/ontology/interfaces/{interface_id}/implement")
def implement_interface(
    interface_id: str,
    body: ImplementIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#32 · Object Type 声明实现接口。"""
    _ = principal
    eng = get_iface_engine()
    try:
        iface = eng.implement(interface_id, body.object_type)
    except InterfaceError as err:
        raise _map_iface_error(err) from err
    log.info("interface_implemented id=%s by=%s", interface_id, body.object_type)
    return iface.model_dump()


@router.get("/v1/ontology/interfaces/{interface_id}/implementors")
def list_implementors(
    interface_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#32 · 列出实现者。"""
    _ = principal
    eng = get_iface_engine()
    try:
        impls = eng.get_implementors(interface_id)
    except InterfaceError as err:
        raise _map_iface_error(err) from err
    return {"interfaceId": interface_id, "implementors": impls}
