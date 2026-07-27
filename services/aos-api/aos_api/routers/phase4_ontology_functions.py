"""Phase 4 · Ontology Functions 路由 (functions + tests)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.ontology_function_engine import get_function_engine

router = APIRouter(prefix="/v1/ontology", tags=["ontology-functions"])


class UpdateFunctionRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    body: str | None = None
    return_type: str | None = None
    status: str | None = None
    category: str | None = None


class AddTestRequest(BaseModel):
    name: str
    inputs: dict[str, Any] = {}
    expected: Any = None
    run: bool = False


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
