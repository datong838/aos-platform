"""Phase 4 · Ontology Functions — 单元测试 (≥3)."""
from __future__ import annotations

import pytest

from aos_api.ontology_function_engine import get_function_engine


@pytest.fixture(autouse=True)
def reset_engine():
    get_function_engine().reset()
    yield


def test_create_and_get_function() -> None:
    eng = get_function_engine()
    fn = eng.create_function(name="compute", display_name="Compute")
    fetched = eng.get_function(fn.id)
    assert fetched is not None
    assert fetched.name == "compute"


def test_update_function_bumps_version() -> None:
    eng = get_function_engine()
    fn = eng.create_function(name="f1")
    updated = eng.update_function(fn.id, description="updated")
    assert updated.description == "updated"
    assert updated.version == 2


def test_add_and_list_tests() -> None:
    eng = get_function_engine()
    fn = eng.create_function(name="f")
    eng.add_test(fn.id, name="t1", inputs={"x": 1})
    eng.add_test(fn.id, name="t2", inputs={"x": 2})
    tests = eng.list_tests(fn.id)
    assert len(tests) == 2


def test_run_test_passes() -> None:
    eng = get_function_engine()
    fn = eng.create_function(name="f", body="return x")
    tc = eng.add_test(fn.id, name="t", inputs={"x": 42}, expected=42)
    result = eng.run_test(fn.id, tc.id)
    assert result.status == "passed"
    assert result.output == 42


def test_run_test_fails() -> None:
    eng = get_function_engine()
    fn = eng.create_function(name="f", body="return x")
    tc = eng.add_test(fn.id, name="t", inputs={"x": 1}, expected=999)
    result = eng.run_test(fn.id, tc.id)
    assert result.status == "failed"


def test_list_functions_filter() -> None:
    eng = get_function_engine()
    eng.create_function(name="f1", status="active")
    eng.create_function(name="f2", status="draft")
    active = eng.list_functions(status="active")
    assert len(active) == 1
    assert active[0].name == "f1"
