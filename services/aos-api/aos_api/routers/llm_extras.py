"""W2-U · k-LLM 扩展能力组路由：#74 数据出境策略 + #75 自定义 LLM 注册 + #77 Prompt 工程."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.llm_extras import (
    CustomLLMRegistry,
    EgressAuditRecord,
    EgressDecision,
    EgressPolicy,
    EgressPolicyEngine,
    FunctionInterface,
    LLMExtrasError,
    LLMSource,
    LLMWebhook,
    PromptEngine,
    PromptTemplate,
    SensitiveField,
    get_custom_llm_registry,
    get_egress_policy_engine,
    get_prompt_engine,
)
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["llm-extras"])
log = get_logger("aos-api.llm-extras")


def _map_err(err: LLMExtrasError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND" or err.code == "VERSION_NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #74 数据出境策略 ════════════════════

class SensitiveFieldIn(BaseModel):
    object_type: str = Field(min_length=1)
    field_path: str = Field(min_length=1)
    sensitivity: str = "sensitive"
    pii: bool = False
    mask_strategy: str = "redact"
    description: str = ""


class EgressPolicyIn(BaseModel):
    id: str = Field(min_length=1)
    name: str
    security_label: str
    allowed_egress: str
    mask_before_egress: bool = False
    audit_sample_rate: float = 0.0
    description: str = ""


class EvaluateIn(BaseModel):
    security_label: str
    payload: dict[str, Any] | None = None
    object_type: str | None = None


class AuditRecordIn(BaseModel):
    security_label: str
    decision: str
    masked_fields: list[str] = Field(default_factory=list)
    model_id: str = ""
    query_snippet: str = ""
    route_rule_id: str = ""


@router.get("/v1/aip/egress/sensitive-fields")
def list_sensitive_fields(
    object_type: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#74 · 列出敏感字段。"""
    _ = principal
    items = get_egress_policy_engine().list_sensitive(object_type=object_type)
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.post("/v1/aip/egress/sensitive-fields")
def register_sensitive_field(
    body: SensitiveFieldIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#74 · 注册敏感字段。"""
    _ = principal
    try:
        s = get_egress_policy_engine().register_sensitive(
            SensitiveField(**body.model_dump()),
        )
    except LLMExtrasError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.delete("/v1/aip/egress/sensitive-fields/{object_type}/{field_path}")
def delete_sensitive_field(
    object_type: str,
    field_path: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#74 · 删除敏感字段。"""
    _ = principal
    ok = get_egress_policy_engine().delete_sensitive(object_type, field_path)
    if not ok:
        raise ApiError(
            code="NOT_FOUND",
            message=f"敏感字段 {object_type}/{field_path} 不存在",
            status_code=404,
        )
    return {"object_type": object_type, "field_path": field_path, "deleted": True}


@router.get("/v1/aip/egress/policies")
def list_egress_policies(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#74 · 列出出境策略。"""
    _ = principal
    items = get_egress_policy_engine().list_policies()
    return {"items": [p.model_dump() for p in items], "count": len(items)}


@router.post("/v1/aip/egress/policies")
def upsert_egress_policy(
    body: EgressPolicyIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#74 · 新增/更新出境策略。"""
    _ = principal
    try:
        p = get_egress_policy_engine().upsert_policy(
            EgressPolicy(**body.model_dump()),
        )
    except LLMExtrasError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.get("/v1/aip/egress/policies/{policy_id}")
def get_egress_policy(
    policy_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#74 · 单条出境策略。"""
    _ = principal
    try:
        return {"item": get_egress_policy_engine().get_policy(policy_id).model_dump()}
    except LLMExtrasError as exc:
        raise _map_err(exc) from exc


@router.delete("/v1/aip/egress/policies/{policy_id}")
def delete_egress_policy(
    policy_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#74 · 删除出境策略。"""
    _ = principal
    ok = get_egress_policy_engine().delete_policy(policy_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"策略 {policy_id} 不存在", status_code=404)
    return {"id": policy_id, "deleted": True}


@router.post("/v1/aip/egress/evaluate")
def evaluate_egress(
    body: EvaluateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#74 · 评估请求出境决策。"""
    _ = principal
    decision = get_egress_policy_engine().evaluate(
        body.security_label, payload=body.payload, object_type=body.object_type,
    )
    return {"item": decision.model_dump()}


@router.get("/v1/aip/egress/audit-records")
def list_audit_records(
    model_id: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#74 · 列出审计记录。"""
    _ = principal
    items = get_egress_policy_engine().list_audit_records(model_id=model_id, limit=limit)
    return {"items": [r.model_dump() for r in items], "count": len(items)}


@router.post("/v1/aip/egress/audit-records")
def append_audit_record(
    body: AuditRecordIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#74 · 手动追加审计记录。"""
    _ = principal
    rec = get_egress_policy_engine().record_audit(
        EgressAuditRecord(**body.model_dump()),
    )
    return {"item": rec.model_dump()}


# ════════════════════ #75 自定义 LLM 注册 ════════════════════

class FunctionInterfaceIn(BaseModel):
    id: str = Field(min_length=1)
    name: str
    function_ref: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    model_hint: str = ""
    description: str = ""


class LLMSourceIn(BaseModel):
    id: str = Field(min_length=1)
    name: str
    source_type: str
    source_ref: str
    model_id: str
    retrieval_config: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class LLMWebhookIn(BaseModel):
    id: str = Field(min_length=1)
    name: str
    url: str
    method: str = "POST"
    auth_type: str = "none"
    auth_secret_ref: str = ""
    request_template: str = ""
    response_path: str = "answer"
    description: str = ""


# —— Function Interfaces ——
@router.get("/v1/aip/custom-llm/function-interfaces")
def list_function_interfaces(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    items = get_custom_llm_registry().list_function_interfaces()
    return {"items": [f.model_dump() for f in items], "count": len(items)}


@router.post("/v1/aip/custom-llm/function-interfaces")
def upsert_function_interface(
    body: FunctionInterfaceIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    f = get_custom_llm_registry().upsert_function_interface(
        FunctionInterface(**body.model_dump()),
    )
    return {"item": f.model_dump()}


@router.get("/v1/aip/custom-llm/function-interfaces/{fi_id}")
def get_function_interface(
    fi_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        return {"item": get_custom_llm_registry().get_function_interface(fi_id).model_dump()}
    except LLMExtrasError as exc:
        raise _map_err(exc) from exc


@router.delete("/v1/aip/custom-llm/function-interfaces/{fi_id}")
def delete_function_interface(
    fi_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    ok = get_custom_llm_registry().delete_function_interface(fi_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"FI {fi_id} 不存在", status_code=404)
    return {"id": fi_id, "deleted": True}


# —— LLM Sources ——
@router.get("/v1/aip/custom-llm/sources")
def list_llm_sources(
    source_type: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    items = get_custom_llm_registry().list_sources(source_type=source_type)
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.post("/v1/aip/custom-llm/sources")
def upsert_llm_source(
    body: LLMSourceIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        s = get_custom_llm_registry().upsert_source(LLMSource(**body.model_dump()))
    except LLMExtrasError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.get("/v1/aip/custom-llm/sources/{src_id}")
def get_llm_source(
    src_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        return {"item": get_custom_llm_registry().get_source(src_id).model_dump()}
    except LLMExtrasError as exc:
        raise _map_err(exc) from exc


@router.delete("/v1/aip/custom-llm/sources/{src_id}")
def delete_llm_source(
    src_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    ok = get_custom_llm_registry().delete_source(src_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"Source {src_id} 不存在", status_code=404)
    return {"id": src_id, "deleted": True}


# —— LLM Webhooks ——
@router.get("/v1/aip/custom-llm/webhooks")
def list_llm_webhooks(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    items = get_custom_llm_registry().list_webhooks()
    return {"items": [w.model_dump() for w in items], "count": len(items)}


@router.post("/v1/aip/custom-llm/webhooks")
def upsert_llm_webhook(
    body: LLMWebhookIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        w = get_custom_llm_registry().upsert_webhook(LLMWebhook(**body.model_dump()))
    except LLMExtrasError as exc:
        raise _map_err(exc) from exc
    return {"item": w.model_dump()}


@router.get("/v1/aip/custom-llm/webhooks/{wh_id}")
def get_llm_webhook(
    wh_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        return {"item": get_custom_llm_registry().get_webhook(wh_id).model_dump()}
    except LLMExtrasError as exc:
        raise _map_err(exc) from exc


@router.delete("/v1/aip/custom-llm/webhooks/{wh_id}")
def delete_llm_webhook(
    wh_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    ok = get_custom_llm_registry().delete_webhook(wh_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"Webhook {wh_id} 不存在", status_code=404)
    return {"id": wh_id, "deleted": True}


@router.get("/v1/aip/custom-llm/all")
def list_all_custom_llm(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#75 · 统一返回三形态列表。"""
    _ = principal
    return get_custom_llm_registry().list_all()


# ════════════════════ #77 Prompt 工程 ════════════════════

class PromptTemplateIn(BaseModel):
    name: str = Field(min_length=1)
    template: str = Field(min_length=1)
    variables: list[str] = Field(default_factory=list)
    few_shot_examples: list[dict[str, str]] = Field(default_factory=list)
    is_active: bool = False
    description: str = ""


class PromptUpdateIn(BaseModel):
    template: str | None = None
    variables: list[str] | None = None
    few_shot_examples: list[dict[str, str]] | None = None
    is_active: bool | None = None
    description: str | None = None
    change_note: str = ""


class ActivateVersionIn(BaseModel):
    version: int


class RenderIn(BaseModel):
    template_id: str
    variables: dict[str, str] | None = None
    few_shot_count: int = 0


class RenderAndCallIn(BaseModel):
    template_id: str
    variables: dict[str, str] | None = None
    model: str | None = None
    few_shot_count: int = 0


@router.get("/v1/aip/prompts/templates")
def list_prompt_templates(
    name: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#77 · 列出 Prompt 模板。"""
    _ = principal
    items = get_prompt_engine().list_templates(name=name)
    return {"items": [t.model_dump() for t in items], "count": len(items)}


@router.post("/v1/aip/prompts/templates")
def create_prompt_template(
    body: PromptTemplateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#77 · 新建模板（version=1）。"""
    _ = principal
    t = get_prompt_engine().create_template(
        PromptTemplate(**body.model_dump()),
    )
    return {"item": t.model_dump()}


@router.get("/v1/aip/prompts/templates/{template_id}")
def get_prompt_template(
    template_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#77 · 单条模板。"""
    _ = principal
    try:
        return {"item": get_prompt_engine().get_template(template_id).model_dump()}
    except LLMExtrasError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/aip/prompts/templates/{template_id}")
def update_prompt_template(
    template_id: str,
    body: PromptUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#77 · 更新模板（自动新增版本）。"""
    _ = principal
    try:
        t = get_prompt_engine().update_template(
            template_id, body.model_dump(exclude_none=True),
        )
    except LLMExtrasError as exc:
        raise _map_err(exc) from exc
    return {"item": t.model_dump()}


@router.delete("/v1/aip/prompts/templates/{template_id}")
def delete_prompt_template(
    template_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#77 · 删除模板及所有版本。"""
    _ = principal
    ok = get_prompt_engine().delete_template(template_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"模板 {template_id} 不存在", status_code=404)
    return {"id": template_id, "deleted": True}


@router.post("/v1/aip/prompts/templates/{template_id}/activate")
def activate_prompt_version(
    template_id: str,
    body: ActivateVersionIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#77 · 激活指定版本。"""
    _ = principal
    try:
        t = get_prompt_engine().activate_version(template_id, body.version)
    except LLMExtrasError as exc:
        raise _map_err(exc) from exc
    return {"item": t.model_dump()}


@router.get("/v1/aip/prompts/templates/{template_id}/versions")
def list_prompt_versions(
    template_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#77 · 模板版本历史。"""
    _ = principal
    items = get_prompt_engine().list_versions(template_id)
    return {"items": [v.model_dump() for v in items], "count": len(items)}


@router.post("/v1/aip/prompts/render")
def render_prompt(
    body: RenderIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#77 · 渲染模板。"""
    _ = principal
    try:
        result = get_prompt_engine().render(
            body.template_id, body.variables, few_shot_count=body.few_shot_count,
        )
    except LLMExtrasError as exc:
        raise _map_err(exc) from exc
    return {"item": result.model_dump()}


@router.post("/v1/aip/prompts/render-and-call")
def render_and_call_prompt(
    body: RenderAndCallIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#77 · 渲染并调用 LLM。"""
    _ = principal
    try:
        result = get_prompt_engine().render_and_call(
            body.template_id, body.variables,
            model=body.model, few_shot_count=body.few_shot_count,
        )
    except LLMExtrasError as exc:
        raise _map_err(exc) from exc
    return {"item": result}
