from __future__ import annotations

from fastapi import APIRouter, Depends

from aos_api.auth import Principal, require_principal
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["me"])
log = get_logger("aos-api.me")


@router.get("/v1/me")
def me(principal: Principal = Depends(require_principal)) -> dict:
    log.debug("me_probe subject=%s", principal.subject)
    return {
        "subject": principal.subject,
        "orgId": principal.org_id,
        "projectId": principal.project_id,
        "roles": principal.roles,
        "markings": principal.markings,
        "tokenKind": principal.token_kind,
    }
