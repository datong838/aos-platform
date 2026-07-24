"""W2-AL · Data Lineage 可视化引擎测试（#130 / #131 / #132）."""
from __future__ import annotations

import threading
from datetime import date, datetime

import pytest

from aos_api.lineage_visualization import (
    BuildSchedule,
    ColumnIndexEntry,
    ColumnLineageSearchEngine,
    ColumnLineageSearchError,
    LineageBuildTimelineEngine,
    LineageBuildTimelineError,
    LineageView,
    LineageVisualizationEngine,
    LineageVisualizationError,
    get_column_lineage_search_engine,
    get_lineage_build_timeline_engine,
    get_lineage_visualization_engine,
)


# ════════════════════ LineageVisualizationEngine ════════════════════

class TestLineageVisualization:
    def setup_method(self) -> None:
        self.eng = LineageVisualizationEngine.__new__(LineageVisualizationEngine)
        self.eng._views = {}
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> LineageView:
        defaults: dict[str, object] = {
            "name": "test-view",
            "root_dataset_rid": "ri.foundry.main.dataset.abc123",
            "graph_mode": "graph",
            "direction": "both",
            "depth": 3,
            "layout": "horizontal",
            "color_by": "type",
            "saved_by": "user1",
        }
        defaults.update(kw)
        return LineageView(**defaults)

    def test_register(self) -> None:
        v = self.eng.register(self._mk())
        assert v.view_id.startswith("lv-")
        assert v.name == "test-view"
        assert v.created_at is not None

    def test_get(self) -> None:
        v = self.eng.register(self._mk())
        got = self.eng.get(v.view_id)
        assert got.view_id == v.view_id

    def test_list_filter_saved_by(self) -> None:
        self.eng.register(self._mk(name="a", saved_by="user1"))
        self.eng.register(self._mk(name="b", saved_by="user2"))
        results = self.eng.list(saved_by="user1")
        assert len(results) == 1
        assert results[0].saved_by == "user1"

    def test_list_filter_graph_mode(self) -> None:
        self.eng.register(self._mk(name="a", graph_mode="graph"))
        self.eng.register(self._mk(name="b", graph_mode="tree"))
        results = self.eng.list(graph_mode="tree")
        assert len(results) == 1
        assert results[0].graph_mode == "tree"

    def test_update(self) -> None:
        v = self.eng.register(self._mk())
        updated = self.eng.update(v.view_id, {"name": "new-name", "depth": 5})
        assert updated.name == "new-name"
        assert updated.depth == 5

    def test_delete(self) -> None:
        v = self.eng.register(self._mk())
        assert self.eng.delete(v.view_id) is True
        assert self.eng.delete(v.view_id) is False

    def test_get_not_found(self) -> None:
        with pytest.raises(LineageVisualizationError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_generate_graph(self) -> None:
        v = self.eng.register(self._mk())
        graph = self.eng.generate_graph(v.view_id)
        assert graph.view_id == v.view_id
        assert len(graph.nodes) > 0
        assert len(graph.edges) > 0
        assert "node_count" in graph.stats
        assert "types" in graph.stats

    def test_expand_node(self) -> None:
        v = self.eng.register(self._mk())
        graph = self.eng.generate_graph(v.view_id)
        node_id = graph.nodes[0].node_id
        self.eng.collapse_node(v.view_id, node_id)
        expanded = self.eng.expand_node(v.view_id, node_id)
        assert len(expanded.nodes) == len(graph.nodes)

    def test_collapse_node(self) -> None:
        v = self.eng.register(self._mk())
        graph = self.eng.generate_graph(v.view_id)
        node_id = graph.nodes[0].node_id
        collapsed = self.eng.collapse_node(v.view_id, node_id)
        assert node_id not in [n.node_id for n in collapsed.nodes]

    def test_color_by_type(self) -> None:
        v = self.eng.register(self._mk(color_by="type"))
        graph = self.eng.generate_graph(v.view_id)
        colored = self.eng.color_by(v.view_id, "type")
        assert all(node.color != "" for node in colored.nodes)

    def test_color_by_health(self) -> None:
        v = self.eng.register(self._mk(color_by="health"))
        colored = self.eng.color_by(v.view_id, "health")
        assert all(node.color != "" for node in colored.nodes)

    def test_share_view(self) -> None:
        v = self.eng.register(self._mk())
        shared = self.eng.share_view(v.view_id, True)
        assert shared.is_public is True
        unshared = self.eng.share_view(v.view_id, False)
        assert unshared.is_public is False

    def test_list_views_by_dataset(self) -> None:
        self.eng.register(self._mk(name="a", root_dataset_rid="ds1"))
        self.eng.register(self._mk(name="b", root_dataset_rid="ds2"))
        results = self.eng.list_views_by_dataset("ds1")
        assert len(results) == 1
        assert results[0].root_dataset_rid == "ds1"

    def test_register_invalid_name(self) -> None:
        with pytest.raises(LineageVisualizationError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_invalid_graph_mode(self) -> None:
        with pytest.raises(LineageVisualizationError) as exc:
            self.eng.register(self._mk(graph_mode="invalid"))
        assert exc.value.code == "INVALID_GRAPH_MODE"

    def test_register_invalid_depth(self) -> None:
        with pytest.raises(LineageVisualizationError) as exc:
            self.eng.register(self._mk(depth=0))
        assert exc.value.code == "INVALID_DEPTH"

    def test_max_views_eviction(self) -> None:
        from aos_api.lineage_visualization import _MAX_VIEWS
        for i in range(_MAX_VIEWS + 5):
            self.eng.register(LineageView(name=f"v-{i}", root_dataset_rid=f"ds-{i}"))
        assert len(self.eng._views) == _MAX_VIEWS


# ════════════════════ ColumnLineageSearchEngine ════════════════════

class TestColumnLineageSearch:
    def setup_method(self) -> None:
        self.eng = ColumnLineageSearchEngine.__new__(ColumnLineageSearchEngine)
        self.eng._columns = {}
        self.eng._lock = threading.Lock()

    def _mk_key(self, dataset_rid: str, column_name: str) -> str:
        return f"{dataset_rid}::{column_name}"

    def test_register_column(self) -> None:
        entry = self.eng.register_column("ds1", "col1", "string", "test column", ["tag1"])
        assert entry.dataset_rid == "ds1"
        assert entry.column_name == "col1"
        assert entry.last_updated is not None

    def test_get_column(self) -> None:
        self.eng.register_column("ds1", "col1")
        entry = self.eng.get_column("ds1", "col1")
        assert entry.column_name == "col1"

    def test_list_columns(self) -> None:
        self.eng.register_column("ds1", "col_a")
        self.eng.register_column("ds1", "col_b")
        self.eng.register_column("ds2", "col_c")
        results = self.eng.list_columns("ds1")
        assert len(results) == 2

    def test_update_column(self) -> None:
        self.eng.register_column("ds1", "col1")
        updated = self.eng.update_column("ds1", "col1", {"description": "new desc", "data_type": "long"})
        assert updated.description == "new desc"
        assert updated.data_type == "long"

    def test_delete_column(self) -> None:
        self.eng.register_column("ds1", "col1")
        assert self.eng.delete_column("ds1", "col1") is True
        assert self.eng.delete_column("ds1", "col1") is False

    def test_search_keyword(self) -> None:
        self.eng.register_column("ds1", "user_id", "long")
        self.eng.register_column("ds1", "user_name", "string")
        self.eng.register_column("ds1", "order_id", "long")
        results = self.eng.search_columns("user")
        assert len(results) == 2

    def test_search_data_type(self) -> None:
        self.eng.register_column("ds1", "col1", "string")
        self.eng.register_column("ds1", "col2", "long")
        self.eng.register_column("ds1", "col3", "string")
        results = self.eng.search_columns("", data_type="long")
        assert len(results) == 1
        assert results[0].data_type == "long"

    def test_search_tag(self) -> None:
        self.eng.register_column("ds1", "col1", tags=["pii"])
        self.eng.register_column("ds1", "col2", tags=["audit"])
        self.eng.register_column("ds1", "col3", tags=["pii", "audit"])
        results = self.eng.search_columns("", tag="pii")
        assert len(results) == 2

    def test_search_combined(self) -> None:
        self.eng.register_column("ds1", "user_name", "string", tags=["pii"])
        self.eng.register_column("ds1", "user_id", "long", tags=["primary_key"])
        self.eng.register_column("ds1", "order_id", "long", tags=["pii"])
        results = self.eng.search_columns("user", data_type="long", tag="primary_key")
        assert len(results) == 1
        assert results[0].column_name == "user_id"

    def test_trace_upstream(self) -> None:
        self.eng.register_column("ds1", "col1")
        result = self.eng.trace_column("ds1", "col1", "upstream", max_depth=2)
        assert result.direction == "upstream"
        assert result.depth == 2
        assert len(result.path) == 3

    def test_trace_downstream(self) -> None:
        self.eng.register_column("ds1", "col1")
        result = self.eng.trace_column("ds1", "col1", "downstream", max_depth=3)
        assert result.direction == "downstream"
        assert len(result.path) == 4

    def test_trace_invalid_direction(self) -> None:
        self.eng.register_column("ds1", "col1")
        with pytest.raises(ColumnLineageSearchError) as exc:
            self.eng.trace_column("ds1", "col1", "invalid")
        assert exc.value.code == "INVALID_DIRECTION"

    def test_build_index(self) -> None:
        count = self.eng.build_index("ds1")
        assert count == 8
        assert len(self.eng._columns) == 8

    def test_get_not_found(self) -> None:
        with pytest.raises(ColumnLineageSearchError) as exc:
            self.eng.get_column("ds1", "nope")
        assert exc.value.code == "NOT_FOUND"

    def test_register_missing_dataset(self) -> None:
        with pytest.raises(ColumnLineageSearchError) as exc:
            self.eng.register_column("", "col1")
        assert exc.value.code == "MISSING_DATASET"

    def test_register_missing_column(self) -> None:
        with pytest.raises(ColumnLineageSearchError) as exc:
            self.eng.register_column("ds1", "")
        assert exc.value.code == "MISSING_COLUMN"

    def test_invalid_depth(self) -> None:
        self.eng.register_column("ds1", "col1")
        with pytest.raises(ColumnLineageSearchError) as exc:
            self.eng.trace_column("ds1", "col1", "upstream", max_depth=0)
        assert exc.value.code == "INVALID_DEPTH"

    def test_max_columns_eviction(self) -> None:
        from aos_api.lineage_visualization import _MAX_COLUMN_INDEX
        for i in range(_MAX_COLUMN_INDEX + 5):
            self.eng.register_column(f"ds-{i}", f"col-{i}")
        assert len(self.eng._columns) == _MAX_COLUMN_INDEX


# ════════════════════ LineageBuildTimelineEngine ════════════════════

class TestLineageBuildTimeline:
    def setup_method(self) -> None:
        self.eng = LineageBuildTimelineEngine.__new__(LineageBuildTimelineEngine)
        self.eng._schedules = {}
        self.eng._runs = {}
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> BuildSchedule:
        defaults: dict[str, object] = {
            "name": "test-schedule",
            "pipeline_id": "pipe-1",
            "cron_expression": "0 0 * * *",
            "timezone": "UTC",
            "status": "active",
        }
        defaults.update(kw)
        return BuildSchedule(**defaults)

    def test_register_schedule(self) -> None:
        s = self.eng.register_schedule(self._mk())
        assert s.schedule_id.startswith("bs-")
        assert s.name == "test-schedule"
        assert s.created_at is not None
        assert s.next_run_at is not None

    def test_get_schedule(self) -> None:
        s = self.eng.register_schedule(self._mk())
        got = self.eng.get_schedule(s.schedule_id)
        assert got.schedule_id == s.schedule_id

    def test_list_filter_pipeline(self) -> None:
        self.eng.register_schedule(self._mk(name="a", pipeline_id="pipe-1"))
        self.eng.register_schedule(self._mk(name="b", pipeline_id="pipe-2"))
        results = self.eng.list_schedules(pipeline_id="pipe-1")
        assert len(results) == 1
        assert results[0].pipeline_id == "pipe-1"

    def test_list_filter_status(self) -> None:
        self.eng.register_schedule(self._mk(name="a", status="active"))
        self.eng.register_schedule(self._mk(name="b", status="paused"))
        results = self.eng.list_schedules(status="paused")
        assert len(results) == 1
        assert results[0].status == "paused"

    def test_update_schedule(self) -> None:
        s = self.eng.register_schedule(self._mk())
        updated = self.eng.update_schedule(s.schedule_id, {"name": "new-name", "timezone": "Asia/Shanghai"})
        assert updated.name == "new-name"
        assert updated.timezone == "Asia/Shanghai"

    def test_delete_schedule(self) -> None:
        s = self.eng.register_schedule(self._mk())
        assert self.eng.delete_schedule(s.schedule_id) is True
        assert self.eng.delete_schedule(s.schedule_id) is False

    def test_get_not_found(self) -> None:
        with pytest.raises(LineageBuildTimelineError) as exc:
            self.eng.get_schedule("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_compute_next_run(self) -> None:
        s = self.eng.register_schedule(self._mk(cron_expression="0 * * * *"))
        next_run = self.eng.compute_next_run(s.schedule_id)
        assert isinstance(next_run, datetime)
        assert next_run > datetime.utcnow()

    def test_invalid_cron(self) -> None:
        with pytest.raises(LineageBuildTimelineError) as exc:
            self.eng.register_schedule(self._mk(cron_expression="invalid-cron"))
        assert exc.value.code == "INVALID_CRON"

    def test_trigger_run(self) -> None:
        s = self.eng.register_schedule(self._mk())
        run = self.eng.trigger_run(s.schedule_id)
        assert run.run_id.startswith("br-")
        assert run.status == "running"
        assert run.started_at is not None

    def test_trigger_paused_schedule(self) -> None:
        s = self.eng.register_schedule(self._mk(status="paused"))
        with pytest.raises(LineageBuildTimelineError) as exc:
            self.eng.trigger_run(s.schedule_id)
        assert exc.value.code == "SCHEDULE_PAUSED"

    def test_complete_run_success(self) -> None:
        s = self.eng.register_schedule(self._mk())
        run = self.eng.trigger_run(s.schedule_id)
        completed = self.eng.complete_run(run.run_id, True, ["ds1", "ds2"])
        assert completed.status == "success"
        assert completed.finished_at is not None
        assert len(completed.datasets_built) == 2
        assert completed.duration_ms >= 0

    def test_complete_run_failed(self) -> None:
        s = self.eng.register_schedule(self._mk())
        run = self.eng.trigger_run(s.schedule_id)
        completed = self.eng.complete_run(run.run_id, False, error_message="timeout")
        assert completed.status == "failed"
        assert completed.error_message == "timeout"

    def test_get_run(self) -> None:
        s = self.eng.register_schedule(self._mk())
        run = self.eng.trigger_run(s.schedule_id)
        got = self.eng.get_run(run.run_id)
        assert got.run_id == run.run_id

    def test_list_runs(self) -> None:
        s = self.eng.register_schedule(self._mk())
        self.eng.trigger_run(s.schedule_id)
        self.eng.trigger_run(s.schedule_id)
        runs = self.eng.list_runs(s.schedule_id)
        assert len(runs) == 2

    def test_pause_resume(self) -> None:
        s = self.eng.register_schedule(self._mk())
        paused = self.eng.pause_schedule(s.schedule_id)
        assert paused.status == "paused"
        resumed = self.eng.resume_schedule(s.schedule_id)
        assert resumed.status == "active"

    def test_get_gantt_chart(self) -> None:
        self.eng.register_schedule(self._mk(name="daily", cron_expression="0 0 * * *"))
        start = date.today()
        from datetime import timedelta
        end = start + timedelta(days=7)
        chart = self.eng.get_gantt_chart(start, end)
        assert chart.chart_id.startswith("gc-")
        assert len(chart.tasks) > 0
        assert chart.start_date == start
        assert chart.end_date == end

    def test_register_invalid_name(self) -> None:
        with pytest.raises(LineageBuildTimelineError) as exc:
            self.eng.register_schedule(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_missing_pipeline(self) -> None:
        with pytest.raises(LineageBuildTimelineError) as exc:
            self.eng.register_schedule(self._mk(pipeline_id=""))
        assert exc.value.code == "MISSING_PIPELINE"

    def test_invalid_status(self) -> None:
        with pytest.raises(LineageBuildTimelineError) as exc:
            self.eng.register_schedule(self._mk(status="invalid"))
        assert exc.value.code == "INVALID_STATUS"

    def test_max_schedules_eviction(self) -> None:
        from aos_api.lineage_visualization import _MAX_SCHEDULES
        for i in range(_MAX_SCHEDULES + 5):
            self.eng.register_schedule(BuildSchedule(name=f"s-{i}", pipeline_id=f"p-{i}", cron_expression="0 0 * * *"))
        assert len(self.eng._schedules) == _MAX_SCHEDULES


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_lineage_visualization_singleton(self) -> None:
        a = get_lineage_visualization_engine()
        b = get_lineage_visualization_engine()
        assert a is b

    def test_column_lineage_search_singleton(self) -> None:
        a = get_column_lineage_search_engine()
        b = get_column_lineage_search_engine()
        assert a is b

    def test_lineage_build_timeline_singleton(self) -> None:
        a = get_lineage_build_timeline_engine()
        b = get_lineage_build_timeline_engine()
        assert a is b
