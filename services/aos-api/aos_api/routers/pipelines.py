"""W1-14 · Pipeline Builder DAG 编辑器 API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.pipeline_builder import PipelineEditorError, get_store

router = APIRouter(tags=["pipelines"])


class CreatePipelineRequest(BaseModel):
    name: str


class ApplyCommandRequest(BaseModel):
    command: dict[str, Any]


class PreviewRequest(BaseModel):
    inputs: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


def _map_error(err: PipelineEditorError, status: int = 400) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=status)


@router.post("/v1/pipeline-builder")
def create_pipeline(req: CreatePipelineRequest):
    pipeline = get_store().create(req.name)
    return pipeline.model_dump()


@router.get("/v1/pipeline-builder")
def list_pipelines():
    return {"pipelines": [p.model_dump() for p in get_store().list_all()]}


@router.get("/v1/pipeline-builder/{pid}")
def get_pipeline(pid: str):
    try:
        return get_store().get(pid).model_dump()
    except PipelineEditorError as err:
        raise _map_error(err, 404) from err


@router.post("/v1/pipeline-builder/{pid}/apply")
def apply_command(pid: str, req: ApplyCommandRequest):
    try:
        editor = get_store().editor(pid)
        pipeline = editor.apply(req.command)
    except PipelineEditorError as err:
        raise _map_error(err) from err
    return pipeline.model_dump()


@router.post("/v1/pipeline-builder/{pid}/undo")
def undo_pipeline(pid: str):
    try:
        editor = get_store().editor(pid)
        pipeline = editor.undo()
    except PipelineEditorError as err:
        raise _map_error(err) from err
    return pipeline.model_dump()


@router.post("/v1/pipeline-builder/{pid}/redo")
def redo_pipeline(pid: str):
    try:
        editor = get_store().editor(pid)
        pipeline = editor.redo()
    except PipelineEditorError as err:
        raise _map_error(err) from err
    return pipeline.model_dump()


@router.post("/v1/pipeline-builder/{pid}/validate")
def validate_pipeline(pid: str):
    try:
        editor = get_store().editor(pid)
    except PipelineEditorError as err:
        raise _map_error(err, 404) from err
    return {"errors": editor.validate()}


@router.post("/v1/pipeline-builder/{pid}/preview")
def preview_pipeline(pid: str, req: PreviewRequest):
    try:
        editor = get_store().editor(pid)
        outputs = editor.preview(req.inputs)
    except PipelineEditorError as err:
        raise _map_error(err) from err
    return {"outputs": {k: v for k, v in outputs.items()}, "counts": {k: len(v) for k, v in outputs.items()}}


@router.delete("/v1/pipeline-builder/{pid}")
def delete_pipeline(pid: str):
    try:
        get_store().delete(pid)
    except PipelineEditorError as err:
        raise _map_error(err, 404) from err
    return {"deleted": pid}
