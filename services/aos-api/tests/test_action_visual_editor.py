"""W2-#16 · Action 可视化编辑器测试。"""
from __future__ import annotations

import pytest

from aos_api.action_visual_editor import (
    ActionVisualEditor,
    FormFieldSpec,
    VisualEditorError,
)


@pytest.fixture
def editor() -> ActionVisualEditor:
    return ActionVisualEditor()


# ---------- form-spec 推导 ----------


def test_generate_form_spec_from_parameters(editor: ActionVisualEditor):
    params = [
        {"name": "title", "type": "string", "required": True},
        {"name": "amount", "type": "number"},
        {"name": "status", "type": "string", "options": ["open", "closed"]},
    ]
    spec = editor.generate_form_spec("act-1", parameters=params)
    assert len(spec.fields) == 3
    by_key = {f.key: f for f in spec.fields}
    assert by_key["title"].widget == "text"
    assert by_key["amount"].widget == "number"
    assert by_key["status"].widget == "select"
    assert by_key["title"].required is True


def test_generate_missing_action_raises(editor: ActionVisualEditor):
    with pytest.raises(VisualEditorError) as exc:
        editor.generate_form_spec("", parameters=[])
    assert exc.value.code == "MISSING_ACTION"


def test_boolean_maps_to_toggle(editor: ActionVisualEditor):
    spec = editor.generate_form_spec("act-2", parameters=[{"name": "flag", "type": "boolean"}])
    assert spec.fields[0].widget == "toggle"


def test_bound_otd_propagation(editor: ActionVisualEditor):
    spec = editor.generate_form_spec(
        "act-3",
        parameters=[{"name": "owner", "type": "object_ref", "objectType": "Employee"}],
    )
    assert spec.fields[0].widget == "object_ref"
    assert spec.fields[0].bound_otd == "Employee"


def test_multiselect_for_multiple(editor: ActionVisualEditor):
    spec = editor.generate_form_spec(
        "act-4",
        parameters=[{"name": "tags", "type": "string", "options": ["a", "b"], "multiple": True}],
    )
    assert spec.fields[0].widget == "multiselect"


def test_unknown_type_defaults_to_text(editor: ActionVisualEditor):
    spec = editor.generate_form_spec("act-5", parameters=[{"name": "x", "type": "weird"}])
    assert spec.fields[0].widget == "text"


# ---------- 校验 ----------


def test_validate_required_missing(editor: ActionVisualEditor):
    editor.generate_form_spec("act-1", parameters=[{"name": "title", "required": True}])
    errors = editor.validate_payload("act-1", {})
    assert any("REQUIRED_MISSING" in e for e in errors)


def test_validate_type_mismatch_number(editor: ActionVisualEditor):
    editor.generate_form_spec("act-1", parameters=[{"name": "amount", "type": "number"}])
    errors = editor.validate_payload("act-1", {"amount": "abc"})
    assert any("TYPE_MISMATCH" in e for e in errors)


def test_validate_select_invalid_option(editor: ActionVisualEditor):
    editor.generate_form_spec(
        "act-1", parameters=[{"name": "status", "options": ["open", "closed"]}]
    )
    errors = editor.validate_payload("act-1", {"status": "unknown"})
    assert any("INVALID_OPTION" in e for e in errors)


def test_validate_valid_payload_no_errors(editor: ActionVisualEditor):
    editor.generate_form_spec(
        "act-1", parameters=[{"name": "amount", "type": "number"}]
    )
    errors = editor.validate_payload("act-1", {"amount": 100})
    assert errors == []


def test_validate_unknown_spec_raises(editor: ActionVisualEditor):
    with pytest.raises(VisualEditorError) as exc:
        editor.validate_payload("ghost", {})
    assert exc.value.code == "NOT_FOUND"


# ---------- 预览 ----------


def test_preview_renders_template(editor: ActionVisualEditor):
    editor.generate_form_spec(
        "act-1",
        parameters=[{"name": "title", "type": "string"}],
        preview_template="标题：{{title}}",
    )
    result = editor.preview("act-1", {"title": "订单"})
    assert result["preview_text"] == "标题：订单"
    assert result["rendered_fields"]["title"] == "订单"


def test_preview_uses_default_when_missing(editor: ActionVisualEditor):
    editor.generate_form_spec(
        "act-1",
        parameters=[{"name": "level", "type": "string", "default": "普通"}],
    )
    result = editor.preview("act-1", {})
    assert result["rendered_fields"]["level"] == "普通"


def test_preview_marks_invalid(editor: ActionVisualEditor):
    editor.generate_form_spec(
        "act-1", parameters=[{"name": "n", "type": "number", "required": True}]
    )
    result = editor.preview("act-1", {"n": "bad"})
    assert result["valid"] is False


def test_update_and_delete_spec(editor: ActionVisualEditor):
    editor.generate_form_spec("act-1", parameters=[{"name": "x", "type": "string"}])
    updated = editor.update_form_spec("act-1", preview_template="新模板")
    assert updated.preview_template == "新模板"
    assert editor.delete("act-1") is True
    assert editor.get_form_spec("act-1") is None
