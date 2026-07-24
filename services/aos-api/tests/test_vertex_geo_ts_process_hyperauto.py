"""W2-BP · Vertex 数字孪生 / 地理时间序列 / Process Mining / Hyperauto 引擎组测试（#32 #33 #34 #35）.

覆盖 4 个内存态引擎的 CRUD、校验、FIFO 淘汰与单例 getter。
每个测试类通过 setup_method 创建全新引擎实例，互不干扰；单例测试不 reset 全局实例。
"""
import pytest
import time

from aos_api.vertex_geo_ts_process_hyperauto import (
    DigitalTwinEngine, TwinModel, TwinSimulation, CausalAnalysis,
    GeoTimeSeriesEngine, LocationTrack, LocationPoint,
    ProcessMiningEngine, EventLog, ProcessFlow,
    HyperautoEngine, IntegrationConfig, SyncRecord,
    VertexGeoTsProcessError,
    get_digital_twin_engine,
    get_geo_time_series_engine,
    get_process_mining_engine,
    get_hyperauto_engine,
)


# ════════════════════ #32 Digital Twin ════════════════════

class TestDigitalTwinEngine:
    def setup_method(self):
        self.engine = DigitalTwinEngine()

    def test_create_twin(self):
        twin = self.engine.create_twin(
            "Twin-A",
            description="desc",
            physical_entity_id="ent-1",
            state={"k": "v"},
            parameters={"temp": 20},
        )
        assert isinstance(twin, TwinModel)
        assert twin.id.startswith("twin-")
        assert twin.name == "Twin-A"
        assert twin.description == "desc"
        assert twin.physical_entity_id == "ent-1"
        assert twin.state == {"k": "v"}
        assert twin.parameters == {"temp": 20}
        assert twin.created_at > 0

    def test_create_twin_invalid_input(self):
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.create_twin("")
        assert exc.value.code == "INVALID_INPUT"

    def test_get_twin(self):
        twin = self.engine.create_twin("T1")
        fetched = self.engine.get_twin(twin.id)
        assert fetched.id == twin.id
        assert fetched.name == "T1"

    def test_get_twin_not_found(self):
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_twin("nonexistent-twin")
        assert exc.value.code == "NOT_FOUND"

    def test_list_twins(self):
        t1 = self.engine.create_twin("T1")
        time.sleep(0.001)
        t2 = self.engine.create_twin("T2")
        twins = self.engine.list_twins()
        assert len(twins) == 2
        # 按 created_at 升序
        assert twins[0].id == t1.id
        assert twins[1].id == t2.id

    def test_update_twin(self):
        twin = self.engine.create_twin("T1", description="d1")
        updated = self.engine.update_twin(
            twin.id, {"name": "T1-updated", "description": "d2"}
        )
        assert updated.name == "T1-updated"
        assert updated.description == "d2"
        # id 字段不可更新
        same = self.engine.update_twin(twin.id, {"id": "fake-id"})
        assert same.id == twin.id
        # 不存在的 twin
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.update_twin("nonexistent", {"name": "x"})
        assert exc.value.code == "NOT_FOUND"

    def test_delete_twin(self):
        twin = self.engine.create_twin("T1")
        assert self.engine.delete_twin(twin.id) is True
        assert self.engine.delete_twin(twin.id) is False
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_twin(twin.id)
        assert exc.value.code == "NOT_FOUND"

    def test_run_simulation(self):
        twin = self.engine.create_twin("T1", parameters={"temp": 10})
        sim = self.engine.run_simulation(twin.id, steps=5)
        assert isinstance(sim, TwinSimulation)
        assert sim.id.startswith("sim-")
        assert sim.twin_id == twin.id
        assert sim.steps == 5
        assert sim.status == "completed"
        assert sim.completed_at > 0
        assert len(sim.results) == 5
        for i, r in enumerate(sim.results):
            assert r["step"] == i
            assert "state" in r
            assert "temp" in r["state"]

    def test_run_simulation_invalid_twin(self):
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.run_simulation("nonexistent-twin")
        assert exc.value.code == "NOT_FOUND"

    def test_get_simulation_and_list_simulations(self):
        twin = self.engine.create_twin("T1")
        sim1 = self.engine.run_simulation(twin.id, steps=3)
        twin2 = self.engine.create_twin("T2")
        sim2 = self.engine.run_simulation(twin2.id, steps=4)
        # get
        fetched = self.engine.get_simulation(sim1.id)
        assert fetched.id == sim1.id
        # not found
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_simulation("nonexistent-sim")
        assert exc.value.code == "NOT_FOUND"
        # filter by twin_id
        by_twin = self.engine.list_simulations(twin_id=twin.id)
        assert len(by_twin) == 1
        assert by_twin[0].id == sim1.id
        # filter by status
        active_sims = self.engine.list_simulations(status="completed")
        assert len(active_sims) == 2
        # 全部
        all_sims = self.engine.list_simulations()
        assert len(all_sims) == 2
        # 升序
        assert all_sims[0].started_at <= all_sims[1].started_at

    def test_analyze_causality(self):
        twin = self.engine.create_twin("T1")
        analysis = self.engine.analyze_causality(
            twin.id,
            cause_variable="temp",
            effect_variable="pressure",
            correlation=0.85,
            lag_seconds=5,
            description="d",
        )
        assert isinstance(analysis, CausalAnalysis)
        assert analysis.id.startswith("causal-")
        assert analysis.twin_id == twin.id
        assert analysis.cause_variable == "temp"
        assert analysis.effect_variable == "pressure"
        assert analysis.correlation == 0.85
        assert analysis.lag_seconds == 5
        assert analysis.description == "d"

    def test_analyze_causality_invalid_correlation(self):
        twin = self.engine.create_twin("T1")
        # correlation > 1
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.analyze_causality(
                twin.id, "c", "e", correlation=1.5
            )
        assert exc.value.code == "INVALID_CORRELATION"
        # correlation < -1
        with pytest.raises(VertexGeoTsProcessError) as exc2:
            self.engine.analyze_causality(
                twin.id, "c", "e", correlation=-1.5
            )
        assert exc2.value.code == "INVALID_CORRELATION"
        # boundary -1 和 1 应通过
        a1 = self.engine.analyze_causality(
            twin.id, "c", "e", correlation=-1
        )
        assert a1.correlation == -1
        a2 = self.engine.analyze_causality(
            twin.id, "c", "e", correlation=1
        )
        assert a2.correlation == 1
        # twin 不存在
        with pytest.raises(VertexGeoTsProcessError) as exc3:
            self.engine.analyze_causality("nonexistent", "c", "e")
        assert exc3.value.code == "NOT_FOUND"
        # cause_variable 不可为空
        with pytest.raises(VertexGeoTsProcessError) as exc4:
            self.engine.analyze_causality(twin.id, "", "e")
        assert exc4.value.code == "INVALID_INPUT"
        # effect_variable 不可为空
        with pytest.raises(VertexGeoTsProcessError) as exc5:
            self.engine.analyze_causality(twin.id, "c", "")
        assert exc5.value.code == "INVALID_INPUT"

    def test_list_causal_analyses_and_delete_causal_analysis(self):
        twin = self.engine.create_twin("T1")
        twin2 = self.engine.create_twin("T2")
        a1 = self.engine.analyze_causality(twin.id, "c1", "e1")
        time.sleep(0.001)
        a2 = self.engine.analyze_causality(twin.id, "c2", "e2")
        a3 = self.engine.analyze_causality(twin2.id, "c3", "e3")
        # list 全部
        all_analyses = self.engine.list_causal_analyses()
        assert len(all_analyses) == 3
        # filter by twin_id
        by_twin = self.engine.list_causal_analyses(twin_id=twin.id)
        assert len(by_twin) == 2
        assert {a.id for a in by_twin} == {a1.id, a2.id}
        # 升序
        assert by_twin[0].created_at <= by_twin[1].created_at
        # delete
        assert self.engine.delete_causal_analysis(a1.id) is True
        assert self.engine.delete_causal_analysis(a1.id) is False
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_causal_analysis(a1.id)
        assert exc.value.code == "NOT_FOUND"
        # get_causal_analysis 成功
        fetched = self.engine.get_causal_analysis(a2.id)
        assert fetched.id == a2.id

    def test_fifo_eviction_simulations(self):
        twin = self.engine.create_twin("T1")
        first_sim = self.engine.run_simulation(twin.id, steps=1)
        capacity = self.engine._MAX_SIMULATIONS
        for i in range(capacity):
            self.engine.run_simulation(twin.id, steps=1)
        # 最早创建的 first_sim 被淘汰
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_simulation(first_sim.id)
        assert exc.value.code == "NOT_FOUND"
        # 总数等于容量上限
        assert len(self.engine.list_simulations()) == capacity


# ════════════════════ #33 Geo Time Series ════════════════════

class TestGeoTimeSeriesEngine:
    def setup_method(self):
        self.engine = GeoTimeSeriesEngine()

    def test_create_track(self):
        track = self.engine.create_track(
            entity_id="ent-1", name="Track-A", sync_enabled=False
        )
        assert isinstance(track, LocationTrack)
        assert track.id.startswith("track-")
        assert track.entity_id == "ent-1"
        assert track.name == "Track-A"
        assert track.sync_enabled is False
        assert track.last_position == {}
        assert track.last_timestamp == 0
        assert track.point_count == 0
        assert track.created_at > 0

    def test_create_track_invalid_input(self):
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.create_track("", "n")
        assert exc.value.code == "INVALID_INPUT"
        with pytest.raises(VertexGeoTsProcessError) as exc2:
            self.engine.create_track("ent-1", "")
        assert exc2.value.code == "INVALID_INPUT"

    def test_get_track_and_list_tracks(self):
        t1 = self.engine.create_track("ent-1", "T1")
        time.sleep(0.001)
        t2 = self.engine.create_track("ent-1", "T2", sync_enabled=False)
        t3 = self.engine.create_track("ent-2", "T3")
        # get
        fetched = self.engine.get_track(t1.id)
        assert fetched.id == t1.id
        # not found
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_track("nonexistent-track")
        assert exc.value.code == "NOT_FOUND"
        # list 全部
        all_tracks = self.engine.list_tracks()
        assert len(all_tracks) == 3
        assert all_tracks[0].created_at <= all_tracks[1].created_at
        # filter by entity_id
        by_entity = self.engine.list_tracks(entity_id="ent-1")
        assert len(by_entity) == 2
        assert {t.id for t in by_entity} == {t1.id, t2.id}
        # filter sync_enabled_only
        sync_enabled = self.engine.list_tracks(sync_enabled_only=True)
        assert t2.id not in {t.id for t in sync_enabled}
        assert t1.id in {t.id for t in sync_enabled}

    def test_update_track_and_delete_track(self):
        track = self.engine.create_track("ent-1", "T1")
        updated = self.engine.update_track(
            track.id, {"name": "T1-updated", "sync_enabled": False}
        )
        assert updated.name == "T1-updated"
        assert updated.sync_enabled is False
        # id 不可更新
        same = self.engine.update_track(track.id, {"id": "fake"})
        assert same.id == track.id
        # 不存在
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.update_track("nonexistent", {"name": "x"})
        assert exc.value.code == "NOT_FOUND"
        # delete
        assert self.engine.delete_track(track.id) is True
        assert self.engine.delete_track(track.id) is False
        with pytest.raises(VertexGeoTsProcessError) as exc2:
            self.engine.get_track(track.id)
        assert exc2.value.code == "NOT_FOUND"

    def test_record_point(self):
        track = self.engine.create_track("ent-1", "T1")
        point = self.engine.record_point(
            track.id,
            latitude=30.0,
            longitude=120.0,
            elevation=10.0,
            speed=5.0,
            heading=90.0,
            metadata={"k": "v"},
        )
        assert isinstance(point, LocationPoint)
        assert point.id.startswith("pt-")
        assert point.track_id == track.id
        assert point.latitude == 30.0
        assert point.longitude == 120.0
        assert point.elevation == 10.0
        assert point.speed == 5.0
        assert point.heading == 90.0
        assert point.metadata == {"k": "v"}
        assert point.timestamp > 0
        # 验证 track 被更新
        updated_track = self.engine.get_track(track.id)
        assert updated_track.last_position == {
            "latitude": 30.0,
            "longitude": 120.0,
        }
        assert updated_track.last_timestamp == point.timestamp
        assert updated_track.point_count == 1
        # 再记录一个点
        point2 = self.engine.record_point(track.id, 31.0, 121.0)
        updated_track2 = self.engine.get_track(track.id)
        assert updated_track2.point_count == 2
        assert updated_track2.last_position == {
            "latitude": 31.0,
            "longitude": 121.0,
        }

    def test_record_point_invalid_lat(self):
        track = self.engine.create_track("ent-1", "T1")
        # latitude > 90
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.record_point(track.id, latitude=91, longitude=0)
        assert exc.value.code == "INVALID_LATITUDE"
        # latitude < -90
        with pytest.raises(VertexGeoTsProcessError) as exc2:
            self.engine.record_point(track.id, latitude=-91, longitude=0)
        assert exc2.value.code == "INVALID_LATITUDE"
        # 边界 -90 和 90 应通过
        p1 = self.engine.record_point(track.id, 90, 0)
        assert p1.latitude == 90
        p2 = self.engine.record_point(track.id, -90, 0)
        assert p2.latitude == -90

    def test_record_point_invalid_lon(self):
        track = self.engine.create_track("ent-1", "T1")
        # longitude > 180
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.record_point(track.id, 0, longitude=181)
        assert exc.value.code == "INVALID_LONGITUDE"
        # longitude < -180
        with pytest.raises(VertexGeoTsProcessError) as exc2:
            self.engine.record_point(track.id, 0, longitude=-181)
        assert exc2.value.code == "INVALID_LONGITUDE"
        # 边界 -180 和 180 应通过
        p1 = self.engine.record_point(track.id, 0, 180)
        assert p1.longitude == 180
        p2 = self.engine.record_point(track.id, 0, -180)
        assert p2.longitude == -180

    def test_record_point_track_not_found(self):
        # lat/lon 校验在 track 查找之前，所以必须用合法 lat/lon
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.record_point("nonexistent-track", 0, 0)
        assert exc.value.code == "NOT_FOUND"

    def test_get_point_and_list_points(self):
        track = self.engine.create_track("ent-1", "T1")
        p1 = self.engine.record_point(track.id, 30, 120)
        time.sleep(0.01)
        p2 = self.engine.record_point(track.id, 31, 121)
        time.sleep(0.01)
        p3 = self.engine.record_point(track.id, 32, 122)
        # get
        fetched = self.engine.get_point(p2.id)
        assert fetched.id == p2.id
        # not found
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_point("nonexistent-pt")
        assert exc.value.code == "NOT_FOUND"
        # list 默认按 timestamp 降序
        pts = self.engine.list_points(track_id=track.id)
        assert [p.id for p in pts] == [p3.id, p2.id, p1.id]
        # limit 限制
        limited = self.engine.list_points(track_id=track.id, limit=2)
        assert len(limited) == 2
        assert limited[0].id == p3.id
        # 全部（无 track 过滤）
        all_pts = self.engine.list_points()
        assert len(all_pts) == 3

    def test_get_track_path(self):
        track = self.engine.create_track("ent-1", "T1")
        p1 = self.engine.record_point(track.id, 30.0, 120.0)
        time.sleep(0.01)
        p2 = self.engine.record_point(track.id, 31.0, 121.0)
        time.sleep(0.01)
        p3 = self.engine.record_point(track.id, 32.0, 122.0)
        path = self.engine.get_track_path(track.id)
        assert path["track_id"] == track.id
        assert path["total_points"] == 3
        assert "distance_km" in path
        assert path["distance_km"] > 0
        assert len(path["points"]) == 3
        # 按时间升序
        assert path["points"][0]["id"] == p1.id
        assert path["points"][2]["id"] == p3.id
        # 不存在的 track
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_track_path("nonexistent-track")
        assert exc.value.code == "NOT_FOUND"
        # limit 验证
        path_limited = self.engine.get_track_path(track.id, limit=2)
        assert path_limited["total_points"] == 2

    def test_delete_point(self):
        track = self.engine.create_track("ent-1", "T1")
        point = self.engine.record_point(track.id, 30, 120)
        assert self.engine.delete_point(point.id) is True
        assert self.engine.delete_point(point.id) is False
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_point(point.id)
        assert exc.value.code == "NOT_FOUND"

    def test_delete_track_cascades_points(self):
        track = self.engine.create_track("ent-1", "T1")
        p1 = self.engine.record_point(track.id, 30, 120)
        p2 = self.engine.record_point(track.id, 31, 121)
        assert self.engine.delete_track(track.id) is True
        # 关联 points 也被清理
        with pytest.raises(VertexGeoTsProcessError):
            self.engine.get_point(p1.id)
        with pytest.raises(VertexGeoTsProcessError):
            self.engine.get_point(p2.id)

    def test_fifo_eviction_points(self):
        track = self.engine.create_track("ent-1", "T1")
        first_point = self.engine.record_point(track.id, 30, 120)
        capacity = self.engine._MAX_POINTS
        for i in range(capacity):
            self.engine.record_point(track.id, 30.0 + i * 0.01, 120.0)
        # 最早创建的 first_point 被淘汰
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_point(first_point.id)
        assert exc.value.code == "NOT_FOUND"
        # 总数等于容量上限（list_points 默认 limit=100，需显式提高）
        assert len(self.engine.list_points(limit=capacity)) == capacity


# ════════════════════ #34 Process Mining ════════════════════

class TestProcessMiningEngine:
    def setup_method(self):
        self.engine = ProcessMiningEngine()

    def test_log_event(self):
        event = self.engine.log_event(
            case_id="case-1",
            activity="start",
            resource="res-1",
            cost=10.5,
            metadata={"k": "v"},
        )
        assert isinstance(event, EventLog)
        assert event.id.startswith("elog-")
        assert event.case_id == "case-1"
        assert event.activity == "start"
        assert event.resource == "res-1"
        assert event.cost == 10.5
        assert event.metadata == {"k": "v"}
        assert event.timestamp > 0

    def test_log_event_invalid_input(self):
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.log_event("", "act")
        assert exc.value.code == "INVALID_INPUT"
        with pytest.raises(VertexGeoTsProcessError) as exc2:
            self.engine.log_event("case-1", "")
        assert exc2.value.code == "INVALID_INPUT"

    def test_get_event_and_list_events(self):
        e1 = self.engine.log_event("case-1", "start")
        time.sleep(0.01)
        e2 = self.engine.log_event("case-1", "end")
        e3 = self.engine.log_event("case-2", "start")
        # get
        fetched = self.engine.get_event(e1.id)
        assert fetched.id == e1.id
        # not found
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_event("nonexistent-elog")
        assert exc.value.code == "NOT_FOUND"
        # list 全部
        all_events = self.engine.list_events()
        assert len(all_events) == 3
        # 升序
        assert all_events[0].timestamp <= all_events[1].timestamp
        # filter by case_id
        by_case = self.engine.list_events(case_id="case-1")
        assert len(by_case) == 2
        assert {e.id for e in by_case} == {e1.id, e2.id}
        # filter by activity
        by_activity = self.engine.list_events(activity="start")
        assert len(by_activity) == 2
        assert {e.id for e in by_activity} == {e1.id, e3.id}
        # 组合过滤
        combined = self.engine.list_events(case_id="case-1", activity="start")
        assert len(combined) == 1
        assert combined[0].id == e1.id

    def test_delete_event(self):
        event = self.engine.log_event("case-1", "start")
        assert self.engine.delete_event(event.id) is True
        assert self.engine.delete_event(event.id) is False
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_event(event.id)
        assert exc.value.code == "NOT_FOUND"

    def test_discover_flow(self):
        # 为同一 case 记录多个事件
        self.engine.log_event("case-1", "start")
        time.sleep(0.01)
        self.engine.log_event("case-1", "review")
        time.sleep(0.01)
        self.engine.log_event("case-1", "approve")
        time.sleep(0.01)
        self.engine.log_event("case-1", "end")
        flow = self.engine.discover_flow("Flow-A", case_ids=["case-1"])
        assert isinstance(flow, ProcessFlow)
        assert flow.id.startswith("flow-")
        assert flow.name == "Flow-A"
        # activities 排序
        assert flow.activities == ["approve", "end", "review", "start"]
        # transitions
        transition_pairs = {(t["from"], t["to"]): t["count"] for t in flow.transitions}
        assert transition_pairs[("start", "review")] == 1
        assert transition_pairs[("review", "approve")] == 1
        assert transition_pairs[("approve", "end")] == 1
        # case_count
        assert flow.case_count == 1

    def test_discover_flow_invalid_input(self):
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.discover_flow("")
        assert exc.value.code == "INVALID_INPUT"

    def test_get_flow_and_list_flows(self):
        self.engine.log_event("case-1", "start")
        flow = self.engine.discover_flow("F1")
        # get
        fetched = self.engine.get_flow(flow.id)
        assert fetched.id == flow.id
        # not found
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_flow("nonexistent-flow")
        assert exc.value.code == "NOT_FOUND"
        # list
        flow2 = self.engine.discover_flow("F2")
        all_flows = self.engine.list_flows()
        assert len(all_flows) == 2
        assert all_flows[0].created_at <= all_flows[1].created_at

    def test_get_flow_analysis(self):
        self.engine.log_event("case-1", "start", cost=10)
        self.engine.log_event("case-1", "end", cost=20)
        flow = self.engine.discover_flow("F1", case_ids=["case-1"])
        analysis = self.engine.get_flow_analysis(flow.id)
        assert analysis["flow_id"] == flow.id
        assert analysis["total_activities"] == 2
        assert analysis["total_transitions"] == 1
        assert analysis["bottleneck_count"] == len(flow.bottlenecks)
        assert analysis["case_count"] == 1
        assert analysis["avg_cost_per_case"] == 30.0
        # not found
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_flow_analysis("nonexistent-flow")
        assert exc.value.code == "NOT_FOUND"

    def test_delete_flow(self):
        self.engine.log_event("case-1", "start")
        flow = self.engine.discover_flow("F1")
        assert self.engine.delete_flow(flow.id) is True
        assert self.engine.delete_flow(flow.id) is False
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_flow(flow.id)
        assert exc.value.code == "NOT_FOUND"

    def test_fifo_eviction_logs(self):
        first_event = self.engine.log_event("case-1", "first")
        capacity = self.engine._MAX_LOGS
        for i in range(capacity):
            self.engine.log_event("case-1", f"act-{i}")
        # 最早创建的 first_event 被淘汰
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_event(first_event.id)
        assert exc.value.code == "NOT_FOUND"
        # 总数等于容量上限
        assert len(self.engine.list_events()) == capacity


# ════════════════════ #35 Hyperauto ════════════════════

class TestHyperautoEngine:
    def setup_method(self):
        self.engine = HyperautoEngine()

    def test_register_integration(self):
        integ = self.engine.register_integration(
            source_system="erp",
            sync_enabled=True,
            auto_ontology_mapping=False,
            sync_interval_seconds=600,
            config={"k": "v"},
        )
        assert isinstance(integ, IntegrationConfig)
        assert integ.id.startswith("integ-")
        assert integ.source_system == "erp"
        assert integ.sync_enabled is True
        assert integ.auto_ontology_mapping is False
        assert integ.sync_interval_seconds == 600
        assert integ.last_sync_at == 0
        assert integ.status == "active"
        assert integ.config == {"k": "v"}
        assert integ.created_at > 0

    def test_register_integration_invalid_source(self):
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.register_integration(source_system="invalid")
        assert exc.value.code == "INVALID_SOURCE_SYSTEM"
        # 合法 source_system 应通过
        for src in ("erp", "crm", "scada", "iot"):
            i = self.engine.register_integration(source_system=src)
            assert i.source_system == src

    def test_get_integration_and_list_integrations(self):
        i1 = self.engine.register_integration("erp")
        time.sleep(0.001)
        i2 = self.engine.register_integration("crm")
        i3 = self.engine.register_integration("erp")
        # get
        fetched = self.engine.get_integration(i1.id)
        assert fetched.id == i1.id
        # not found
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_integration("nonexistent-integ")
        assert exc.value.code == "NOT_FOUND"
        # list 全部
        all_integs = self.engine.list_integrations()
        assert len(all_integs) == 3
        assert all_integs[0].created_at <= all_integs[1].created_at
        # filter by source_system
        by_source = self.engine.list_integrations(source_system="erp")
        assert len(by_source) == 2
        assert {i.id for i in by_source} == {i1.id, i3.id}
        # filter by status
        paused = self.engine.pause_integration(i1.id)
        by_status = self.engine.list_integrations(status="paused")
        assert len(by_status) == 1
        assert by_status[0].id == paused.id

    def test_update_integration(self):
        integ = self.engine.register_integration("erp")
        updated = self.engine.update_integration(
            integ.id,
            {"sync_interval_seconds": 100, "config": {"k2": "v2"}},
        )
        assert updated.sync_interval_seconds == 100
        assert updated.config == {"k2": "v2"}
        # id 不可更新
        same = self.engine.update_integration(integ.id, {"id": "fake"})
        assert same.id == integ.id
        # 不存在
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.update_integration("nonexistent", {"status": "x"})
        assert exc.value.code == "NOT_FOUND"

    def test_pause_and_resume_integration(self):
        integ = self.engine.register_integration("erp")
        assert integ.status == "active"
        paused = self.engine.pause_integration(integ.id)
        assert paused.status == "paused"
        # 再次获取确认
        assert self.engine.get_integration(integ.id).status == "paused"
        resumed = self.engine.resume_integration(integ.id)
        assert resumed.status == "active"
        assert self.engine.get_integration(integ.id).status == "active"
        # 不存在
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.pause_integration("nonexistent")
        assert exc.value.code == "NOT_FOUND"
        with pytest.raises(VertexGeoTsProcessError) as exc2:
            self.engine.resume_integration("nonexistent")
        assert exc2.value.code == "NOT_FOUND"

    def test_delete_integration(self):
        integ = self.engine.register_integration("erp")
        assert self.engine.delete_integration(integ.id) is True
        assert self.engine.delete_integration(integ.id) is False
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_integration(integ.id)
        assert exc.value.code == "NOT_FOUND"

    def test_delete_integration_cascades_syncs(self):
        integ = self.engine.register_integration("erp")
        sync = self.engine.run_sync(integ.id)
        assert self.engine.delete_integration(integ.id) is True
        # 关联 syncs 也被清理
        with pytest.raises(VertexGeoTsProcessError):
            self.engine.get_sync(sync.id)

    def test_run_sync(self):
        integ = self.engine.register_integration("erp")
        sync = self.engine.run_sync(integ.id)
        assert isinstance(sync, SyncRecord)
        assert sync.id.startswith("syncrec-")
        assert sync.integration_id == integ.id
        assert sync.records_synced >= 10
        assert sync.objects_created >= 0
        assert sync.objects_updated >= 0
        assert sync.errors >= 0
        assert sync.status == "completed"
        assert sync.completed_at > 0
        assert sync.started_at > 0
        # integration.last_sync_at 被更新
        updated_integ = self.engine.get_integration(integ.id)
        assert updated_integ.last_sync_at == sync.completed_at
        assert updated_integ.last_sync_at > 0

    def test_run_sync_invalid_integration(self):
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.run_sync("nonexistent-integ")
        assert exc.value.code == "NOT_FOUND"

    def test_run_sync_paused(self):
        integ = self.engine.register_integration("erp")
        self.engine.pause_integration(integ.id)
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.run_sync(integ.id)
        assert exc.value.code == "INVALID_STATUS"

    def test_get_sync_list_syncs_and_delete_sync(self):
        i1 = self.engine.register_integration("erp")
        i2 = self.engine.register_integration("crm")
        s1 = self.engine.run_sync(i1.id)
        time.sleep(0.001)
        s2 = self.engine.run_sync(i1.id)
        s3 = self.engine.run_sync(i2.id)
        # get
        fetched = self.engine.get_sync(s1.id)
        assert fetched.id == s1.id
        # not found
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_sync("nonexistent-syncrec")
        assert exc.value.code == "NOT_FOUND"
        # list 全部
        all_syncs = self.engine.list_syncs()
        assert len(all_syncs) == 3
        assert all_syncs[0].started_at <= all_syncs[1].started_at
        # filter by integration_id
        by_integ = self.engine.list_syncs(integration_id=i1.id)
        assert len(by_integ) == 2
        assert {s.id for s in by_integ} == {s1.id, s2.id}
        # filter by status
        completed = self.engine.list_syncs(status="completed")
        assert len(completed) == 3
        # delete
        assert self.engine.delete_sync(s1.id) is True
        assert self.engine.delete_sync(s1.id) is False
        with pytest.raises(VertexGeoTsProcessError) as exc2:
            self.engine.get_sync(s1.id)
        assert exc2.value.code == "NOT_FOUND"

    def test_fifo_eviction_syncs(self):
        integ = self.engine.register_integration("erp")
        first_sync = self.engine.run_sync(integ.id)
        capacity = self.engine._MAX_SYNCS
        for i in range(capacity):
            self.engine.run_sync(integ.id)
        # 最早创建的 first_sync 被淘汰
        with pytest.raises(VertexGeoTsProcessError) as exc:
            self.engine.get_sync(first_sync.id)
        assert exc.value.code == "NOT_FOUND"
        # 总数等于容量上限
        assert len(self.engine.list_syncs()) == capacity


# ════════════════════ Singleton Getters ════════════════════

def test_singleton_getters():
    assert get_digital_twin_engine() is get_digital_twin_engine()
    assert get_geo_time_series_engine() is get_geo_time_series_engine()
    assert get_process_mining_engine() is get_process_mining_engine()
    assert get_hyperauto_engine() is get_hyperauto_engine()
