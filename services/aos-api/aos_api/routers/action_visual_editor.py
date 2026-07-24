"""W2-#16 · Action 可视化编辑器 API 路由。

详见 docs/palantier/20_tech/220tech_w2-c-ontology-manager.md §2.5。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.action_visual_editor import ActionVisualEditor, VisualEditorError, get_editor
from aos_api.errors import ApiError

router = APIRouter(tags=["action-visual-editor"])


def _map_error(err: VisualEditorError) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=400)


class ParamIn(BaseModel):
    name: str
    type: str = "string"
    label: str = ""
    required: bool = False
    default: Any = None
    options: list[str] = Field(default_factory=list)
    enum: list[str] = Field(default_factory=list)
    multiple: bool = False
    bound_otd: str = ""
    objectType: str = ""


class GenerateSpecRequest(BaseModel):
    action_type_id: str
    parameters: list[ParamIn] = Field(default_factory=list)
    wizard_steps: list[dict[str, Any]] = Field(default_factory=list)
    preview_template: str = ""


class ValidatePayloadRequest(BaseModel):
    payload: dict[str, Any]


class PreviewRequest(BaseModel):
    payload: dict[str, Any]


@router.get("/v1/action-editor/specs")
def list_specs():
    return {"items": [s.model_dump() for s in get_editor().list_all()]}


@router.post("/v1/action-editor/specs/generate")
def generate_spec(req: GenerateSpecRequest):
    params = [p.model_dump(exclude_none=True) for p in req.parameters]
    try:
        spec = get_editor().generate_form_spec(
            req.action_type_id,
            parameters=params,
            wizard_steps=req.wizard_steps,
            preview_template=req.preview_template,
        )
    except VisualEditorError as err:
        raise _map_error(err) from err
    return spec.model_dump()


@router.get("/v1/action-editor/specs/{action_type_id}")
def get_spec(action_type_id: str):
    spec = get_editor().get_form_spec(action_type_id)
    if spec is None:
        raise ApiError(code="NOT_FOUND", message=f"Action {action_type_id} 的 form-spec 不存在", status_code=404)
    return spec.model_dump()


@router.post("/v1/action-editor/specs/{action_type_id}/validate")
def validate_payload(action_type_id: str, req: ValidatePayloadRequest):
    try:
        errors = get_editor().validate_payload(action_type_id, req.payload)
    except VisualEditorError as err:
        raise _map_error(err) from err
    return {"action_type_id": action_type_id, "errors": errors, "valid": len(errors) == 0}


@router.post("/v1/action-editor/specs/{action_type_id}/preview")
def preview(action_type_id: str, req: PreviewRequest):
    try:
        result = get_editor().preview(action_type_id, req.payload)
    except VisualEditorError as err:
        raise _map_error(err) from err
    return result


@router.delete("/v1/action-editor/specs/{action_type_id}")
def delete_spec(action_type_id: str):
    ok = get_editor().delete(action_type_id)
    return {"action_type_id": action_type_id, "deleted": ok}
