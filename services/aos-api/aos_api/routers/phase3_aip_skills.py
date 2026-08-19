"""AIP skill template list + publish-evaluated control plane."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query

from aos_api.aip_agent_registry_contracts import (
    PublishEvaluatedSkillRevisionRequest,
    SkillTemplateRevision,
    TemplateLifecycle,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryError,
    AipAgentRegistryNotFound,
    AipAgentRegistryPersistenceError,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_contracts import TenantContext
from aos_api.aip_skill_publication_service import AipSkillPublicationService
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/aip", tags=["aip-skills"])
_SKILLS = AipSkillRegistry()
_PUBLICATION = AipSkillPublicationService()


class SkillListResponse(BaseModel):
    tenant: TenantContext
    items: list[SkillTemplateRevision]
    count: int = Field(ge=0)


class PublishEvaluatedSkillResponse(BaseModel):
    tenant: TenantContext
    skill: SkillTemplateRevision
    receiptId: str
    operation: str


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _idem(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 120:
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="Idempotency-Key must be 1..120 characters",
            status_code=400,
        )
    return cleaned


def _map_error(exc: AipAgentRegistryError) -> ApiError:
    if isinstance(exc, AipAgentRegistryNotFound):
        return ApiError(code="AIP_NOT_FOUND", message=str(exc), status_code=404)
    if isinstance(exc, AipAgentRegistryConflict):
        return ApiError(code="AIP_CONFLICT", message=str(exc), status_code=409)
    if isinstance(exc, AipAgentRegistryTransitionBlocked):
        return ApiError(code="AIP_TRANSITION_BLOCKED", message=str(exc), status_code=409)
    if isinstance(exc, AipAgentRegistryPersistenceError):
        return ApiError(code="AIP_PERSISTENCE", message=str(exc), status_code=500)
    return ApiError(code="AIP_ERROR", message=str(exc), status_code=400)


@router.get("/skills", response_model=SkillListResponse)
def list_skills(
    principal: Principal = Depends(require_principal),
    lifecycle: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> SkillListResponse:
    life = None
    if lifecycle:
        try:
            life = TemplateLifecycle(lifecycle)
        except ValueError as exc:
            raise ApiError(
                code="AIP_INVALID_ARGUMENT",
                message="lifecycle must be a known TemplateLifecycle",
                status_code=400,
            ) from exc
    try:
        items = _SKILLS.list_skills(lifecycle=life, limit=limit)
    except ValueError as exc:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message=str(exc), status_code=400) from exc
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return SkillListResponse(
        tenant=TenantContext(org_id=principal.org_id, project_id=principal.project_id),
        items=items,
        count=len(items),
    )


@router.post("/skills/publish-evaluated", response_model=PublishEvaluatedSkillResponse)
def publish_evaluated_skill(
    body: PublishEvaluatedSkillRevisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> PublishEvaluatedSkillResponse:
    scope = _scope(principal)
    # Prefer header idempotency; body also carries key for service hash.
    header_key = _idem(idempotency_key)
    if body.idempotency_key.strip() != header_key:
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="Idempotency-Key header must match body.idempotencyKey",
            status_code=400,
        )
    try:
        skill, receipt = _PUBLICATION.publish_evaluated_revision(
            scope,
            body,
            actor=principal.subject or "aip-skill-publish",
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return PublishEvaluatedSkillResponse(
        tenant=TenantContext(org_id=principal.org_id, project_id=principal.project_id),
        skill=skill,
        receiptId=str(getattr(receipt, "receipt_id", None) or getattr(receipt, "id", "")),
        operation=str(getattr(receipt, "operation", "skill_template.publish_evaluated")),
    )
