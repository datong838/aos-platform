"""W2-U · k-LLM 扩展能力组测试：#74 数据出境策略 + #75 自定义 LLM 注册 + #77 Prompt 工程."""
from __future__ import annotations

import pytest

from aos_api.llm_extras import (
    CustomLLMRegistry,
    EgressAuditRecord,
    EgressPolicy,
    EgressPolicyEngine,
    FunctionInterface,
    LLMExtrasError,
    LLMSource,
    LLMWebhook,
    PromptEngine,
    PromptTemplate,
    SensitiveField,
)


# ──────────────── #74 数据出境策略 ────────────────

def test_egress_register_sensitive():
    eng = EgressPolicyEngine()
    s = eng.register_sensitive(SensitiveField(
        object_type="Employee", field_path="salary",
    ))
    assert s.object_type == "Employee"
    assert s.sensitivity == "sensitive"


def test_egress_list_sensitive_filter():
    eng = EgressPolicyEngine()
    eng.register_sensitive(SensitiveField(object_type="Employee", field_path="salary"))
    eng.register_sensitive(SensitiveField(object_type="Customer", field_path="phone"))
    assert len(eng.list_sensitive()) == 2
    assert len(eng.list_sensitive(object_type="Employee")) == 1


def test_egress_delete_sensitive():
    eng = EgressPolicyEngine()
    eng.register_sensitive(SensitiveField(object_type="Employee", field_path="salary"))
    assert eng.delete_sensitive("Employee", "salary") is True
    assert eng.list_sensitive() == []
    assert eng.delete_sensitive("Employee", "salary") is False


def test_egress_upsert_policy():
    eng = EgressPolicyEngine()
    p = eng.upsert_policy(EgressPolicy(
        id="p1", name="敏感策略",
        security_label="sensitive", allowed_egress="restricted",
        mask_before_egress=True,
    ))
    assert p.id == "p1"
    assert p.mask_before_egress is True


def test_egress_get_policy_not_found():
    eng = EgressPolicyEngine()
    with pytest.raises(LLMExtrasError) as exc:
        eng.get_policy("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_egress_list_policies():
    eng = EgressPolicyEngine()
    eng.upsert_policy(EgressPolicy(id="p1", name="a", security_label="public", allowed_egress="allow"))
    eng.upsert_policy(EgressPolicy(id="p2", name="b", security_label="restricted", allowed_egress="forbidden"))
    assert len(eng.list_policies()) == 2


def test_egress_delete_policy():
    eng = EgressPolicyEngine()
    eng.upsert_policy(EgressPolicy(id="p1", name="a", security_label="public", allowed_egress="allow"))
    assert eng.delete_policy("p1") is True
    with pytest.raises(LLMExtrasError):
        eng.get_policy("p1")


def test_egress_evaluate_public_allow():
    eng = EgressPolicyEngine()
    d = eng.evaluate("public")
    assert d.allowed is True
    assert d.egress == "allow"


def test_egress_evaluate_restricted_forbidden():
    eng = EgressPolicyEngine()
    d = eng.evaluate("restricted")
    assert d.allowed is False
    assert d.egress == "forbidden"


def test_egress_evaluate_sensitive_with_mask():
    eng = EgressPolicyEngine()
    eng.register_sensitive(SensitiveField(object_type="Employee", field_path="salary"))
    eng.upsert_policy(EgressPolicy(
        id="p1", name="敏感脱敏后允许",
        security_label="sensitive", allowed_egress="restricted",
        mask_before_egress=True,
    ))
    d = eng.evaluate("sensitive", payload={"salary": 5000, "name": "Alice"}, object_type="Employee")
    assert d.allowed is True
    assert d.egress == "restricted"
    assert "salary" in d.masked_fields


def test_egress_evaluate_default_no_policy():
    eng = EgressPolicyEngine()
    # internal 默认 allow
    d = eng.evaluate("internal")
    assert d.allowed is True
    assert d.egress == "allow"


def test_egress_evaluate_audit_required():
    # 注入确定性 random，使 audit_rate=0.5 时一定触发
    eng = EgressPolicyEngine(rng=lambda: 0.3)
    eng.upsert_policy(EgressPolicy(
        id="p1", name="抽检",
        security_label="public", allowed_egress="allow",
        audit_sample_rate=0.5,
    ))
    d = eng.evaluate("public")
    assert d.audit_required is True


def test_egress_evaluate_audit_not_required():
    eng = EgressPolicyEngine(rng=lambda: 0.8)
    eng.upsert_policy(EgressPolicy(
        id="p1", name="抽检",
        security_label="public", allowed_egress="allow",
        audit_sample_rate=0.5,
    ))
    d = eng.evaluate("public")
    assert d.audit_required is False


def test_egress_record_and_list_audit():
    eng = EgressPolicyEngine()
    eng.record_audit(EgressAuditRecord(
        security_label="sensitive", decision="restricted", model_id="m1",
    ))
    eng.record_audit(EgressAuditRecord(
        security_label="public", decision="allow", model_id="m2",
    ))
    all_records = eng.list_audit_records()
    assert len(all_records) == 2
    m1_records = eng.list_audit_records(model_id="m1")
    assert len(m1_records) == 1
    assert m1_records[0].model_id == "m1"


def test_egress_evaluate_restricted_no_mask_disallowed():
    eng = EgressPolicyEngine()
    eng.upsert_policy(EgressPolicy(
        id="p1", name="敏感无脱敏",
        security_label="sensitive", allowed_egress="restricted",
        mask_before_egress=False,
    ))
    d = eng.evaluate("sensitive")
    assert d.allowed is False
    assert "未启用 mask_before_egress" in d.reason


def test_egress_invalid_sensitivity():
    eng = EgressPolicyEngine()
    with pytest.raises(LLMExtrasError) as exc:
        eng.register_sensitive(SensitiveField(
            object_type="X", field_path="y", sensitivity="invalid",
        ))
    assert exc.value.code == "INVALID_SENSITIVITY"


# ──────────────── #75 自定义 LLM 注册 ────────────────

def test_registry_upsert_function_interface():
    r = CustomLLMRegistry()
    f = r.upsert_function_interface(FunctionInterface(
        id="fi1", name="摘要FI", function_ref="fn-summarize",
    ))
    assert f.id == "fi1"
    assert f.function_ref == "fn-summarize"


def test_registry_get_function_interface_not_found():
    r = CustomLLMRegistry()
    with pytest.raises(LLMExtrasError) as exc:
        r.get_function_interface("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_registry_list_function_interfaces():
    r = CustomLLMRegistry()
    r.upsert_function_interface(FunctionInterface(id="fi1", name="a", function_ref="f1"))
    r.upsert_function_interface(FunctionInterface(id="fi2", name="b", function_ref="f2"))
    assert len(r.list_function_interfaces()) == 2


def test_registry_delete_function_interface():
    r = CustomLLMRegistry()
    r.upsert_function_interface(FunctionInterface(id="fi1", name="a", function_ref="f1"))
    assert r.delete_function_interface("fi1") is True
    with pytest.raises(LLMExtrasError):
        r.get_function_interface("fi1")


def test_registry_upsert_source():
    r = CustomLLMRegistry()
    s = r.upsert_source(LLMSource(
        id="s1", name="知识库LLM",
        source_type="knowledge_base", source_ref="kb-1", model_id="m1",
    ))
    assert s.id == "s1"
    assert s.source_type == "knowledge_base"


def test_registry_get_source_not_found():
    r = CustomLLMRegistry()
    with pytest.raises(LLMExtrasError) as exc:
        r.get_source("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_registry_list_sources_filter():
    r = CustomLLMRegistry()
    r.upsert_source(LLMSource(id="s1", name="a", source_type="knowledge_base", source_ref="kb", model_id="m"))
    r.upsert_source(LLMSource(id="s2", name="b", source_type="vector_index", source_ref="vi", model_id="m"))
    assert len(r.list_sources()) == 2
    assert len(r.list_sources(source_type="knowledge_base")) == 1


def test_registry_delete_source():
    r = CustomLLMRegistry()
    r.upsert_source(LLMSource(id="s1", name="a", source_type="dataset", source_ref="d", model_id="m"))
    assert r.delete_source("s1") is True
    with pytest.raises(LLMExtrasError):
        r.get_source("s1")


def test_registry_upsert_webhook():
    r = CustomLLMRegistry()
    w = r.upsert_webhook(LLMWebhook(id="w1", name="自定义LLM", url="https://x/llm"))
    assert w.id == "w1"
    assert w.method == "POST"


def test_registry_get_webhook_not_found():
    r = CustomLLMRegistry()
    with pytest.raises(LLMExtrasError) as exc:
        r.get_webhook("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_registry_list_webhooks():
    r = CustomLLMRegistry()
    r.upsert_webhook(LLMWebhook(id="w1", name="a", url="https://a"))
    r.upsert_webhook(LLMWebhook(id="w2", name="b", url="https://b"))
    assert len(r.list_webhooks()) == 2


def test_registry_delete_webhook():
    r = CustomLLMRegistry()
    r.upsert_webhook(LLMWebhook(id="w1", name="a", url="https://a"))
    assert r.delete_webhook("w1") is True
    with pytest.raises(LLMExtrasError):
        r.get_webhook("w1")


def test_registry_list_all():
    r = CustomLLMRegistry()
    r.upsert_function_interface(FunctionInterface(id="fi1", name="a", function_ref="f"))
    r.upsert_source(LLMSource(id="s1", name="b", source_type="dataset", source_ref="d", model_id="m"))
    r.upsert_webhook(LLMWebhook(id="w1", name="c", url="https://x"))
    all_items = r.list_all()
    assert "function_interfaces" in all_items
    assert "sources" in all_items
    assert "webhooks" in all_items
    assert len(all_items["function_interfaces"]) == 1
    assert len(all_items["sources"]) == 1
    assert len(all_items["webhooks"]) == 1


def test_registry_invalid_source_type():
    r = CustomLLMRegistry()
    with pytest.raises(LLMExtrasError) as exc:
        r.upsert_source(LLMSource(
            id="s1", name="a", source_type="invalid",
            source_ref="x", model_id="m",
        ))
    assert exc.value.code == "INVALID_SOURCE_TYPE"


def test_registry_invalid_webhook_method():
    r = CustomLLMRegistry()
    with pytest.raises(LLMExtrasError) as exc:
        r.upsert_webhook(LLMWebhook(id="w1", name="a", url="https://x", method="DELETE"))
    assert exc.value.code == "INVALID_METHOD"


# ──────────────── #77 Prompt 工程 ────────────────

def _ok_chat(query, model=None, **kw):
    return {"answer": f"[{model}] {query}", "model": model}


def test_prompt_create_template():
    eng = PromptEngine()
    t = eng.create_template(PromptTemplate(
        name="greet", template="Hello {{name}}!",
    ))
    assert t.version == 1
    assert "name" in t.variables
    assert t.is_active is True  # 同 name 首个自动 active


def test_prompt_get_template_not_found():
    eng = PromptEngine()
    with pytest.raises(LLMExtrasError) as exc:
        eng.get_template("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_prompt_list_templates_filter():
    eng = PromptEngine()
    eng.create_template(PromptTemplate(name="a", template="x"))
    eng.create_template(PromptTemplate(name="b", template="y"))
    assert len(eng.list_templates()) == 2
    assert len(eng.list_templates(name="a")) == 1


def test_prompt_update_creates_new_version():
    eng = PromptEngine()
    t = eng.create_template(PromptTemplate(name="greet", template="v1 {{name}}"))
    updated = eng.update_template(t.id, {"template": "v2 {{name}}"})
    assert updated.version == 2
    assert updated.template == "v2 {{name}}"
    # 旧版本历史保留
    versions = eng.list_versions(t.id)
    assert len(versions) == 2


def test_prompt_delete_template():
    eng = PromptEngine()
    t = eng.create_template(PromptTemplate(name="greet", template="x"))
    assert eng.delete_template(t.id) is True
    with pytest.raises(LLMExtrasError):
        eng.get_template(t.id)
    # 版本历史也清除
    assert eng.list_versions(t.id) == []


def test_prompt_activate_version():
    eng = PromptEngine()
    t = eng.create_template(PromptTemplate(name="greet", template="v1"))
    eng.update_template(t.id, {"template": "v2"})
    eng.update_template(t.id, {"template": "v3"})
    # 激活 v2
    activated = eng.activate_version(t.id, 2)
    assert activated.version == 2
    assert activated.template == "v2"
    assert activated.is_active is True


def test_prompt_list_versions_sorted():
    eng = PromptEngine()
    t = eng.create_template(PromptTemplate(name="greet", template="v1"))
    eng.update_template(t.id, {"template": "v2"})
    eng.update_template(t.id, {"template": "v3"})
    versions = eng.list_versions(t.id)
    assert [v.version for v in versions] == [1, 2, 3]


def test_prompt_render_basic():
    eng = PromptEngine()
    t = eng.create_template(PromptTemplate(
        name="greet", template="Hello {{name}}, you are {{role}}!",
    ))
    result = eng.render(t.id, {"name": "Alice", "role": "admin"})
    assert result.rendered == "Hello Alice, you are admin!"
    assert result.variables_used == {"name": "Alice", "role": "admin"}
    assert result.template_id == t.id


def test_prompt_render_missing_variable_preserved():
    eng = PromptEngine()
    t = eng.create_template(PromptTemplate(
        name="greet", template="Hello {{name}}, {{missing}}!",
    ))
    result = eng.render(t.id, {"name": "Alice"})
    assert result.rendered == "Hello Alice, {{missing}}!"


def test_prompt_render_with_few_shot():
    eng = PromptEngine()
    t = eng.create_template(PromptTemplate(
        name="classify",
        template="Classify: {{text}}",
        few_shot_examples=[
            {"user": "good", "assistant": "positive"},
            {"user": "bad", "assistant": "negative"},
            {"user": "ok", "assistant": "neutral"},
        ],
    ))
    result = eng.render(t.id, {"text": "great"}, few_shot_count=2)
    assert result.few_shot_count == 2
    assert "User: good" in result.rendered
    assert "Assistant: positive" in result.rendered
    assert "Classify: great" in result.rendered


def test_prompt_render_few_shot_count_exceeds_actual():
    eng = PromptEngine()
    t = eng.create_template(PromptTemplate(
        name="x", template="T: {{x}}",
        few_shot_examples=[{"user": "a", "assistant": "b"}],
    ))
    result = eng.render(t.id, {"x": "y"}, few_shot_count=5)
    # 仅 1 个示例可用
    assert result.few_shot_count == 1


def test_prompt_render_inactive_falls_back_to_active():
    eng = PromptEngine()
    t1 = eng.create_template(PromptTemplate(name="greet", template="v1 {{name}}", is_active=True))
    t2 = eng.create_template(PromptTemplate(name="greet", template="v2 {{name}}", is_active=False))
    # t2 是 inactive，渲染时回退到 t1
    result = eng.render(t2.id, {"name": "Alice"})
    # 注意：因 t2 inactive 会找同 name 的 active 即 t1
    assert "v1" in result.rendered


def test_prompt_render_and_call_end_to_end():
    eng = PromptEngine(chat_callable=_ok_chat)
    t = eng.create_template(PromptTemplate(
        name="greet", template="Hello {{name}}!",
    ))
    result = eng.render_and_call(t.id, {"name": "Alice"}, model="m1")
    assert "answer" in result
    assert "Hello Alice!" in result["answer"]
    assert result["template_id"] == t.id
    assert result["version"] == 1


def test_prompt_auto_extract_variables():
    eng = PromptEngine()
    t = eng.create_template(PromptTemplate(
        name="x", template="{{a}} and {{b}} and {{a}}",
    ))
    # 变量去重排序
    assert t.variables == ["a", "b"]
