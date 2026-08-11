"""Read-only tenant-scoped API for AIP-4 authority records."""
# FastAPI dependency injection intentionally evaluates Depends at import time.
# ruff: noqa: B008

from __future__ import annotations

from fastapi import APIRouter, Depends

from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityNotFound,
    AipEvalAuthorityPersistenceError,
    AipEvalAuthorityStore,
)
from aos_api.aip_eval_contracts import (
    DatasetRevisionRef,
    EvalRunAuthorityRecord,
    LineageEvent,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(
    prefix="/v1/aip/eval-authority",
    tags=["aip-eval-authority"],
)
_STORE = AipEvalAuthorityStore()


def get_aip_eval_authority_store() -> AipEvalAuthorityStore:
    return _STORE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _map_error(exc: Exception) -> ApiError:
    if isinstance(exc, AipEvalAuthorityNotFound):
        return ApiError(code=exc.code, message="authority record not found", status_code=404)
    if isinstance(exc, AipEvalAuthorityPersistenceError):
        return ApiError(
            code=exc.code,
            message="eval authority persistence is unavailable",
            status_code=503,
        )
    return ApiError(
        code="AIP_EVAL_AUTHORITY_READ_FAILED",
        message="eval authority read failed",
        status_code=500,
    )


@router.get(
    "/datasets/{dataset_id}/revisions/{revision}",
    response_model=DatasetRevisionRef,
)
def get_dataset_revision(
    dataset_id: str,
    revision: int,
    principal: Principal = Depends(require_principal),
    store: AipEvalAuthorityStore = Depends(get_aip_eval_authority_store),
) -> DatasetRevisionRef:
    try:
        return store.get_dataset_revision(_scope(principal), dataset_id, revision)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/runs/{run_id}", response_model=EvalRunAuthorityRecord)
def get_eval_run(
    run_id: str,
    principal: Principal = Depends(require_principal),
    store: AipEvalAuthorityStore = Depends(get_aip_eval_authority_store),
) -> EvalRunAuthorityRecord:
    try:
        return store.get_eval_run(_scope(principal), run_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/lineage/{lineage_id}", response_model=list[LineageEvent])
def list_lineage_events(
    lineage_id: str,
    principal: Principal = Depends(require_principal),
    store: AipEvalAuthorityStore = Depends(get_aip_eval_authority_store),
) -> list[LineageEvent]:
    try:
        return store.list_lineage_events(_scope(principal), lineage_id)
    except Exception as exc:
        raise _map_error(exc) from exc


__all__ = ["router"]
