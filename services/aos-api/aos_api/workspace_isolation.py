"""TWA.4 / TWA.11 — workspace isolation items (in-memory)."""
from __future__ import annotations

from typing import Any

# (org_id, project_id, item_id) -> payload
_ITEMS: dict[tuple[str, str, str], dict[str, Any]] = {}


def reset_items() -> None:
    _ITEMS.clear()


def put_item(org_id: str, project_id: str, item: dict[str, Any]) -> dict[str, Any]:
    key = (org_id, project_id, item["id"])
    _ITEMS[key] = item
    return item


def get_item(org_id: str, project_id: str, item_id: str) -> dict[str, Any] | None:
    return _ITEMS.get((org_id, project_id, item_id))


def list_items(org_id: str, project_id: str) -> list[dict[str, Any]]:
    return [v for (o, p, _), v in _ITEMS.items() if o == org_id and p == project_id]


def count_items(org_id: str, project_id: str) -> int:
    return sum(1 for (o, p, _) in _ITEMS if o == org_id and p == project_id)


def clear_items(org_id: str, project_id: str) -> int:
    keys = [k for k in _ITEMS if k[0] == org_id and k[1] == project_id]
    for k in keys:
        del _ITEMS[k]
    return len(keys)
