"""Principal-scoped canonical DataRequirement control API."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response, Security
from fastapi.security import HTTPBearer
from pydantic import Field

from aos_api.aip_contracts import AipContractModel
from aos_api.auth import Principal, require_principal
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
from aos_api.data_requirement_store import (
    DataRequirementApplyResult,
    DataRequirementConflict,
    DataRequirementIdempotencyConflict,
    DataRequirementInvalidTransition,
    DataRequirementNotFound,
    DataRequirementStore,
    DataRequirementStoreError,
    DataRequirementValidationError,
)
from aos_api.errors import ApiError, ErrorBody
from aos_api.tenant_scope import TenantScope


_bearer = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/v1/data/requirements", tags=["data-requirements"], dependencies=[Security(_bearer)])
_ERRORS = {code: {"model": ErrorBody} for code in (400, 401, 403, 404, 409, 500)}
_WRITE_ROLES = {"admin", "developer", "data-owner"}


class DataRequirementCommand(AipContractModel):
    expected_version: int = Field(ge=0)
    revision: DataRequirementRevisionRecord


class DataRequirementCommandResult(AipContractModel):
    exact_ref: dict
    version: int
    etag: str
    replayed: bool


class FulfillmentReceiptView(AipContractModel):
    fulfillment_id: str
    receipt_id: str
    requirement_revision: int
    status: Literal["fulfilled", "partial", "rejected", "unknown"]
    artifact_refs: list[dict]
    source_readiness_ref: dict
    cutoff_at: datetime
    fulfilled_at: datetime
    content_hash: str
    created_by: str


PrincipalDependency = Annotated[Principal, Depends(require_principal)]


@lru_cache(maxsize=1)
def get_data_requirement_store() -> DataRequirementStore:
    return DataRequirementStore()


StoreDependency = Annotated[DataRequirementStore, Depends(get_data_requirement_store)]


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _require_writer(principal: Principal) -> None:
    if not _WRITE_ROLES.intersection(principal.roles):
        raise ApiError(code="AUTH_FORBIDDEN", message="DataRequirement write role required", status_code=403)


def _etag(value: str) -> str:
    return f'"{value}"'


def _map_error(exc: DataRequirementStoreError) -> ApiError:
    status = 404 if isinstance(exc, DataRequirementNotFound) else 409 if isinstance(exc, (DataRequirementConflict, DataRequirementIdempotencyConflict, DataRequirementInvalidTransition)) else 400 if isinstance(exc, DataRequirementValidationError) else 500
    return ApiError(code=exc.code, message=str(exc), status_code=status)


def _command(
    operation: str,
    requirement_id: str,
    body: DataRequirementCommand,
    principal: Principal,
    store: DataRequirementStore,
    idempotency_key: str,
    if_match: str | None,
) -> DataRequirementApplyResult:
    _require_writer(principal)
    if body.revision.requirement_id != requirement_id:
        raise ApiError(code="DATA_REQUIREMENT_ID_MISMATCH", message="path and body requirementId differ", status_code=409)
    if operation == "request":
        if if_match is not None:
            raise ApiError(code="DATA_REQUIREMENT_ETAG_CONFLICT", message="create does not accept If-Match", status_code=409)
    else:
        current = store.get_current(_scope(principal), requirement_id)
        if if_match != _etag(current.content_hash):
            raise ApiError(code="DATA_REQUIREMENT_ETAG_CONFLICT", message="If-Match must bind the current exact revision", status_code=409)
    try:
        return getattr(store, operation)(_scope(principal), principal.subject, idempotency_key, body.revision, expected_version=body.expected_version)
    except DataRequirementStoreError as exc:
        raise _map_error(exc) from exc


def _result(result: DataRequirementApplyResult, response: Response) -> DataRequirementCommandResult:
    response.headers["ETag"] = _etag(result.etag)
    return DataRequirementCommandResult(exact_ref=result.exact_ref.model_dump(mode="json", by_alias=True), version=result.version, etag=result.etag, replayed=result.replayed)


@router.post("", response_model=DataRequirementCommandResult, operation_id="dataRequirementCreate", responses=_ERRORS)
def create_requirement(body: DataRequirementCommand, response: Response, principal: PrincipalDependency, store: StoreDependency, idempotency_key: Annotated[str, Header(alias="Idempotency-Key")], if_match: Annotated[str | None, Header(alias="If-Match")] = None):
    return _result(_command("request", body.revision.requirement_id, body, principal, store, idempotency_key, if_match), response)


@router.get("/{requirement_id}", response_model=DataRequirementRevisionRecord, operation_id="dataRequirementGet", responses=_ERRORS)
def get_requirement(requirement_id: str, response: Response, principal: PrincipalDependency, store: StoreDependency):
    try:
        item = store.get_current(_scope(principal), requirement_id)
    except DataRequirementStoreError as exc:
        raise _map_error(exc) from exc
    response.headers["ETag"] = _etag(item.content_hash)
    return item


def _transition(operation: str, requirement_id: str, body: DataRequirementCommand, response: Response, principal: Principal, store: DataRequirementStore, idempotency_key: str, if_match: str):
    return _result(_command(operation, requirement_id, body, principal, store, idempotency_key, if_match), response)


@router.post("/{requirement_id}:accept", response_model=DataRequirementCommandResult, operation_id="dataRequirementAccept", responses=_ERRORS)
def accept_requirement(requirement_id: str, body: DataRequirementCommand, response: Response, principal: PrincipalDependency, store: StoreDependency, idempotency_key: Annotated[str, Header(alias="Idempotency-Key")], if_match: Annotated[str, Header(alias="If-Match")]):
    return _transition("accept", requirement_id, body, response, principal, store, idempotency_key, if_match)


@router.post("/{requirement_id}:reject", response_model=DataRequirementCommandResult, operation_id="dataRequirementReject", responses=_ERRORS)
def reject_requirement(requirement_id: str, body: DataRequirementCommand, response: Response, principal: PrincipalDependency, store: StoreDependency, idempotency_key: Annotated[str, Header(alias="Idempotency-Key")], if_match: Annotated[str, Header(alias="If-Match")]):
    return _transition("reject", requirement_id, body, response, principal, store, idempotency_key, if_match)


@router.post("/{requirement_id}:cancel", response_model=DataRequirementCommandResult, operation_id="dataRequirementCancel", responses=_ERRORS)
def cancel_requirement(requirement_id: str, body: DataRequirementCommand, response: Response, principal: PrincipalDependency, store: StoreDependency, idempotency_key: Annotated[str, Header(alias="Idempotency-Key")], if_match: Annotated[str, Header(alias="If-Match")]):
    return _transition("cancel", requirement_id, body, response, principal, store, idempotency_key, if_match)


@router.get("/{requirement_id}/receipts", response_model=list[FulfillmentReceiptView], operation_id="dataRequirementReceiptList", responses=_ERRORS)
def list_receipts(requirement_id: str, principal: PrincipalDependency, store: StoreDependency):
    try:
        return [asdict(item) for item in store.list_fulfillment_receipts(_scope(principal), requirement_id)]
    except DataRequirementStoreError as exc:
        raise _map_error(exc) from exc
