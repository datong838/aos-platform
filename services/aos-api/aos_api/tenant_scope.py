"""TWA.5 — tenant scope helpers + ledger loader (no I/O beyond package data)."""
from __future__ import annotations

import json
from importlib import resources
from typing import Any


def filter_by_tenant(
    items: list[dict[str, Any]],
    org_id: str,
    project_id: str,
    *,
    org_key: str = "orgId",
    project_key: str = "projectId",
) -> list[dict[str, Any]]:
    return [
        it
        for it in items
        if it.get(org_key) == org_id and it.get(project_key) == project_id
    ]


def belongs_to_tenant(
    item: dict[str, Any] | None,
    org_id: str,
    project_id: str,
    *,
    org_key: str = "orgId",
    project_key: str = "projectId",
) -> bool:
    if not item:
        return False
    return item.get(org_key) == org_id and item.get(project_key) == project_id


def load_tenant_ledger() -> dict[str, Any]:
    raw = resources.files("aos_api").joinpath("tenant_ledger.json").read_text(
        encoding="utf-8"
    )
    return json.loads(raw)


def p0_open_gaps(ledger: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = ledger or load_tenant_ledger()
    return [
        e
        for e in data.get("entries", [])
        if e.get("priority") == "P0" and e.get("status") == "GAP"
    ]
