"""TWA.9 / TWA.10 — Organization list / enter / create / invite / join."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api import membership as mem
from aos_api import org_invites as invites
from aos_api import orgs as org_store
from aos_api import tenant_data as tdata
from aos_api import workspaces_catalog as ws_cat
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["orgs"])
log = get_logger("aos-api.orgs-router")


class OrgCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    id: str | None = None
    joinPolicy: str | None = None


class InviteCreateIn(BaseModel):
    role: str = "viewer"
    projectId: str | None = None
    maxUses: int = 10
    ttlHours: int = 168


class JoinRequestIn(BaseModel):
    message: str = ""
    projectId: str | None = None


class JoinDecideIn(BaseModel):
    decision: str = Field(min_length=1)
    role: str = "viewer"
    projectId: str | None = None


@router.get("/v1/orgs/directory")
def org_directory(principal: Principal = Depends(require_principal)) -> dict:
    items = org_store.list_directory(principal.subject)
    return {"items": items}


@router.get("/v1/orgs")
def list_orgs(principal: Principal = Depends(require_principal)) -> dict:
    mem.ensure_default_membership(
        principal.org_id, principal.project_id, principal.subject
    )
    items = org_store.list_orgs_for_subject(principal.subject)
    # Always include current org in list surface
    if not any(i["id"] == principal.org_id for i in items):
        org_store.ensure_org(principal.org_id)
        items = [org_store.get_org(principal.org_id), *items]  # type: ignore[list-item]
        items = [i for i in items if i]
    log.info(
        "orgs_list subject=%s count=%s",
        principal.subject,
        len(items),
    )
    return {
        "items": items,
        "currentOrgId": principal.org_id,
    }


@router.post("/v1/orgs")
def create_org(
    body: OrgCreateIn,
    principal: Principal = Depends(require_principal),
) -> dict:
    try:
        created = org_store.create_org(
            name=body.name,
            org_id=body.id,
            join_policy=body.joinPolicy or "invite_or_apply",
            actor_id=principal.subject,
        )
    except ValueError as exc:
        msg = str(exc)
        code = "CONFLICT" if "already exists" in msg else "VALIDATION"
        raise ApiError(
            code=code,
            message=msg,
            status_code=409 if code == "CONFLICT" else 400,
        ) from exc
    return created


@router.post("/v1/orgs/{org_id}/enter")
def enter_org(
    org_id: str,
    principal: Principal = Depends(require_principal),
) -> dict:
    org = org_store.get_org(org_id) or org_store.ensure_org(org_id)
    projects = mem.member_project_ids(org_id, principal.subject)
    if not projects:
        # bootstrap only for current org continuity in dev; foreign empty → forbid
        if org_id == principal.org_id:
            mem.ensure_default_membership(org_id, principal.project_id, principal.subject)
            projects = mem.member_project_ids(org_id, principal.subject)
        if not projects:
            mem.append_audit(
                org_id=org_id,
                project_id="-",
                actor_id=principal.subject,
                action="org.enter_denied",
                detail={"reason": "not_member"},
            )
            raise ApiError(
                code="FORBIDDEN",
                message="not a member of this organization",
                status_code=403,
            )
    project_id = org_store.default_project_for_org(org_id, principal.subject)
    assert project_id is not None
    mem.append_audit(
        org_id=org_id,
        project_id=project_id,
        actor_id=principal.subject,
        action="org.enter",
        detail={"fromOrg": principal.org_id},
    )
    log.info(
        "org_enter subject=%s org=%s project=%s",
        principal.subject,
        org_id,
        project_id,
    )
    return {
        "orgId": org_id,
        "orgName": org["name"],
        "projectId": project_id,
        "workspaceName": org_store.workspace_display_name(org_id, project_id),
    }


@router.post("/v1/orgs/{org_id}/invites")
def create_org_invite(
    org_id: str,
    body: InviteCreateIn,
    principal: Principal = Depends(require_principal),
) -> dict:
    if not org_store.get_org(org_id):
        raise ApiError(code="NOT_FOUND", message="organization not found", status_code=404)
    if not mem.can_manage_org(org_id, principal.subject):
        raise ApiError(
            code="FORBIDDEN",
            message="organization admin required",
            status_code=403,
        )
    org = org_store.get_org(org_id) or {}
    if org.get("joinPolicy") == "closed":
        raise ApiError(
            code="FORBIDDEN",
            message="organization does not allow invites",
            status_code=403,
        )
    project_id = body.projectId or "dev-project"
    if not ws_cat.get_workspace(org_id, project_id):
        ws_cat.ensure_workspace(org_id, project_id, name=project_id)
    try:
        return invites.create_invite(
            org_id=org_id,
            actor_id=principal.subject,
            role=body.role,
            project_id=project_id,
            max_uses=body.maxUses,
            ttl_hours=body.ttlHours,
        )
    except ValueError as exc:
        raise ApiError(code="VALIDATION", message=str(exc), status_code=400) from exc


@router.get("/v1/org-invites/{token}")
def preview_invite(
    token: str,
    principal: Principal = Depends(require_principal),
) -> dict:
    row = invites.get_invite(token)
    if not row:
        raise ApiError(code="NOT_FOUND", message="invite not found", status_code=404)
    org = org_store.get_org(row["orgId"]) or org_store.ensure_org(row["orgId"])
    pub = invites.public_invite(row)
    pub["orgName"] = org["name"]
    pub["alreadyMember"] = mem.is_member(
        row["orgId"], row["projectId"], principal.subject
    )
    return pub


@router.post("/v1/org-invites/{token}/accept")
def accept_invite(
    token: str,
    principal: Principal = Depends(require_principal),
) -> dict:
    try:
        accepted = invites.accept_invite(token=token, subject=principal.subject)
    except LookupError as exc:
        raise ApiError(
            code="INVITE_UNAVAILABLE",
            message=str(exc),
            status_code=410,
        ) from exc
    org = org_store.get_org(accepted["orgId"]) or org_store.ensure_org(accepted["orgId"])
    return {
        **accepted,
        "orgName": org["name"],
        "workspaceName": org_store.workspace_display_name(
            accepted["orgId"], accepted["projectId"]
        ),
        "ok": True,
    }


@router.post("/v1/orgs/{org_id}/join-requests")
def create_join_request(
    org_id: str,
    body: JoinRequestIn,
    principal: Principal = Depends(require_principal),
) -> dict:
    org = org_store.get_org(org_id)
    if not org:
        raise ApiError(code="NOT_FOUND", message="organization not found", status_code=404)
    policy = org.get("joinPolicy") or "invite_or_apply"
    if policy != "invite_or_apply":
        raise ApiError(
            code="FORBIDDEN",
            message="organization does not accept join applications",
            status_code=403,
        )
    project_id = body.projectId or "dev-project"
    if mem.is_member(org_id, project_id, principal.subject) or org_id in mem.member_org_ids(
        principal.subject
    ):
        raise ApiError(
            code="CONFLICT",
            message="already a member of this organization",
            status_code=409,
        )
    if not ws_cat.get_workspace(org_id, project_id):
        ws_cat.ensure_workspace(org_id, project_id, name=project_id)
    return invites.create_join_request(
        org_id=org_id,
        subject=principal.subject,
        message=body.message,
        project_id=project_id,
    )


@router.get("/v1/orgs/{org_id}/join-requests")
def list_join_requests(
    org_id: str,
    principal: Principal = Depends(require_principal),
) -> dict:
    if not org_store.get_org(org_id):
        raise ApiError(code="NOT_FOUND", message="organization not found", status_code=404)
    if not mem.can_manage_org(org_id, principal.subject):
        raise ApiError(
            code="FORBIDDEN",
            message="organization admin required",
            status_code=403,
        )
    return {"items": invites.list_join_requests(org_id)}


@router.post("/v1/orgs/{org_id}/join-requests/{request_id}/decide")
def decide_join_request(
    org_id: str,
    request_id: str,
    body: JoinDecideIn,
    principal: Principal = Depends(require_principal),
) -> dict:
    if not mem.can_manage_org(org_id, principal.subject):
        raise ApiError(
            code="FORBIDDEN",
            message="organization admin required",
            status_code=403,
        )
    try:
        return invites.decide_join_request(
            org_id=org_id,
            request_id=request_id,
            decision=body.decision,  # type: ignore[arg-type]
            actor_id=principal.subject,
            role=body.role,
            project_id=body.projectId,
        )
    except LookupError as exc:
        raise ApiError(code="NOT_FOUND", message=str(exc), status_code=404) from exc
    except ValueError as exc:
        raise ApiError(code="VALIDATION", message=str(exc), status_code=400) from exc


@router.get("/v1/orgs/{org_id}/data")
def org_data_summary(
    org_id: str,
    principal: Principal = Depends(require_principal),
) -> dict:
    if not org_store.get_org(org_id):
        raise ApiError(code="NOT_FOUND", message="organization not found", status_code=404)
    if org_id not in mem.member_org_ids(principal.subject):
        raise ApiError(code="FORBIDDEN", message="not a member", status_code=403)
    return tdata.summarize_org(org_id)


@router.post("/v1/orgs/{org_id}/data/clear")
def org_data_clear(
    org_id: str,
    principal: Principal = Depends(require_principal),
) -> dict:
    if not org_store.get_org(org_id):
        raise ApiError(code="NOT_FOUND", message="organization not found", status_code=404)
    if not mem.can_manage_org(org_id, principal.subject):
        raise ApiError(
            code="FORBIDDEN",
            message="organization admin required to clear data",
            status_code=403,
        )
    return tdata.clear_org_data(org_id, actor_id=principal.subject)


@router.delete("/v1/orgs/{org_id}")
def delete_org(
    org_id: str,
    principal: Principal = Depends(require_principal),
) -> dict:
    if not org_store.get_org(org_id):
        raise ApiError(code="NOT_FOUND", message="organization not found", status_code=404)
    if not mem.can_manage_org(org_id, principal.subject):
        raise ApiError(
            code="FORBIDDEN",
            message="organization admin required to delete organization",
            status_code=403,
        )
    try:
        return tdata.delete_org(org_id, actor_id=principal.subject)
    except ValueError as exc:
        if str(exc) == "NOT_EMPTY":
            summary = tdata.summarize_org(org_id)
            raise ApiError(
                code="NOT_EMPTY",
                message="organization still has business data; clear data first",
                status_code=409,
                details=summary,
            ) from exc
        raise ApiError(code="VALIDATION", message=str(exc), status_code=400) from exc
    except LookupError as exc:
        raise ApiError(code="NOT_FOUND", message=str(exc), status_code=404) from exc
