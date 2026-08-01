"""W1-12 · Evals 评测门控 API 路由。

详见 docs/palantier/20_tech/220tech_evals-engine.md。
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.evals_engine import EvalsError, EvalSuite, TestCase, get_engine

router = APIRouter(tags=["evals"])


def _map_error(err: EvalsError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


class CreateSuiteRequest(BaseModel):
    name: str
    cases: list[TestCase] = Field(default_factory=list)
    gate_threshold: float = 0.8


class RunRequest(BaseModel):
    suite_id: str
    target_type: str = "function"
    target_expr: str = ""
    reuse_latest_report: bool = False


@router.post("/v1/evals/suites")
def create_suite(req: CreateSuiteRequest):
    suite = EvalSuite(name=req.name, cases=req.cases, gate_threshold=req.gate_threshold)
    return get_engine().create_suite(suite)


@router.get("/v1/evals/suites")
def list_suites():
    return {"items": get_engine().list_suites()}


@router.get("/v1/evals/suites/{suite_id}")
def get_suite(suite_id: str):
    suite = get_engine().get_suite(suite_id)
    if suite is None:
        raise ApiError(code="NOT_FOUND", message=f"评测集 {suite_id} 不存在", status_code=404)
    return suite


@router.post("/v1/evals/run")
def run_eval(req: RunRequest):
    from aos_api.function_engine import evaluate, parse

    def target_fn(inputs: dict) -> object:
        if req.target_expr:
            return evaluate(parse(req.target_expr), inputs)
        return inputs.get("expected", "")

    engine = get_engine()
    try:
        report = engine.run(req.suite_id, target_fn)
        return report
    except EvalsError as err:
        raise _map_error(err) from err


@router.get("/v1/evals/{suite_id}/report")
def get_report(suite_id: str):
    report = get_engine().get_report(suite_id)
    if report is None:
        raise ApiError(code="NOT_FOUND", message=f"评测集 {suite_id} 暂无报告", status_code=404)
    return report


@router.post("/v1/evals/gate-check")
def gate_check(req: RunRequest):
    from aos_api.function_engine import evaluate, parse

    def target_fn(inputs: dict) -> object:
        if req.target_expr:
            return evaluate(parse(req.target_expr), inputs)
        return inputs.get("expected", "")

    engine = get_engine()
    try:
        if req.reuse_latest_report:
            suite = engine.get_suite(req.suite_id)
            report = engine.get_report(req.suite_id)
            if suite is None:
                raise EvalsError("NOT_FOUND", f"评测集 {req.suite_id} 不存在")
            if report is None or report.suite_id != req.suite_id:
                raise EvalsError("NOT_FOUND", f"评测集 {req.suite_id} 暂无可复用报告")
            return {
                "suite_id": req.suite_id,
                "gate_passed": report.gate_passed,
                "pass_rate": report.pass_rate,
                "threshold": suite.gate_threshold,
                "passed": report.passed,
                "failed": report.failed,
                "total": report.total,
                "run_at": report.run_at,
            }
        return engine.gate_check(req.suite_id, target_fn)
    except EvalsError as err:
        raise _map_error(err) from err


@router.get("/v1/evals/{suite_id}/history")
def eval_history(suite_id: str):
    return {"items": [r.model_dump() for r in get_engine().history(suite_id)]}
