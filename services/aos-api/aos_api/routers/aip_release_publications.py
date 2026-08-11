"""Canonical AIP-4 E2 release-gate and append-only publication endpoints."""
# FastAPI dependency injection intentionally evaluates Depends at import time.
# ruff: noqa: B008
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from aos_api.aip_eval_contracts import PublicationEvent, ReleaseGateDecision
from aos_api.aip_release_publication_models import (
    DeriveReleaseGateRequest,
    PublishReleaseRequest,
    RevokePublicationRequest,
)
from aos_api.aip_release_publication_service import (
    AipPublicationAlreadyRevoked,
    AipReleaseAssetUnsupported,
    AipReleaseGateRejected,
    AipReleasePublicationConflict,
    AipReleasePublicationIntegrityError,
    AipReleasePublicationNotFound,
    AipReleasePublicationPersistenceError,
    AipReleasePublicationService,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip", tags=["aip-release-publications"])
_SERVICE = AipReleasePublicationService()


def get_aip_release_publication_service() -> AipReleasePublicationService:
    return _SERVICE


def _map_error(exc: Exception) -> ApiError:
    if isinstance(exc, AipReleasePublicationNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(
        exc,
        (
            AipReleasePublicationConflict,
            AipPublicationAlreadyRevoked,
        ),
    ):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, (AipReleaseGateRejected, AipReleaseAssetUnsupported)):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    if isinstance(exc, AipReleasePublicationIntegrityError):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    if isinstance(exc, AipReleasePublicationPersistenceError):
        return ApiError(
            code=exc.code,
            message="release publication persistence is unavailable",
            status_code=503,
        )
    return ApiError(
        code="AIP_RELEASE_PUBLICATION_FAILED",
        message="release publication failed",
        status_code=500,
    )


@router.post(
    "/release-gates/derive",
    response_model=ReleaseGateDecision,
    status_code=status.HTTP_201_CREATED,
)
def derive_release_gate(
    body: DeriveReleaseGateRequest,
    principal: Principal = Depends(require_principal),
    service: AipReleasePublicationService = Depends(
        get_aip_release_publication_service
    ),
) -> ReleaseGateDecision:
    try:
        return service.derive_gate(
            TenantScope(principal.org_id, principal.project_id),
            actor=principal.subject,
            request=body,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/publications/logic",
    response_model=PublicationEvent,
    status_code=status.HTTP_201_CREATED,
)
def publish_logic_revision(
    body: PublishReleaseRequest,
    principal: Principal = Depends(require_principal),
    service: AipReleasePublicationService = Depends(
        get_aip_release_publication_service
    ),
) -> PublicationEvent:
    try:
        return service.publish(
            TenantScope(principal.org_id, principal.project_id),
            actor=principal.subject,
            request=body,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/publications/{publication_id}/revoke",
    response_model=PublicationEvent,
    status_code=status.HTTP_201_CREATED,
)
def revoke_publication(
    publication_id: str,
    body: RevokePublicationRequest,
    principal: Principal = Depends(require_principal),
    service: AipReleasePublicationService = Depends(
        get_aip_release_publication_service
    ),
) -> PublicationEvent:
    try:
        return service.revoke(
            TenantScope(principal.org_id, principal.project_id),
            publication_id=publication_id,
            actor=principal.subject,
            request=body,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


__all__ = ["get_aip_release_publication_service", "router"]
