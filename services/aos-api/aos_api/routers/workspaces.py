"""TWA.3/TWA.4/TWA.7/TWA.10/TWA.11 — workspaces catalog, members, create, delete."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api import membership as mem
from aos_api import orgs as org_store
from aos_api import tenant_data as tdata
from aos_api import workspace_isolation as iso
from aos_api import workspaces_catalog as ws_cat
from aos_api.oidc import allow_dev

router = APIRouter(tags=["workspaces"])
log = get_logger("aos-api.workspaces")


def _find_workspace(org_id: str, workspace_id: str) -> dict[str, Any] | None:
    return ws_cat.get_workspace(org_id, workspace_id)


@router.get("/v1/workspaces")
def list_workspaces(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    # Ensure caller has at least membership on current project (dev bootstrap)
    mem.ensure_default_membership(
        principal.org_id, principal.project_id, principal.subject
    )
    # Ensure current project exists in catalog for continuity
    if not ws_cat.get_workspace(principal.org_id, principal.project_id):
        ws_cat.ensure_workspace(
            principal.org_id,
            principal.project_id,
            name=org_store.workspace_display_name(principal.org_id, principal.project_id),
        )
    catalog = ws_cat.list_workspaces_for_org(principal.org_id)
    member_ids = mem.member_project_ids(principal.org_id, principal.subject)
    items = [w for w in catalog if w["id"] in member_ids]
    log.info(
        "workspaces_list org=%s count=%s subject=%s",
        principal.org_id,
        len(items),
        principal.subject,
    )
    return {"items": items, "currentProjectId": principal.project_id}


class WorkspaceCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    id: str | None = None


@router.post("/v1/workspaces")
def create_workspace(
    body: WorkspaceCreateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if not mem.can_manage_org(principal.org_id, principal.subject):
        # bootstrap: if user somehow has no admin but is only member via ensure — still require admin
        if not mem.is_member(principal.org_id, principal.project_id, principal.subject):
            mem.ensure_default_membership(
                principal.org_id, principal.project_id, principal.subject
            )
        if not mem.can_manage_org(principal.org_id, principal.subject):
            raise ApiError(
                code="FORBIDDEN",
                message="organization admin required to create workspace",
                status_code=403,
            )
    try:
        ws = ws_cat.create_workspace(
            principal.org_id,
            name=body.name,
            project_id=body.id,
            kind="custom",
        )
    except ValueError as exc:
        msg = str(exc)
        code = "CONFLICT" if "already exists" in msg else "VALIDATION"
        raise ApiError(
            code=code,
            message=msg,
            status_code=409 if code == "CONFLICT" else 400,
        ) from exc
    mem.upsert_member(
        principal.org_id,
        ws["id"],
        principal.subject,
        "owner",
        actor_id=principal.subject,
    )
    mem.append_audit(
        org_id=principal.org_id,
        project_id=ws["id"],
        actor_id=principal.subject,
        action="workspace.create",
        detail={"name": ws["name"]},
    )
    log.info(
        "workspace_create org=%s project=%s subject=%s",
        principal.org_id,
        ws["id"],
        principal.subject,
    )
    return ws


@router.get("/v1/workspaces/{workspace_id}/data")
def workspace_data_summary(
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
    return tdata.summarize_workspace(principal.org_id, workspace_id)


@router.post("/v1/workspaces/{workspace_id}/data/clear")
def workspace_data_clear(
    workspace_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if not _find_workspace(principal.org_id, workspace_id):
        raise ApiError(code="NOT_FOUND", message="workspace not found", status_code=404)
    if not tdata.can_admin_workspace(
        principal.org_id, workspace_id, principal.subject
    ):
        raise ApiError(
            code="FORBIDDEN",
            message="admin or owner required to clear workspace data",
            status_code=403,
        )
    return tdata.clear_workspace_data(
        principal.org_id, workspace_id, actor_id=principal.subject
    )


@router.delete("/v1/workspaces/{workspace_id}")
def delete_workspace(
    workspace_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if not _find_workspace(principal.org_id, workspace_id):
        raise ApiError(code="NOT_FOUND", message="workspace not found", status_code=404)
    if not tdata.can_admin_workspace(
        principal.org_id, workspace_id, principal.subject
    ):
        raise ApiError(
            code="FORBIDDEN",
            message="admin or owner required to delete workspace",
            status_code=403,
        )
    try:
        return tdata.delete_workspace(
            principal.org_id, workspace_id, actor_id=principal.subject
        )
    except ValueError as exc:
        if str(exc) == "NOT_EMPTY":
            summary = tdata.summarize_workspace(principal.org_id, workspace_id)
            raise ApiError(
                code="NOT_EMPTY",
                message="workspace still has business data; clear data first",
                status_code=409,
                details=summary,
            ) from exc
        raise ApiError(code="VALIDATION", message=str(exc), status_code=400) from exc


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
    subject: str | None = None
    email: str | None = None
    phone: str | None = None
    displayName: str | None = None
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
    from aos_api import person_identity as person

    items = [
        person.enrich_member_row(m)
        for m in mem.list_members(principal.org_id, workspace_id)
    ]
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
    from aos_api import person_identity as person

    try:
        identity = person.resolve_member_identity(
            subject=body.subject,
            email=body.email,
            phone=body.phone,
            display_name=body.displayName,
        )
    except ValueError as exc:
        raise ApiError(code="VALIDATION", message=str(exc), status_code=400) from exc
    row = mem.upsert_member(
        principal.org_id,
        workspace_id,
        identity["subject"],
        body.role,
        actor_id=principal.subject,
    )
    return person.enrich_member_row(row)


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
    item = {
        "id": iid,
        "name": body.name,
        "orgId": principal.org_id,
        "projectId": principal.project_id,
    }
    iso.put_item(principal.org_id, principal.project_id, item)
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
    listed = iso.list_items(principal.org_id, principal.project_id)
    log.info(
        "workspace_items_list org=%s project=%s count=%s",
        principal.org_id,
        principal.project_id,
        len(listed),
    )
    return {"items": listed}


@router.get("/v1/workspace-items/{item_id}")
def get_workspace_item(
    item_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    item = iso.get_item(principal.org_id, principal.project_id, item_id)
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
    listed = mem.list_audit(principal.org_id, principal.project_id)
    log.info(
        "audit_list org=%s project=%s count=%s",
        principal.org_id,
        principal.project_id,
        len(listed),
    )
    return {"items": listed}


def reset_isolation_store() -> None:
    """Test helper."""
    iso.reset_items()
    mem.reset_membership_store()
    mem.seed_dev_defaults()
    ws_cat.reset_workspace_catalog()
    ws_cat.seed_dev_workspaces()
    org_store.reset_org_store()
    org_store.seed_dev_orgs()
    from aos_api import org_invites as invites
    from aos_api.person_identity import reset_person_store, seed_dev_persons

    invites.reset_org_invites_store()
    reset_person_store()
    seed_dev_persons()
