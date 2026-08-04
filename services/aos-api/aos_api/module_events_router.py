"""Module Events Router — Phase C 222plan.

Endpoints for Workshop module event bindings.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.module_events import (
    create_event,
    delete_event,
    get_event,
    list_actions_catalog,
    list_events,
    list_triggers_catalog,
    seed_events_if_empty,
    update_event,
)

router = APIRouter(
    prefix="/v1/modules",
    tags=["module-events"],
    dependencies=[Depends(require_principal)],
)


class EventCreate(BaseModel):
    name: str = "新事件"
    trigger: dict = {}
    action: dict = {}
    enabled: bool = True
    sortOrder: int = 0


class EventUpdate(BaseModel):
    name: str | None = None
    trigger: dict | None = None
    action: dict | None = None
    enabled: bool | None = None
    sortOrder: int | None = None


def _get_module_event(module_id: str, event_id: str) -> dict:
    item = get_event(event_id)
    if not item or item.get("moduleId") != module_id:
        raise HTTPException(status_code=404, detail="Event not found")
    return item


@router.get("/{module_id}/events")
def get_module_events(module_id: str) -> dict:
    """List all event bindings for a module."""
    seed_events_if_empty(module_id)
    items = list_events(module_id)
    return {"moduleId": module_id, "items": items, "count": len(items)}


@router.post("/{module_id}/events")
def post_module_event(module_id: str, body: EventCreate) -> dict:
    """Create a new event binding for a module."""
    seed_events_if_empty(module_id)
    item = create_event(module_id, body.model_dump())
    return {"ok": True, "item": item}


@router.get("/{module_id}/events/{event_id}")
def get_single_event(module_id: str, event_id: str) -> dict:
    """Get a single event binding."""
    item = _get_module_event(module_id, event_id)
    return {"item": item}


@router.put("/{module_id}/events/{event_id}")
def put_module_event(module_id: str, event_id: str, body: EventUpdate) -> dict:
    """Update an event binding."""
    _get_module_event(module_id, event_id)
    item = update_event(event_id, body.model_dump(exclude_none=True))
    if not item:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"ok": True, "item": item}


@router.delete("/{module_id}/events/{event_id}")
def delete_module_event(module_id: str, event_id: str) -> dict:
    """Delete an event binding."""
    _get_module_event(module_id, event_id)
    ok = delete_event(event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"ok": True}


@router.get("/{module_id}/events/triggers/catalog")
def get_triggers_catalog(module_id: str) -> dict:
    """Return available trigger types catalog."""
    return {"items": list_triggers_catalog()}


@router.get("/{module_id}/events/actions/catalog")
def get_actions_catalog(module_id: str) -> dict:
    """Return available action types catalog."""
    return {"items": list_actions_catalog()}
