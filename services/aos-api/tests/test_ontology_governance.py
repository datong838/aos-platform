"""W2-I · Ontology 治理组测试：#38 Usage Metrics + #69 Graph Query."""
from __future__ import annotations

import pytest

from aos_api.ontology_governance import (
    GraphQueryEngine,
    UsageMetric,
    UsageMetricsEngine,
)


# ── #38 Usage Metrics ──
def test_usage_record_and_aggregate():
    eng = UsageMetricsEngine(window_days=7)
    eng.record("read", user_id="u1", source="api", day="2026-07-20")
    eng.record("read", user_id="u2", source="workshop", day="2026-07-20")
    eng.record("write", user_id="u1", source="api", day="2026-07-21")
    eng.record("interaction", user_id="u3", source="quiver", day="2026-07-21")

    m = eng.get_global()
    assert m.reads == 2
    assert m.writes == 1
    assert m.interactions == 1
    assert m.active_users == 3
    assert m.sources["api"] == 2
    assert m.sources["workshop"] == 1
    assert m.sources["quiver"] == 1


def test_usage_per_object_type():
    eng = UsageMetricsEngine(window_days=7)
    eng.record("read", user_id="u1", object_type="Employee", day="2026-07-20")
    eng.record("read", user_id="u1", object_type="Employee", day="2026-07-20")
    eng.record("write", user_id="u2", object_type="Employee", day="2026-07-21")
    eng.record("read", user_id="u1", object_type="Department", day="2026-07-20")

    emp = eng.get_object_type("Employee")
    assert emp.reads == 2
    assert emp.writes == 1
    assert emp.active_users == 2

    dept = eng.get_object_type("Department")
    assert dept.reads == 1
    assert dept.writes == 0

    empty = eng.get_object_type("Nonexistent")
    assert empty.reads == 0
    assert empty.active_users == 0


def test_usage_per_link_type():
    eng = UsageMetricsEngine(window_days=7)
    eng.record("read", user_id="u1", link_type="reports_to", day="2026-07-20")
    eng.record("read", user_id="u2", link_type="member_of", day="2026-07-21")

    reports = eng.get_link_type("reports_to")
    assert reports.reads == 1
    assert reports.active_users == 1

    empty = eng.get_link_type("missing")
    assert empty.reads == 0


def test_usage_daily_series():
    eng = UsageMetricsEngine(window_days=5)
    eng.record("read", day="2026-07-20")
    eng.record("write", day="2026-07-21")
    eng.record("read", day="2026-07-21")

    m = eng.get_global()
    assert len(m.daily_series) == 5
    # 找到有数据的天
    reads_by_day = {d["date"]: d["reads"] for d in m.daily_series}
    assert reads_by_day.get("2026-07-20", 0) == 1
    assert reads_by_day.get("2026-07-21", 0) == 1


def test_usage_prune_old():
    eng = UsageMetricsEngine(window_days=3)
    eng.record("read", day="2026-07-01")  # 太早了
    eng.record("read", day="2026-07-20")

    m = eng.get_global()
    assert m.reads == 1  # 只算窗口内的


def test_usage_reset():
    eng = UsageMetricsEngine(window_days=7)
    eng.record("read", day="2026-07-20")
    assert eng.get_global().reads == 1
    eng.reset()
    assert eng.get_global().reads == 0


def test_usage_metric_model():
    m = UsageMetric(reads=10, writes=5, active_users=3)
    assert m.reads == 10
    assert m.window_days == 30


def test_usage_multiple_sources():
    eng = UsageMetricsEngine(window_days=7)
    for i in range(10):
        eng.record("read", source="workshop", day="2026-07-20")
    for i in range(5):
        eng.record("read", source="quiver", day="2026-07-20")
    for i in range(3):
        eng.record("read", source="api", day="2026-07-20")

    m = eng.get_global()
    assert m.sources["workshop"] == 10
    assert m.sources["quiver"] == 5
    assert m.sources["api"] == 3
    assert m.reads == 18


# ── #69 Graph Query ──
def _build_sample_graph() -> GraphQueryEngine:
    eng = GraphQueryEngine()
    eng.add_edges_batch([
        # Employee hierarchy (A -> B -> C -> D)
        ("reports_to", "Employee", "B", "Employee", "A"),
        ("reports_to", "Employee", "C", "Employee", "B"),
        ("reports_to", "Employee", "D", "Employee", "C"),
        # Department membership
        ("member_of", "Employee", "A", "Department", "Eng"),
        ("member_of", "Employee", "B", "Department", "Eng"),
        ("member_of", "Employee", "C", "Department", "Eng"),
        # Cross dept
        ("member_of", "Employee", "D", "Department", "Sales"),
        # Peer
        ("works_with", "Employee", "A", "Employee", "E"),
        ("works_with", "Employee", "E", "Employee", "F"),
    ])
    return eng


def test_multi_hop_1():
    eng = _build_sample_graph()
    result = eng.multi_hop("Employee", "C", 1)
    assert result["hops"] == 1
    assert result["totalNodes"] == 2  # B (reports_to out 反向... 等等我需要检查方向)
    # 注意：add_edge 的 src/dst 方向
    # reports_to C → B（C 向 B 汇报），所以 out 方向是 C -> B
    # member_of C → Eng
    ids = {(n["type"], n["id"]) for n in result["nodes"]}
    assert ("Employee", "B") in ids
    assert ("Department", "Eng") in ids


def test_multi_hop_2():
    eng = _build_sample_graph()
    result = eng.multi_hop("Employee", "D", 2)
    assert result["hops"] == 2
    assert result["totalNodes"] >= 2
    ids = {(n["type"], n["id"]) for n in result["nodes"]}
    assert ("Employee", "C") in ids
    # 第二跳：C -> B, C -> Eng
    assert ("Employee", "B") in ids or ("Department", "Eng") in ids


def test_multi_hop_rel_filter():
    eng = _build_sample_graph()
    result = eng.multi_hop("Employee", "A", 2, rel="works_with")
    # A -works_with-> E -works_with-> F
    ids = {(n["type"], n["id"]) for n in result["nodes"]}
    assert ("Employee", "E") in ids
    assert ("Employee", "F") in ids
    # 不应有 Department
    assert not any(n["type"] == "Department" for n in result["nodes"])


def test_multi_hop_direction_in():
    eng = _build_sample_graph()
    # in 方向：谁指向我
    result = eng.multi_hop("Employee", "A", 1, direction="in")
    ids = {(n["type"], n["id"]) for n in result["nodes"]}
    # B reports_to A，所以 B 是 A 的入边邻居
    assert ("Employee", "B") in ids


def test_multi_hop_direction_both():
    eng = _build_sample_graph()
    result = eng.multi_hop("Employee", "B", 1, direction="both")
    ids = {(n["type"], n["id"]) for n in result["nodes"]}
    assert ("Employee", "A") in ids  # out: B->A
    assert ("Employee", "C") in ids  # in:  C->B


def test_multi_hop_hops_limit():
    eng = _build_sample_graph()
    with pytest.raises(ValueError):
        eng.multi_hop("Employee", "A", 6)
    with pytest.raises(ValueError):
        eng.multi_hop("Employee", "A", 0)


def test_shortest_path_found():
    eng = _build_sample_graph()
    # A 到 D 的路径：A <- B <- C <- D (reports_to)
    result = eng.shortest_path(
        "Employee", "A", "Employee", "D",
        max_hops=4,
    )
    assert result["found"] is True
    assert result["distance"] == 3
    assert len(result["path"]) == 4


def test_shortest_path_with_rel_filter():
    eng = _build_sample_graph()
    result = eng.shortest_path(
        "Employee", "A", "Employee", "F",
        max_hops=4,
        rels=["works_with"],
    )
    assert result["found"] is True
    assert result["distance"] == 2
    assert len(result["path"]) == 3


def test_shortest_path_not_found():
    eng = _build_sample_graph()
    # 最大跳数不够
    result = eng.shortest_path(
        "Employee", "A", "Employee", "D",
        max_hops=2,
        rels=["works_with"],  # 仅 works_with 关系不到 D
    )
    assert result["found"] is False
    assert result["distance"] == -1


def test_shortest_path_same_node():
    eng = _build_sample_graph()
    result = eng.shortest_path("Employee", "A", "Employee", "A")
    assert result["found"] is True
    assert result["distance"] == 0
    assert len(result["path"]) == 1


def test_expand():
    eng = _build_sample_graph()
    result = eng.expand(
        [("Employee", "A")],
        hops=2,
    )
    assert result["hops"] == 2
    assert result["seedCount"] == 1
    assert result["totalNodes"] >= 3
    # 节点应包含种子 A
    types_ids = {(n["type"], n["id"]) for n in result["nodes"]}
    assert ("Employee", "A") in types_ids


def test_expand_max_nodes():
    eng = _build_sample_graph()
    result = eng.expand(
        [("Employee", "A")],
        hops=3,
        max_nodes=5,
    )
    assert result["totalNodes"] <= 5


def test_graph_reset():
    eng = _build_sample_graph()
    assert eng.multi_hop("Employee", "A", 1)["totalNodes"] > 0
    eng.reset()
    assert eng.multi_hop("Employee", "A", 1)["totalNodes"] == 0
