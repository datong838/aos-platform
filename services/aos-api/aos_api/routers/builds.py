"""W1-4 · Build 引擎 API 路由。

详见 docs/palantier/20_tech/220tech_build-engine.md。
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.jobs.build_engine import (
    JobError,
    JobSpec,
    JobStep,
    get_engine,
)

router = APIRouter(tags=["builds"])


def _map_error(err: JobError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


class CreateBuildRequest(BaseModel):
    inputs: list[str]
    steps: list[JobStep] = Field(default_factory=list)
    outputs: list[str]
    name: str = "untitled-build"


@router.post("/v1/builds")
def create_build(req: CreateBuildRequest):
    spec = JobSpec(
        inputs=req.inputs, steps=req.steps, outputs=req.outputs, name=req.name
    )
    try:
        return get_engine().create_job(spec)
    except JobError as err:
        raise _map_error(err) from err


@router.get("/v1/builds")
def list_builds():
    return get_engine().list_jobs()


@router.get("/v1/builds/dlq")
def list_dlq():
    return {"items": get_engine().dlq.list(), "count": get_engine().dlq.count()}


@router.get("/v1/builds/dlq/{entry_id}")
def get_dlq_entry(entry_id: str):
    entry = get_engine().dlq.get(entry_id)
    if entry is None:
        raise ApiError(code="NOT_FOUND", message=f"DLQ 条目 {entry_id} 不存在", status_code=404)
    return entry


@router.delete("/v1/builds/dlq/{entry_id}")
def remove_dlq_entry(entry_id: str):
    ok = get_engine().dlq.remove(entry_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"DLQ 条目 {entry_id} 不存在", status_code=404)
    return {"removed": True, "id": entry_id}


@router.get("/v1/builds/{job_id}")
def get_build(job_id: str):
    job = get_engine().get_job(job_id)
    if job is None:
        raise ApiError(code="NOT_FOUND", message=f"Job {job_id} 不存在", status_code=404)
    return job


@router.post("/v1/builds/{job_id}/cancel")
def cancel_build(job_id: str):
    try:
        return get_engine().cancel_job(job_id)
    except JobError as err:
        raise _map_error(err) from err


@router.post("/v1/builds/{job_id}/retry")
def retry_build(job_id: str):
    try:
        return get_engine().retry_job(job_id)
    except JobError as err:
        raise _map_error(err) from err
