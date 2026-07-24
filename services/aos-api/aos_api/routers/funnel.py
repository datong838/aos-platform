"""W1-5 · Funnel 四阶段管道 API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.funnel_engine import FunnelError, get_engine

router = APIRouter(tags=["funnel"])


def _map_error(err: FunnelError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


class RunFunnelRequest(BaseModel):
    source_dataset: str
    target_object_type: str = "default"
    primary_key: str = "id"
    input_rows: list[dict[str, Any]] = Field(default_factory=list)
    mode: str = "snapshot"


@router.post("/v1/funnel/run")
def run_funnel(req: RunFunnelRequest):
    try:
        return get_engine().run(
            source_dataset=req.source_dataset,
            target_object_type=req.target_object_type,
            primary_key=req.primary_key,
            input_rows=req.input_rows,
            mode=req.mode,
        )
    except FunnelError as err:
        raise _map_error(err) from err


@router.post("/v1/funnel/reindex")
def reindex_funnel(req: RunFunnelRequest):
    """W2-#11 · 全量重索引触发（snapshot 模式 + 重置增量水位）。"""
    try:
        return get_engine().reindex(
            source_dataset=req.source_dataset,
            target_object_type=req.target_object_type,
            primary_key=req.primary_key,
            input_rows=req.input_rows,
        )
    except FunnelError as err:
        raise _map_error(err) from err


@router.get("/v1/funnel")
def list_funnels():
    return get_engine().list_pipelines()


@router.get("/v1/funnel/{pipeline_id}")
def get_funnel(pipeline_id: str):
    p = get_engine().get_pipeline(pipeline_id)
    if p is None:
        raise ApiError(code="NOT_FOUND", message=f"Pipeline {pipeline_id} 不存在", status_code=404)
    return p


@router.get("/v1/funnel/{pipeline_id}/stage/{stage_name}")
def get_funnel_stage(pipeline_id: str, stage_name: str):
    try:
        return get_engine().get_stage(pipeline_id, stage_name)
    except FunnelError as err:
        raise _map_error(err) from err
