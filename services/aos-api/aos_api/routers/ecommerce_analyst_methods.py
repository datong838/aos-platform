"""Governed descriptive method configuration for the ecommerce analyst."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field, field_validator

from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef, MethodRevision
from aos_api.ecommerce_analyst_authority_store import (
    AnalystAuthorityConflict,
    AnalystAuthorityIdempotencyConflict,
    AnalystAuthorityNotFound,
    EcommerceAnalystAuthorityStore,
    canonical_hash,
)
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


router = APIRouter(prefix="/v1/ecommerce/analyst/methods", tags=["ecommerce-analyst-methods"])
_STORE = EcommerceAnalystAuthorityStore()


class PublishMethodRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_id: str = Field(alias="methodId", min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    algorithm: Literal["descriptive_snapshot_v1"]
    insight_kind: Literal["observation"] = Field(alias="insightKind")
    min_source_items: int = Field(alias="minSourceItems", strict=True, ge=1, le=100)
    max_source_age_seconds: int = Field(alias="maxSourceAgeSeconds", strict=True, ge=1, le=31536000)
    limitations: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(min_length=1, max_length=50)
    expected_version: int = Field(alias="expectedVersion", strict=True, ge=0)
    prior_ref: AnalystExactRef | None = Field(default=None, alias="priorRef")
    created_at: datetime = Field(alias="createdAt")

    @field_validator("created_at")
    @classmethod
    def _aware_created_at(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("createdAt must include a timezone")
        return value


class PublishMethodResponse(BaseModel):
    exact_ref: AnalystExactRef = Field(alias="exactRef")
    method: MethodRevision


def get_method_store() -> EcommerceAnalystAuthorityStore:
    return _STORE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _error(exc: Exception) -> ApiError:
    if isinstance(exc, AnalystAuthorityNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, (AnalystAuthorityConflict, AnalystAuthorityIdempotencyConflict)):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    return ApiError(code="ECOMMERCE_ANALYST_METHOD_ERROR", message="method authority unavailable", status_code=500)


@router.post("", response_model=PublishMethodResponse, status_code=201)
def publish_method(
    body: PublishMethodRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120),
    principal: Principal = Depends(require_principal),
    store: EcommerceAnalystAuthorityStore = Depends(get_method_store),
) -> PublishMethodResponse:
    if not {role.lower() for role in principal.roles}.intersection({"admin", "analyst_editor"}):
        raise ApiError(code="AIP_SCOPE_FORBIDDEN", message="analyst method editor role required", status_code=403)
    key = idempotency_key.strip()
    if not key or key != idempotency_key:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="invalid Idempotency-Key", status_code=400)
    if body.expected_version == 0 and body.prior_ref is not None:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="initial method cannot have priorRef", status_code=422)
    if body.expected_version > 0 and body.prior_ref is None:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="successor method requires priorRef", status_code=422)
    item = MethodRevision(
        tenant={"orgId": principal.org_id, "projectId": principal.project_id},
        methodId=body.method_id, revision=body.expected_version + 1,
        version=body.expected_version + 1, priorRef=body.prior_ref,
        contentHash="0" * 64, createdBy=principal.subject,
        createdAt=body.created_at, name=body.name,
        description=body.description, algorithm=body.algorithm,
        insightKind=body.insight_kind, minSourceItems=body.min_source_items,
        maxSourceAgeSeconds=body.max_source_age_seconds, limitations=body.limitations,
    )
    item = item.model_copy(update={"content_hash": canonical_hash(
        item.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
    )})
    try:
        ref = store.publish_method(_scope(principal), principal.subject, key, item,
                                   expected_version=body.expected_version)
        return PublishMethodResponse(exactRef=ref, method=store.get_method_exact(_scope(principal), ref))
    except (AnalystAuthorityConflict, AnalystAuthorityIdempotencyConflict, AnalystAuthorityNotFound) as exc:
        raise _error(exc) from exc


@router.get("/receipts/{idempotency_key}", response_model=AnalystExactRef | None)
def find_method_receipt(
    idempotency_key: str,
    principal: Principal = Depends(require_principal),
    store: EcommerceAnalystAuthorityStore = Depends(get_method_store),
) -> AnalystExactRef | None:
    if not {role.lower() for role in principal.roles}.intersection({"admin", "analyst_editor"}):
        raise ApiError(code="AIP_SCOPE_FORBIDDEN", message="analyst method editor role required", status_code=403)
    return store.find_method_publication_receipt(_scope(principal), idempotency_key)


@router.get("/{method_id}/current", response_model=MethodRevision)
def get_method_current(
    method_id: str,
    principal: Principal = Depends(require_principal),
    store: EcommerceAnalystAuthorityStore = Depends(get_method_store),
) -> MethodRevision:
    try:
        return store.get_method_current(_scope(principal), method_id)
    except AnalystAuthorityNotFound as exc:
        raise _error(exc) from exc


@router.get("/{method_id}/revisions/{revision}/{content_hash}", response_model=MethodRevision)
def get_method_exact(
    method_id: str,
    revision: int,
    content_hash: str,
    principal: Principal = Depends(require_principal),
    store: EcommerceAnalystAuthorityStore = Depends(get_method_store),
) -> MethodRevision:
    try:
        ref = AnalystExactRef(resourceType="MethodRevision", resourceId=method_id,
                              revision=revision, contentHash=content_hash)
        return store.get_method_exact(_scope(principal), ref)
    except AnalystAuthorityNotFound as exc:
        raise _error(exc) from exc
