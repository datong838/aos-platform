"""W1-3 · Funnel 可视化映射编辑器 API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.errors import ApiError
from aos_api.funnel_mapping import (
    FunnelMappingError,
    MappingRule,
    SchemaField,
    get_editor,
)

router = APIRouter(tags=["funnel-mappings"])


class CreateRequest(BaseModel):
    name: str
    source_schema: list[SchemaField]
    target_schema: list[SchemaField]


class AddRuleRequest(BaseModel):
    rule: MappingRule


class PreviewRequest(BaseModel):
    source_rows: list[dict[str, Any]]


class ApplyTemplateRequest(BaseModel):
    template: str


def _map_error(err: FunnelMappingError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


@router.post("/v1/funnel-mappings")
def create_mapping(req: CreateRequest):
    spec = get_editor().create(req.name, req.source_schema, req.target_schema)
    return spec.model_dump()


@router.get("/v1/funnel-mappings")
def list_mappings():
    return {"mappings": [s.model_dump() for s in get_editor().list_all()]}


@router.get("/v1/funnel-mappings/{spec_id}")
def get_mapping(spec_id: str):
    try:
        return get_editor().get(spec_id).model_dump()
    except FunnelMappingError as err:
        raise _map_error(err, 404) from err


@router.delete("/v1/funnel-mappings/{spec_id}")
def delete_mapping(spec_id: str):
    try:
        get_editor().delete(spec_id)
    except FunnelMappingError as err:
        raise _map_error(err, 404) from err
    return {"deleted": spec_id}


@router.post("/v1/funnel-mappings/{spec_id}/rules")
def add_rule(spec_id: str, req: AddRuleRequest):
    try:
        spec = get_editor().add_rule(spec_id, req.rule)
    except FunnelMappingError as err:
        raise _map_error(err) from err
    return spec.model_dump()


@router.delete("/v1/funnel-mappings/{spec_id}/rules/{target_field}")
def remove_rule(spec_id: str, target_field: str):
    try:
        spec = get_editor().remove_rule(spec_id, target_field)
    except FunnelMappingError as err:
        raise _map_error(err) from err
    return spec.model_dump()


@router.post("/v1/funnel-mappings/{spec_id}/auto-map")
def auto_map(spec_id: str):
    try:
        spec = get_editor().auto_map(spec_id)
    except FunnelMappingError as err:
        raise _map_error(err) from err
    return spec.model_dump()


@router.post("/v1/funnel-mappings/{spec_id}/lint")
def lint_mapping(spec_id: str):
    try:
        result = get_editor().lint(spec_id)
    except FunnelMappingError as err:
        raise _map_error(err) from err
    return result.model_dump()


@router.post("/v1/funnel-mappings/{spec_id}/apply-template")
def apply_template(spec_id: str, req: ApplyTemplateRequest):
    try:
        spec = get_editor().apply_template(spec_id, req.template)
    except FunnelMappingError as err:
        raise _map_error(err) from err
    return spec.model_dump()


@router.post("/v1/funnel-mappings/{spec_id}/preview")
def preview_mapping(spec_id: str, req: PreviewRequest):
    try:
        rows = get_editor().preview(spec_id, req.source_rows)
    except FunnelMappingError as err:
        raise _map_error(err) from err
    return {"rows": rows, "count": len(rows)}


@router.get("/v1/funnel-mappings/templates/list")
def list_templates():
    return {"templates": get_editor().list_templates()}
