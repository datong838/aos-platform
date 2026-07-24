"""W1-3 · Funnel 可视化映射编辑器单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.funnel_mapping import (
    FunnelMappingEditor,
    FunnelMappingError,
    MappingRule,
    SchemaField,
)
from aos_api.main import create_app

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}

_SOURCE = [
    SchemaField(name="order_id", type="string", nullable=False),
    SchemaField(name="cust_id", type="string"),
    SchemaField(name="amount", type="number"),
    SchemaField(name="created_at", type="date"),
]
_TARGET = [
    SchemaField(name="order_id", type="string", nullable=False),
    SchemaField(name="customer_id", type="string", nullable=False),
    SchemaField(name="total", type="number"),
    SchemaField(name="timestamp", type="date"),
]


def _new_editor() -> FunnelMappingEditor:
    return FunnelMappingEditor()


def _create_sample(editor: FunnelMappingEditor):
    return editor.create("demo", _SOURCE, _TARGET)


# --- 引擎：CRUD --- #

def test_create_and_get():
    e = _new_editor()
    spec = _create_sample(e)
    assert spec.name == "demo"
    assert e.get(spec.id).id == spec.id


def test_list():
    e = _new_editor()
    _create_sample(e)
    _create_sample(e)
    assert len(e.list_all()) == 2


def test_delete():
    e = _new_editor()
    spec = _create_sample(e)
    e.delete(spec.id)
    with pytest.raises(FunnelMappingError):
        e.get(spec.id)


def test_get_404():
    e = _new_editor()
    with pytest.raises(FunnelMappingError) as exc:
        e.get("ghost")
    assert exc.value.code == "NOT_FOUND"


# --- 引擎：规则 --- #

def test_add_rule():
    e = _new_editor()
    spec = _create_sample(e)
    e.add_rule(spec.id, MappingRule(source_field="order_id", target_field="order_id"))
    assert len(e.get(spec.id).rules) == 1


def test_add_rule_bad_target():
    e = _new_editor()
    spec = _create_sample(e)
    with pytest.raises(FunnelMappingError) as exc:
        e.add_rule(spec.id, MappingRule(source_field="x", target_field="ghost"))
    assert exc.value.code == "RULE_BAD_TARGET"


def test_add_rule_upsert():
    e = _new_editor()
    spec = _create_sample(e)
    e.add_rule(spec.id, MappingRule(source_field="order_id", target_field="order_id"))
    e.add_rule(spec.id, MappingRule(source_field="cust_id", target_field="order_id", default="NA"))
    rules = e.get(spec.id).rules
    assert len(rules) == 1
    assert rules[0].source_field == "cust_id"


def test_remove_rule():
    e = _new_editor()
    spec = _create_sample(e)
    e.add_rule(spec.id, MappingRule(source_field="order_id", target_field="order_id"))
    e.remove_rule(spec.id, "order_id")
    assert e.get(spec.id).rules == []


def test_remove_rule_not_found():
    e = _new_editor()
    spec = _create_sample(e)
    with pytest.raises(FunnelMappingError):
        e.remove_rule(spec.id, "ghost")


# --- 引擎：auto_map --- #

def test_auto_map_by_name_and_type():
    e = _new_editor()
    spec = _create_sample(e)
    spec = e.auto_map(spec.id)
    targets = {r.target_field for r in spec.rules}
    assert "order_id" in targets
    assert "timestamp" not in targets


def test_auto_map_matches_when_name_aligns():
    e = _new_editor()
    source = [
        SchemaField(name="order_id", type="string"),
        SchemaField(name="timestamp", type="date"),
    ]
    target = [
        SchemaField(name="order_id", type="string"),
        SchemaField(name="timestamp", type="date"),
    ]
    spec = e.create("aligned", source, target)
    spec = e.auto_map(spec.id)
    targets = {r.target_field for r in spec.rules}
    assert targets == {"order_id", "timestamp"}


def test_auto_map_skips_type_mismatch():
    e = _new_editor()
    source = [SchemaField(name="flag", type="boolean")]
    target = [SchemaField(name="flag", type="number")]
    spec = e.create("m", source, target)
    spec = e.auto_map(spec.id)
    assert spec.rules == []


# --- 引擎：lint --- #

def test_lint_passed():
    e = _new_editor()
    spec = _create_sample(e)
    e.auto_map(spec.id)
    e.add_rule(spec.id, MappingRule(source_field="cust_id", target_field="customer_id"))
    result = e.lint(spec.id)
    assert result.passed is True or len(result.errors) == 0


def test_lint_unmapped_required():
    e = _new_editor()
    spec = _create_sample(e)
    result = e.lint(spec.id)
    assert any("UNMAPPED_REQUIRED" in err for err in result.errors)


def test_lint_type_mismatch():
    e = _new_editor()
    source = [SchemaField(name="flag", type="boolean")]
    target = [SchemaField(name="flag", type="number", nullable=False)]
    spec = e.create("m", source, target)
    e.add_rule(spec.id, MappingRule(source_field="flag", target_field="flag"))
    result = e.lint(spec.id)
    assert any("TYPE_MISMATCH" in err for err in result.errors)


# --- 引擎：模板 --- #

def test_apply_template_ecommerce():
    e = _new_editor()
    spec = _create_sample(e)
    spec = e.apply_template(spec.id, "ecommerce")
    assert spec.template == "ecommerce"
    targets = {f.name for f in spec.target_schema}
    assert "order_id" in targets
    assert any(r.target_field == "order_id" for r in spec.rules)


def test_apply_template_bad():
    e = _new_editor()
    spec = _create_sample(e)
    with pytest.raises(FunnelMappingError) as exc:
        e.apply_template(spec.id, "bogus")
    assert exc.value.code == "BAD_TEMPLATE"


def test_list_templates():
    e = _new_editor()
    templates = e.list_templates()
    assert set(templates) == {"ecommerce", "manufacturing", "finance"}


# --- 引擎：preview --- #

def test_preview_basic():
    e = _new_editor()
    spec = _create_sample(e)
    e.auto_map(spec.id)
    e.add_rule(spec.id, MappingRule(source_field="cust_id", target_field="customer_id"))
    rows = e.preview(spec.id, [
        {"order_id": "O1", "cust_id": "C1", "amount": 100, "created_at": "2026-01-01"},
    ])
    assert rows[0]["order_id"] == "O1"
    assert rows[0]["customer_id"] == "C1"


def test_preview_with_transform():
    e = _new_editor()
    spec = _create_sample(e)
    e.add_rule(spec.id, MappingRule(
        source_field="amount", target_field="total", transform_expr="amount * 110 / 100"))
    rows = e.preview(spec.id, [{"amount": 100}])
    assert abs(rows[0]["total"] - 110.0) < 1e-9


def test_preview_default_value():
    e = _new_editor()
    spec = _create_sample(e)
    e.add_rule(spec.id, MappingRule(
        source_field=None, target_field="customer_id", default="UNKNOWN"))
    rows = e.preview(spec.id, [{}])
    assert rows[0]["customer_id"] == "UNKNOWN"


# --- API --- #

@pytest.fixture()
def client(monkeypatch):
    fresh = FunnelMappingEditor()
    monkeypatch.setattr("aos_api.routers.funnel_mappings.get_editor", lambda: fresh)
    return TestClient(create_app())


def test_api_create(client):
    resp = client.post("/v1/funnel-mappings", json={
        "name": "demo",
        "source_schema": [{"name": "a", "type": "string"}],
        "target_schema": [{"name": "a", "type": "string"}],
    }, headers=_H)
    assert resp.status_code == 200


def test_api_list(client):
    client.post("/v1/funnel-mappings", json={
        "name": "d", "source_schema": [], "target_schema": []}, headers=_H)
    resp = client.get("/v1/funnel-mappings", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["mappings"]) == 1


def test_api_auto_map(client):
    pid = client.post("/v1/funnel-mappings", json={
        "name": "d",
        "source_schema": [{"name": "x", "type": "string"}],
        "target_schema": [{"name": "x", "type": "string"}],
    }, headers=_H).json()["id"]
    resp = client.post(f"/v1/funnel-mappings/{pid}/auto-map", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["rules"]) == 1


def test_api_lint(client):
    pid = client.post("/v1/funnel-mappings", json={
        "name": "d",
        "source_schema": [{"name": "x", "type": "string"}],
        "target_schema": [{"name": "y", "type": "string", "nullable": False}],
    }, headers=_H).json()["id"]
    resp = client.post(f"/v1/funnel-mappings/{pid}/lint", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["passed"] is False


def test_api_preview(client):
    pid = client.post("/v1/funnel-mappings", json={
        "name": "d",
        "source_schema": [{"name": "x", "type": "string"}],
        "target_schema": [{"name": "x", "type": "string"}],
    }, headers=_H).json()["id"]
    client.post(f"/v1/funnel-mappings/{pid}/auto-map", headers=_H)
    resp = client.post(f"/v1/funnel-mappings/{pid}/preview", json={
        "source_rows": [{"x": "hello"}]}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["rows"][0]["x"] == "hello"


def test_api_templates(client):
    resp = client.get("/v1/funnel-mappings/templates/list", headers=_H)
    assert resp.status_code == 200
    assert "ecommerce" in resp.json()["templates"]


def test_api_apply_template(client):
    pid = client.post("/v1/funnel-mappings", json={
        "name": "d",
        "source_schema": [{"name": "order_num", "type": "string"}],
        "target_schema": [],
    }, headers=_H).json()["id"]
    resp = client.post(f"/v1/funnel-mappings/{pid}/apply-template", json={"template": "ecommerce"}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["template"] == "ecommerce"


def test_api_get_404(client):
    resp = client.get("/v1/funnel-mappings/ghost", headers=_H)
    assert resp.status_code == 404
