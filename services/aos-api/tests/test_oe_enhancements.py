"""W2-M · Object Explorer 增强测试：#48 高级搜索 + #49 保存探索 + #50 批量导出."""
from __future__ import annotations

import pytest

from aos_api.oe_enhancements import (
    ExportEngine,
    ExportError,
    ExplorationEngine,
    ExplorationError,
    SavedExploration,
    SearchEngine,
    SearchError,
    parse_expression,
)


# ── #48 高级搜索：解析 ──

def test_parse_simple_equality():
    ast = parse_expression('name = "Alice"')
    assert ast["type"] == "comparison"
    assert ast["field"] == "name"
    assert ast["op"] == "="
    assert ast["value"] == "Alice"


def test_parse_and_or():
    ast = parse_expression('name = "Alice" AND age > 30')
    assert ast["type"] == "and"
    assert ast["left"]["op"] == "="
    assert ast["right"]["op"] == ">"


def test_parse_not_and_parens():
    ast = parse_expression('NOT (status = "closed" OR status = "archived")')
    assert ast["type"] == "not"
    inner = ast["operand"]
    assert inner["type"] == "or"


def test_parse_in_clause():
    ast = parse_expression('status IN ("open", "pending", "review")')
    assert ast["op"] == "IN"
    assert ast["value"] == ["open", "pending", "review"]


def test_parse_like_and_regex():
    ast1 = parse_expression('name LIKE "Al%"')
    assert ast1["op"] == "LIKE"
    ast2 = parse_expression('email ~= ".*@example.com"')
    assert ast2["op"] == "~="


def test_parse_error_unclosed_string():
    with pytest.raises(SearchError):
        parse_expression('name = "Alice')


def test_parse_error_missing_operator():
    with pytest.raises(SearchError):
        parse_expression('name "Alice"')


# ── #48 高级搜索：执行 ──

def test_search_equality():
    eng = SearchEngine()
    eng.index("Employee", [
        {"id": "1", "name": "Alice", "age": 30},
        {"id": "2", "name": "Bob", "age": 25},
    ])
    result = eng.search("Employee", 'name = "Alice"')
    assert result["total"] == 1
    assert result["objects"][0]["name"] == "Alice"


def test_search_numeric_comparison():
    eng = SearchEngine()
    eng.index("Employee", [
        {"id": "1", "name": "Alice", "age": 30},
        {"id": "2", "name": "Bob", "age": 25},
        {"id": "3", "name": "Carol", "age": 35},
    ])
    result = eng.search("Employee", "age > 28")
    assert result["total"] == 2


def test_search_and_or_combo():
    eng = SearchEngine()
    eng.index("Employee", [
        {"id": "1", "name": "Alice", "dept": "Eng", "age": 30},
        {"id": "2", "name": "Bob", "dept": "Sales", "age": 40},
        {"id": "3", "name": "Carol", "dept": "Eng", "age": 50},
    ])
    result = eng.search("Employee", 'dept = "Eng" AND age > 35')
    assert result["total"] == 1
    assert result["objects"][0]["name"] == "Carol"


def test_search_like_wildcard():
    eng = SearchEngine()
    eng.index("Employee", [
        {"id": "1", "name": "Alice"},
        {"id": "2", "name": "Alicia"},
        {"id": "3", "name": "Bob"},
    ])
    result = eng.search("Employee", 'name LIKE "Al%"')
    assert result["total"] == 2


def test_search_in_clause():
    eng = SearchEngine()
    eng.index("Employee", [
        {"id": "1", "status": "open"},
        {"id": "2", "status": "pending"},
        {"id": "3", "status": "closed"},
    ])
    result = eng.search("Employee", 'status IN ("open", "pending")')
    assert result["total"] == 2


def test_search_not():
    eng = SearchEngine()
    eng.index("Employee", [
        {"id": "1", "status": "open"},
        {"id": "2", "status": "closed"},
        {"id": "3", "status": "archived"},
    ])
    result = eng.search("Employee", 'NOT status = "open"')
    assert result["total"] == 2


def test_search_pagination():
    eng = SearchEngine()
    eng.index("Employee", [{"id": str(i), "name": f"emp{i}"} for i in range(10)])
    result = eng.search("Employee", 'name LIKE "emp%"', limit=3, offset=2)
    assert result["total"] == 10
    assert len(result["objects"]) == 3
    assert result["objects"][0]["id"] == "2"


# ── #49 保存探索 ──

def test_exploration_create_and_get():
    eng = ExplorationEngine()
    exp = eng.create(SavedExploration(
        name="Active Employees",
        object_type="Employee",
        kind="dynamic",
        owner="alice",
        query={"expression": 'status = "active"', "limit": 50},
    ))
    fetched = eng.get(exp.id)
    assert fetched.name == "Active Employees"
    assert fetched.owner == "alice"


def test_exploration_get_not_found():
    eng = ExplorationEngine()
    with pytest.raises(ExplorationError) as exc:
        eng.get("nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_exploration_list_filter():
    eng = ExplorationEngine()
    eng.create(SavedExploration(name="a", object_type="Employee", owner="alice"))
    eng.create(SavedExploration(name="b", object_type="Department", owner="bob", visibility="public"))
    # alice 看自己的 + 公共
    items = eng.list(owner="alice")
    assert len(items) == 2
    # 只看 Employee
    emp_items = eng.list(object_type="Employee")
    assert len(emp_items) == 1


def test_exploration_update():
    eng = ExplorationEngine()
    exp = eng.create(SavedExploration(name="old", object_type="Employee", owner="alice"))
    updated = eng.update(exp.id, {"name": "new", "visibility": "public"})
    assert updated.name == "new"
    assert updated.visibility == "public"


def test_exploration_delete():
    eng = ExplorationEngine()
    exp = eng.create(SavedExploration(name="temp", object_type="Employee", owner="alice"))
    assert eng.delete(exp.id) is True
    with pytest.raises(ExplorationError):
        eng.get(exp.id)


def test_exploration_execute_dynamic():
    exp_eng = ExplorationEngine()
    search_eng = SearchEngine()
    search_eng.index("Employee", [
        {"id": "1", "name": "Alice", "status": "active"},
        {"id": "2", "name": "Bob", "status": "inactive"},
    ])
    exp = exp_eng.create(SavedExploration(
        name="Active",
        object_type="Employee",
        kind="dynamic",
        owner="alice",
        query={"expression": 'status = "active"'},
    ))
    result = exp_eng.execute(exp.id, search_eng)
    assert result["total"] == 1
    assert result["objects"][0]["name"] == "Alice"


def test_exploration_execute_static_rejected():
    eng = ExplorationEngine()
    exp = eng.create(SavedExploration(
        name="Static List",
        object_type="Employee",
        kind="static",
        owner="alice",
        object_ids=["1", "2", "3"],
    ))
    with pytest.raises(ExplorationError) as exc:
        eng.execute(exp.id, SearchEngine())
    assert exc.value.code == "NOT_DYNAMIC"


# ── #50 批量导出 ──

def test_export_csv():
    eng = ExportEngine()
    objects = [
        {"id": "1", "name": "Alice", "age": 30},
        {"id": "2", "name": "Bob", "age": 25},
    ]
    result = eng.export("Employee", objects, fmt="csv")
    assert result["format"] == "csv"
    assert result["total_rows"] == 2
    assert "name" in result["content"]
    assert "Alice" in result["content"]


def test_export_excel_has_bom():
    eng = ExportEngine()
    result = eng.export("OT", [{"id": "1", "name": "x"}], fmt="excel")
    assert result["content"].startswith("\ufeff")


def test_export_json():
    eng = ExportEngine()
    objects = [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
    result = eng.export("Employee", objects, fmt="json")
    assert result["format"] == "json"
    assert len(result["content"]) == 2
    assert result["content"][0]["name"] == "Alice"


def test_export_specific_columns():
    eng = ExportEngine()
    objects = [{"id": "1", "name": "Alice", "age": 30, "email": "a@x.com"}]
    result = eng.export("Employee", objects, fmt="csv", columns=["name", "age"])
    assert result["columns"] == ["name", "age"]
    assert "email" not in result["content"]


def test_export_filter_by_ids():
    eng = ExportEngine()
    objects = [
        {"id": "1", "name": "Alice"},
        {"id": "2", "name": "Bob"},
        {"id": "3", "name": "Carol"},
    ]
    result = eng.export("Employee", objects, fmt="csv", object_ids=["1", "3"])
    assert result["total_rows"] == 2


def test_export_invalid_format():
    eng = ExportEngine()
    with pytest.raises(ExportError) as exc:
        eng.export("OT", [], fmt="xml")
    assert exc.value.code == "INVALID_FORMAT"


def test_bulk_update():
    eng = ExportEngine()
    objects = [
        {"id": "1", "name": "Alice"},
        {"id": "2", "name": "Bob"},
    ]
    result = eng.bulk_update(objects, {"status": "active"})
    assert result["updated"] == 2
    assert all(o["status"] == "active" for o in result["objects"])


def test_bulk_update_by_ids():
    eng = ExportEngine()
    objects = [
        {"id": "1", "name": "Alice"},
        {"id": "2", "name": "Bob"},
        {"id": "3", "name": "Carol"},
    ]
    result = eng.bulk_update(objects, {"flagged": True}, object_ids=["1", "3"])
    assert result["updated"] == 2


def test_bulk_delete():
    eng = ExportEngine()
    objects = [
        {"id": "1", "name": "Alice"},
        {"id": "2", "name": "Bob"},
        {"id": "3", "name": "Carol"},
    ]
    result = eng.bulk_delete(objects, object_ids=["2"])
    assert result["deleted"] == 1
    assert result["remaining"] == 2
