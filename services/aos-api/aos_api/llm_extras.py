"""W2-U · k-LLM 扩展能力组：#74 数据出境策略 + #75 自定义 LLM 注册 + #77 Prompt 工程.

本模块是 ``aos_api.llm_gateway.chat()`` 之上的策略层与元数据层：
    - EgressPolicyEngine  数据出境策略（敏感标记 + 字段级 egress 评估 + 审计抽检）
    - CustomLLMRegistry   自定义 LLM 注册（Function Interfaces / Source / Webhook 三形态）
    - PromptEngine        Prompt 工程（模板 CRUD + 变量注入 + Few-shot + 版本管理 + 渲染）

底层网关 ``chat(query, model=X)`` 不重写，仅作为调用出口。
"""
from __future__ import annotations

import random
import re
import threading
import time
import uuid
from typing import Any, Callable

from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────────
# 公共工具
# ────────────────────────────────────────────────────────────────

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


class LLMExtrasError(Exception):
    """W2-U 扩展能力层错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


# ════════════════════════════════════════════════════════════════
# #74 数据出境策略
# ════════════════════════════════════════════════════════════════

class SensitiveField(BaseModel):
    """敏感字段标记。"""

    object_type: str
    field_path: str
    sensitivity: str = "sensitive"   # public / internal / sensitive / restricted
    pii: bool = False
    mask_strategy: str = "redact"    # none / hash / redact / substitute
    description: str = ""


class EgressPolicy(BaseModel):
    """数据出境策略。"""

    id: str
    name: str
    security_label: str              # public / internal / sensitive / restricted
    allowed_egress: str              # allow / restricted / forbidden
    mask_before_egress: bool = False
    audit_sample_rate: float = 0.0
    description: str = ""


class EgressDecision(BaseModel):
    """单次请求的出境决策。"""

    allowed: bool
    egress: str                      # allow / restricted / forbidden
    masked_fields: list[str] = Field(default_factory=list)
    audit_required: bool = False
    reason: str = ""


class EgressAuditRecord(BaseModel):
    """出境审计记录。"""

    id: str = Field(default_factory=lambda: _uid("audit"))
    timestamp: float = Field(default_factory=_now_ts)
    security_label: str
    decision: str
    masked_fields: list[str] = Field(default_factory=list)
    model_id: str = ""
    query_snippet: str = ""
    route_rule_id: str = ""


_DEFAULT_EGRESS_MAP = {
    "public": "allow",
    "internal": "allow",
    "sensitive": "restricted",
    "restricted": "forbidden",
}


def _walk_fields(payload: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """递归扫描 payload 顶层 + 一层嵌套（性能保护）。返回 [(path, value)]。"""
    out: list[tuple[str, Any]] = []
    if not isinstance(payload, dict):
        return out
    for k, v in payload.items():
        path = f"{prefix}.{k}" if prefix else str(k)
        out.append((path, v))
        if isinstance(v, dict):
            for k2, v2 in v.items():
                out.append((f"{path}.{k2}", v2))
    return out


class EgressPolicyEngine:
    """#74 · 数据出境策略引擎。"""

    def __init__(
        self,
        rng: Callable[[], float] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._sensitive: dict[tuple[str, str], SensitiveField] = {}
        self._policies: dict[str, EgressPolicy] = {}
        self._audit: list[EgressAuditRecord] = []
        self._rng = rng or random.random

    # —— 敏感字段 ——
    def register_sensitive(self, sf: SensitiveField) -> SensitiveField:
        if sf.sensitivity not in {"public", "internal", "sensitive", "restricted"}:
            raise LLMExtrasError(
                "INVALID_SENSITIVITY",
                f"未知敏感等级: {sf.sensitivity}",
            )
        if sf.mask_strategy not in {"none", "hash", "redact", "substitute"}:
            raise LLMExtrasError(
                "INVALID_MASK_STRATEGY",
                f"未知脱敏策略: {sf.mask_strategy}",
            )
        with self._lock:
            self._sensitive[(sf.object_type, sf.field_path)] = sf
        return sf

    def list_sensitive(self, object_type: str | None = None) -> list[SensitiveField]:
        with self._lock:
            items = list(self._sensitive.values())
        if object_type:
            items = [s for s in items if s.object_type == object_type]
        return items

    def delete_sensitive(self, object_type: str, field_path: str) -> bool:
        with self._lock:
            return self._sensitive.pop((object_type, field_path), None) is not None

    # —— 出境策略 ——
    def upsert_policy(self, policy: EgressPolicy) -> EgressPolicy:
        if policy.security_label not in {"public", "internal", "sensitive", "restricted"}:
            raise LLMExtrasError(
                "INVALID_SECURITY_LABEL",
                f"未知安全等级: {policy.security_label}",
            )
        if policy.allowed_egress not in {"allow", "restricted", "forbidden"}:
            raise LLMExtrasError(
                "INVALID_EGRESS",
                f"未知 egress: {policy.allowed_egress}",
            )
        if not (0.0 <= policy.audit_sample_rate <= 1.0):
            raise LLMExtrasError(
                "INVALID_AUDIT_RATE",
                f"audit_sample_rate 必须在 [0,1]: {policy.audit_sample_rate}",
            )
        with self._lock:
            self._policies[policy.id] = policy
        return policy

    def get_policy(self, policy_id: str) -> EgressPolicy:
        with self._lock:
            p = self._policies.get(policy_id)
        if not p:
            raise LLMExtrasError("NOT_FOUND", f"出境策略 {policy_id} 不存在")
        return p

    def list_policies(self) -> list[EgressPolicy]:
        with self._lock:
            return list(self._policies.values())

    def delete_policy(self, policy_id: str) -> bool:
        with self._lock:
            return self._policies.pop(policy_id, None) is not None

    # —— 评估 ——
    def evaluate(
        self,
        security_label: str,
        payload: dict[str, Any] | None = None,
        object_type: str | None = None,
    ) -> EgressDecision:
        # 找匹配策略
        with self._lock:
            policy = next(
                (p for p in self._policies.values()
                 if p.security_label == security_label),
                None,
            )

        if policy is None:
            # 默认策略
            egress = _DEFAULT_EGRESS_MAP.get(security_label, "forbidden")
            mask_before = False
            audit_rate = 0.0
            policy_id = ""
        else:
            egress = policy.allowed_egress
            mask_before = policy.mask_before_egress
            audit_rate = policy.audit_sample_rate
            policy_id = policy.id

        masked_fields: list[str] = []
        if mask_before and payload is not None and object_type:
            with self._lock:
                sensitives = [
                    s for s in self._sensitive.values()
                    if s.object_type == object_type
                ]
            payload_fields = _walk_fields(payload)
            sens_paths = {s.field_path for s in sensitives}
            for path, _ in payload_fields:
                if path in sens_paths:
                    masked_fields.append(path)

        audit_required = audit_rate > 0 and self._rng() < audit_rate

        if egress == "forbidden":
            return EgressDecision(
                allowed=False, egress="forbidden",
                masked_fields=masked_fields,
                audit_required=audit_required,
                reason=f"安全等级 {security_label} 禁止出境",
            )
        if egress == "restricted" and not mask_before:
            return EgressDecision(
                allowed=False, egress="restricted",
                masked_fields=[],
                audit_required=audit_required,
                reason=f"安全等级 {security_label} 需脱敏后出境，但策略未启用 mask_before_egress",
            )
        if egress == "restricted":
            return EgressDecision(
                allowed=True, egress="restricted",
                masked_fields=masked_fields,
                audit_required=audit_required,
                reason=f"安全等级 {security_label} 脱敏后允许出境",
            )
        return EgressDecision(
            allowed=True, egress="allow",
            masked_fields=[],
            audit_required=audit_required,
            reason=f"安全等级 {security_label} 允许出境",
        )

    # —— 审计 ——
    def record_audit(self, record: EgressAuditRecord) -> EgressAuditRecord:
        with self._lock:
            self._audit.append(record)
            if len(self._audit) > 200:
                self._audit = self._audit[-200:]
        return record

    def list_audit_records(
        self,
        model_id: str | None = None,
        limit: int = 50,
    ) -> list[EgressAuditRecord]:
        with self._lock:
            items = list(self._audit)
        if model_id:
            items = [r for r in items if r.model_id == model_id]
        return list(reversed(items[-limit:]))


# ════════════════════════════════════════════════════════════════
# #75 自定义 LLM 注册
# ════════════════════════════════════════════════════════════════

class FunctionInterface(BaseModel):
    """Function Interfaces 形态。"""

    id: str
    name: str
    function_ref: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    model_hint: str = ""
    description: str = ""


class LLMSource(BaseModel):
    """Source 形态 — LLM + 数据源组合。"""

    id: str
    name: str
    source_type: str                  # knowledge_base / vector_index / dataset / media_set
    source_ref: str
    model_id: str
    retrieval_config: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class LLMWebhook(BaseModel):
    """Webhook 形态 — 通过外部 webhook 接入自定义 LLM。"""

    id: str
    name: str
    url: str
    method: str = "POST"              # GET / POST
    auth_type: str = "none"           # none / bearer / basic / hmac
    auth_secret_ref: str = ""
    request_template: str = ""
    response_path: str = "answer"
    description: str = ""


_VALID_SOURCE_TYPES = {"knowledge_base", "vector_index", "dataset", "media_set"}
_VALID_WEBHOOK_METHODS = {"GET", "POST"}
_VALID_WEBHOOK_AUTH = {"none", "bearer", "basic", "hmac"}


class CustomLLMRegistry:
    """#75 · 自定义 LLM 注册（Function Interfaces / Source / Webhook 三形态）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._fis: dict[str, FunctionInterface] = {}
        self._sources: dict[str, LLMSource] = {}
        self._webhooks: dict[str, LLMWebhook] = {}

    # —— Function Interfaces ——
    def upsert_function_interface(self, fi: FunctionInterface) -> FunctionInterface:
        with self._lock:
            self._fis[fi.id] = fi
        return fi

    def get_function_interface(self, fi_id: str) -> FunctionInterface:
        with self._lock:
            f = self._fis.get(fi_id)
        if not f:
            raise LLMExtrasError("NOT_FOUND", f"Function Interface {fi_id} 不存在")
        return f

    def list_function_interfaces(self) -> list[FunctionInterface]:
        with self._lock:
            return list(self._fis.values())

    def delete_function_interface(self, fi_id: str) -> bool:
        with self._lock:
            return self._fis.pop(fi_id, None) is not None

    # —— LLM Source ——
    def upsert_source(self, src: LLMSource) -> LLMSource:
        if src.source_type not in _VALID_SOURCE_TYPES:
            raise LLMExtrasError(
                "INVALID_SOURCE_TYPE",
                f"未知 source_type: {src.source_type}（合法: {sorted(_VALID_SOURCE_TYPES)}）",
            )
        with self._lock:
            self._sources[src.id] = src
        return src

    def get_source(self, src_id: str) -> LLMSource:
        with self._lock:
            s = self._sources.get(src_id)
        if not s:
            raise LLMExtrasError("NOT_FOUND", f"LLM Source {src_id} 不存在")
        return s

    def list_sources(self, source_type: str | None = None) -> list[LLMSource]:
        with self._lock:
            items = list(self._sources.values())
        if source_type:
            items = [s for s in items if s.source_type == source_type]
        return items

    def delete_source(self, src_id: str) -> bool:
        with self._lock:
            return self._sources.pop(src_id, None) is not None

    # —— LLM Webhook ——
    def upsert_webhook(self, wh: LLMWebhook) -> LLMWebhook:
        if wh.method not in _VALID_WEBHOOK_METHODS:
            raise LLMExtrasError(
                "INVALID_METHOD",
                f"未知 method: {wh.method}（合法: {sorted(_VALID_WEBHOOK_METHODS)}）",
            )
        if wh.auth_type not in _VALID_WEBHOOK_AUTH:
            raise LLMExtrasError(
                "INVALID_AUTH_TYPE",
                f"未知 auth_type: {wh.auth_type}（合法: {sorted(_VALID_WEBHOOK_AUTH)}）",
            )
        with self._lock:
            self._webhooks[wh.id] = wh
        return wh

    def get_webhook(self, wh_id: str) -> LLMWebhook:
        with self._lock:
            w = self._webhooks.get(wh_id)
        if not w:
            raise LLMExtrasError("NOT_FOUND", f"LLM Webhook {wh_id} 不存在")
        return w

    def list_webhooks(self) -> list[LLMWebhook]:
        with self._lock:
            return list(self._webhooks.values())

    def delete_webhook(self, wh_id: str) -> bool:
        with self._lock:
            return self._webhooks.pop(wh_id, None) is not None

    # —— 统一 ——
    def list_all(self) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            return {
                "function_interfaces": [f.model_dump() for f in self._fis.values()],
                "sources": [s.model_dump() for s in self._sources.values()],
                "webhooks": [w.model_dump() for w in self._webhooks.values()],
            }


# ════════════════════════════════════════════════════════════════
# #77 Prompt 工程
# ════════════════════════════════════════════════════════════════

class PromptTemplate(BaseModel):
    """Prompt 模板。"""

    id: str = Field(default_factory=lambda: _uid("tpl"))
    name: str
    template: str
    variables: list[str] = Field(default_factory=list)
    few_shot_examples: list[dict[str, str]] = Field(default_factory=list)
    version: int = 1
    is_active: bool = False
    description: str = ""
    created_at: float = Field(default_factory=_now_ts)


class PromptVersion(BaseModel):
    """Prompt 版本记录。"""

    template_id: str
    version: int
    template: str
    timestamp: float = Field(default_factory=_now_ts)
    change_note: str = ""


class RenderResult(BaseModel):
    """渲染结果。"""

    rendered: str
    variables_used: dict[str, str] = Field(default_factory=dict)
    few_shot_count: int = 0
    template_id: str
    version: int


class PromptEngine:
    """#77 · Prompt 工程引擎。"""

    def __init__(
        self,
        chat_callable: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        # template_id → 模板（仅最新版本）
        self._templates: dict[str, PromptTemplate] = {}
        # template_id → 版本历史
        self._versions: dict[str, list[PromptVersion]] = {}
        self._chat = chat_callable

    def _resolve_chat(self) -> Callable[..., dict[str, Any]]:
        if self._chat is not None:
            return self._chat
        from aos_api.llm_gateway import chat as _chat
        self._chat = _chat
        return self._chat

    # —— CRUD ——
    def create_template(self, tpl: PromptTemplate) -> PromptTemplate:
        # 自动提取变量
        if not tpl.variables:
            tpl.variables = sorted(set(_VAR_RE.findall(tpl.template)))
        with self._lock:
            # 同 name 不允许重复 id，但允许多个版本（version=1 时 is_active=True）
            self._templates[tpl.id] = tpl
            self._versions.setdefault(tpl.id, []).append(
                PromptVersion(
                    template_id=tpl.id,
                    version=tpl.version,
                    template=tpl.template,
                    change_note="初始版本",
                )
            )
            # 同 name 仅一个 active
            if tpl.is_active:
                self._deactivate_others_locked(tpl.name, tpl.id)
            else:
                # 若同 name 无其他 active，则当前激活
                has_active = any(
                    t.is_active for t in self._templates.values()
                    if t.name == tpl.name and t.id != tpl.id
                )
                if not has_active:
                    tpl.is_active = True
        return tpl

    def get_template(self, template_id: str) -> PromptTemplate:
        with self._lock:
            t = self._templates.get(template_id)
        if not t:
            raise LLMExtrasError("NOT_FOUND", f"模板 {template_id} 不存在")
        return t

    def list_templates(self, name: str | None = None) -> list[PromptTemplate]:
        with self._lock:
            items = list(self._templates.values())
        if name:
            items = [t for t in items if t.name == name]
        return items

    def update_template(
        self,
        template_id: str,
        updates: dict[str, Any],
    ) -> PromptTemplate:
        with self._lock:
            t = self._templates.get(template_id)
            if not t:
                raise LLMExtrasError("NOT_FOUND", f"模板 {template_id} 不存在")
            new_version = t.version + 1
            new_template = PromptTemplate(
                id=t.id,
                name=t.name,
                template=str(updates.get("template", t.template)),
                variables=updates.get("variables") or sorted(
                    set(_VAR_RE.findall(str(updates.get("template", t.template))))
                ),
                few_shot_examples=updates.get("few_shot_examples", t.few_shot_examples),
                version=new_version,
                is_active=bool(updates.get("is_active", True)),
                description=updates.get("description", t.description),
                created_at=_now_ts(),
            )
            self._templates[template_id] = new_template
            self._versions.setdefault(template_id, []).append(
                PromptVersion(
                    template_id=template_id,
                    version=new_version,
                    template=new_template.template,
                    change_note=str(updates.get("change_note", "")),
                )
            )
            if new_template.is_active:
                self._deactivate_others_locked(new_template.name, template_id)
            return new_template

    def delete_template(self, template_id: str) -> bool:
        with self._lock:
            t = self._templates.pop(template_id, None)
            self._versions.pop(template_id, None)
            return t is not None

    def activate_version(self, template_id: str, version: int) -> PromptTemplate:
        with self._lock:
            t = self._templates.get(template_id)
            if not t:
                raise LLMExtrasError("NOT_FOUND", f"模板 {template_id} 不存在")
            versions = self._versions.get(template_id, [])
            target = next((v for v in versions if v.version == version), None)
            if not target:
                raise LLMExtrasError(
                    "VERSION_NOT_FOUND",
                    f"模板 {template_id} 无版本 {version}",
                )
            t.template = target.template
            t.version = version
            t.is_active = True
            t.variables = sorted(set(_VAR_RE.findall(target.template)))
            self._deactivate_others_locked(t.name, template_id)
            return t

    def list_versions(self, template_id: str) -> list[PromptVersion]:
        with self._lock:
            return list(self._versions.get(template_id, []))

    def _deactivate_others_locked(self, name: str, active_id: str) -> None:
        """同 name 其他模板置为 inactive（调用方持锁）。"""
        for t in self._templates.values():
            if t.name == name and t.id != active_id:
                t.is_active = False

    def _find_active(self, name: str) -> PromptTemplate | None:
        """按 name 找 active 模板。"""
        with self._lock:
            return next(
                (t for t in self._templates.values()
                 if t.name == name and t.is_active),
                None,
            )

    # —— 渲染 ——
    def render(
        self,
        template_id: str,
        variables: dict[str, str] | None = None,
        few_shot_count: int = 0,
    ) -> RenderResult:
        t = self.get_template(template_id)
        # 若 inactive，回退到同 name active
        if not t.is_active:
            active = self._find_active(t.name)
            if active:
                t = active

        rendered = t.template
        variables_used: dict[str, str] = {}
        for var_name, var_val in (variables or {}).items():
            rendered = rendered.replace(f"{{{{{var_name}}}}}", str(var_val))
            variables_used[var_name] = str(var_val)

        # Few-shot 拼接
        actual_few_shot = 0
        if few_shot_count > 0 and t.few_shot_examples:
            shots = t.few_shot_examples[:few_shot_count]
            actual_few_shot = len(shots)
            prefix = ""
            for shot in shots:
                u = shot.get("user", "")
                a = shot.get("assistant", "")
                prefix += f"User: {u}\nAssistant: {a}\n\n"
            rendered = prefix + rendered

        return RenderResult(
            rendered=rendered,
            variables_used=variables_used,
            few_shot_count=actual_few_shot,
            template_id=t.id,
            version=t.version,
        )

    def render_and_call(
        self,
        template_id: str,
        variables: dict[str, str] | None = None,
        model: str | None = None,
        few_shot_count: int = 0,
    ) -> dict[str, Any]:
        chat = self._resolve_chat()
        result = self.render(template_id, variables, few_shot_count=few_shot_count)
        chat_out = chat(result.rendered, model=model)
        return {
            "answer": chat_out.get("answer", ""),
            "model": chat_out.get("model") or model or "",
            "template_id": result.template_id,
            "version": result.version,
            "rendered": result.rendered,
            "raw": chat_out,
        }


# ────────────────────────────────────────────────────────────────
# 单例 getters（双重检查锁）
# ────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_egress_engine: EgressPolicyEngine | None = None
_custom_llm_registry: CustomLLMRegistry | None = None
_prompt_engine: PromptEngine | None = None


def get_egress_policy_engine() -> EgressPolicyEngine:
    global _egress_engine
    if _egress_engine is None:
        with _lock:
            if _egress_engine is None:
                _egress_engine = EgressPolicyEngine()
    return _egress_engine


def get_custom_llm_registry() -> CustomLLMRegistry:
    global _custom_llm_registry
    if _custom_llm_registry is None:
        with _lock:
            if _custom_llm_registry is None:
                _custom_llm_registry = CustomLLMRegistry()
    return _custom_llm_registry


def get_prompt_engine() -> PromptEngine:
    global _prompt_engine
    if _prompt_engine is None:
        with _lock:
            if _prompt_engine is None:
                _prompt_engine = PromptEngine()
    return _prompt_engine
