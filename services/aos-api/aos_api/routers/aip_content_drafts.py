"""Content-1 read-only Draft readiness endpoint."""
from fastapi import APIRouter, Depends

from aos_api.aip_content_contracts import ContentDraftReadinessDecision, ContentDraftReadinessRequest
from aos_api.aip_content_draft_readiness import AipContentDraftReadinessService
from aos_api.auth import Principal, require_principal
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/content/drafts", tags=["aip-content-drafts"])
_SERVICE = AipContentDraftReadinessService()


def get_content_draft_readiness_service() -> AipContentDraftReadinessService:
    return _SERVICE


@router.post("/readiness", response_model=ContentDraftReadinessDecision)
def readiness(
    body: ContentDraftReadinessRequest,
    principal: Principal = Depends(require_principal),
    service: AipContentDraftReadinessService = Depends(
        get_content_draft_readiness_service
    ),
) -> ContentDraftReadinessDecision:
    return service.evaluate(TenantScope(principal.org_id, principal.project_id), body)
