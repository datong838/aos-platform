"""TWA.9 — Organization list / enter."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from aos_api import membership as mem
from aos_api import orgs as org_store
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["orgs"])
log = get_logger("aos-api.orgs-router")


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
        "workspaceName": (
            "测试工作区"
            if project_id in ("dev-project", "test-workspace")
            else project_id
        ),
    }
