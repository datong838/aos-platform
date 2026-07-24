"""Wave-0 in-memory Mock aligned with foundry/html Inbox narrative (T0.7)."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.mock")

_MODULES: list[dict[str, Any]] = [
    {
        "id": "mod-ops-inbox",
        "name": "运营台 Inbox",
        "status": "published",
        "description": "Demo-aligned Module for Workshop Inbox",
        "objectType": "WorkOrder",
        "markings": ["public"],
        "entryPath": "/workshop/inbox",
        "widgets": ["table", "filters", "selection"],
        "buddyBound": True,
    },
    {
        "id": "mod-canvas-draft",
        "name": "画布草稿",
        "status": "draft",
        "description": "Canvas editor placeholder",
        "objectType": "WorkOrder",
        "markings": ["restricted"],
        "entryPath": "/workshop/canvas",
        "widgets": ["canvas"],
        "buddyBound": False,
    },
    {
        "id": "mod-buddy-assist",
        "name": "Buddy 助手",
        "status": "published",
        "description": "AIP Assist Module",
        "objectType": "WorkOrder",
        "markings": ["public"],
        "entryPath": "/workshop/buddy",
        "widgets": ["chat"],
        "buddyBound": True,
    },
]

_OBJECTS: list[dict[str, Any]] = [
    {
        "id": "wo-1001",
        "type": "WorkOrder",
        "title": "机房巡检-A区",
        "status": "open",
        "priority": "P1",
        "owner": "ops-alice",
        "site": "DC-East",
    },
    {
        "id": "wo-1002",
        "type": "WorkOrder",
        "title": "链路告警复核",
        "status": "in_progress",
        "priority": "P0",
        "owner": "ops-bob",
        "site": "DC-West",
    },
    {
        "id": "wo-1003",
        "type": "WorkOrder",
        "title": "备件更换",
        "status": "open",
        "priority": "P2",
        "owner": "ops-carol",
        "site": "DC-East",
    },
]


def list_modules() -> list[dict[str, Any]]:
    log.debug("mock_list_modules count=%s", len(_MODULES))
    return deepcopy(_MODULES)


def get_module(module_id: str) -> dict[str, Any] | None:
    for m in _MODULES:
        if m["id"] == module_id:
            return deepcopy(m)
    return None


def create_module(payload: dict[str, Any]) -> dict[str, Any]:
    mid = payload.get("id") or f"mod-{len(_MODULES) + 1}"
    item = {
        "id": mid,
        "name": payload.get("name") or mid,
        "status": payload.get("status") or "draft",
        "description": payload.get("description") or "",
        "objectType": payload.get("objectType") or "WorkOrder",
        "markings": payload.get("markings") or ["public"],
        "entryPath": payload.get("entryPath") or "/workshop/inbox",
        "widgets": payload.get("widgets") or ["table", "filters"],
        "buddyBound": bool(payload.get("buddyBound", True)),
    }
    _MODULES.append(item)
    log.info("mock_create_module id=%s entry=%s", mid, item["entryPath"])
    return deepcopy(item)


def update_module(module_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    for i, m in enumerate(_MODULES):
        if m["id"] != module_id:
            continue
        allowed = {
            "name",
            "description",
            "objectType",
            "markings",
            "entryPath",
            "widgets",
            "buddyBound",
            "status",
        }
        updated = deepcopy(m)
        for k, v in patch.items():
            if k in allowed and v is not None:
                updated[k] = v
        _MODULES[i] = updated
        log.info("mock_update_module id=%s", module_id)
        return deepcopy(updated)
    return None


def publish_module(module_id: str) -> dict[str, Any] | None:
    mod = update_module(module_id, {"status": "published"})
    if not mod:
        return None
    return {
        **mod,
        "publish": {
            "adapter": "apollo-lite",
            "channel": "dev",
            "status": "ACCEPTED",
        },
    }


def module_runtime(module_id: str) -> dict[str, Any] | None:
    mod = get_module(module_id)
    if not mod:
        return None
    return {
        "moduleId": module_id,
        "layout": {"widgets": mod.get("widgets") or ["table", "filters", "selection"]},
        "variables": {"selectionLimit": 10},
        "events": [{"id": "refresh", "type": "query"}],
        "objectType": mod["objectType"],
        "entryPath": mod.get("entryPath") or "/workshop/inbox",
        "buddyBound": bool(mod.get("buddyBound", False)),
    }


def query_objects(
    *,
    filters: list[dict[str, Any]] | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    filters = filters or []
    if len(filters) > 10:
        raise ValueError("filters exceed 10 dimensions")
    rows = deepcopy(_OBJECTS)
    for f in filters:
        field = f.get("field")
        value = f.get("value")
        if field and value is not None:
            rows = [r for r in rows if str(r.get(field)) == str(value)]
    total = len(rows)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    page_rows = rows[start:end]
    log.info(
        "mock_object_query filters=%s page=%s size=%s total=%s returned=%s",
        len(filters),
        page,
        page_size,
        total,
        len(page_rows),
    )
    return {
        "items": page_rows,
        "page": page,
        "pageSize": page_size,
        "total": total,
        "selectionLimit": 10,
    }


def reset_mock_state() -> None:
    """Tests only — re-seed is implicit via module-level lists; recreate known ids."""
    global _MODULES, _OBJECTS
    seed_ids = {"mod-ops-inbox", "mod-canvas-draft", "mod-buddy-assist"}
    _MODULES[:] = [m for m in _MODULES if m["id"] in seed_ids]
    # ensure buddy module exists after older test runs
    if not any(m["id"] == "mod-buddy-assist" for m in _MODULES):
        _MODULES.append(
            {
                "id": "mod-buddy-assist",
                "name": "Buddy 助手",
                "status": "published",
                "description": "AIP Assist Module",
                "objectType": "WorkOrder",
                "markings": ["public"],
                "entryPath": "/workshop/buddy",
                "widgets": ["chat"],
                "buddyBound": True,
            }
        )
    log.debug("mock_reset modules=%s", len(_MODULES))
