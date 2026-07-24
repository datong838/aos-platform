"""W2-R · Action Webhook/Sections/Revert 路由：#64 Webhook 副作用 + #65 Section 分组 + #66 Revert 撤销."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.action_webhook import (
    ActionSection,
    RevertError,
    RevertRule,
    SectionError,
    SectionField,
    WebhookError,
    WebhookSideEffect,
    get_revert_engine,
    get_section_engine,
    get_webhook_engine,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["action-webhook"])
log = get_logger("aos-api.action-webhook")


def _map_webhook_error(err: WebhookError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_section_error(err: SectionError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_revert_error(err: RevertError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ─────────────── #64 Action Webhook 副作用 ───────────────

class WebhookEffectIn(BaseModel):
    action_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    mode: str = "data_output"
    method: str = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
    input_mapping: dict[str, Any] = Field(default_factory=dict)
    output_mapping: dict[str, Any] = Field(default_factory=dict)
    auth_type: str = "none"
    auth_config: dict[str, Any] = Field(default_factory=dict)
    retry_policy: dict[str, Any] = Field(default_factory=dict)


class WebhookEffectUpdateIn(BaseModel):
    name: str | None = None
    url: str | None = None
    mode: str | None = None
    method: str | None = None
    headers: dict[str, str] | None = None
    input_mapping: dict[str, Any] | None = None
    output_mapping: dict[str, Any] | None = None
    auth_type: str | None = None
    auth_config: dict[str, Any] | None = None
    retry_policy: dict[str, Any] | None = None


class BuildRequestIn(BaseModel):
    action_params: dict[str, Any] = Field(default_factory=dict)


class ApplyResponseIn(BaseModel):
    response: dict[str, Any]


@router.get("/v1/actions/webhook-effects")
def list_webhook_effects(
    action_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#64 · 列出 Webhook 副作用。"""
    _ = principal
    items = get_webhook_engine().list(action_id=action_id)
    return {"items": [e.model_dump() for e in items], "count": len(items)}


@router.post("/v1/actions/webhook-effects")
def create_webhook_effect(
    body: WebhookEffectIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#64 · 创建 Webhook 副作用。"""
    _ = principal
    effect = WebhookSideEffect(**body.model_dump())
    try:
        created = get_webhook_engine().create(effect)
        log.info("webhook_effect_created id=%s action=%s", created.id, created.action_id)
        return created.model_dump()
    except WebhookError as err:
        raise _map_webhook_error(err) from err


@router.get("/v1/actions/webhook-effects/{effect_id}")
def get_webhook_effect(
    effect_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#64 · 获取 Webhook 副作用详情。"""
    _ = principal
    try:
        return get_webhook_engine().get(effect_id).model_dump()
    except WebhookError as err:
        raise _map_webhook_error(err) from err


@router.put("/v1/actions/webhook-effects/{effect_id}")
def update_webhook_effect(
    effect_id: str,
    body: WebhookEffectUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#64 · 更新 Webhook 副作用。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        effect = get_webhook_engine().update(effect_id, updates)
        log.info("webhook_effect_updated id=%s", effect_id)
        return effect.model_dump()
    except WebhookError as err:
        raise _map_webhook_error(err) from err


@router.delete("/v1/actions/webhook-effects/{effect_id}")
def delete_webhook_effect(
    effect_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#64 · 删除 Webhook 副作用。"""
    _ = principal
    try:
        get_webhook_engine().delete(effect_id)
        log.info("webhook_effect_deleted id=%s", effect_id)
        return {"deleted": True, "id": effect_id}
    except WebhookError as err:
        raise _map_webhook_error(err) from err


@router.post("/v1/actions/webhook-effects/{effect_id}/build-request")
def build_webhook_request(
    effect_id: str,
    body: BuildRequestIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#64 · 根据 Action 参数构建 Webhook 请求 payload。"""
    _ = principal
    try:
        return get_webhook_engine().build_request(effect_id, body.action_params)
    except WebhookError as err:
        raise _map_webhook_error(err) from err


@router.post("/v1/actions/webhook-effects/{effect_id}/apply-response")
def apply_webhook_response(
    effect_id: str,
    body: ApplyResponseIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#64 · 将 Webhook 响应按 output_mapping 写回 Action 输出字段。"""
    _ = principal
    try:
        return get_webhook_engine().apply_response(effect_id, body.response)
    except WebhookError as err:
        raise _map_webhook_error(err) from err


# ─────────────── #65 Action Sections 分组 ───────────────

class SectionFieldIn(BaseModel):
    param_name: str = Field(min_length=1)
    span: int = 1


class SectionIn(BaseModel):
    action_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    display_name: str = ""
    layout: str = "single_column"
    collapsed: bool = False
    visible_condition: str = ""
    fields: list[SectionFieldIn] = Field(default_factory=list)
    order: int = 0


class SectionUpdateIn(BaseModel):
    name: str | None = None
    display_name: str | None = None
    layout: str | None = None
    collapsed: bool | None = None
    visible_condition: str | None = None
    fields: list[SectionFieldIn] | None = None
    order: int | None = None


class ReorderIn(BaseModel):
    ordered_ids: list[str] = Field(default_factory=list)


class VisibilityIn(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


@router.get("/v1/actions/sections")
def list_sections(
    action_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#65 · 列出 Section。"""
    _ = principal
    items = get_section_engine().list(action_id=action_id)
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.post("/v1/actions/sections")
def create_section(
    body: SectionIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#65 · 创建 Section。"""
    _ = principal
    section = ActionSection(
        action_id=body.action_id,
        name=body.name,
        display_name=body.display_name,
        layout=body.layout,
        collapsed=body.collapsed,
        visible_condition=body.visible_condition,
        fields=[SectionField(**f.model_dump()) for f in body.fields],
        order=body.order,
    )
    try:
        created = get_section_engine().create(section)
        log.info("section_created id=%s action=%s", created.id, created.action_id)
        return created.model_dump()
    except SectionError as err:
        raise _map_section_error(err) from err


@router.get("/v1/actions/sections/{section_id}")
def get_section(
    section_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#65 · 获取 Section 详情。"""
    _ = principal
    try:
        return get_section_engine().get(section_id).model_dump()
    except SectionError as err:
        raise _map_section_error(err) from err


@router.put("/v1/actions/sections/{section_id}")
def update_section(
    section_id: str,
    body: SectionUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#65 · 更新 Section。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        section = get_section_engine().update(section_id, updates)
        log.info("section_updated id=%s", section_id)
        return section.model_dump()
    except SectionError as err:
        raise _map_section_error(err) from err


@router.delete("/v1/actions/sections/{section_id}")
def delete_section(
    section_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#65 · 删除 Section。"""
    _ = principal
    try:
        get_section_engine().delete(section_id)
        log.info("section_deleted id=%s", section_id)
        return {"deleted": True, "id": section_id}
    except SectionError as err:
        raise _map_section_error(err) from err


@router.post("/v1/actions/sections/{section_id}/visibility")
def evaluate_section_visibility(
    section_id: str,
    body: VisibilityIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#65 · 评估 Section 可见性。"""
    _ = principal
    try:
        return get_section_engine().evaluate_visibility(section_id, body.context)
    except SectionError as err:
        raise _map_section_error(err) from err


@router.post("/v1/actions/{action_id}/sections/reorder")
def reorder_sections(
    action_id: str,
    body: ReorderIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#65 · 批量重排序 Section。"""
    _ = principal
    items = get_section_engine().reorder(action_id, body.ordered_ids)
    log.info("sections_reordered action=%s count=%d", action_id, len(items))
    return {"items": [s.model_dump() for s in items], "count": len(items)}


# ─────────────── #66 Action 撤销（Revert） ───────────────

class RevertRuleIn(BaseModel):
    action_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    revert_window_seconds: int = 0
    pre_revert_check: dict[str, Any] = Field(default_factory=dict)
    on_revert_action_id: str = ""
    requires_confirmation: bool = True


class RevertRuleUpdateIn(BaseModel):
    name: str | None = None
    revert_window_seconds: int | None = None
    pre_revert_check: dict[str, Any] | None = None
    on_revert_action_id: str | None = None
    requires_confirmation: bool | None = None


class RevertCheckIn(BaseModel):
    submission_context: dict[str, Any] = Field(default_factory=dict)


class RevertExecuteIn(BaseModel):
    submission_id: str = Field(min_length=1)
    submission_context: dict[str, Any] = Field(default_factory=dict)


class RecordStatusUpdateIn(BaseModel):
    status: str = Field(min_length=1)


@router.get("/v1/actions/revert-rules")
def list_revert_rules(
    action_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#66 · 列出撤销规则。"""
    _ = principal
    items = get_revert_engine().list_rules(action_id=action_id)
    return {"items": [r.model_dump() for r in items], "count": len(items)}


@router.post("/v1/actions/revert-rules")
def create_revert_rule(
    body: RevertRuleIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#66 · 创建撤销规则。"""
    _ = principal
    rule = RevertRule(**body.model_dump())
    created = get_revert_engine().create_rule(rule)
    log.info("revert_rule_created id=%s action=%s", created.id, created.action_id)
    return created.model_dump()


@router.get("/v1/actions/revert-rules/{rule_id}")
def get_revert_rule(
    rule_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#66 · 获取撤销规则详情。"""
    _ = principal
    try:
        return get_revert_engine().get_rule(rule_id).model_dump()
    except RevertError as err:
        raise _map_revert_error(err) from err


@router.put("/v1/actions/revert-rules/{rule_id}")
def update_revert_rule(
    rule_id: str,
    body: RevertRuleUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#66 · 更新撤销规则。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        rule = get_revert_engine().update_rule(rule_id, updates)
        log.info("revert_rule_updated id=%s", rule_id)
        return rule.model_dump()
    except RevertError as err:
        raise _map_revert_error(err) from err


@router.delete("/v1/actions/revert-rules/{rule_id}")
def delete_revert_rule(
    rule_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#66 · 删除撤销规则。"""
    _ = principal
    try:
        get_revert_engine().delete_rule(rule_id)
        log.info("revert_rule_deleted id=%s", rule_id)
        return {"deleted": True, "id": rule_id}
    except RevertError as err:
        raise _map_revert_error(err) from err


@router.post("/v1/actions/revert-rules/{rule_id}/check")
def check_revert(
    rule_id: str,
    body: RevertCheckIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#66 · 检查提交是否符合撤销条件。"""
    _ = principal
    try:
        return get_revert_engine().check(rule_id, body.submission_context)
    except RevertError as err:
        raise _map_revert_error(err) from err


@router.post("/v1/actions/revert-rules/{rule_id}/execute")
def execute_revert(
    rule_id: str,
    body: RevertExecuteIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#66 · 执行撤销，生成 RevertRecord。"""
    _ = principal
    try:
        record = get_revert_engine().execute(
            rule_id, body.submission_id, body.submission_context
        )
        log.info(
            "revert_executed rule=%s submission=%s record=%s status=%s",
            rule_id, body.submission_id, record.id, record.status,
        )
        return record.model_dump()
    except RevertError as err:
        raise _map_revert_error(err) from err


@router.get("/v1/actions/revert-records")
def list_revert_records(
    rule_id: str | None = None,
    submission_id: str | None = None,
    status: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#66 · 列出撤销记录。"""
    _ = principal
    items = get_revert_engine().list_records(
        rule_id=rule_id, submission_id=submission_id, status=status
    )
    return {"items": [r.model_dump() for r in items], "count": len(items)}


@router.get("/v1/actions/revert-records/{record_id}")
def get_revert_record(
    record_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#66 · 获取撤销记录详情。"""
    _ = principal
    try:
        return get_revert_engine().get_record(record_id).model_dump()
    except RevertError as err:
        raise _map_revert_error(err) from err


@router.put("/v1/actions/revert-records/{record_id}/status")
def update_revert_record_status(
    record_id: str,
    body: RecordStatusUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#66 · 更新撤销记录状态（状态机转换）。"""
    _ = principal
    try:
        record = get_revert_engine().update_record_status(record_id, body.status)
        log.info("revert_record_status_updated id=%s status=%s", record_id, body.status)
        return record.model_dump()
    except RevertError as err:
        raise _map_revert_error(err) from err
