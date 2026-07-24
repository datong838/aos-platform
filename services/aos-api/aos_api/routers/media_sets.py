"""W1-16 · MediaSet 类型化 + 表格行变换 API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.errors import ApiError
from aos_api.media_set import MediaSetError, get_store

router = APIRouter(tags=["media-sets"])


class CreateRequest(BaseModel):
    name: str
    type: str


class AddMediaRequest(BaseModel):
    media_ref_id: str


class TransformRequest(BaseModel):
    op: str
    config: dict[str, Any] = {}


def _map_error(err: MediaSetError, status: int = 400) -> ApiError:
    if err.code in {"NOT_FOUND", "MEDIA_NOT_FOUND"}:
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


@router.post("/v1/media-set-builder")
def create_set(req: CreateRequest):
    try:
        ms = get_store().create(req.name, req.type)
    except MediaSetError as err:
        raise _map_error(err) from err
    return ms.model_dump()


@router.get("/v1/media-set-builder")
def list_sets():
    return {"media_sets": [ms.model_dump() for ms in get_store().list_all()]}


@router.get("/v1/media-set-builder/{set_id}")
def get_set(set_id: str):
    try:
        return get_store().get(set_id).model_dump()
    except MediaSetError as err:
        raise _map_error(err, 404) from err


@router.delete("/v1/media-set-builder/{set_id}")
def delete_set(set_id: str):
    try:
        get_store().delete(set_id)
    except MediaSetError as err:
        raise _map_error(err, 404) from err
    return {"deleted": set_id}


@router.post("/v1/media-set-builder/{set_id}/media")
def add_media(set_id: str, req: AddMediaRequest):
    try:
        ms = get_store().add_media(set_id, req.media_ref_id)
    except MediaSetError as err:
        raise _map_error(err) from err
    return ms.model_dump()


@router.delete("/v1/media-set-builder/{set_id}/media/{ref_id}")
def remove_media(set_id: str, ref_id: str):
    try:
        ms = get_store().remove_media(set_id, ref_id)
    except MediaSetError as err:
        raise _map_error(err) from err
    return ms.model_dump()


@router.get("/v1/media-set-builder/{set_id}/rows")
def get_rows(set_id: str):
    try:
        rows = get_store().get_rows(set_id)
    except MediaSetError as err:
        raise _map_error(err, 404) from err
    return {"rows": rows, "count": len(rows)}


@router.post("/v1/media-set-builder/{set_id}/transform")
def transform_set(set_id: str, req: TransformRequest):
    try:
        rows = get_store().transform(set_id, req.op, req.config)
    except MediaSetError as err:
        raise _map_error(err) from err
    return {"rows": rows, "count": len(rows)}
