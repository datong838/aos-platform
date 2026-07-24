"""W2-AA · 触发器与 Ontology 链接输出组路由：#97 事件触发器 + #98 复合触发器 + #91 链接类型输出."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.triggers_and_link_output import (
    CompositeTrigger,
    EventTrigger,
    LinkTypeDefinition,
    TriggersAndLinkOutputError,
    get_composite_trigger_engine,
    get_event_trigger_engine,
    get_link_type_output_engine,
)

router = APIRouter(tags=["triggers-and-link-output"])
log = get_logger("aos-api.triggers-and-link-output")


def _map_err(err: TriggersAndLinkOutputError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #97 Event Trigger ════════════════════

class EventTriggerIn(BaseModel):
    name: str = Field(min_length=1)
    event_source: str = Field(min_length=1)
    target_pipeline_id: str = Field(min_length=1)
    source_ref: str = ""
    condition: str = ""
    enabled: bool = True
    cooldown_seconds: float = 0.0


class EventTriggerUpdateIn(BaseModel):
    name: str | None = None
    event_source: str | None = None
    target_pipeline_id: str | None = None
    source_ref: str | None = None
    condition: str | None = None
    enabled: bool | None = None
    cooldown_seconds: float | None = None


class FireIn(BaseModel):
    event_payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/v1/pipeline-triggers/events")
def register_event_trigger(
    body: EventTriggerIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 注册事件触发器。"""
    _ = principal
    try:
        t = get_event_trigger_engine().register(EventTrigger(**body.model_dump()))
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc
    return {"item": t.model_dump()}


@router.get("/v1/pipeline-triggers/events")
def list_event_triggers(
    event_source: str | None = None,
    enabled_only: bool = False,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 事件触发器列表。"""
    _ = principal
    items = get_event_trigger_engine().list(
        event_source=event_source, enabled_only=enabled_only,
    )
    return {"items": [t.model_dump() for t in items], "count": len(items)}


@router.get("/v1/pipeline-triggers/events/{trigger_id}")
def get_event_trigger(
    trigger_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 单条事件触发器。"""
    _ = principal
    try:
        return {"item": get_event_trigger_engine().get(trigger_id).model_dump()}
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/pipeline-triggers/events/{trigger_id}")
def update_event_trigger(
    trigger_id: str,
    body: EventTriggerUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 更新事件触发器。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        t = get_event_trigger_engine().update(trigger_id, updates)
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc
    return {"item": t.model_dump()}


@router.delete("/v1/pipeline-triggers/events/{trigger_id}")
def delete_event_trigger(
    trigger_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 删除事件触发器。"""
    _ = principal
    ok = get_event_trigger_engine().delete(trigger_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"触发器 {trigger_id} 不存在", status_code=404)
    return {"id": trigger_id, "deleted": True}


@router.post("/v1/pipeline-triggers/events/{trigger_id}/fire")
def fire_event_trigger(
    trigger_id: str,
    body: FireIn | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 点火事件触发器。"""
    _ = principal
    payload = body.event_payload if body else {}
    try:
        f = get_event_trigger_engine().fire(trigger_id, payload)
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc
    return {"item": f.model_dump()}


@router.get("/v1/pipeline-triggers/events-fires")
def list_event_fires(
    trigger_id: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 点火记录列表。"""
    _ = principal
    items = get_event_trigger_engine().list_fires(trigger_id=trigger_id, limit=limit)
    return {"items": [f.model_dump() for f in items], "count": len(items)}


# ════════════════════ #98 Composite Trigger ════════════════════

class CompositeTriggerIn(BaseModel):
    name: str = Field(min_length=1)
    logic: str = Field(min_length=1)
    child_trigger_ids: list[str] = Field(min_length=1)
    target_pipeline_id: str = Field(min_length=1)
    enabled: bool = True
    cooldown_seconds: float = 0.0


class CompositeTriggerUpdateIn(BaseModel):
    name: str | None = None
    logic: str | None = None
    child_trigger_ids: list[str] | None = None
    target_pipeline_id: str | None = None
    enabled: bool | None = None
    cooldown_seconds: float | None = None


class EvaluateIn(BaseModel):
    child_fires: dict[str, bool] = Field(default_factory=dict)


@router.post("/v1/pipeline-triggers/composites")
def register_composite_trigger(
    body: CompositeTriggerIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 注册复合触发器。"""
    _ = principal
    try:
        t = get_composite_trigger_engine().register(CompositeTrigger(**body.model_dump()))
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc
    return {"item": t.model_dump()}


@router.get("/v1/pipeline-triggers/composites")
def list_composite_triggers(
    enabled_only: bool = False,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 复合触发器列表。"""
    _ = principal
    items = get_composite_trigger_engine().list(enabled_only=enabled_only)
    return {"items": [t.model_dump() for t in items], "count": len(items)}


@router.get("/v1/pipeline-triggers/composites/{trigger_id}")
def get_composite_trigger(
    trigger_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 单条复合触发器。"""
    _ = principal
    try:
        return {"item": get_composite_trigger_engine().get(trigger_id).model_dump()}
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/pipeline-triggers/composites/{trigger_id}")
def update_composite_trigger(
    trigger_id: str,
    body: CompositeTriggerUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 更新复合触发器。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        t = get_composite_trigger_engine().update(trigger_id, updates)
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc
    return {"item": t.model_dump()}


@router.delete("/v1/pipeline-triggers/composites/{trigger_id}")
def delete_composite_trigger(
    trigger_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 删除复合触发器。"""
    _ = principal
    ok = get_composite_trigger_engine().delete(trigger_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"复合触发器 {trigger_id} 不存在", status_code=404)
    return {"id": trigger_id, "deleted": True}


@router.post("/v1/pipeline-triggers/composites/{trigger_id}/evaluate")
def evaluate_composite_trigger(
    trigger_id: str,
    body: EvaluateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 评估复合触发器。"""
    _ = principal
    try:
        result = get_composite_trigger_engine().evaluate(trigger_id, body.child_fires)
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc
    return {"item": result}


@router.post("/v1/pipeline-triggers/composites/{trigger_id}/fire")
def fire_composite_trigger(
    trigger_id: str,
    body: EvaluateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 复合触发器点火。"""
    _ = principal
    try:
        f = get_composite_trigger_engine().fire(trigger_id, body.child_fires)
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc
    return {"item": f.model_dump()}


# ════════════════════ #91 LinkType Output ════════════════════

class LinkTypeIn(BaseModel):
    name: str = Field(min_length=1)
    display_name: str = ""
    cardinality: str = Field(min_length=1)
    source_object_type: str = Field(min_length=1)
    target_object_type: str = Field(min_length=1)
    source_pk_field: str = Field(min_length=1)
    target_fk_field: str = Field(min_length=1)
    display_field: str = ""
    source_pipeline_id: str = ""
    description: str = ""


class LinkTypeUpdateIn(BaseModel):
    name: str | None = None
    display_name: str | None = None
    cardinality: str | None = None
    source_object_type: str | None = None
    target_object_type: str | None = None
    source_pk_field: str | None = None
    target_fk_field: str | None = None
    display_field: str | None = None
    source_pipeline_id: str | None = None
    description: str | None = None


class InferLinkIn(BaseModel):
    source_object_type: str = Field(min_length=1)
    target_object_type: str = Field(min_length=1)
    rows: list[dict[str, Any]] = Field(min_length=1)
    fk_field: str = Field(min_length=1)
    display_field: str = ""


class PreviewLinksIn(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    limit: int = 100


@router.post("/v1/pipeline-outputs/link-types")
def register_link_type(
    body: LinkTypeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#91 · 注册链接类型。"""
    _ = principal
    try:
        l = get_link_type_output_engine().register(LinkTypeDefinition(**body.model_dump()))
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc
    return {"item": l.model_dump()}


@router.get("/v1/pipeline-outputs/link-types")
def list_link_types(
    source_object_type: str | None = None,
    target_object_type: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#91 · 链接类型列表。"""
    _ = principal
    items = get_link_type_output_engine().list(
        source_object_type=source_object_type,
        target_object_type=target_object_type,
    )
    return {"items": [l.model_dump() for l in items], "count": len(items)}


@router.get("/v1/pipeline-outputs/link-types/{link_id}")
def get_link_type(
    link_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#91 · 单条链接类型。"""
    _ = principal
    try:
        return {"item": get_link_type_output_engine().get(link_id).model_dump()}
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/pipeline-outputs/link-types/{link_id}")
def update_link_type(
    link_id: str,
    body: LinkTypeUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#91 · 更新链接类型。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        l = get_link_type_output_engine().update(link_id, updates)
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc
    return {"item": l.model_dump()}


@router.delete("/v1/pipeline-outputs/link-types/{link_id}")
def delete_link_type(
    link_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#91 · 删除链接类型。"""
    _ = principal
    ok = get_link_type_output_engine().delete(link_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"链接类型 {link_id} 不存在", status_code=404)
    return {"id": link_id, "deleted": True}


@router.post("/v1/pipeline-outputs/link-types/infer")
def infer_link_type(
    body: InferLinkIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#91 · 从对象数据推断链接类型。"""
    _ = principal
    try:
        l = get_link_type_output_engine().infer_from_objects(
            source_ot=body.source_object_type,
            target_ot=body.target_object_type,
            rows=body.rows,
            fk_field=body.fk_field,
            display_field=body.display_field,
        )
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc
    return {"item": l.model_dump()}


@router.post("/v1/pipeline-outputs/link-types/{link_id}/preview")
def preview_links(
    link_id: str,
    body: PreviewLinksIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#91 · 预览链接实例。"""
    _ = principal
    try:
        items = get_link_type_output_engine().preview_links(
            link_id=link_id, rows=body.rows, limit=body.limit,
        )
    except TriggersAndLinkOutputError as exc:
        raise _map_err(exc) from exc
    return {"items": items, "count": len(items)}
