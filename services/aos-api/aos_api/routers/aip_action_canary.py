"""W5-07 canonical Action Kill and bounded Canary control API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, status

from aos_api.aip_action_canary_models import (
    CanaryPlanSnapshot,
    DecideCanaryPlanRequest,
    DecideKillPolicyRequest,
    EffectiveKillDecision,
    EvaluateKillPolicyRequest,
    KillDrillReceiptSnapshot,
    KillPolicyRevisionSnapshot,
    ProposeCanaryPlanRequest,
    ProposeKillPolicyRequest,
    SimulateKillDrillRequest,
)
from aos_api.aip_action_canary_service import AipActionCanaryError, AipActionCanaryService
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError

router = APIRouter(prefix="/v1/aip", tags=["aip-action-canary"])
_SERVICE = AipActionCanaryService()


def get_aip_action_canary_service() -> AipActionCanaryService:
    return _SERVICE


def _idem(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 200:
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="Idempotency-Key must be 1..200 characters",
            status_code=400,
        )
    return cleaned


def _map(exc: AipActionCanaryError) -> ApiError:
    return ApiError(code=exc.code, message=str(exc), status_code=exc.status_code)


@router.post(
    "/action-kill-policies",
    response_model=KillPolicyRevisionSnapshot,
    status_code=status.HTTP_201_CREATED,
)
def propose_kill_policy(
    body: ProposeKillPolicyRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipActionCanaryService = Depends(get_aip_action_canary_service),
) -> KillPolicyRevisionSnapshot:
    try:
        return service.propose_kill_policy(principal, _idem(idempotency_key), body)
    except AipActionCanaryError as exc:
        raise _map(exc) from exc


@router.post(
    "/action-kill-policies/{policy_id}/revisions/{revision}/decision",
    response_model=KillPolicyRevisionSnapshot,
)
def decide_kill_policy(
    policy_id: str,
    revision: int,
    body: DecideKillPolicyRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipActionCanaryService = Depends(get_aip_action_canary_service),
) -> KillPolicyRevisionSnapshot:
    try:
        return service.decide_kill_policy(
            principal, policy_id, revision, _idem(idempotency_key), body
        )
    except AipActionCanaryError as exc:
        raise _map(exc) from exc


@router.post(
    "/action-kill-policies/effective",
    response_model=EffectiveKillDecision,
)
def evaluate_kill_policy(
    body: EvaluateKillPolicyRequest,
    principal: Principal = Depends(require_principal),
    service: AipActionCanaryService = Depends(get_aip_action_canary_service),
) -> EffectiveKillDecision:
    try:
        return service.evaluate(principal, body)
    except AipActionCanaryError as exc:
        raise _map(exc) from exc


@router.post(
    "/action-canary-plans",
    response_model=CanaryPlanSnapshot,
    status_code=status.HTTP_201_CREATED,
)
def propose_canary_plan(
    body: ProposeCanaryPlanRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipActionCanaryService = Depends(get_aip_action_canary_service),
) -> CanaryPlanSnapshot:
    try:
        return service.propose_canary_plan(principal, _idem(idempotency_key), body)
    except AipActionCanaryError as exc:
        raise _map(exc) from exc


@router.post(
    "/action-canary-plans/{plan_id}/revisions/{revision}/decision",
    response_model=CanaryPlanSnapshot,
)
def decide_canary_plan(
    plan_id: str,
    revision: int,
    body: DecideCanaryPlanRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipActionCanaryService = Depends(get_aip_action_canary_service),
) -> CanaryPlanSnapshot:
    try:
        return service.decide_canary_plan(
            principal, plan_id, revision, _idem(idempotency_key), body
        )
    except AipActionCanaryError as exc:
        raise _map(exc) from exc


@router.post(
    "/action-kill-drills/simulations",
    response_model=KillDrillReceiptSnapshot,
    status_code=status.HTTP_201_CREATED,
)
def simulate_kill_drill(
    body: SimulateKillDrillRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipActionCanaryService = Depends(get_aip_action_canary_service),
) -> KillDrillReceiptSnapshot:
    try:
        return service.simulate_kill_drill(principal, _idem(idempotency_key), body)
    except AipActionCanaryError as exc:
        raise _map(exc) from exc
