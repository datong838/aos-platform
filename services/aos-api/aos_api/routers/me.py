from __future__ import annotations

from fastapi import APIRouter, Depends

from aos_api.auth import Principal, require_principal
from aos_api.logging_facade import get_logger
from aos_api import orgs as org_store
from aos_api import membership as mem

router = APIRouter(tags=["me"])
log = get_logger("aos-api.me")


def _workspace_name(project_id: str) -> str:
    """TWA.2 · 产品名；技术 id 仍为 project_id。"""
    if project_id in ("dev-project", "test-workspace"):
        return "测试工作区"
    return project_id


@router.get("/v1/me")
def me(principal: Principal = Depends(require_principal)) -> dict:
    mem.ensure_default_membership(
        principal.org_id, principal.project_id, principal.subject
    )
    ws = _workspace_name(principal.project_id)
    org_items = org_store.list_orgs_for_subject(principal.subject)
    if not any(i["id"] == principal.org_id for i in org_items):
        org_store.ensure_org(principal.org_id)
        cur = org_store.get_org(principal.org_id)
        if cur:
            org_items = [cur, *org_items]
    log.info(
        "me_probe subject=%s org=%s project=%s workspace=%s",
        principal.subject,
        principal.org_id,
        principal.project_id,
        ws,
    )
    return {
        "subject": principal.subject,
        "orgId": principal.org_id,
        "orgName": org_store.org_name(principal.org_id),
        "projectId": principal.project_id,
        "workspaceName": ws,
        "roles": principal.roles,
        "markings": principal.markings,
        "tokenKind": principal.token_kind,
        "orgs": org_items,
    }
