"""W2-20 · Pipeline 多数据源 API 路由。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.multi_source import (
    DataSource,
    JoinConfig,
    MultiSourceEngine,
    MultiSourceError,
    get_engine,
)

router = APIRouter(tags=["multi-source"])


def _map_error(err: MultiSourceError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


class AddSourceRequest(BaseModel):
    source_id: str
    name: str = ""
    rows: list[dict] = Field(default_factory=list)


class AddJoinRequest(BaseModel):
    left_source_id: str
    right_source_id: str
    left_key: str
    right_key: str
    join_type: str = "inner"


class CreatePipelineRequest(BaseModel):
    name: str = ""


@router.post("/v1/multi-source-pipelines")
def create_pipeline(req: CreatePipelineRequest):
    return get_engine().create(req.name)


@router.get("/v1/multi-source-pipelines/{msp_id}")
def get_pipeline(msp_id: str):
    msp = get_engine().get(msp_id)
    if msp is None:
        raise ApiError(code="NOT_FOUND", message=f"多源管道 {msp_id} 不存在", status_code=404)
    return msp


@router.post("/v1/multi-source-pipelines/{msp_id}/sources")
def add_source(msp_id: str, req: AddSourceRequest):
    try:
        src = DataSource(id=req.source_id, name=req.name, rows=req.rows)
        return get_engine().add_source(msp_id, src)
    except MultiSourceError as err:
        raise _map_error(err) from err


@router.post("/v1/multi-source-pipelines/{msp_id}/joins")
def add_join(msp_id: str, req: AddJoinRequest):
    try:
        join = JoinConfig(
            left_source_id=req.left_source_id, right_source_id=req.right_source_id,
            left_key=req.left_key, right_key=req.right_key, join_type=req.join_type,
        )
        return get_engine().add_join(msp_id, join)
    except MultiSourceError as err:
        raise _map_error(err) from err


@router.post("/v1/multi-source-pipelines/{msp_id}/execute")
def execute_pipeline(msp_id: str):
    try:
        result = get_engine().execute(msp_id)
        return {"rows": result, "count": len(result)}
    except MultiSourceError as err:
        raise _map_error(err) from err
