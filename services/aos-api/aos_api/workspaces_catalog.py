"""TWA.10 — workspace catalog (PG-backed · 164 v1.1)."""
from __future__ import annotations

import re
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.workspaces-catalog")

_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")

# (org_id, project_id) -> meta
_WS: dict[tuple[str, str], dict[str, Any]] = {}


def workspace_count() -> int:
    return len(_WS)


def reset_workspace_catalog(*, purge_db: bool = False) -> None:
    """Clear in-memory workspace cache; 默认不清 meta_workspace。"""
    import os

    _WS.clear()
    from aos_api import twa_pg

    if (os.getenv("AOS_TWA_STORE") or "").strip().lower() == "pg":
        twa_pg.truncate_workspaces()
    if not purge_db:
        return
    try:
        with connect() as conn:
            conn.execute("DELETE FROM meta_workspace")
            conn.commit()
    except Exception:  # noqa: BLE001
        log.debug("workspace_purge_skip", exc_info=True)


def _persist_ws(row: dict[str, Any]) -> None:
    try:
        from aos_api.tenant_catalog import ensure_tenant_catalog_schema

        ensure_tenant_catalog_schema()
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO meta_workspace
                  (org_id, project_id, name, deletable, kind, updated_at)
                VALUES (%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (org_id, project_id) DO UPDATE SET
                  name=EXCLUDED.name,
                  deletable=EXCLUDED.deletable,
                  kind=EXCLUDED.kind,
                  updated_at=NOW()
                """,
                (
                    row["orgId"],
                    row["id"],
                    row["name"],
                    bool(row.get("deletable", True)),
                    row.get("kind") or "custom",
                ),
            )
            conn.commit()
    except Exception:  # noqa: BLE001
        log.warning(
            "workspace_persist_fail org=%s project=%s",
            row.get("orgId"),
            row.get("id"),
            exc_info=True,
        )
    try:
        from aos_api import twa_pg

        twa_pg.upsert_workspace(row)
    except Exception:  # noqa: BLE001
        log.debug("workspace_twa_dual_write_skip", exc_info=True)


def _delete_ws_db(org_id: str, project_id: str) -> None:
    try:
        with connect() as conn:
            conn.execute(
                "DELETE FROM meta_workspace WHERE org_id=%s AND project_id=%s",
                (org_id, project_id),
            )
            conn.commit()
    except Exception:  # noqa: BLE001
        log.warning(
            "workspace_delete_fail org=%s project=%s", org_id, project_id, exc_info=True
        )
    try:
        from aos_api import twa_pg

        twa_pg.delete_workspace(org_id, project_id)
    except Exception:  # noqa: BLE001
        log.debug("workspace_twa_delete_skip", exc_info=True)


def load_workspaces_from_db() -> int:
    _WS.clear()
    try:
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT org_id, project_id, name, deletable, kind
                FROM meta_workspace ORDER BY org_id, project_id
                """
            ).fetchall()
    except Exception:  # noqa: BLE001
        log.warning("workspace_load_fail", exc_info=True)
        return 0
    for r in rows:
        key = (str(r["org_id"]), str(r["project_id"]))
        _WS[key] = {
            "id": str(r["project_id"]),
            "orgId": str(r["org_id"]),
            "name": str(r["name"]),
            "deletable": bool(r["deletable"]),
            "kind": str(r["kind"] or "custom"),
        }
    log.info("workspace_load count=%s", len(_WS))
    return len(_WS)


def seed_dev_workspaces() -> None:
    # 仅默认组织保留测试/运营工作区种子；不再为 org-a/org-b 播种
    org = "dev-org"
    if (org, "dev-project") not in _WS:
        ensure_workspace(
            org,
            "dev-project",
            name="测试工作区",
            deletable=True,
            kind="test",
        )
    if (org, "prj-ops") not in _WS:
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
        _persist_ws(_WS[key])
    elif name and _WS[key].get("name") != name:
        _WS[key]["name"] = name
        _persist_ws(_WS[key])
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
    _delete_ws_db(org_id, project_id)
    log.info("workspace_catalog_remove org=%s project=%s", org_id, project_id)
    return True
