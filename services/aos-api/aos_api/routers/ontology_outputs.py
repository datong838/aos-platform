"""W2-3 · Ontology 对象类型输出 API 路由。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.ontology_output import (
    ObjectField,
    ObjectTypeDefinition,
    OntologyOutputError,
    OntologyOutputStore,
    get_store,
)

router = APIRouter(tags=["ontology-outputs"])


def _map_error(err: OntologyOutputError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


class DefineRequest(BaseModel):
    name: str
    display_name: str = ""
    primary_key: str
    title_field: str = ""
    fields: list[ObjectField] = Field(default_factory=list)
    source_dataset_rid: str = ""
    source_pipeline_id: str = ""


class PreviewRequest(BaseModel):
    rows: list[dict] = Field(default_factory=list)
    limit: int = 100


class InferRequest(BaseModel):
    rows: list[dict] = Field(default_factory=list)


@router.post("/v1/ontology-outputs")
def define_otd(req: DefineRequest):
    otd = ObjectTypeDefinition(
        name=req.name,
        display_name=req.display_name or req.name,
        primary_key=req.primary_key,
        title_field=req.title_field,
        fields=req.fields,
        source_dataset_rid=req.source_dataset_rid,
        source_pipeline_id=req.source_pipeline_id,
    )
    try:
        return get_store().define(otd)
    except OntologyOutputError as err:
        raise _map_error(err) from err


@router.get("/v1/ontology-outputs")
def list_otds():
    return {"items": get_store().list_all()}


@router.get("/v1/ontology-outputs/{otd_id}")
def get_otd(otd_id: str):
    otd = get_store().get(otd_id)
    if otd is None:
        raise ApiError(code="NOT_FOUND", message=f"对象类型定义 {otd_id} 不存在", status_code=404)
    return otd


@router.delete("/v1/ontology-outputs/{otd_id}")
def delete_otd(otd_id: str):
    ok = get_store().delete(otd_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"对象类型定义 {otd_id} 不存在", status_code=404)
    return {"deleted": True, "id": otd_id}


@router.post("/v1/ontology-outputs/infer-fields")
def infer_fields(req: InferRequest):
    store = OntologyOutputStore()
    return {"fields": [f.model_dump() for f in store.infer_fields(req.rows)]}


@router.post("/v1/ontology-outputs/{otd_id}/preview")
def preview_objects(otd_id: str, req: PreviewRequest):
    try:
        objects = get_store().preview_objects(otd_id, req.rows, req.limit)
        return {"objects": objects, "count": len(objects)}
    except OntologyOutputError as err:
        raise _map_error(err) from err
