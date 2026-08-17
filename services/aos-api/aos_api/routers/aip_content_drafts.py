"""Content-1 Draft readiness and governed registration endpoints."""
from fastapi import APIRouter, Depends, Header

from aos_api.aip_content_contracts import (
    ContentDraftReadinessDecision,
    ContentDraftReadinessRequest,
    ContentDraftRegisterRequest,
    ContentDraftRegistrationReceipt,
)
from aos_api.aip_content_draft_readiness import AipContentDraftReadinessService
from aos_api.aip_content_draft_store import (
    AipContentDraftStore,
    ContentDraftRegistrationBlocked,
    ContentDraftRegistrationConflict,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/content/drafts", tags=["aip-content-drafts"])
_SERVICE = AipContentDraftReadinessService()
_STORE = AipContentDraftStore()


def get_content_draft_readiness_service() -> AipContentDraftReadinessService:
    return _SERVICE


def get_content_draft_store() -> AipContentDraftStore:
    return _STORE


@router.post("/readiness", response_model=ContentDraftReadinessDecision)
def readiness(
    body: ContentDraftReadinessRequest,
    principal: Principal = Depends(require_principal),
    service: AipContentDraftReadinessService = Depends(
        get_content_draft_readiness_service
    ),
) -> ContentDraftReadinessDecision:
    return service.evaluate(TenantScope(principal.org_id, principal.project_id), body)


@router.post("/registrations", response_model=ContentDraftRegistrationReceipt)
def register_draft(
    body: ContentDraftRegisterRequest,
    idempotency_key: str = Header(
        min_length=1, max_length=200, alias="Idempotency-Key"
    ),
    principal: Principal = Depends(require_principal),
    store: AipContentDraftStore = Depends(get_content_draft_store),
) -> ContentDraftRegistrationReceipt:
    if not {role.lower() for role in principal.roles}.intersection(
        {"admin", "executor", "aip_executor"}
    ):
        raise ApiError(
            code="AIP_SCOPE_FORBIDDEN",
            message="trusted Content Draft executor role required",
            status_code=403,
        )
    try:
        return store.register(
            TenantScope(principal.org_id, principal.project_id),
            principal.subject,
            idempotency_key,
            body,
        )
    except ContentDraftRegistrationConflict as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=409) from exc
    except ContentDraftRegistrationBlocked as exc:
        raise ApiError(code=exc.code, message=str(exc), status_code=503) from exc
