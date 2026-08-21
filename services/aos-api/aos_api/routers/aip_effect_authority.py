"""EffectReview / EffectMaturity authority API (W-L19)."""

# ruff: noqa: B008
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from aos_api.aip_effect_review import (
    CreateEffectReviewRequest,
    EffectAxisSnapshot,
    EffectMaturityDecision,
    EffectReviewRevision,
    EvaluateEffectMaturityRequest,
)
from aos_api.aip_effect_review_store import (
    AipEffectReviewConflict,
    AipEffectReviewNotFound,
    AipEffectReviewStore,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/effect-authority", tags=["aip-effect-authority"])
_STORE = AipEffectReviewStore()


def get_aip_effect_review_store() -> AipEffectReviewStore:
    return _STORE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _require_role(principal: Principal) -> None:
    if not {role.lower() for role in principal.roles}.intersection(
        {"admin", "executor", "aip_executor"}
    ):
        raise ApiError(
            code="AIP_SCOPE_FORBIDDEN",
            message="trusted effect authority role required",
            status_code=403,
        )


def _map_error(exc: Exception) -> ApiError:
    if isinstance(exc, AipEffectReviewNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, AipEffectReviewConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    return ApiError(
        code="AIP_EFFECT_REVIEW_FAILED",
        message="effect authority operation failed",
        status_code=500,
    )


@router.post("/reviews", response_model=EffectReviewRevision)
def create_review(
    body: CreateEffectReviewRequest,
    principal: Principal = Depends(require_principal),
    store: AipEffectReviewStore = Depends(get_aip_effect_review_store),
) -> EffectReviewRevision:
    _require_role(principal)
    try:
        return store.create_review(
            _scope(principal), body, principal.subject, now=datetime.now(UTC)
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/reviews/{subject_id}", response_model=EffectReviewRevision)
def get_review(
    subject_id: str,
    principal: Principal = Depends(require_principal),
    store: AipEffectReviewStore = Depends(get_aip_effect_review_store),
) -> EffectReviewRevision:
    try:
        return store.get_latest_review(_scope(principal), subject_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/maturity", response_model=EffectMaturityDecision)
def evaluate_maturity(
    body: EvaluateEffectMaturityRequest,
    principal: Principal = Depends(require_principal),
    store: AipEffectReviewStore = Depends(get_aip_effect_review_store),
) -> EffectMaturityDecision:
    _require_role(principal)
    try:
        return store.evaluate_maturity(
            _scope(principal), body, principal.subject, now=datetime.now(UTC)
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/axes/{subject_id}", response_model=EffectAxisSnapshot)
def get_axes(
    subject_id: str,
    principal: Principal = Depends(require_principal),
    store: AipEffectReviewStore = Depends(get_aip_effect_review_store),
) -> EffectAxisSnapshot:
    try:
        return store.get_axis_snapshot(_scope(principal), subject_id)
    except Exception as exc:
        raise _map_error(exc) from exc
