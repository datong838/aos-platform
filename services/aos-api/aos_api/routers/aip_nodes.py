"""W2-#7 · AIP/LLM 节点 API 路由。

详见 docs/palantier/20_tech/220tech_w2-b-aip-functions.md §2.1。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.aip_nodes import AipError, execute_llm_node, list_templates
from aos_api.errors import ApiError

router = APIRouter(tags=["aip-nodes"])


def _map_error(err: AipError) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=400)


class ExecuteLlmNodeRequest(BaseModel):
    rows: list[dict[str, Any]]
    template: str
    prompt: str | None = None
    input_column: str | None = None
    output_column: str = "llm_output"
    model: str = ""


@router.get("/v1/aip/templates")
def list_aip_templates():
    return {"items": [t.model_dump() for t in list_templates()]}


@router.post("/v1/aip/llm-node/execute")
def execute_llm(req: ExecuteLlmNodeRequest):
    config: dict[str, Any] = {
        "template": req.template,
        "output_column": req.output_column,
    }
    if req.prompt:
        config["prompt"] = req.prompt
    if req.input_column:
        config["input_column"] = req.input_column
    if req.model:
        config["model"] = req.model
    try:
        result = execute_llm_node(req.rows, config)
    except AipError as err:
        raise _map_error(err) from err
    return {"result": result, "count": len(result)}
