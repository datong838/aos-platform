"""W1-1 · Function 表达式引擎 API 路由。

暴露 /v1/functions/eval 与 /v1/functions/typecheck 两个端点，
引擎层 FunctionError 统一映射为现有 ApiError 错误体系。

详见 docs/palantier/20_tech/220tech_function-engine.md。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.function_engine import (
    FunctionError,
    TypeInferer,
    evaluate,
    parse,
)

router = APIRouter(tags=["functions"])


class EvalRequest(BaseModel):
    expression: str
    context: dict[str, Any] = Field(default_factory=dict)


class EvalResponse(BaseModel):
    result: Any
    type: str


class TypeCheckRequest(BaseModel):
    expression: str
    context_schema: dict[str, str] = Field(default_factory=dict)


class TypeCheckResponse(BaseModel):
    ok: bool
    inferred_type: str | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)


def _map_error(err: FunctionError) -> ApiError:
    return ApiError(
        code=err.code,
        message=err.message,
        status_code=400,
        details={"position": err.position, "detail": err.detail},
    )


@router.post("/v1/functions/eval")
def eval_expression(req: EvalRequest) -> EvalResponse:
    try:
        expr = parse(req.expression)
        result = evaluate(expr, req.context)
    except FunctionError as err:
        raise _map_error(err) from err
    return EvalResponse(result=result, type=_result_type(result))


@router.post("/v1/functions/typecheck")
def typecheck_expression(req: TypeCheckRequest) -> TypeCheckResponse:
    try:
        expr = parse(req.expression)
    except FunctionError as err:
        return TypeCheckResponse(
            ok=False,
            errors=[
                {
                    "code": err.code,
                    "message": err.message,
                    "position": err.position,
                }
            ],
        )
    inferer = TypeInferer(req.context_schema)
    inferred = inferer.infer(expr)
    if inferer.errors:
        return TypeCheckResponse(
            ok=False,
            inferred_type=inferred,
            errors=[
                {"code": e.code, "message": e.message, "position": e.position}
                for e in inferer.errors
            ],
        )
    return TypeCheckResponse(ok=True, inferred_type=inferred)


def _result_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (list, tuple)):
        return "array"
    return "object"


# --- W1-10 沙箱 / 可组合 / TS 类型生成 --- #
from aos_api.function_sandbox import (
    FunctionComposer,
    FunctionDef,
    SandboxedEvaluator,
    TypeGenerator,
)


class SandboxEvalRequest(BaseModel):
    expression: str
    context: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = 5000


class ComposeRequest(BaseModel):
    functions: list[dict[str, Any]]
    entry: str
    context: dict[str, Any] = Field(default_factory=dict)


class TypeScriptRequest(BaseModel):
    expression: str
    context_schema: dict[str, str] = Field(default_factory=dict)


@router.post("/v1/functions/sandbox/eval")
def sandbox_eval(req: SandboxEvalRequest):
    sb = SandboxedEvaluator()
    sb.TIMEOUT_SEC = req.timeout_ms / 1000.0
    try:
        result = sb.eval(req.expression, req.context)
    except FunctionError as err:
        raise _map_error(err) from err
    return {"result": result, "type": _result_type(result)}


@router.post("/v1/functions/compose")
def compose_functions(req: ComposeRequest):
    defs = [
        FunctionDef(
            name=d["name"],
            expression=d["expression"],
            params=d.get("params", {}),
        )
        for d in req.functions
    ]
    composer = FunctionComposer()
    composer.register(defs)
    try:
        result = composer.call(req.entry, req.context)
    except FunctionError as err:
        raise _map_error(err) from err
    return {"result": result, "type": _result_type(result)}


@router.post("/v1/functions/typescript")
def generate_typescript(req: TypeScriptRequest):
    gen = TypeGenerator()
    try:
        ts_type = gen.generate(req.expression, req.context_schema)
    except FunctionError as err:
        raise _map_error(err) from err
    return {"typescript": ts_type}
