"""Phase 4 · Ontology Branches + Graph Health — 单元测试 (≥3)."""
from __future__ import annotations

import pytest

from aos_api.ontology_engine import get_engine


@pytest.fixture(autouse=True)
def reset_engine():
    get_engine().reset()
    yield


def test_create_and_list_branch() -> None:
    eng = get_engine()
    br = eng.create_branch(name="dev-feature", parent_branch="main")
    assert br.name == "dev-feature"
    items = eng.list_branches()
    assert len(items) == 1
    assert items[0].id == br.id


def test_list_branches_status_filter() -> None:
    eng = get_engine()
    eng.create_branch(name="b1", status="active")
    eng.create_branch(name="b2", status="merged")
    active = eng.list_branches(status="active")
    assert len(active) == 1
    assert active[0].name == "b1"


def test_update_branch() -> None:
    eng = get_engine()
    br = eng.create_branch(name="feat")
    updated = eng.update_branch(br.id, status="merged", description="Merged feat")
    assert updated.status == "merged"
    assert updated.description == "Merged feat"


def test_graph_health() -> None:
    eng = get_engine()
    ot = eng.create_object_type(name="customer")
    eng.create_object(ot.id, name="C1")
    eng.set_column_mapping(ot.id, [{"source_column": "x", "target_property": "y"}])
    health = eng.graph_health()
    assert health["total_object_types"] == 1
    assert health["total_objects"] == 1
    assert health["mapping_coverage"] == 1.0
    assert health["orphan_count"] == 0
    assert health["healthy"] is True


def test_graph_health_with_orphan() -> None:
    eng = get_engine()
    eng.create_object_type(name="customer")  # 无 mapping → orphan
    eng.create_object_type(name="order")
    health = eng.graph_health()
    assert health["orphan_count"] == 2
    assert health["healthy"] is False
