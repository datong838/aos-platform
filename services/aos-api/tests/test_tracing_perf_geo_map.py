"""W2-BO · Distributed Tracing / Pipeline Perf / Geospatial / Map Visualization 引擎组测试（#26 #27 #30 #31）.

覆盖 4 个内存态引擎的 CRUD、校验、FIFO 淘汰与单例 getter。
每个测试类通过 setup_method 创建全新引擎实例，互不干扰；单例测试不 reset 全局实例。
"""
import pytest
import time

from aos_api.tracing_perf_geo_map import (
    DistributedTracingEngine, TraceSpan, TraceContext,
    PipelinePerfEngine, PerfProfile, PerfBenchmark,
    GeospatialEngine, GeoFeature, GeoQuery,
    MapVisualizationEngine, MapLayer, MapTemplate,
    TracingPerfGeoMapError,
    get_distributed_tracing_engine,
    get_pipeline_perf_engine,
    get_geospatial_engine,
    get_map_visualization_engine,
)


# ════════════════════ #26 Distributed Tracing ════════════════════

class TestDistributedTracingEngine:
    def setup_method(self):
        self.engine = DistributedTracingEngine()

    def test_start_trace(self):
        trace, root_span = self.engine.start_trace(
            "op", "svc", attributes={"k": "v"}
        )
        assert isinstance(trace, TraceContext)
        assert isinstance(root_span, TraceSpan)
        assert trace.trace_id
        assert trace.id.startswith("trace-")
        assert trace.root_span_id == root_span.id
        assert trace.span_count == 1
        assert trace.service_count == 1
        assert trace.status == "active"
        assert trace.started_at > 0
        assert trace.completed_at == 0
        assert root_span.id.startswith("span-")
        assert root_span.trace_id == trace.trace_id
        assert root_span.parent_span_id == ""
        assert root_span.operation_name == "op"
        assert root_span.service_name == "svc"
        assert root_span.status == "active"
        assert root_span.attributes == {"k": "v"}
        assert root_span.events == []

    def test_start_trace_invalid_input(self):
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.start_trace("", "svc")
        assert exc.value.code == "INVALID_INPUT"
        with pytest.raises(TracingPerfGeoMapError) as exc2:
            self.engine.start_trace("op", "")
        assert exc2.value.code == "INVALID_INPUT"

    def test_start_span(self):
        trace, root = self.engine.start_trace("root", "svc")
        child = self.engine.start_span(
            trace.trace_id, "child", "svc", parent_span_id=root.id
        )
        assert child.id.startswith("span-")
        assert child.trace_id == trace.trace_id
        assert child.parent_span_id == root.id
        assert child.operation_name == "child"
        assert child.service_name == "svc"
        assert child.status == "active"
        # span_count 递增
        updated_trace = self.engine.get_trace(trace.trace_id)
        assert updated_trace.span_count == 2

    def test_start_span_invalid_trace(self):
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.start_span("nonexistent-tid", "op", "svc")
        assert exc.value.code == "NOT_FOUND"

    def test_start_span_invalid_input(self):
        trace, root = self.engine.start_trace("root", "svc")
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.start_span(trace.trace_id, "", "svc")
        assert exc.value.code == "INVALID_INPUT"
        with pytest.raises(TracingPerfGeoMapError) as exc2:
            self.engine.start_span(trace.trace_id, "op", "")
        assert exc2.value.code == "INVALID_INPUT"

    def test_finish_span(self):
        trace, span = self.engine.start_trace("op", "svc")
        time.sleep(0.002)
        finished = self.engine.finish_span(
            span.id, status="completed", events=[{"name": "done"}]
        )
        assert finished.status == "completed"
        assert finished.end_time > 0
        assert finished.duration_ms > 0
        assert finished.events == [{"name": "done"}]
        # error 状态
        trace2, span2 = self.engine.start_trace("op2", "svc")
        finished_err = self.engine.finish_span(span2.id, status="error")
        assert finished_err.status == "error"

    def test_finish_span_invalid_status(self):
        trace, span = self.engine.start_trace("op", "svc")
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.finish_span(span.id, status="active")
        assert exc.value.code == "INVALID_STATUS"
        with pytest.raises(TracingPerfGeoMapError) as exc2:
            self.engine.finish_span(span.id, status="bogus")
        assert exc2.value.code == "INVALID_STATUS"

    def test_finish_span_not_found(self):
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.finish_span("nonexistent", status="completed")
        assert exc.value.code == "NOT_FOUND"

    def test_get_span(self):
        trace, span = self.engine.start_trace("op", "svc")
        got = self.engine.get_span(span.id)
        assert got.id == span.id
        assert got.operation_name == "op"
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_span("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_spans(self):
        trace1, root1 = self.engine.start_trace("op1", "svc-a")
        trace2, root2 = self.engine.start_trace("op2", "svc-b")
        child = self.engine.start_span(
            trace1.trace_id, "child", "svc-a", parent_span_id=root1.id
        )
        self.engine.finish_span(root1.id, status="completed")
        self.engine.finish_span(child.id, status="error")
        # filter by trace_id
        spans_t1 = self.engine.list_spans(trace_id=trace1.trace_id)
        assert len(spans_t1) == 2
        assert all(s.trace_id == trace1.trace_id for s in spans_t1)
        # filter by status
        completed = self.engine.list_spans(status="completed")
        assert all(s.status == "completed" for s in completed)
        assert any(s.id == root1.id for s in completed)
        errors = self.engine.list_spans(status="error")
        assert all(s.status == "error" for s in errors)
        assert len(errors) == 1
        # combined filter
        both = self.engine.list_spans(trace_id=trace1.trace_id, status="completed")
        assert len(both) == 1
        assert both[0].id == root1.id

    def test_add_event(self):
        trace, span = self.engine.start_trace("op", "svc")
        updated = self.engine.add_event(span.id, {"name": "event1", "ts": 123})
        assert len(updated.events) == 1
        assert updated.events[0] == {"name": "event1", "ts": 123}
        updated2 = self.engine.add_event(span.id, {"name": "event2"})
        assert len(updated2.events) == 2
        assert updated2.events[1] == {"name": "event2"}
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.add_event("nonexistent", {"name": "x"})
        assert exc.value.code == "NOT_FOUND"

    def test_finish_trace(self):
        trace, root = self.engine.start_trace("op", "svc")
        time.sleep(0.002)
        finished = self.engine.finish_trace(trace.trace_id, status="completed")
        assert finished.status == "completed"
        assert finished.completed_at > 0
        # error 状态
        trace2, root2 = self.engine.start_trace("op2", "svc")
        finished_err = self.engine.finish_trace(trace2.trace_id, status="error")
        assert finished_err.status == "error"
        # invalid status
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.finish_trace(trace.trace_id, status="active")
        assert exc.value.code == "INVALID_STATUS"

    def test_get_trace(self):
        trace, root = self.engine.start_trace("op", "svc")
        got = self.engine.get_trace(trace.trace_id)
        assert got.trace_id == trace.trace_id
        assert got.root_span_id == root.id
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_trace("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_traces(self):
        trace1, _ = self.engine.start_trace("op1", "svc-a")
        trace2, _ = self.engine.start_trace("op2", "svc-b")
        self.engine.finish_trace(trace1.trace_id, status="completed")
        # no filter
        all_traces = self.engine.list_traces()
        assert len(all_traces) == 2
        assert all(isinstance(t, TraceContext) for t in all_traces)
        # filter by status
        active = self.engine.list_traces(status="active")
        assert all(t.status == "active" for t in active)
        assert len(active) == 1
        assert active[0].trace_id == trace2.trace_id
        completed = self.engine.list_traces(status="completed")
        assert all(t.status == "completed" for t in completed)
        assert len(completed) == 1
        assert completed[0].trace_id == trace1.trace_id

    def test_get_trace_tree(self):
        trace, root = self.engine.start_trace("root", "svc-a")
        child = self.engine.start_span(
            trace.trace_id, "child", "svc-b", parent_span_id=root.id
        )
        time.sleep(0.002)
        self.engine.finish_span(root.id, status="completed")
        self.engine.finish_span(child.id, status="completed")
        tree = self.engine.get_trace_tree(trace.trace_id)
        assert tree["trace_id"] == trace.trace_id
        assert len(tree["spans"]) == 2
        assert all(isinstance(s, dict) for s in tree["spans"])
        assert tree["by_service"] == {"svc-a": 1, "svc-b": 1}
        assert tree["total_duration_ms"] > 0
        # 不存在的 trace
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_trace_tree("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_delete_span(self):
        trace, root = self.engine.start_trace("op", "svc")
        child = self.engine.start_span(trace.trace_id, "child", "svc")
        assert self.engine.delete_span(child.id) is True
        assert self.engine.delete_span(child.id) is False  # already deleted
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_span(child.id)
        assert exc.value.code == "NOT_FOUND"
        # root 仍存在
        assert self.engine.get_span(root.id).id == root.id

    def test_delete_trace(self):
        trace, root = self.engine.start_trace("op", "svc")
        child = self.engine.start_span(trace.trace_id, "child", "svc")
        assert self.engine.delete_trace(trace.trace_id) is True
        assert self.engine.delete_trace(trace.trace_id) is False  # already deleted
        # trace 已删除
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_trace(trace.trace_id)
        assert exc.value.code == "NOT_FOUND"
        # 关联 spans 也被清理
        with pytest.raises(TracingPerfGeoMapError):
            self.engine.get_span(root.id)
        with pytest.raises(TracingPerfGeoMapError):
            self.engine.get_span(child.id)

    def test_fifo_eviction_spans(self):
        trace, root_span = self.engine.start_trace("root", "svc")
        capacity = self.engine._MAX_SPANS
        for i in range(capacity):
            self.engine.start_span(trace.trace_id, f"op{i}", "svc")
        # 最早创建的 root_span 被淘汰
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_span(root_span.id)
        assert exc.value.code == "NOT_FOUND"
        # 总数等于容量上限
        assert len(self.engine.list_spans()) == capacity


# ════════════════════ #27 Pipeline Perf ════════════════════

class TestPipelinePerfEngine:
    def setup_method(self):
        self.engine = PipelinePerfEngine()

    def test_create_profile(self):
        profile = self.engine.create_profile(
            "pipe-1",
            "spark_optimization",
            description="desc",
            config={"k": "v"},
            estimated_improvement_pct=12.5,
        )
        assert profile.id.startswith("perf-")
        assert profile.pipeline_id == "pipe-1"
        assert profile.optimization_type == "spark_optimization"
        assert profile.description == "desc"
        assert profile.config == {"k": "v"}
        assert profile.estimated_improvement_pct == 12.5
        assert profile.applied is False
        assert profile.created_at > 0

    def test_create_profile_invalid_type(self):
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.create_profile("pipe-1", "bogus_type")
        assert exc.value.code == "INVALID_OPTIMIZATION_TYPE"
        with pytest.raises(TracingPerfGeoMapError) as exc2:
            self.engine.create_profile("", "spark_optimization")
        assert exc2.value.code == "INVALID_INPUT"

    def test_get_profile(self):
        profile = self.engine.create_profile("pipe-1", "spark_optimization")
        got = self.engine.get_profile(profile.id)
        assert got.id == profile.id
        assert got.pipeline_id == "pipe-1"
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_profile("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_profiles(self):
        p1 = self.engine.create_profile("pipe-1", "spark_optimization")
        p2 = self.engine.create_profile("pipe-1", "projection_pushdown")
        p3 = self.engine.create_profile("pipe-2", "spark_optimization")
        self.engine.apply_profile(p1.id)
        # filter by pipeline_id
        pipe1 = self.engine.list_profiles(pipeline_id="pipe-1")
        assert len(pipe1) == 2
        assert all(p.pipeline_id == "pipe-1" for p in pipe1)
        # filter by optimization_type
        spark = self.engine.list_profiles(optimization_type="spark_optimization")
        assert len(spark) == 2
        assert all(p.optimization_type == "spark_optimization" for p in spark)
        # filter by applied_only
        applied = self.engine.list_profiles(applied_only=True)
        assert len(applied) == 1
        assert applied[0].id == p1.id
        # no filter
        all_profiles = self.engine.list_profiles()
        assert len(all_profiles) == 3

    def test_update_profile(self):
        profile = self.engine.create_profile("pipe-1", "spark_optimization", "desc")
        updated = self.engine.update_profile(
            profile.id,
            {"description": "new desc", "estimated_improvement_pct": 15.0},
        )
        assert updated.description == "new desc"
        assert updated.estimated_improvement_pct == 15.0
        assert updated.id == profile.id  # id 不可变
        assert updated.pipeline_id == "pipe-1"
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.update_profile("nonexistent", {"description": "x"})
        assert exc.value.code == "NOT_FOUND"

    def test_apply_profile(self):
        profile = self.engine.create_profile("pipe-1", "spark_optimization")
        assert profile.applied is False
        applied = self.engine.apply_profile(profile.id)
        assert applied.applied is True
        # 持久化
        got = self.engine.get_profile(profile.id)
        assert got.applied is True
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.apply_profile("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_delete_profile(self):
        profile = self.engine.create_profile("pipe-1", "spark_optimization")
        assert self.engine.delete_profile(profile.id) is True
        assert self.engine.delete_profile(profile.id) is False
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_profile(profile.id)
        assert exc.value.code == "NOT_FOUND"

    def test_record_benchmark(self):
        bench = self.engine.record_benchmark(
            "pipe-1",
            before_duration_ms=1000,
            after_duration_ms=600,
            profile_id="perf-1234",
        )
        assert bench.id.startswith("bench-")
        assert bench.pipeline_id == "pipe-1"
        assert bench.profile_id == "perf-1234"
        assert bench.before_duration_ms == 1000
        assert bench.after_duration_ms == 600
        # improvement_pct = (1000 - 600) / 1000 * 100 = 40
        assert bench.improvement_pct == pytest.approx(40.0)
        assert bench.measured_at > 0

    def test_record_benchmark_invalid_input(self):
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.record_benchmark("", 1000, 600)
        assert exc.value.code == "INVALID_INPUT"
        with pytest.raises(TracingPerfGeoMapError) as exc2:
            self.engine.record_benchmark("pipe-1", 0, 600)
        assert exc2.value.code == "INVALID_DURATION"
        with pytest.raises(TracingPerfGeoMapError) as exc3:
            self.engine.record_benchmark("pipe-1", -1, 600)
        assert exc3.value.code == "INVALID_DURATION"

    def test_get_benchmark(self):
        bench = self.engine.record_benchmark("pipe-1", 1000, 600)
        got = self.engine.get_benchmark(bench.id)
        assert got.id == bench.id
        assert got.pipeline_id == "pipe-1"
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_benchmark("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_benchmarks(self):
        b1 = self.engine.record_benchmark("pipe-1", 1000, 600)
        b2 = self.engine.record_benchmark("pipe-1", 800, 400)
        b3 = self.engine.record_benchmark("pipe-2", 500, 250)
        # no filter
        all_b = self.engine.list_benchmarks()
        assert len(all_b) == 3
        # filter by pipeline_id
        pipe1 = self.engine.list_benchmarks(pipeline_id="pipe-1")
        assert len(pipe1) == 2
        assert all(b.pipeline_id == "pipe-1" for b in pipe1)
        pipe2 = self.engine.list_benchmarks(pipeline_id="pipe-2")
        assert len(pipe2) == 1
        assert pipe2[0].id == b3.id

    def test_delete_benchmark(self):
        bench = self.engine.record_benchmark("pipe-1", 1000, 600)
        assert self.engine.delete_benchmark(bench.id) is True
        assert self.engine.delete_benchmark(bench.id) is False
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_benchmark(bench.id)
        assert exc.value.code == "NOT_FOUND"


# ════════════════════ #30 Geospatial ════════════════════

class TestGeospatialEngine:
    def setup_method(self):
        self.engine = GeospatialEngine()

    def test_add_feature(self):
        feature = self.engine.add_feature(
            "p1",
            "point",
            coordinates=[1.0, 2.0],
            properties={"k": "v"},
            crs="EPSG:4326",
        )
        assert feature.id.startswith("geo-")
        assert feature.name == "p1"
        assert feature.geometry_type == "point"
        assert feature.coordinates == [1.0, 2.0]
        assert feature.properties == {"k": "v"}
        assert feature.crs == "EPSG:4326"
        assert feature.created_at > 0

    def test_add_feature_invalid_geometry_type(self):
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.add_feature("p", "bogus", coordinates=[1, 2])
        assert exc.value.code == "INVALID_GEOMETRY_TYPE"
        with pytest.raises(TracingPerfGeoMapError) as exc2:
            self.engine.add_feature("", "point", coordinates=[1, 2])
        assert exc2.value.code == "INVALID_INPUT"

    def test_get_feature(self):
        feature = self.engine.add_feature("p", "point", coordinates=[1, 2])
        got = self.engine.get_feature(feature.id)
        assert got.id == feature.id
        assert got.name == "p"
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_feature("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_features(self):
        f1 = self.engine.add_feature("p1", "point", coordinates=[1, 2])
        f2 = self.engine.add_feature("l1", "linestring", coordinates=[[0, 0], [1, 1]])
        f3 = self.engine.add_feature("p2", "point", coordinates=[3, 4])
        # no filter
        all_f = self.engine.list_features()
        assert len(all_f) == 3
        # filter by geometry_type
        points = self.engine.list_features(geometry_type="point")
        assert len(points) == 2
        assert all(f.geometry_type == "point" for f in points)
        lines = self.engine.list_features(geometry_type="linestring")
        assert len(lines) == 1
        assert lines[0].id == f2.id

    def test_update_feature(self):
        feature = self.engine.add_feature("p", "point", coordinates=[1, 2])
        updated = self.engine.update_feature(
            feature.id, {"name": "updated", "properties": {"k": "v"}}
        )
        assert updated.name == "updated"
        assert updated.properties == {"k": "v"}
        assert updated.id == feature.id
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.update_feature("nonexistent", {"name": "x"})
        assert exc.value.code == "NOT_FOUND"

    def test_delete_feature(self):
        feature = self.engine.add_feature("p", "point", coordinates=[1, 2])
        assert self.engine.delete_feature(feature.id) is True
        assert self.engine.delete_feature(feature.id) is False
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_feature(feature.id)
        assert exc.value.code == "NOT_FOUND"

    def test_query_bbox(self):
        inside = self.engine.add_feature("inside", "point", coordinates=[5.0, 5.0])
        outside = self.engine.add_feature("outside", "point", coordinates=[50.0, 50.0])
        # 非 point 类型（coordinates[0] 是 list）应被跳过
        line = self.engine.add_feature(
            "line", "linestring", coordinates=[[0, 0], [1, 1]]
        )
        query = self.engine.query_bbox(0.0, 0.0, 10.0, 10.0)
        assert query.id.startswith("gq-")
        assert query.query_type == "bbox"
        assert query.parameters == {
            "min_x": 0.0,
            "min_y": 0.0,
            "max_x": 10.0,
            "max_y": 10.0,
        }
        assert inside.id in query.results
        assert outside.id not in query.results
        assert line.id not in query.results
        assert query.executed_at > 0

    def test_query_distance(self):
        near = self.engine.add_feature("near", "point", coordinates=[3.0, 4.0])  # dist=5
        far = self.engine.add_feature("far", "point", coordinates=[100.0, 100.0])
        query = self.engine.query_distance(0.0, 0.0, radius=10.0)
        assert query.query_type == "distance"
        assert query.parameters == {
            "center_x": 0.0,
            "center_y": 0.0,
            "radius": 10.0,
        }
        assert near.id in query.results
        assert far.id not in query.results
        # radius 为 0 仅匹配精确重合点
        exact = self.engine.add_feature("exact", "point", coordinates=[0.0, 0.0])
        q0 = self.engine.query_distance(0.0, 0.0, radius=0.0)
        assert exact.id in q0.results
        assert near.id not in q0.results
        # radius 为负
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.query_distance(0.0, 0.0, radius=-1.0)
        assert exc.value.code == "INVALID_RADIUS"

    def test_get_query(self):
        self.engine.add_feature("p", "point", coordinates=[1, 1])
        query = self.engine.query_bbox(0, 0, 10, 10)
        got = self.engine.get_query(query.id)
        assert got.id == query.id
        assert got.query_type == "bbox"
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_query("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_queries(self):
        self.engine.add_feature("p", "point", coordinates=[1, 1])
        self.engine.query_bbox(0, 0, 10, 10)
        self.engine.query_distance(0, 0, 5)
        self.engine.query_bbox(0, 0, 20, 20)
        # no filter
        all_q = self.engine.list_queries()
        assert len(all_q) == 3
        # filter by query_type
        bbox_q = self.engine.list_queries(query_type="bbox")
        assert len(bbox_q) == 2
        assert all(q.query_type == "bbox" for q in bbox_q)
        dist_q = self.engine.list_queries(query_type="distance")
        assert len(dist_q) == 1

    def test_delete_query(self):
        self.engine.add_feature("p", "point", coordinates=[1, 1])
        query = self.engine.query_bbox(0, 0, 10, 10)
        assert self.engine.delete_query(query.id) is True
        assert self.engine.delete_query(query.id) is False
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_query(query.id)
        assert exc.value.code == "NOT_FOUND"

    def test_export_geojson(self):
        f1 = self.engine.add_feature(
            "p1", "point", coordinates=[1, 2], properties={"key": "val"}
        )
        f2 = self.engine.add_feature("p2", "point", coordinates=[3, 4])
        geojson = self.engine.export_geojson()
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 2
        feat = geojson["features"][0]
        assert feat["type"] == "Feature"
        assert feat["id"] == f1.id
        assert feat["geometry"]["type"] == "point"
        assert feat["geometry"]["coordinates"] == [1, 2]
        assert feat["properties"]["name"] == "p1"
        assert feat["properties"]["crs"] == "EPSG:4326"
        assert feat["properties"]["key"] == "val"
        # 按 feature_ids 过滤
        geojson2 = self.engine.export_geojson(feature_ids=[f1.id])
        assert len(geojson2["features"]) == 1
        assert geojson2["features"][0]["id"] == f1.id
        # 不存在的 id
        geojson3 = self.engine.export_geojson(feature_ids=["nonexistent"])
        assert len(geojson3["features"]) == 0

    def test_fifo_eviction_features(self):
        capacity = self.engine._MAX_FEATURES
        first = self.engine.add_feature("first", "point", coordinates=[0, 0])
        for i in range(capacity):
            self.engine.add_feature(f"f{i}", "point", coordinates=[0, 0])
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_feature(first.id)
        assert exc.value.code == "NOT_FOUND"
        assert len(self.engine.list_features()) == capacity


# ════════════════════ #31 Map Visualization ════════════════════

class TestMapVisualizationEngine:
    def setup_method(self):
        self.engine = MapVisualizationEngine()

    def test_create_layer(self):
        layer = self.engine.create_layer(
            "L1",
            "tile",
            source="osm",
            style={"color": "red"},
            opacity=0.8,
            z_index=3,
        )
        assert layer.id.startswith("layer-")
        assert layer.name == "L1"
        assert layer.layer_type == "tile"
        assert layer.source == "osm"
        assert layer.style == {"color": "red"}
        assert layer.visible is True
        assert layer.opacity == 0.8
        assert layer.z_index == 3
        assert layer.created_at > 0

    def test_create_layer_invalid_type(self):
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.create_layer("L", "bogus")
        assert exc.value.code == "INVALID_LAYER_TYPE"
        with pytest.raises(TracingPerfGeoMapError) as exc2:
            self.engine.create_layer("", "tile")
        assert exc2.value.code == "INVALID_INPUT"

    def test_create_layer_invalid_opacity(self):
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.create_layer("L", "tile", opacity=1.5)
        assert exc.value.code == "INVALID_OPACITY"
        with pytest.raises(TracingPerfGeoMapError) as exc2:
            self.engine.create_layer("L", "tile", opacity=-0.1)
        assert exc2.value.code == "INVALID_OPACITY"
        # 边界值有效
        layer0 = self.engine.create_layer("L", "tile", opacity=0.0)
        assert layer0.opacity == 0.0
        layer1 = self.engine.create_layer("L", "tile", opacity=1.0)
        assert layer1.opacity == 1.0

    def test_get_layer(self):
        layer = self.engine.create_layer("L", "tile")
        got = self.engine.get_layer(layer.id)
        assert got.id == layer.id
        assert got.name == "L"
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_layer("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_layers(self):
        l1 = self.engine.create_layer("l1", "tile")
        l2 = self.engine.create_layer("l2", "geojson")
        l3 = self.engine.create_layer("l3", "tile")
        self.engine.toggle_visibility(l1.id)  # l1 不可见
        # no filter
        all_l = self.engine.list_layers()
        assert len(all_l) == 3
        # filter by layer_type
        tiles = self.engine.list_layers(layer_type="tile")
        assert len(tiles) == 2
        assert all(l.layer_type == "tile" for l in tiles)
        # filter by visible_only
        visible = self.engine.list_layers(visible_only=True)
        assert len(visible) == 2
        assert all(l.visible for l in visible)
        assert l1.id not in [l.id for l in visible]
        # combined filter
        visible_tiles = self.engine.list_layers(
            layer_type="tile", visible_only=True
        )
        assert len(visible_tiles) == 1
        assert visible_tiles[0].id == l3.id

    def test_update_layer(self):
        layer = self.engine.create_layer("L", "tile", opacity=0.5)
        updated = self.engine.update_layer(
            layer.id, {"opacity": 0.8, "z_index": 5, "name": "new"}
        )
        assert updated.opacity == 0.8
        assert updated.z_index == 5
        assert updated.name == "new"
        assert updated.id == layer.id
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.update_layer("nonexistent", {"opacity": 0.1})
        assert exc.value.code == "NOT_FOUND"

    def test_toggle_visibility(self):
        layer = self.engine.create_layer("L", "tile")
        assert layer.visible is True
        toggled = self.engine.toggle_visibility(layer.id)
        assert toggled.visible is False
        toggled2 = self.engine.toggle_visibility(layer.id)
        assert toggled2.visible is True
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.toggle_visibility("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_delete_layer(self):
        layer = self.engine.create_layer("L", "tile")
        assert self.engine.delete_layer(layer.id) is True
        assert self.engine.delete_layer(layer.id) is False
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_layer(layer.id)
        assert exc.value.code == "NOT_FOUND"

    def test_create_template(self):
        template = self.engine.create_template(
            "T1",
            description="desc",
            layers=["layer-1"],
            center=[1.0, 2.0],
            zoom=5.0,
        )
        assert template.id.startswith("map-")
        assert template.name == "T1"
        assert template.description == "desc"
        assert template.layers == ["layer-1"]
        assert template.center == [1.0, 2.0]
        assert template.zoom == 5.0
        assert template.created_at > 0
        # 默认值
        template2 = self.engine.create_template("T2")
        assert template2.description == ""
        assert template2.layers == []
        assert template2.center == [0.0, 0.0]
        assert template2.zoom == 1.0
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.create_template("")
        assert exc.value.code == "INVALID_INPUT"

    def test_get_template(self):
        template = self.engine.create_template("T", "desc")
        got = self.engine.get_template(template.id)
        assert got.id == template.id
        assert got.name == "T"
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_template("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_templates(self):
        t1 = self.engine.create_template("T1")
        t2 = self.engine.create_template("T2")
        all_t = self.engine.list_templates()
        assert len(all_t) == 2
        assert all(isinstance(t, MapTemplate) for t in all_t)
        assert {t.id for t in all_t} == {t1.id, t2.id}

    def test_add_layer_to_template(self):
        layer = self.engine.create_layer("L", "tile")
        template = self.engine.create_template("T", "desc")
        updated = self.engine.add_layer_to_template(template.id, layer.id)
        assert layer.id in updated.layers
        # 重复添加不重复
        updated2 = self.engine.add_layer_to_template(template.id, layer.id)
        assert updated2.layers.count(layer.id) == 1
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.add_layer_to_template("nonexistent", layer.id)
        assert exc.value.code == "NOT_FOUND"

    def test_delete_template(self):
        template = self.engine.create_template("T", "desc")
        assert self.engine.delete_template(template.id) is True
        assert self.engine.delete_template(template.id) is False
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_template(template.id)
        assert exc.value.code == "NOT_FOUND"

    def test_fifo_eviction_layers(self):
        capacity = self.engine._MAX_LAYERS
        first = self.engine.create_layer("first", "tile")
        for i in range(capacity):
            self.engine.create_layer(f"l{i}", "tile")
        with pytest.raises(TracingPerfGeoMapError) as exc:
            self.engine.get_layer(first.id)
        assert exc.value.code == "NOT_FOUND"
        assert len(self.engine.list_layers()) == capacity


# ════════════════════ Singleton getters ════════════════════

def test_singleton_getters():
    assert get_distributed_tracing_engine() is get_distributed_tracing_engine()
    assert get_pipeline_perf_engine() is get_pipeline_perf_engine()
    assert get_geospatial_engine() is get_geospatial_engine()
    assert get_map_visualization_engine() is get_map_visualization_engine()
