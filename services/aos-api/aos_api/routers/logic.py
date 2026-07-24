"""W1-2 · Logic 编排引擎 API 路由。

详见 docs/palantier/20_tech/220tech_logic-engine.md。
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.logic_engine import BLOCK_CATALOG, Block, LogicEngine, LogicError, LogicGraph

router = APIRouter(tags=["logic"])


def _map_error(err: LogicError) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=400)


class RunRequest(BaseModel):
    blocks: list[Block] = Field(default_factory=list)
    inputs: dict[str, object] = Field(default_factory=dict)
    debug: bool = False


@router.get("/v1/logic/blocks")
def list_block_types():
    return {"items": BLOCK_CATALOG}


@router.post("/v1/logic/run")
def run_logic(req: RunRequest):
    engine = LogicEngine()
    try:
        ctx = engine.run(req.blocks, req.inputs, debug=False)
        return {
            "variables": ctx.variables,
            "results": [r.model_dump() for r in ctx.results],
            "cot": ctx.cot,
        }
    except LogicError as err:
        raise _map_error(err) from err


@router.post("/v1/logic/debug")
def debug_logic(req: RunRequest):
    engine = LogicEngine()
    try:
        ctx = engine.run(req.blocks, req.inputs, debug=True)
        return {
            "variables": ctx.variables,
            "results": [r.model_dump() for r in ctx.results],
            "cot": ctx.cot,
            "proposed_edits": ctx.proposed_edits,
        }
    except LogicError as err:
        raise _map_error(err) from err


class GraphRunRequest(BaseModel):
    graph: LogicGraph
    inputs: dict[str, object] = Field(default_factory=dict)
    debug: bool = False
    max_steps: int = 256


@router.post("/v1/logic/run-graph")
def run_graph_logic(req: GraphRunRequest):
    """W2-#17 · LogicGraph 条件路由图编排执行。"""
    engine = LogicEngine()
    try:
        ctx = engine.run_graph(req.graph, req.inputs, debug=False, max_steps=req.max_steps)
        return {
            "variables": ctx.variables,
            "results": [r.model_dump() for r in ctx.results],
            "cot": ctx.cot,
        }
    except LogicError as err:
        raise _map_error(err) from err


@router.post("/v1/logic/debug-graph")
def debug_graph_logic(req: GraphRunRequest):
    """W2-#17 · LogicGraph 图编排调试（收集 proposed_edits + cot）。"""
    engine = LogicEngine()
    try:
        ctx = engine.run_graph(req.graph, req.inputs, debug=True, max_steps=req.max_steps)
        return {
            "variables": ctx.variables,
            "results": [r.model_dump() for r in ctx.results],
            "cot": ctx.cot,
            "proposed_edits": ctx.proposed_edits,
        }
    except LogicError as err:
        raise _map_error(err) from err
