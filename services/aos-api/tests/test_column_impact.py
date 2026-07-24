"""W2-AG · 列级影响分析测试（#109 增量补丁）.

覆盖 ColumnImpactEngine：规则 CRUD + BFS 影响分析。
"""
from __future__ import annotations

import threading

import pytest

from aos_api.column_impact import (
    ColumnImpactEngine,
    ColumnImpactError,
    ColumnImpactRule,
    ImpactResult,
    get_impact_engine,
)


class TestColumnImpact:
    def setup_method(self) -> None:
        self.eng = ColumnImpactEngine.__new__(ColumnImpactEngine)
        self.eng._rules = {}
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> ColumnImpactRule:
        defaults: dict[str, object] = {
            "source_dataset_rid": "ds-1",
            "source_column": "col_a",
            "downstream_datasets": ["ds-2"],
            "downstream_columns": ["ds-2.col_b"],
            "transform_expr": "col_a * 2",
        }
        defaults.update(kw)
        return ColumnImpactRule(**defaults)

    def test_register_returns_with_id(self) -> None:
        r = self.eng.register(self._mk())
        assert r.id.startswith("cir-")

    def test_register_missing_source_dataset(self) -> None:
        with pytest.raises(ColumnImpactError) as exc:
            self.eng.register(self._mk(source_dataset_rid=""))
        assert exc.value.code == "MISSING_SOURCE_DATASET"

    def test_register_missing_source_column(self) -> None:
        with pytest.raises(ColumnImpactError) as exc:
            self.eng.register(self._mk(source_column=""))
        assert exc.value.code == "MISSING_SOURCE_COLUMN"

    def test_get_not_found(self) -> None:
        with pytest.raises(ColumnImpactError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(source_column="a"))
        self.eng.register(self._mk(source_column="b"))
        assert len(self.eng.list()) == 2

    def test_list_filter_by_source_dataset(self) -> None:
        self.eng.register(self._mk(source_dataset_rid="ds-a", source_column="x"))
        self.eng.register(self._mk(source_dataset_rid="ds-b", source_column="y"))
        items = self.eng.list(source_dataset_rid="ds-a")
        assert len(items) == 1
        assert items[0].source_dataset_rid == "ds-a"

    def test_delete(self) -> None:
        r = self.eng.register(self._mk())
        assert self.eng.delete(r.id) is True
        assert self.eng.delete(r.id) is False

    def test_analyze_impact_single_layer(self) -> None:
        self.eng.register(ColumnImpactRule(
            source_dataset_rid="ds-1",
            source_column="col_a",
            downstream_datasets=["ds-2"],
            downstream_columns=["ds-2.col_b"],
        ))
        result = self.eng.analyze_impact("ds-1", "col_a")
        assert isinstance(result, ImpactResult)
        assert "ds-2" in result.impacted_datasets
        assert "ds-2.col_b" in result.impacted_columns
        assert result.depth >= 1

    def test_analyze_impact_multi_layer(self) -> None:
        self.eng.register(ColumnImpactRule(
            source_dataset_rid="ds-1",
            source_column="a",
            downstream_datasets=["ds-2"],
            downstream_columns=["ds-2.b"],
        ))
        self.eng.register(ColumnImpactRule(
            source_dataset_rid="ds-2",
            source_column="b",
            downstream_datasets=["ds-3"],
            downstream_columns=["ds-3.c"],
        ))
        result = self.eng.analyze_impact("ds-1", "a")
        assert "ds-2" in result.impacted_datasets
        assert "ds-3" in result.impacted_datasets
        assert "ds-3.c" in result.impacted_columns
        assert result.depth >= 2

    def test_analyze_impact_cycle_prevention(self) -> None:
        self.eng.register(ColumnImpactRule(
            source_dataset_rid="ds-a",
            source_column="x",
            downstream_datasets=["ds-b"],
            downstream_columns=["ds-b.y"],
        ))
        self.eng.register(ColumnImpactRule(
            source_dataset_rid="ds-b",
            source_column="y",
            downstream_datasets=["ds-a"],
            downstream_columns=["ds-a.x"],
        ))
        result = self.eng.analyze_impact("ds-a", "x")
        assert result.depth >= 1
        assert "ds-b" in result.impacted_datasets

    def test_analyze_impact_no_rules(self) -> None:
        result = self.eng.analyze_impact("ds-none", "col-nope")
        assert result.impacted_datasets == []
        assert result.impacted_columns == []
        assert result.depth == 0

    def test_analyze_impact_multiple_rules_same_source(self) -> None:
        self.eng.register(ColumnImpactRule(
            source_dataset_rid="ds-1", source_column="a",
            downstream_datasets=["ds-2"],
            downstream_columns=["ds-2.b"],
        ))
        self.eng.register(ColumnImpactRule(
            source_dataset_rid="ds-1", source_column="a",
            downstream_datasets=["ds-3"],
            downstream_columns=["ds-3.c"],
        ))
        result = self.eng.analyze_impact("ds-1", "a")
        assert "ds-2" in result.impacted_datasets
        assert "ds-3" in result.impacted_datasets

    def test_max_rules_eviction(self) -> None:
        from aos_api.column_impact import _MAX_RULES
        for i in range(_MAX_RULES + 5):
            self.eng.register(ColumnImpactRule(
                source_dataset_rid=f"ds-{i}",
                source_column=f"col-{i}",
            ))
        assert len(self.eng._rules) == _MAX_RULES


class TestSingletons:
    def test_impact_singleton(self) -> None:
        a = get_impact_engine()
        b = get_impact_engine()
        assert a is b
