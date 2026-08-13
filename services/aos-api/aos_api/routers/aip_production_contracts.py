"""W2 canonical production contract API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import Field

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_production_contract_store import (
    AipProductionContractStore, ProductionContractConflict,
    ProductionContractDependencyBlocked, ProductionContractError,
    ProductionContractIdempotencyConflict, ProductionContractNotFound,
)
from aos_api.aip_production_contracts import (
    CreateBriefRequest, CreateEvidenceBundleRequest, EvidenceBundleRevision,
    ReviseBriefRequest, TaskBriefRevision,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/production-contracts", tags=["aip-production-contracts"])
_STORE = AipProductionContractStore()


class FreezeBriefRequest(AipContractModel):
    expected_version: int = Field(ge=1)


def get_store() -> AipProductionContractStore:
    return _STORE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _key(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 120:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="Idempotency-Key must be 1..120 characters", status_code=400)
    return cleaned


def _map(exc: ProductionContractError) -> ApiError:
    if isinstance(exc, ProductionContractNotFound): return ApiError(code=exc.code,message=str(exc),status_code=404)
    if isinstance(exc,(ProductionContractConflict,ProductionContractIdempotencyConflict)): return ApiError(code=exc.code,message=str(exc),status_code=409)
    if isinstance(exc,ProductionContractDependencyBlocked): return ApiError(code=exc.code,message=str(exc),status_code=422)
    return ApiError(code=exc.code,message="production contract persistence failed",status_code=503)


@router.post("/task-briefs", response_model=TaskBriefRevision, status_code=status.HTTP_201_CREATED)
def create_brief(body: CreateBriefRequest, idempotency_key: str=Header(alias="Idempotency-Key"), principal:Principal=Depends(require_principal), store:AipProductionContractStore=Depends(get_store)):
    try:return store.create_brief(_scope(principal),principal.subject,_key(idempotency_key),body)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.get("/task-briefs/{brief_id}", response_model=TaskBriefRevision)
def get_brief(brief_id:str, revision:int|None=Query(default=None,ge=1), principal:Principal=Depends(require_principal), store:AipProductionContractStore=Depends(get_store)):
    try:return store.get_brief(_scope(principal),brief_id,revision)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.post("/task-briefs/{brief_id}/revisions", response_model=TaskBriefRevision, status_code=status.HTTP_201_CREATED)
def revise_brief(brief_id:str,body:ReviseBriefRequest,idempotency_key:str=Header(alias="Idempotency-Key"),principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.revise_brief(_scope(principal),principal.subject,brief_id,_key(idempotency_key),body)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.post("/task-briefs/{brief_id}/freeze",response_model=TaskBriefRevision)
def freeze_brief(brief_id:str,body:FreezeBriefRequest,idempotency_key:str=Header(alias="Idempotency-Key"),principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.freeze_brief(_scope(principal),principal.subject,brief_id,body.expected_version,_key(idempotency_key))
    except ProductionContractError as exc:raise _map(exc) from exc


@router.post("/evidence-bundles",response_model=EvidenceBundleRevision,status_code=status.HTTP_201_CREATED)
def create_bundle(body:CreateEvidenceBundleRequest,idempotency_key:str=Header(alias="Idempotency-Key"),principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.create_evidence_bundle(_scope(principal),principal.subject,_key(idempotency_key),body)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.get("/evidence-bundles/{bundle_id}",response_model=EvidenceBundleRevision)
def get_bundle(bundle_id:str,revision:int=Query(default=1,ge=1),principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.get_evidence_bundle(_scope(principal),bundle_id,revision)
    except ProductionContractError as exc:raise _map(exc) from exc
