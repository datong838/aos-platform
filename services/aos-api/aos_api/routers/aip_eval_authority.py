"""Tenant-scoped authority reads and explicit queue-only Skill preparation."""
# FastAPI dependency injection intentionally evaluates Depends at import time.
# ruff: noqa: B008

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import JSONResponse
from pydantic import model_validator

from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound
from aos_api.aip_contracts import AipContractModel

from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityNotFound,
    AipEvalAuthorityConflict,
    AipEvalAuthorityPersistenceError,
    AipEvalAuthorityStore,
)
from aos_api.aip_eval_contracts import (
    DatasetRevisionRef,
    AssetRevisionRef,
    AssetType,
    EvalRunAuthorityRecord,
    EvalSuiteRevision,
    LineageEvent,
)
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError, error_payload
from aos_api.ecommerce_skill_eval_queue import queue_skill_eval, skill_eval_queue_run_id
from aos_api.tenant_scope import TenantScope

router = APIRouter(
    prefix="/v1/aip/eval-authority",
    tags=["aip-eval-authority"],
)
_STORE = AipEvalAuthorityStore()
_REGISTRY = AipEvalPackRegistry()


def get_aip_eval_authority_store() -> AipEvalAuthorityStore:
    return _STORE


def get_aip_eval_pack_registry() -> AipEvalPackRegistry:
    return _REGISTRY


class QueueSkillEvalRequest(AipContractModel):
    suite_ref: AssetRevisionRef

    @model_validator(mode="after")
    def exact_suite(self):
        ref = self.suite_ref
        if (ref.asset_type is not AssetType.EVAL_SUITE or not ref.revision.isdecimal()
                or int(ref.revision) < 1 or str(int(ref.revision)) != ref.revision):
            raise ValueError("exact positive EvalSuite reference required")
        return self


def get_skill_eval_queue():
    return queue_skill_eval


@router.post("/skill-runs", response_model=EvalRunAuthorityRecord)
def queue_skill_run(
    body: QueueSkillEvalRequest,
    response: Response,
    principal: Principal = Depends(require_principal),
    idempotency_key: str = Header(min_length=1, max_length=200, alias="Idempotency-Key"),
    prepare=Depends(get_skill_eval_queue),
):
    """Persist metadata only; never start Target, Judge, Host or Provider."""
    if not {"admin", "owner"}.intersection(principal.roles):
        raise ApiError(code="AIP_SKILL_EVAL_QUEUE_FORBIDDEN", message="无权创建评测运行", status_code=403)
    if idempotency_key != idempotency_key.strip():
        raise ApiError(code="AIP_SKILL_EVAL_QUEUE_KEY_INVALID", message="请求标识不能有首尾空格", status_code=422)
    scope = _scope(principal)
    run_id = skill_eval_queue_run_id(scope, idempotency_key)
    location = "/v1/aip/eval-authority/runs/" + run_id
    headers = {"Cache-Control": "no-store", "Location": location}
    try:
        result = prepare(scope, body.suite_ref, idempotency_key=idempotency_key, actor=principal.subject)
        if (result.tenant.org_id, result.tenant.project_id) != scope.key or result.run_id != run_id:
            raise RuntimeError("queued result scope or identity differs")
    except (AipEvalAuthorityNotFound, AipAgentRegistryNotFound):
        return JSONResponse(status_code=404, headers=headers, content=error_payload(
            code="AIP_SKILL_EVAL_SOURCE_NOT_FOUND", message="评测来源或目标版本不存在"))
    except (AipEvalAuthorityConflict, ValueError):
        return JSONResponse(status_code=409, headers=headers, content=error_payload(
            code="AIP_SKILL_EVAL_QUEUE_CONFLICT", message="评测来源或请求绑定不符合当前要求"))
    except Exception:
        return JSONResponse(status_code=503, headers=headers, content=error_payload(
            code="AIP_SKILL_EVAL_QUEUE_OUTCOME_UNKNOWN",
            message="结果尚未确认，请读取原运行核对，不要重复提交",
            details={"runId": run_id, "readUrl": location, "outcomeUnknown": True}))
    response.headers.update(headers)
    return result


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


@router.get("/datasets", response_model=list[DatasetRevisionRef])
def list_dataset_revisions(
    principal: Principal = Depends(require_principal),
    store: AipEvalAuthorityStore = Depends(get_aip_eval_authority_store),
) -> list[DatasetRevisionRef]:
    try:
        return store.list_dataset_revisions(_scope(principal))
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/suites", response_model=list[EvalSuiteRevision])
def list_suite_revisions(
    principal: Principal = Depends(require_principal),
    registry: AipEvalPackRegistry = Depends(get_aip_eval_pack_registry),
) -> list[EvalSuiteRevision]:
    try:
        return registry.list_suite_revisions(_scope(principal))
    except Exception as exc:
        raise _map_error(exc) from exc


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
