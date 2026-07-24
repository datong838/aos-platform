"""W2-6 · Pipeline Builder 输出系统 API 路由。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.pipeline_output import (
    OutputConfig,
    OutputTarget,
    PipelineOutputEngine,
    PipelineOutputError,
    get_engine,
)

router = APIRouter(tags=["pipeline-outputs"])


def _map_error(err: PipelineOutputError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


class RegisterTargetRequest(BaseModel):
    target_dataset_rid: str
    write_mode: str = "append"
    primary_key: str = ""


class ExecuteRequest(BaseModel):
    input_rows: list[dict] = Field(default_factory=list)


@router.post("/v1/pipeline-outputs/targets")
def register_target(req: RegisterTargetRequest):
    target = OutputTarget(config=OutputConfig(
        target_dataset_rid=req.target_dataset_rid,
        write_mode=req.write_mode,
        primary_key=req.primary_key,
    ))
    return get_engine().register_target(target)


@router.get("/v1/pipeline-outputs/targets")
def list_targets():
    return {"items": get_engine().list_targets()}


@router.get("/v1/pipeline-outputs/targets/{target_id}")
def get_target(target_id: str):
    t = get_engine().get_target(target_id)
    if t is None:
        raise ApiError(code="NOT_FOUND", message=f"输出目标 {target_id} 不存在", status_code=404)
    return t


@router.post("/v1/pipeline-outputs/targets/{target_id}/execute")
def execute_output(target_id: str, req: ExecuteRequest):
    try:
        return get_engine().execute(target_id, req.input_rows)
    except PipelineOutputError as err:
        raise _map_error(err) from err


@router.get("/v1/pipeline-outputs/datasets/{rid}")
def get_dataset(rid: str):
    return {"rows": get_engine().get_dataset(rid)}
