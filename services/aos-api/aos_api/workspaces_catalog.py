"""TWA.10 — mutable workspace catalog (seed + created; memory + optional PG 181m)."""
from __future__ import annotations

import re
from typing import Any

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.workspaces-catalog")

_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")

# (org_id, project_id) -> meta
_WS: dict[tuple[str, str], dict[str, Any]] = {}


def reset_workspace_catalog() -> None:
    _WS.clear()
    from aos_api import twa_pg

    twa_pg.truncate_workspaces()


def seed_dev_workspaces() -> None:
    for org in ("dev-org", "org-a", "org-b"):
        ensure_workspace(
            org,
            "dev-project",
            name="测试工作区",
            deletable=True,
            kind="test",
        )
        ensure_workspace(
            org,
            "prj-ops",
            name="生产运营工作区",
            deletable=False,
            kind="ops",
        )


def ensure_workspace(
    org_id: str,
    project_id: str,
    *,
    name: str | None = None,
    deletable: bool = True,
    kind: str = "custom",
) -> dict[str, Any]:
    key = (org_id, project_id)
    if key not in _WS:
        _WS[key] = {
            "id": project_id,
            "orgId": org_id,
            "name": name or project_id,
            "deletable": deletable,
            "kind": kind,
        }
    elif name:
        _WS[key]["name"] = name
    from aos_api import twa_pg

    twa_pg.upsert_workspace(_WS[key])
    return dict(_WS[key])


def get_workspace(org_id: str, project_id: str) -> dict[str, Any] | None:
    row = _WS.get((org_id, project_id))
    return dict(row) if row else None


def list_workspaces_for_org(org_id: str) -> list[dict[str, Any]]:
    return [dict(v) for (o, _), v in sorted(_WS.items()) if o == org_id]


def create_workspace(
    org_id: str,
    *,
    name: str,
    project_id: str | None = None,
    kind: str = "custom",
) -> dict[str, Any]:
    pid = (project_id or "").strip()
    if not pid:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip().lower()).strip("-")
        slug = slug[:40] or "ws"
        pid = f"ws-{slug}"
        n = 0
        while (org_id, pid) in _WS:
            n += 1
            pid = f"ws-{slug}-{n}"
    if not _SAFE.match(pid):
        raise ValueError("project id must be 2-64 chars [A-Za-z0-9._-]")
    if (org_id, pid) in _WS:
        raise ValueError("workspace already exists")
    row = ensure_workspace(
        org_id,
        pid,
        name=name.strip() or pid,
        deletable=True,
        kind=kind,
    )
    log.info("workspace_catalog_create org=%s project=%s name=%s", org_id, pid, row["name"])
    return row


def remove_workspace(org_id: str, project_id: str) -> bool:
    key = (org_id, project_id)
    if key not in _WS:
        return False
    del _WS[key]
    from aos_api import twa_pg

    twa_pg.delete_workspace(org_id, project_id)
    log.info("workspace_catalog_remove org=%s project=%s", org_id, project_id)
    return True


# bootstrap
seed_dev_workspaces()
