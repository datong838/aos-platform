"""W1-9 · MediaReference Bridge API 路由。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.errors import ApiError
from aos_api.media_reference import MediaReferenceError, get_store

router = APIRouter(tags=["media-references"])


class RegisterRequest(BaseModel):
    kind: str = "document"
    storage: str = "local"
    bucket: str
    path: str
    mime: str = ""
    size_bytes: int = 0
    owner_object_type: str = ""
    owner_object_id: str = ""


class ThumbnailRequest(BaseModel):
    sizes: list[str] | None = None


def _map_error(err: MediaReferenceError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


@router.post("/v1/media-references")
def register(req: RegisterRequest):
    try:
        ref = get_store().register(
            req.kind, req.storage, req.bucket, req.path,
            req.mime, req.size_bytes, req.owner_object_type, req.owner_object_id,
        )
    except MediaReferenceError as err:
        raise _map_error(err) from err
    return ref.model_dump()


@router.get("/v1/media-references")
def list_refs():
    return {"media_references": [r.model_dump() for r in get_store().list_all()]}


@router.get("/v1/media-references/{ref_id}")
def get_ref(ref_id: str):
    try:
        return get_store().get(ref_id).model_dump()
    except MediaReferenceError as err:
        raise _map_error(err, 404) from err


@router.delete("/v1/media-references/{ref_id}")
def delete_ref(ref_id: str):
    try:
        get_store().delete(ref_id)
    except MediaReferenceError as err:
        raise _map_error(err, 404) from err
    return {"deleted": ref_id}


@router.get("/v1/media-references/{ref_id}/signed-url")
def signed_url(ref_id: str, expires: int = 3600):
    try:
        url = get_store().get_signed_url(ref_id, expires)
    except MediaReferenceError as err:
        raise _map_error(err, 404) from err
    return {"url": url, "expires_in": expires}


@router.post("/v1/media-references/{ref_id}/thumbnails")
def thumbnails(ref_id: str, req: ThumbnailRequest):
    try:
        result = get_store().generate_thumbnail(ref_id, req.sizes)
    except MediaReferenceError as err:
        raise _map_error(err) from err
    return {"thumbnails": result}


@router.get("/v1/media-references/by-owner/{object_type}/{object_id}")
def list_by_owner(object_type: str, object_id: str):
    refs = get_store().list_by_owner(object_type, object_id)
    return {"media_references": [r.model_dump() for r in refs], "count": len(refs)}
