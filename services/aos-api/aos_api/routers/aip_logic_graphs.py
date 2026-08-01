"""Canonical Stage A1 API for persisted AIP Logic canvas graphs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from aos_api.aip_logic_graph_models import (
    CreateLogicGraphRequest,
    LogicGraphSnapshot,
    LogicGraphValidationError,
    LogicGraphValidationResult,
    ReplaceLogicGraphRequest,
    ValidateLogicGraphRequest,
    validate_logic_graph,
)
from aos_api.aip_logic_graph_store import (
    LogicGraphConflict,
    LogicGraphIntegrityError,
    LogicGraphNotFound,
    LogicGraphStore,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError


router = APIRouter(prefix="/v1/aip/logic/graphs", tags=["aip-logic-graphs"])
_STORE = LogicGraphStore()


class LogicGraphListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LogicGraphSnapshot] = Field(default_factory=list)
    count: int = 0


def get_logic_graph_store() -> LogicGraphStore:
    return _STORE


def _invalid_graph(exc: LogicGraphValidationError) -> ApiError:
    return ApiError(
        code="LOGIC_GRAPH_INVALID",
        message="logic graph validation failed",
        status_code=422,
        details={"issues": [issue.model_dump(exclude_none=True) for issue in exc.issues]},
    )


def _not_found(exc: LogicGraphNotFound) -> ApiError:
    return ApiError(code=exc.code, message=str(exc), status_code=404)


def _conflict(exc: LogicGraphConflict) -> ApiError:
    return ApiError(
        code=exc.code,
        message=str(exc),
        status_code=409,
        details={
            "expected_revision": exc.expected_revision,
            "current_revision": exc.current_revision,
        },
    )


def _integrity_error(exc: LogicGraphIntegrityError) -> ApiError:
    return ApiError(
        code=exc.code,
        message="stored logic graph failed checksum verification",
        status_code=500,
    )


@router.post("", response_model=LogicGraphSnapshot, status_code=status.HTTP_201_CREATED)
def create_logic_graph(
    body: CreateLogicGraphRequest,
    principal: Principal = Depends(require_principal),
    store: LogicGraphStore = Depends(get_logic_graph_store),
) -> LogicGraphSnapshot:
    try:
        return store.create(
            principal.org_id, principal.project_id, principal.subject, body
        )
    except LogicGraphValidationError as exc:
        raise _invalid_graph(exc) from exc
    except LogicGraphConflict as exc:
        raise _conflict(exc) from exc
    except LogicGraphIntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.get("", response_model=LogicGraphListResponse)
def list_logic_graphs(
    principal: Principal = Depends(require_principal),
    store: LogicGraphStore = Depends(get_logic_graph_store),
) -> LogicGraphListResponse:
    try:
        items = store.list(principal.org_id, principal.project_id)
    except LogicGraphIntegrityError as exc:
        raise _integrity_error(exc) from exc
    return LogicGraphListResponse(items=items, count=len(items))


@router.post("/validate", response_model=LogicGraphValidationResult)
def validate_logic_graph_draft(
    body: ValidateLogicGraphRequest,
    _principal: Principal = Depends(require_principal),
) -> LogicGraphValidationResult:
    return validate_logic_graph(body)


@router.get("/{graph_id}", response_model=LogicGraphSnapshot)
def get_logic_graph(
    graph_id: str,
    principal: Principal = Depends(require_principal),
    store: LogicGraphStore = Depends(get_logic_graph_store),
) -> LogicGraphSnapshot:
    try:
        return store.get(principal.org_id, principal.project_id, graph_id)
    except LogicGraphNotFound as exc:
        raise _not_found(exc) from exc
    except LogicGraphIntegrityError as exc:
        raise _integrity_error(exc) from exc


@router.put("/{graph_id}", response_model=LogicGraphSnapshot)
def replace_logic_graph(
    graph_id: str,
    body: ReplaceLogicGraphRequest,
    principal: Principal = Depends(require_principal),
    store: LogicGraphStore = Depends(get_logic_graph_store),
) -> LogicGraphSnapshot:
    try:
        return store.replace(
            principal.org_id,
            principal.project_id,
            graph_id,
            principal.subject,
            body,
        )
    except LogicGraphValidationError as exc:
        raise _invalid_graph(exc) from exc
    except LogicGraphNotFound as exc:
        raise _not_found(exc) from exc
    except LogicGraphConflict as exc:
        raise _conflict(exc) from exc
    except LogicGraphIntegrityError as exc:
        raise _integrity_error(exc) from exc
