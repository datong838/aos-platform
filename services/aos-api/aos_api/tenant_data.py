"""TWA.11 — tenant business-data summary / clear / delete gates."""
from __future__ import annotations

from typing import Any

from aos_api import membership as mem
from aos_api import org_invites as invites
from aos_api import orgs as org_store
from aos_api import workspace_isolation as items
from aos_api import workspaces_catalog as ws_cat
from aos_api.logging_facade import get_logger
from aos_api.routers import plugins as plugin_store

log = get_logger("aos-api.tenant-data")


def _pg_count(sql: str, params: tuple[Any, ...]) -> int:
    try:
        from aos_api.db import connect

        with connect() as conn:
            row = conn.execute(sql, params).fetchone()
            if not row:
                return 0
            return int(row[0] or 0)
    except Exception as exc:  # pragma: no cover - DB optional in unit tests
        log.warning("tenant_data_pg_count_skip err=%s", exc)
        return 0


def _pg_execute(sql: str, params: tuple[Any, ...]) -> int:
    try:
        from aos_api.db import connect

        with connect() as conn:
            cur = conn.execute(sql, params)
            try:
                return int(cur.rowcount or 0)
            except Exception:
                return 0
    except Exception as exc:  # pragma: no cover
        log.warning("tenant_data_pg_exec_skip err=%s", exc)
        return 0


def summarize_workspace(org_id: str, project_id: str) -> dict[str, Any]:
    counts = {
        "workspaceItems": items.count_items(org_id, project_id),
        "pluginConfigs": plugin_store.count_configs(org_id, project_id),
        "modules": _pg_count(
            "SELECT COUNT(*) FROM meta_module WHERE org_id=%s AND project_id=%s",
            (org_id, project_id),
        ),
        "drafts": _pg_count(
            "SELECT COUNT(*) FROM draft_dataset WHERE org_id=%s AND project_id=%s",
            (org_id, project_id),
        ),
        "wikiPages": _pg_count(
            "SELECT COUNT(*) FROM wiki_page WHERE org_id=%s AND project_id=%s",
            (org_id, project_id),
        ),
    }
    total = int(sum(counts.values()))
    return {
        "orgId": org_id,
        "projectId": project_id,
        "counts": counts,
        "total": total,
        "empty": total == 0,
    }


def clear_workspace_data(
    org_id: str, project_id: str, *, actor_id: str
) -> dict[str, Any]:
    cleared = {
        "workspaceItems": items.clear_items(org_id, project_id),
        "pluginConfigs": plugin_store.clear_configs(org_id, project_id),
        "modules": _pg_execute(
            "DELETE FROM meta_module WHERE org_id=%s AND project_id=%s",
            (org_id, project_id),
        ),
        "drafts": _pg_execute(
            "DELETE FROM draft_dataset WHERE org_id=%s AND project_id=%s",
            (org_id, project_id),
        ),
        "wikiPages": _pg_execute(
            "DELETE FROM wiki_page WHERE org_id=%s AND project_id=%s",
            (org_id, project_id),
        ),
    }
    # wiki versions best-effort
    cleared["wikiVersions"] = _pg_execute(
        "DELETE FROM wiki_page_version WHERE org_id=%s AND project_id=%s",
        (org_id, project_id),
    )
    mem.append_audit(
        org_id=org_id,
        project_id=project_id,
        actor_id=actor_id,
        action="workspace.data_clear",
        detail=cleared,
    )
    log.info(
        "workspace_data_clear org=%s project=%s actor=%s cleared=%s",
        org_id,
        project_id,
        actor_id,
        cleared,
    )
    summary = summarize_workspace(org_id, project_id)
    return {"cleared": cleared, **summary}


def can_admin_workspace(org_id: str, project_id: str, subject: str) -> bool:
    return mem.can_manage_members(org_id, project_id, subject) or mem.can_manage_org(
        org_id, subject
    )


def delete_workspace(
    org_id: str, project_id: str, *, actor_id: str
) -> dict[str, Any]:
    summary = summarize_workspace(org_id, project_id)
    if not summary["empty"]:
        raise ValueError("NOT_EMPTY")
    if not ws_cat.get_workspace(org_id, project_id):
        raise LookupError("workspace not found")
    mem.remove_all_members_for_project(org_id, project_id, actor_id=actor_id)
    ws_cat.remove_workspace(org_id, project_id)
    mem.append_audit(
        org_id=org_id,
        project_id=project_id,
        actor_id=actor_id,
        action="workspace.delete",
        detail={},
    )
    log.info("workspace_delete org=%s project=%s actor=%s", org_id, project_id, actor_id)
    return {"ok": True, "orgId": org_id, "projectId": project_id}


def summarize_org(org_id: str) -> dict[str, Any]:
    workspaces = ws_cat.list_workspaces_for_org(org_id)
    known = {w["id"] for w in workspaces}
    for pid in mem.project_ids_for_org(org_id):
        if pid not in known and pid != "-":
            known.add(pid)
            workspaces.append({"id": pid, "orgId": org_id, "name": pid})
    children = [summarize_workspace(org_id, w["id"]) for w in workspaces]
    total = sum(int(c["total"]) for c in children)
    return {
        "orgId": org_id,
        "workspaces": children,
        "total": total,
        "empty": total == 0,
        "workspaceCount": len(children),
    }


def clear_org_data(org_id: str, *, actor_id: str) -> dict[str, Any]:
    summary = summarize_org(org_id)
    cleared_each = []
    for child in summary["workspaces"]:
        cleared_each.append(
            clear_workspace_data(org_id, child["projectId"], actor_id=actor_id)
        )
    mem.append_audit(
        org_id=org_id,
        project_id="-",
        actor_id=actor_id,
        action="org.data_clear",
        detail={"workspaces": len(cleared_each)},
    )
    after = summarize_org(org_id)
    return {"clearedWorkspaces": cleared_each, **after}


def delete_org(org_id: str, *, actor_id: str) -> dict[str, Any]:
    if not org_store.get_org(org_id):
        raise LookupError("organization not found")
    summary = summarize_org(org_id)
    if not summary["empty"]:
        raise ValueError("NOT_EMPTY")
    for child in list(summary["workspaces"]):
        pid = child["projectId"]
        mem.remove_all_members_for_project(org_id, pid, actor_id=actor_id)
        ws_cat.remove_workspace(org_id, pid)
    mem.remove_all_members_for_org(org_id, actor_id=actor_id)
    artifacts = invites.clear_org_artifacts(org_id)
    org_store.remove_org(org_id)
    mem.append_audit(
        org_id=org_id,
        project_id="-",
        actor_id=actor_id,
        action="org.delete",
        detail={"artifacts": artifacts},
    )
    log.info("org_delete id=%s actor=%s", org_id, actor_id)
    return {"ok": True, "orgId": org_id, "artifacts": artifacts}
