"""MediaSet Browser Interaction API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.media_set_browser_interaction import (
    BrowserError,
    InteractionError,
    TranscriptionError,
    get_browser_engine,
    get_interaction_engine,
    get_transcription_engine,
)

router = APIRouter(prefix="/media-set-browser-interaction", tags=["media-set-browser-interaction"])


def _map_browser_error(err: BrowserError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_interaction_error(err: InteractionError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_transcription_error(err: TranscriptionError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ─────────────── MediaSetBrowserEngine 路由 ───────────────

class CreateItemRequest(BaseModel):
    media_set_id: str
    file_name: str
    file_type: str
    file_size: int
    preview_url: str | None = None
    metadata: dict[str, Any] = {}


@router.get("/items")
def browse_items(
    media_set_id: str = Query(...),
    file_type: str | None = Query(None),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_browser_engine()
    try:
        items = eng.browse_items(media_set_id, file_type)
    except BrowserError as err:
        raise _map_browser_error(err) from err
    return {"items": [item.model_dump() for item in items], "count": len(items)}


@router.get("/items/{item_id}")
def get_item(
    item_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_browser_engine()
    try:
        return eng.get_item(item_id).model_dump()
    except BrowserError as err:
        raise _map_browser_error(err, 404) from err


@router.get("/items/search")
def search_items(
    media_set_id: str = Query(...),
    query: str = Query(...),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_browser_engine()
    items = eng.search_items(media_set_id, query)
    return {"items": [item.model_dump() for item in items], "count": len(items)}


@router.post("/items")
def create_item(
    body: CreateItemRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_browser_engine()
    try:
        item = eng.create_item(
            media_set_id=body.media_set_id,
            file_name=body.file_name,
            file_type=body.file_type,
            file_size=body.file_size,
            preview_url=body.preview_url,
            metadata=body.metadata,
        )
    except BrowserError as err:
        raise _map_browser_error(err) from err
    return item.model_dump()


@router.delete("/items/{item_id}")
def delete_item(
    item_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_browser_engine()
    try:
        eng.delete_item(item_id)
    except BrowserError as err:
        raise _map_browser_error(err, 404) from err
    return {"deleted": item_id}


@router.get("/items/{item_id}/preview")
def get_item_preview(
    item_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_browser_engine()
    try:
        return eng.get_item_preview(item_id)
    except BrowserError as err:
        raise _map_browser_error(err, 404) from err


# ─────────────── MediaInteractionEngine 路由 ───────────────

class CreateViewRequest(BaseModel):
    item_id: str
    view_type: str


class UpdateViewRequest(BaseModel):
    brightness: float | None = None
    contrast: float | None = None
    zoom: float | None = None
    pan_x: float | None = None
    pan_y: float | None = None
    rotation: float | None = None


class AddAnnotationRequest(BaseModel):
    type: str = "note"
    content: dict[str, Any] = {}


@router.post("/views")
def create_view(
    body: CreateViewRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_interaction_engine()
    try:
        view = eng.create_view(body.item_id, body.view_type)
    except InteractionError as err:
        raise _map_interaction_error(err) from err
    return view.model_dump()


@router.get("/views/{view_id}")
def get_view(
    view_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_interaction_engine()
    try:
        return eng.get_view(view_id).model_dump()
    except InteractionError as err:
        raise _map_interaction_error(err, 404) from err


@router.put("/views/{view_id}")
def update_view(
    view_id: str,
    body: UpdateViewRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_interaction_engine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        view = eng.update_view(view_id, **updates)
    except InteractionError as err:
        raise _map_interaction_error(err) from err
    return view.model_dump()


@router.delete("/views/{view_id}")
def delete_view(
    view_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_interaction_engine()
    try:
        eng.delete_view(view_id)
    except InteractionError as err:
        raise _map_interaction_error(err, 404) from err
    return {"deleted": view_id}


@router.get("/views/{view_id}/annotations")
def get_annotations(
    view_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_interaction_engine()
    try:
        annotations = eng.get_annotations(view_id)
    except InteractionError as err:
        raise _map_interaction_error(err, 404) from err
    return {"annotations": [ann.model_dump() for ann in annotations], "count": len(annotations)}


@router.post("/views/{view_id}/annotations")
def add_annotation(
    view_id: str,
    body: AddAnnotationRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_interaction_engine()
    try:
        annotation = eng.add_annotation(view_id, body.model_dump())
    except InteractionError as err:
        raise _map_interaction_error(err) from err
    return annotation.model_dump()


@router.delete("/views/{view_id}/annotations/{annotation_id}")
def delete_annotation(
    view_id: str,
    annotation_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_interaction_engine()
    try:
        eng.delete_annotation(view_id, annotation_id)
    except InteractionError as err:
        raise _map_interaction_error(err, 404) from err
    return {"deleted": annotation_id}


# ─────────────── AudioTranscriptionEngine 路由 ───────────────

class CreateTranscriptionJobRequest(BaseModel):
    item_id: str
    language: str = "auto"


@router.post("/transcription-jobs")
def create_transcription_job(
    body: CreateTranscriptionJobRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_transcription_engine()
    try:
        job = eng.create_job(body.item_id, body.language)
    except TranscriptionError as err:
        raise _map_transcription_error(err) from err
    return job.model_dump()


@router.get("/transcription-jobs/{job_id}")
def get_transcription_job(
    job_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_transcription_engine()
    try:
        return eng.get_job(job_id).model_dump()
    except TranscriptionError as err:
        raise _map_transcription_error(err, 404) from err


@router.get("/transcription-jobs")
def list_transcription_jobs(
    media_set_id: str | None = Query(None),
    status: str | None = Query(None),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_transcription_engine()
    try:
        jobs = eng.list_jobs(media_set_id=media_set_id, status=status)
    except TranscriptionError as err:
        raise _map_transcription_error(err) from err
    return {"jobs": [job.model_dump() for job in jobs], "count": len(jobs)}


@router.post("/transcription-jobs/{job_id}/cancel")
def cancel_transcription_job(
    job_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_transcription_engine()
    try:
        job = eng.cancel_job(job_id)
    except TranscriptionError as err:
        raise _map_transcription_error(err) from err
    return job.model_dump()


@router.get("/transcription-jobs/{job_id}/transcript")
def get_transcript(
    job_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_transcription_engine()
    try:
        return eng.get_transcript(job_id)
    except TranscriptionError as err:
        raise _map_transcription_error(err, 404) from err


@router.get("/items/{item_id}/estimate-language")
def estimate_language(
    item_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_transcription_engine()
    try:
        return eng.estimate_language(item_id)
    except TranscriptionError as err:
        raise _map_transcription_error(err, 404) from err