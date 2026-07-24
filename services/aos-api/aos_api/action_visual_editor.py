"""W2-#16 · Action 可视化编辑器。

从 Action Type 的 parameters 推导表单 spec + 校验 payload + 创建向导 + 实时预览。
独立内存 store，不修改 meta_action_type DB 表。

详见 docs/palantier/20_tech/220tech_w2-c-ontology-manager.md §2.5。
"""
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


FormWidget = Literal[
    "text",
    "number",
    "select",
    "multiselect",
    "toggle",
    "date",
    "object_ref",
    "expression",
]


class FormFieldSpec(BaseModel):
    key: str
    label: str
    widget: FormWidget
    required: bool = False
    default: Any = None
    options: list[str] = Field(default_factory=list)
    bound_otd: str = ""


class ActionFormSpec(BaseModel):
    action_type_id: str
    fields: list[FormFieldSpec] = Field(default_factory=list)
    wizard_steps: list[dict[str, Any]] = Field(default_factory=list)
    preview_template: str = ""


class VisualEditorError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_PARAM_TYPE_MAP: dict[str, FormWidget] = {
    "string": "text",
    "text": "text",
    "number": "number",
    "integer": "number",
    "float": "number",
    "boolean": "toggle",
    "bool": "toggle",
    "date": "date",
    "datetime": "date",
    "object_ref": "object_ref",
    "expression": "expression",
}


def _infer_widget(param_type: str, param: dict[str, Any]) -> FormWidget:
    if "options" in param or "enum" in param:
        return "multiselect" if param.get("multiple") else "select"
    return _PARAM_TYPE_MAP.get(param_type, "text")


class ActionVisualEditor:
    """Action 可视化编辑器：form-spec 推导 + 校验 + 预览。"""

    def __init__(self) -> None:
        self._specs: dict[str, ActionFormSpec] = {}

    def generate_form_spec(
        self,
        action_type_id: str,
        parameters: list[dict[str, Any]] | None = None,
        wizard_steps: list[dict[str, Any]] | None = None,
        preview_template: str = "",
    ) -> ActionFormSpec:
        if not action_type_id:
            raise VisualEditorError("MISSING_ACTION", "缺少 action_type_id")
        fields: list[FormFieldSpec] = []
        for param in parameters or []:
            key = param.get("name") or param.get("key") or ""
            if not key:
                continue
            param_type = str(param.get("type", "string"))
            widget = _infer_widget(param_type, param)
            fields.append(FormFieldSpec(
                key=key,
                label=param.get("label") or key,
                widget=widget,
                required=bool(param.get("required", False)),
                default=param.get("default"),
                options=list(param.get("options") or param.get("enum") or []),
                bound_otd=str(param.get("bound_otd") or param.get("objectType") or ""),
            ))
        spec = ActionFormSpec(
            action_type_id=action_type_id,
            fields=fields,
            wizard_steps=wizard_steps or [],
            preview_template=preview_template,
        )
        self._specs[action_type_id] = spec
        return spec

    def get_form_spec(self, action_type_id: str) -> ActionFormSpec | None:
        return self._specs.get(action_type_id)

    def update_form_spec(
        self, action_type_id: str, **fields_updates: Any
    ) -> ActionFormSpec:
        spec = self._specs.get(action_type_id)
        if spec is None:
            raise VisualEditorError("NOT_FOUND", f"Action {action_type_id!r} 的 form-spec 不存在，请先 generate")
        updated = spec.model_copy(update=fields_updates)
        self._specs[action_type_id] = updated
        return updated

    def list_all(self) -> list[ActionFormSpec]:
        return list(self._specs.values())

    def delete(self, action_type_id: str) -> bool:
        existed = action_type_id in self._specs
        self._specs.pop(action_type_id, None)
        return existed

    def validate_payload(self, action_type_id: str, payload: dict[str, Any]) -> list[str]:
        spec = self._specs.get(action_type_id)
        if spec is None:
            raise VisualEditorError("NOT_FOUND", f"Action {action_type_id!r} 的 form-spec 不存在")
        errors: list[str] = []
        for field in spec.fields:
            if field.required and (field.key not in payload or payload.get(field.key) in (None, "")):
                errors.append(f"REQUIRED_MISSING: {field.key}（{field.label}）必填")
                continue
            val = payload.get(field.key)
            if val is None:
                continue
            widget_errors = _validate_widget_value(field, val)
            errors.extend(widget_errors)
        return errors

    def preview(self, action_type_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        spec = self._specs.get(action_type_id)
        if spec is None:
            raise VisualEditorError("NOT_FOUND", f"Action {action_type_id!r} 的 form-spec 不存在")
        rendered_fields: dict[str, Any] = {}
        for field in spec.fields:
            val = payload.get(field.key, field.default)
            rendered_fields[field.key] = val
        preview_text = spec.preview_template
        for key, val in rendered_fields.items():
            preview_text = preview_text.replace(f"{{{{{key}}}}}", str(val))
        return {
            "action_type_id": action_type_id,
            "rendered_fields": rendered_fields,
            "preview_text": preview_text,
            "valid": len(self.validate_payload(action_type_id, payload)) == 0,
        }


def _validate_widget_value(field: FormFieldSpec, val: Any) -> list[str]:
    errors: list[str] = []
    if field.widget == "number":
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            errors.append(f"TYPE_MISMATCH: {field.key} 需要数字，得到 {type(val).__name__}")
    elif field.widget == "toggle":
        if not isinstance(val, bool):
            errors.append(f"TYPE_MISMATCH: {field.key} 需要布尔值，得到 {type(val).__name__}")
    elif field.widget == "select":
        if field.options and str(val) not in field.options:
            errors.append(f"INVALID_OPTION: {field.key}={val!r} 不在选项 {field.options} 中")
    elif field.widget == "multiselect":
        if not isinstance(val, list):
            errors.append(f"TYPE_MISMATCH: {field.key} 需要列表")
        elif field.options:
            for item in val:
                if str(item) not in field.options:
                    errors.append(f"INVALID_OPTION: {field.key} 含非法选项 {item!r}")
    return errors


_editor = ActionVisualEditor()


def get_editor() -> ActionVisualEditor:
    return _editor
