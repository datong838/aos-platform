"""W2-#25 · 多语言 Transform API 路由。

详见 docs/palantier/20_tech/220tech_w2-b-aip-functions.md §2.4。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.multi_language_transform import (
    MultiLanguageError,
    get_engine,
    list_supported_languages,
)

router = APIRouter(tags=["multi-language"])


def _map_error(err: MultiLanguageError) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=400)


class RegisterTransformRequest(BaseModel):
    language: str
    source: str
    name: str
    description: str = ""


class InvokeTransformRequest(BaseModel):
    transform_id: str
    rows: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/v1/multi-language/languages")
def list_languages():
    return {"items": list_supported_languages()}


@router.get("/v1/multi-language/transforms")
def list_transforms():
    return {"items": [t.model_dump() for t in get_engine().list_all()]}


@router.post("/v1/multi-language/transforms")
def register_transform(req: RegisterTransformRequest):
    try:
        tf = get_engine().register(req.language, req.source, req.name, req.description)
    except MultiLanguageError as err:
        raise _map_error(err) from err
    return tf.model_dump()


@router.post("/v1/multi-language/transforms/invoke")
def invoke_transform(req: InvokeTransformRequest):
    try:
        result = get_engine().invoke(req.transform_id, req.rows)
    except MultiLanguageError as err:
        raise _map_error(err) from err
    return {"result": result, "count": len(result)}


@router.delete("/v1/multi-language/transforms/{transform_id}")
def delete_transform(transform_id: str):
    ok = get_engine().delete(transform_id)
    return {"transform_id": transform_id, "deleted": ok}
