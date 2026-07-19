"""TWA.3/TWA.4/TWA.7 — workspaces catalog, isolation probe, members, enter."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api import membership as mem
from aos_api.oidc import allow_dev

router = APIRouter(tags=["workspaces"])
log = get_logger("aos-api.workspaces")

# (org_id, project_id, item_id) -> payload
_ITEMS: dict[tuple[str, str, str], dict[str, Any]] = {}


def _workspace_catalog(org_id: str) -> list[dict[str, Any]]:
    """Dev catalog — product names; ids are project_id."""
    return [
        {
            "id": "dev-project",
            "orgId": org_id,
            "name": "测试工作区",
            "deletable": True,
            "kind": "test",
        },
        {
            "id": "prj-ops",
            "orgId": org_id,
            "name": "生产运营工作区",
            "deletable": False,
            "kind": "ops",
        },
    ]


def _find_workspace(org_id: str, workspace_id: str) -> dict[str, Any] | None:
    for w in _workspace_catalog(org_id):
        if w["id"] == workspace_id:
            return w
    return None


@router.get("/v1/workspaces")
def list_workspaces(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    # Ensure caller has at least membership on current project (dev bootstrap)
    mem.ensure_default_membership(
        principal.org_id, principal.project_id, principal.subject
    )
    catalog = _workspace_catalog(principal.org_id)
    member_ids = mem.member_project_ids(principal.org_id, principal.subject)
    items = [w for w in catalog if w["id"] in member_ids]
    log.info(
        "workspaces_list org=%s count=%s subject=%s",
        principal.org_id,
        len(items),
        principal.subject,
    )
    return {"items": items, "currentProjectId": principal.project_id}


@router.post("/v1/workspaces/{workspace_id}/enter")
def enter_workspace(
    workspace_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    ws = _find_workspace(principal.org_id, workspace_id)
    if not ws:
        raise ApiError(code="NOT_FOUND", message="workspace not found", status_code=404)
    if not mem.is_member(principal.org_id, workspace_id, principal.subject):
        mem.append_audit(
            org_id=principal.org_id,
            project_id=workspace_id,
            actor_id=principal.subject,
            action="workspace.enter_denied",
            detail={"workspaceId": workspace_id},
        )
        raise ApiError(
            code="WORKSPACE_FORBIDDEN",
            message="not a member of this workspace",
            status_code=403,
        )
    mem.append_audit(
        org_id=principal.org_id,
        project_id=workspace_id,
        actor_id=principal.subject,
        action="workspace.enter",
        detail={"workspaceId": workspace_id, "name": ws["name"]},
    )
    log.info(
        "workspace_enter id=%s org=%s subject=%s",
        workspace_id,
        principal.org_id,
        principal.subject,
    )
    return {
        "orgId": principal.org_id,
        "projectId": workspace_id,
        "workspaceName": ws["name"],
        "ok": True,
    }


class MemberIn(BaseModel):
    subject: str = Field(min_length=1)
    role: str = Field(min_length=1)


@router.get("/v1/workspaces/{workspace_id}/members")
def list_workspace_members(
    workspace_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if not _find_workspace(principal.org_id, workspace_id):
        raise ApiError(code="NOT_FOUND", message="workspace not found", status_code=404)
    if not mem.is_member(principal.org_id, workspace_id, principal.subject):
        raise ApiError(
            code="WORKSPACE_FORBIDDEN",
            message="not a member of this workspace",
            status_code=403,
        )
    items = mem.list_members(principal.org_id, workspace_id)
    return {"items": items, "workspaceId": workspace_id}


@router.post("/v1/workspaces/{workspace_id}/members")
def add_workspace_member(
    workspace_id: str,
    body: MemberIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if not _find_workspace(principal.org_id, workspace_id):
        raise ApiError(code="NOT_FOUND", message="workspace not found", status_code=404)
    if not mem.can_manage_members(principal.org_id, workspace_id, principal.subject):
        raise ApiError(
            code="WORKSPACE_FORBIDDEN",
            message="admin or owner required",
            status_code=403,
        )
    if body.role not in mem.ROLES:
        raise ApiError(code="BAD_REQUEST", message="invalid role", status_code=400)
    return mem.upsert_member(
        principal.org_id,
        workspace_id,
        body.subject,
        body.role,
        actor_id=principal.subject,
    )


@router.delete("/v1/workspaces/{workspace_id}/members/{member_subject}")
def delete_workspace_member(
    workspace_id: str,
    member_subject: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if not _find_workspace(principal.org_id, workspace_id):
        raise ApiError(code="NOT_FOUND", message="workspace not found", status_code=404)
    if not mem.can_manage_members(principal.org_id, workspace_id, principal.subject):
        raise ApiError(
            code="WORKSPACE_FORBIDDEN",
            message="admin or owner required",
            status_code=403,
        )
    ok = mem.remove_member(
        principal.org_id,
        workspace_id,
        member_subject,
        actor_id=principal.subject,
    )
    if not ok:
        raise ApiError(code="NOT_FOUND", message="member not found", status_code=404)
    return {"ok": True, "subject": member_subject}


class WorkspaceItemIn(BaseModel):
    name: str = Field(min_length=1)
    id: str | None = None


@router.post("/v1/workspace-items")
def create_workspace_item(
    body: WorkspaceItemIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """TWA.4 probe write — scoped to current org/project."""
    if not allow_dev() and principal.token_kind == "dev":
        raise ApiError(code="AUTH_DEV_DISABLED", message="dev disabled", status_code=401)
    iid = body.id or f"wi-{uuid.uuid4().hex[:8]}"
    key = (principal.org_id, principal.project_id, iid)
    item = {
        "id": iid,
        "name": body.name,
        "orgId": principal.org_id,
        "projectId": principal.project_id,
    }
    _ITEMS[key] = item
    log.info(
        "workspace_item_create id=%s org=%s project=%s",
        iid,
        principal.org_id,
        principal.project_id,
    )
    return item


@router.get("/v1/workspace-items")
def list_workspace_items(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    items = [
        v
        for (o, p, _), v in _ITEMS.items()
        if o == principal.org_id and p == principal.project_id
    ]
    log.info(
        "workspace_items_list org=%s project=%s count=%s",
        principal.org_id,
        principal.project_id,
        len(items),
    )
    return {"items": items}


@router.get("/v1/workspace-items/{item_id}")
def get_workspace_item(
    item_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    key = (principal.org_id, principal.project_id, item_id)
    item = _ITEMS.get(key)
    if not item:
        log.warning(
            "workspace_item_denied id=%s org=%s project=%s",
            item_id,
            principal.org_id,
            principal.project_id,
        )
        raise ApiError(
            code="NOT_FOUND",
            message=f"workspace item {item_id} not found",
            status_code=404,
        )
    return item


@router.get("/v1/audit")
def list_audit(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    items = mem.list_audit(principal.org_id, principal.project_id)
    log.info(
        "audit_list org=%s project=%s count=%s",
        principal.org_id,
        principal.project_id,
        len(items),
    )
    return {"items": items}


def reset_isolation_store() -> None:
    """Test helper."""
    _ITEMS.clear()
    mem.reset_membership_store()
    mem.seed_dev_defaults()
