"""Phase 4 · Ontology Functions 路由 (functions + tests)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.ontology_function_engine import FunctionParam, get_function_engine

router = APIRouter(prefix="/v1/ontology", tags=["ontology-functions"])


class FunctionParamPayload(BaseModel):
    name: str
    datatype: str = "string"
    required: bool = True
    default: Any = None
    description: str = ""


class UpdateFunctionRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    body: str | None = None
    return_type: str | None = None
    status: str | None = None
    category: str | None = None
    # W3-C4 · 允许保存参数表
    params: list[FunctionParamPayload] | None = None


class AddTestRequest(BaseModel):
    name: str
    inputs: dict[str, Any] = {}
    expected: Any = None
    run: bool = False


class QuickTestRequest(BaseModel):
    """W3-C4 · 试跑面板薄封装。"""
    payload: dict[str, Any] = {}
    name: str = "adhoc"


@router.get("/functions")
async def list_functions(
    status: str | None = Query(None),
    category: str | None = Query(None),
) -> dict[str, Any]:
    """W3-C4 · 函数列表（引擎 list_functions 已有，补路由）。"""
    eng = get_function_engine()
    items = eng.list_functions(status=status, category=category)
    return {"items": [f.model_dump() for f in items], "count": len(items)}


@router.get("/functions/{fn_id}")
async def get_function(fn_id: str) -> dict[str, Any]:
    eng = get_function_engine()
    fn = eng.get_function(fn_id)
    if fn is None:
        raise HTTPException(404, f"Function {fn_id} not found")
    return fn.model_dump()


@router.put("/functions/{fn_id}")
async def update_function(fn_id: str, req: UpdateFunctionRequest) -> dict[str, Any]:
    eng = get_function_engine()
    try:
        data = {k: v for k, v in req.model_dump().items() if v is not None}
        if "params" in data and data["params"] is not None:
            data["params"] = [FunctionParam(**p) for p in data["params"]]
        fn = eng.update_function(fn_id, **data)
        return fn.model_dump()
    except KeyError:
        raise HTTPException(404, f"Function {fn_id} not found")


@router.get("/functions/{fn_id}/tests")
async def list_tests(fn_id: str) -> dict[str, Any]:
    eng = get_function_engine()
    if eng.get_function(fn_id) is None:
        raise HTTPException(404, f"Function {fn_id} not found")
    items = eng.list_tests(fn_id)
    return {"items": [t.model_dump() for t in items], "count": len(items)}


@router.post("/functions/{fn_id}/tests")
async def add_test(fn_id: str, req: AddTestRequest) -> dict[str, Any]:
    eng = get_function_engine()
    try:
        tc = eng.add_test(fn_id, name=req.name, inputs=req.inputs, expected=req.expected)
        if req.run:
            tc = eng.run_test(fn_id, tc.id)
        return tc.model_dump()
    except KeyError:
        raise HTTPException(404, f"Function {fn_id} not found")


@router.post("/functions/{fn_id}/test")
async def quick_test(fn_id: str, req: QuickTestRequest) -> dict[str, Any]:
    """W3-C4 · 试跑别名：创建临时用例并立即 run，返回前端友好结构。"""
    eng = get_function_engine()
    if eng.get_function(fn_id) is None:
        raise HTTPException(404, f"Function {fn_id} not found")
    try:
        tc = eng.add_test(fn_id, name=req.name, inputs=req.payload)
        tc = eng.run_test(fn_id, tc.id)
        ok = tc.status == "passed"
        error_rows = []
        if tc.error:
            error_rows.append({"param": "_", "message": tc.error})
        return {
            "ok": ok,
            "output": "" if tc.output is None else (
                tc.output if isinstance(tc.output, str) else str(tc.output)
            ),
            "duration": 0,
            "errorRows": error_rows or None,
            "status": tc.status,
            "testId": tc.id,
        }
    except KeyError:
        raise HTTPException(404, f"Function {fn_id} not found")
