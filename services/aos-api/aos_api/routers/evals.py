"""Tenant-scoped persisted Evals API for immutable Logic graph evidence."""

# FastAPI dependency injection intentionally evaluates Depends at import time.
# ruff: noqa: B008

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from aos_api.aip_eval_models import (
    EvalGateEvidence,
    EvalReportEvidence,
    LogicGraphEvalTarget,
    gate_from_report,
)
from aos_api.aip_eval_store import (
    EvalConflict,
    EvalEvidenceStore,
    EvalIntegrityError,
    EvalNotFound,
    EvalPersistenceError,
    EvalStoreError,
    EvalTargetConflict,
    EvalTargetNotFound,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.evals_engine import EvalSuite, TestCase, get_engine

router = APIRouter(tags=["evals"])
_STORE = EvalEvidenceStore()


def get_eval_store() -> EvalEvidenceStore:
    return _STORE


def _map_store_error(err: EvalStoreError) -> ApiError:
    if isinstance(err, (EvalNotFound, EvalTargetNotFound)):
        return ApiError(code=err.code, message=str(err), status_code=404)
    if isinstance(err, (EvalConflict, EvalTargetConflict)):
        details = None
        if isinstance(err, EvalTargetConflict):
            details = {
                "expected_hash": err.expected_hash,
                "current_hash": err.current_hash,
            }
        return ApiError(
            code=err.code, message=str(err), status_code=409, details=details
        )
    if isinstance(err, EvalPersistenceError):
        return ApiError(
            code=err.code,
            message="eval evidence persistence is unavailable",
            status_code=503,
        )
    if isinstance(err, EvalIntegrityError):
        return ApiError(
            code=err.code,
            message="eval evidence integrity verification failed",
            status_code=500,
        )
    return ApiError(code=err.code, message="eval evidence operation failed", status_code=500)


class CreateSuiteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    cases: list[TestCase] = Field(default_factory=list)
    gate_threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class RunRequest(BaseModel):
    suite_id: str = Field(min_length=1, max_length=160)
    target_type: Literal["logic_graph"]
    target_id: str = Field(min_length=1, max_length=160)
    target_revision: int = Field(ge=1)
    target_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_expr: str = Field(default="", max_length=32_768)
    reuse_latest_report: bool = False

    @field_validator("suite_id", "target_id")
    @classmethod
    def _non_blank_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("identifier must not be blank")
        return normalized


def _target(req: RunRequest) -> LogicGraphEvalTarget:
    return LogicGraphEvalTarget(
        target_type=req.target_type,
        target_id=req.target_id,
        target_revision=req.target_revision,
        target_hash=req.target_hash,
    )


def _run_and_persist(
    req: RunRequest,
    *,
    principal: Principal,
    store: EvalEvidenceStore,
) -> tuple[EvalSuite, EvalReportEvidence]:
    expression = req.target_expr.strip()
    if not expression:
        raise ApiError(
            code="EVAL_TARGET_REQUIRED",
            message="target_expr is required; expected-output fallback is disabled",
            status_code=422,
        )
    target = _target(req)
    try:
        suite = store.get_suite(principal.org_id, principal.project_id, req.suite_id)
        store.require_logic_target(
            principal.org_id, principal.project_id, target
        )
    except EvalStoreError as err:
        raise _map_store_error(err) from err

    from aos_api.function_engine import evaluate, parse

    try:
        parsed = parse(expression)

        def target_fn(inputs: dict) -> object:
            return evaluate(parsed, inputs)

        evaluated = get_engine().evaluate_suite(suite, target_fn)
    except Exception as exc:
        raise ApiError(
            code="EVAL_TARGET_EXECUTION_FAILED",
            message="eval target execution failed",
            status_code=422,
        ) from exc

    report = EvalReportEvidence(
        suite_id=evaluated.suite_id,
        target_type=target.target_type,
        target_id=target.target_id,
        target_revision=target.target_revision,
        target_hash=target.target_hash,
        results=evaluated.results,
        pass_rate=evaluated.pass_rate,
        passed=evaluated.passed,
        failed=evaluated.failed,
        total=evaluated.total,
        gate_passed=evaluated.gate_passed,
        run_at=evaluated.run_at,
    )
    try:
        saved = store.save_report(
            principal.org_id, principal.project_id, principal.subject, report
        )
    except EvalStoreError as err:
        raise _map_store_error(err) from err
    return suite, saved


@router.post("/v1/evals/suites")
def create_suite(
    req: CreateSuiteRequest,
    principal: Principal = Depends(require_principal),
    store: EvalEvidenceStore = Depends(get_eval_store),
) -> EvalSuite:
    suite = EvalSuite(
        name=req.name, cases=req.cases, gate_threshold=req.gate_threshold
    )
    try:
        return store.create_suite(
            principal.org_id, principal.project_id, principal.subject, suite
        )
    except EvalStoreError as err:
        raise _map_store_error(err) from err


@router.get("/v1/evals/suites")
def list_suites(
    principal: Principal = Depends(require_principal),
    store: EvalEvidenceStore = Depends(get_eval_store),
) -> dict[str, list[EvalSuite]]:
    try:
        return {"items": store.list_suites(principal.org_id, principal.project_id)}
    except EvalStoreError as err:
        raise _map_store_error(err) from err


@router.get("/v1/evals/suites/{suite_id}")
def get_suite(
    suite_id: str,
    principal: Principal = Depends(require_principal),
    store: EvalEvidenceStore = Depends(get_eval_store),
) -> EvalSuite:
    try:
        return store.get_suite(principal.org_id, principal.project_id, suite_id)
    except EvalStoreError as err:
        raise _map_store_error(err) from err


@router.post("/v1/evals/run")
def run_eval(
    req: RunRequest,
    principal: Principal = Depends(require_principal),
    store: EvalEvidenceStore = Depends(get_eval_store),
) -> EvalReportEvidence:
    _, report = _run_and_persist(req, principal=principal, store=store)
    return report


@router.get("/v1/evals/reports/{report_id}")
def get_report_by_id(
    report_id: str,
    principal: Principal = Depends(require_principal),
    store: EvalEvidenceStore = Depends(get_eval_store),
) -> EvalReportEvidence:
    try:
        return store.get_report(principal.org_id, principal.project_id, report_id)
    except EvalStoreError as err:
        raise _map_store_error(err) from err


@router.get("/v1/evals/{suite_id}/report")
def get_report(
    suite_id: str,
    principal: Principal = Depends(require_principal),
    store: EvalEvidenceStore = Depends(get_eval_store),
) -> EvalReportEvidence:
    try:
        return store.latest_report(principal.org_id, principal.project_id, suite_id)
    except EvalStoreError as err:
        raise _map_store_error(err) from err


@router.post("/v1/evals/gate-check")
def gate_check(
    req: RunRequest,
    principal: Principal = Depends(require_principal),
    store: EvalEvidenceStore = Depends(get_eval_store),
) -> EvalGateEvidence:
    try:
        if req.reuse_latest_report:
            suite = store.get_suite(
                principal.org_id, principal.project_id, req.suite_id
            )
            report = store.latest_report(
                principal.org_id,
                principal.project_id,
                req.suite_id,
                target=_target(req),
            )
        else:
            suite, report = _run_and_persist(
                req, principal=principal, store=store
            )
    except EvalStoreError as err:
        raise _map_store_error(err) from err
    return gate_from_report(report, threshold=suite.gate_threshold)


@router.get("/v1/evals/{suite_id}/history")
def eval_history(
    suite_id: str,
    principal: Principal = Depends(require_principal),
    store: EvalEvidenceStore = Depends(get_eval_store),
) -> dict[str, list[dict]]:
    try:
        items = store.history(principal.org_id, principal.project_id, suite_id)
    except EvalStoreError as err:
        raise _map_store_error(err) from err
    return {"items": [item.model_dump(mode="json") for item in items]}
