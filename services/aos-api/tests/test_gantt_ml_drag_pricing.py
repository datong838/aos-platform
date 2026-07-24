"""W2-BM · Gantt / ML Scheduling / Workshop Drag / Compute Pricing 引擎组测试（#18 #19 #20 #21）.

覆盖 4 个内存态引擎的 CRUD、校验、FIFO 淘汰与单例 getter。
每个测试类通过 setup_method 创建全新引擎实例，互不干扰；单例测试不 reset 全局实例。
"""
import pytest

from aos_api.gantt_ml_drag_pricing import (
    GanttScheduleEngine, GanttTask, GanttAssignment,
    MLSchedulingEngine, MLModel, MLPrediction,
    WorkshopDragEngine, DragElement, DragSession,
    ComputePricingEngine, PricingTier, UsageMeter,
    GanttMlDragPricingError,
    get_gantt_schedule_engine,
    get_ml_scheduling_engine,
    get_workshop_drag_engine,
    get_compute_pricing_engine,
)


# ════════════════════ #18 Gantt Schedule ════════════════════

class TestGanttScheduleEngine:
    def setup_method(self):
        self.engine = GanttScheduleEngine()

    def test_create_task(self):
        task = self.engine.create_task(
            name="Task A",
            start_time=1000.0,
            end_time=2000.0,
            resource_id="r1",
        )
        assert task.id.startswith("gtask-")
        assert task.name == "Task A"
        assert task.start_time == 1000.0
        assert task.end_time == 2000.0
        assert task.resource_id == "r1"
        assert task.progress == 0.0
        assert task.dependencies == []
        assert task.constraints == {}
        assert task.color == "#3b82f6"
        assert task.created_at > 0

    def test_create_task_invalid_time(self):
        # end_time == start_time -> error
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.create_task("T", 1000.0, 1000.0)
        assert exc.value.code == "INVALID_TIME_RANGE"
        # end_time < start_time -> error
        with pytest.raises(GanttMlDragPricingError) as exc2:
            self.engine.create_task("T", 1000.0, 999.0)
        assert exc2.value.code == "INVALID_TIME_RANGE"

    def test_get_task(self):
        task = self.engine.create_task("T", 1000.0, 2000.0)
        got = self.engine.get_task(task.id)
        assert got.id == task.id
        assert got.name == "T"

    def test_get_task_not_found(self):
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.get_task("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_tasks(self):
        t1 = self.engine.create_task("T1", 1000.0, 2000.0, resource_id="r1")
        t2 = self.engine.create_task("T2", 2000.0, 3000.0, resource_id="r2")
        t3 = self.engine.create_task("T3", 3000.0, 4000.0, resource_id="r1")
        # all
        all_tasks = self.engine.list_tasks()
        assert len(all_tasks) == 3
        assert {t.id for t in all_tasks} == {t1.id, t2.id, t3.id}
        # filter by resource_id
        r1_tasks = self.engine.list_tasks(resource_id="r1")
        assert {t.id for t in r1_tasks} == {t1.id, t3.id}
        # resource with no tasks
        assert self.engine.list_tasks(resource_id="rX") == []

    def test_update_task(self):
        task = self.engine.create_task("T", 1000.0, 2000.0)
        updated = self.engine.update_task(
            task.id,
            {"name": "Renamed", "progress": 0.5, "id": "should-be-ignored"},
        )
        assert updated.name == "Renamed"
        assert updated.progress == 0.5
        # id 不可被更新
        assert updated.id == task.id

    def test_move_task(self):
        task = self.engine.create_task("T", 1000.0, 2000.0)  # duration 1000
        moved = self.engine.move_task(task.id, 5000.0)
        assert moved.start_time == 5000.0
        assert moved.end_time == 6000.0  # duration preserved

    def test_move_task_dependency_violation(self):
        dep = self.engine.create_task("Dep", 1000.0, 3000.0)
        task = self.engine.create_task(
            "T", 3000.0, 4000.0, dependencies=[dep.id]
        )
        # 移动到依赖结束之前 -> 违规
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.move_task(task.id, 2500.0)
        assert exc.value.code == "DEPENDENCY_VIOLATION"
        # 移动到依赖结束之时（>=）-> 允许
        moved = self.engine.move_task(task.id, 3000.0)
        assert moved.start_time == 3000.0
        assert moved.end_time == 4000.0

    def test_delete_task(self):
        task = self.engine.create_task("T", 1000.0, 2000.0)
        assert self.engine.delete_task(task.id) is True
        with pytest.raises(GanttMlDragPricingError):
            self.engine.get_task(task.id)
        # 重复删除返回 False
        assert self.engine.delete_task(task.id) is False

    def test_assign_resource(self):
        task = self.engine.create_task("T", 1000.0, 2000.0)
        a = self.engine.assign_resource(
            task.id, "r1", allocation_percent=50.0, suggested=False
        )
        assert a.id.startswith("gassign-")
        assert a.task_id == task.id
        assert a.resource_id == "r1"
        assert a.allocation_percent == 50.0
        assert a.suggested is False

    def test_suggest_assignment(self):
        task = self.engine.create_task("T", 1000.0, 2000.0)
        a = self.engine.suggest_assignment(task.id)
        assert a.task_id == task.id
        assert a.resource_id.startswith("resource-")
        assert a.suggested is True
        assert a.allocation_percent == 100.0

    def test_list_assignments(self):
        t1 = self.engine.create_task("T1", 1000.0, 2000.0)
        t2 = self.engine.create_task("T2", 2000.0, 3000.0)
        a1 = self.engine.assign_resource(t1.id, "r1")
        a2 = self.engine.assign_resource(t2.id, "r2")
        a3 = self.engine.assign_resource(t1.id, "r3")
        # all
        assert len(self.engine.list_assignments()) == 3
        # filter by task_id
        assert {a.id for a in self.engine.list_assignments(task_id=t1.id)} == {a1.id, a3.id}
        # filter by resource_id
        assert {a.id for a in self.engine.list_assignments(resource_id="r2")} == {a2.id}

    def test_fifo_eviction_tasks(self):
        capacity = self.engine._MAX_TASKS
        first = self.engine.create_task("first", 1000.0, 2000.0)
        # 再创建 capacity 条，总计 capacity+1，触发一次淘汰
        for i in range(capacity):
            self.engine.create_task(f"t{i}", 1000.0, 2000.0)
        # 最早创建的 first 被淘汰
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.get_task(first.id)
        assert exc.value.code == "NOT_FOUND"
        # 总数等于容量上限
        assert len(self.engine.list_tasks()) == capacity


# ════════════════════ #19 ML Scheduling ════════════════════

class TestMLSchedulingEngine:
    def setup_method(self):
        self.engine = MLSchedulingEngine()

    def test_register_model(self):
        m = self.engine.register_model("M", "lstm", features=["f1", "f2"])
        assert m.id.startswith("ml-")
        assert m.name == "M"
        assert m.algorithm == "lstm"
        assert m.features == ["f1", "f2"]
        assert m.trained is False
        assert m.accuracy == 0.0
        assert m.created_at > 0

    def test_register_model_invalid_algorithm(self):
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.register_model("M", "random_forest")
        assert exc.value.code == "INVALID_ALGORITHM"

    def test_get_model(self):
        m = self.engine.register_model("M", "regression")
        got = self.engine.get_model(m.id)
        assert got.id == m.id
        assert got.algorithm == "regression"

    def test_get_model_not_found(self):
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.get_model("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_models(self):
        m1 = self.engine.register_model("M1", "regression")
        m2 = self.engine.register_model("M2", "lstm")
        m3 = self.engine.register_model("M3", "regression")
        self.engine.train_model(m1.id, 0.9)
        # all
        assert len(self.engine.list_models()) == 3
        # filter by algorithm
        reg = self.engine.list_models(algorithm="regression")
        assert {m.id for m in reg} == {m1.id, m3.id}
        # trained_only
        trained = self.engine.list_models(trained_only=True)
        assert {m.id for m in trained} == {m1.id}

    def test_train_model(self):
        m = self.engine.register_model("M", "arima")
        trained = self.engine.train_model(m.id, 0.85)
        assert trained.trained is True
        assert trained.accuracy == 0.85
        # 持久化
        assert self.engine.get_model(m.id).trained is True

    def test_train_model_invalid_accuracy(self):
        m = self.engine.register_model("M", "arima")
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.train_model(m.id, 1.5)
        assert exc.value.code == "INVALID_ACCURACY"
        with pytest.raises(GanttMlDragPricingError) as exc2:
            self.engine.train_model(m.id, -0.1)
        assert exc2.value.code == "INVALID_ACCURACY"

    def test_predict(self):
        m = self.engine.register_model("M", "transformer")
        self.engine.train_model(m.id, 0.9)
        p = self.engine.predict(
            m.id, "r1", 42.5, confidence=0.8, horizon_seconds=1800
        )
        assert p.id.startswith("pred-")
        assert p.model_id == m.id
        assert p.predicted_resource_id == "r1"
        assert p.predicted_value == 42.5
        assert p.confidence == 0.8
        assert p.horizon_seconds == 1800
        assert p.predicted_at > 0

    def test_predict_untrained_model(self):
        m = self.engine.register_model("M", "transformer")
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.predict(m.id, "r1", 1.0)
        assert exc.value.code == "MODEL_NOT_TRAINED"

    def test_list_predictions(self):
        m = self.engine.register_model("M", "regression")
        self.engine.train_model(m.id, 0.9)
        p1 = self.engine.predict(m.id, "r1", 1.0)
        p2 = self.engine.predict(m.id, "r2", 2.0)
        # all
        assert len(self.engine.list_predictions()) == 2
        # filter by model_id
        assert {p.id for p in self.engine.list_predictions(model_id=m.id)} == {p1.id, p2.id}
        # filter by resource_id
        assert {p.id for p in self.engine.list_predictions(resource_id="r1")} == {p1.id}

    def test_delete_prediction(self):
        m = self.engine.register_model("M", "regression")
        self.engine.train_model(m.id, 0.9)
        p = self.engine.predict(m.id, "r1", 1.0)
        assert self.engine.delete_prediction(p.id) is True
        assert self.engine.delete_prediction(p.id) is False
        with pytest.raises(GanttMlDragPricingError):
            self.engine.get_prediction(p.id)

    def test_fifo_eviction_predictions(self):
        m = self.engine.register_model("M", "regression")
        self.engine.train_model(m.id, 0.9)
        capacity = self.engine._MAX_PREDICTIONS
        first = self.engine.predict(m.id, "r1", 1.0)
        for i in range(capacity):
            self.engine.predict(m.id, "r1", float(i))
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.get_prediction(first.id)
        assert exc.value.code == "NOT_FOUND"
        assert len(self.engine.list_predictions()) == capacity


# ════════════════════ #20 Workshop Drag ════════════════════

class TestWorkshopDragEngine:
    def setup_method(self):
        self.engine = WorkshopDragEngine()

    def test_create_element(self):
        e = self.engine.create_element(
            "node", x=10, y=20, width=100, height=50,
            rotation=0, z_index=1, metadata={"k": "v"},
        )
        assert e.id.startswith("elem-")
        assert e.element_type == "node"
        assert e.x == 10
        assert e.y == 20
        assert e.width == 100
        assert e.height == 50
        assert e.rotation == 0
        assert e.z_index == 1
        assert e.locked is False
        assert e.metadata == {"k": "v"}
        assert e.created_at > 0

    def test_create_element_invalid_type(self):
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.create_element("widget")
        assert exc.value.code == "INVALID_ELEMENT_TYPE"

    def test_get_element(self):
        e = self.engine.create_element("node")
        got = self.engine.get_element(e.id)
        assert got.id == e.id
        assert got.element_type == "node"

    def test_get_element_not_found(self):
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.get_element("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_elements(self):
        e1 = self.engine.create_element("node")
        e2 = self.engine.create_element("edge")
        e3 = self.engine.create_element("node")
        assert len(self.engine.list_elements()) == 3
        nodes = self.engine.list_elements(element_type="node")
        assert {e.id for e in nodes} == {e1.id, e3.id}
        assert self.engine.list_elements(element_type="port") == []

    def test_move_element(self):
        e = self.engine.create_element("node", x=0, y=0)
        moved = self.engine.move_element(e.id, 5, 7)
        assert moved.x == 5
        assert moved.y == 7

    def test_move_locked_element(self):
        e = self.engine.create_element("node")
        self.engine.lock_element(e.id)
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.move_element(e.id, 1, 1)
        assert exc.value.code == "ELEMENT_LOCKED"

    def test_resize_element(self):
        e = self.engine.create_element("node")
        resized = self.engine.resize_element(e.id, 200, 100)
        assert resized.width == 200
        assert resized.height == 100

    def test_rotate_element(self):
        e = self.engine.create_element("node")
        rotated = self.engine.rotate_element(e.id, 90.0)
        assert rotated.rotation == 90.0

    def test_lock_element(self):
        e = self.engine.create_element("node")
        locked = self.engine.lock_element(e.id)
        assert locked.locked is True
        assert self.engine.get_element(e.id).locked is True

    def test_unlock_element(self):
        e = self.engine.create_element("node")
        self.engine.lock_element(e.id)
        unlocked = self.engine.unlock_element(e.id)
        assert unlocked.locked is False
        assert self.engine.get_element(e.id).locked is False

    def test_delete_element(self):
        e = self.engine.create_element("node")
        assert self.engine.delete_element(e.id) is True
        assert self.engine.delete_element(e.id) is False
        with pytest.raises(GanttMlDragPricingError):
            self.engine.get_element(e.id)

    def test_create_session(self):
        s = self.engine.create_session("canvas-1", "user-1")
        assert s.id.startswith("session-")
        assert s.canvas_id == "canvas-1"
        assert s.user_id == "user-1"
        assert s.elements == []
        assert s.active is True

    def test_get_session(self):
        s = self.engine.create_session("c1", "u1")
        got = self.engine.get_session(s.id)
        assert got.id == s.id

    def test_get_session_not_found(self):
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.get_session("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list_sessions(self):
        s1 = self.engine.create_session("c1", "u1")
        s2 = self.engine.create_session("c2", "u2")
        s3 = self.engine.create_session("c1", "u3")
        self.engine.close_session(s1.id)
        # all
        assert len(self.engine.list_sessions()) == 3
        # filter by canvas_id
        c1 = self.engine.list_sessions(canvas_id="c1")
        assert {s.id for s in c1} == {s1.id, s3.id}
        # active_only 排除已关闭
        active = self.engine.list_sessions(active_only=True)
        assert s1.id not in {s.id for s in active}
        assert {s.id for s in active} == {s2.id, s3.id}

    def test_add_element_to_session(self):
        s = self.engine.create_session("c1", "u1")
        e = self.engine.create_element("node")
        updated = self.engine.add_element_to_session(s.id, e.id)
        assert e.id in updated.elements
        # 幂等：重复添加不重复
        updated2 = self.engine.add_element_to_session(s.id, e.id)
        assert updated2.elements.count(e.id) == 1

    def test_close_session(self):
        s = self.engine.create_session("c1", "u1")
        closed = self.engine.close_session(s.id)
        assert closed.active is False
        assert self.engine.get_session(s.id).active is False

    def test_fifo_eviction_elements(self):
        capacity = self.engine._MAX_ELEMENTS
        first = self.engine.create_element("node")
        for i in range(capacity):
            self.engine.create_element("node")
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.get_element(first.id)
        assert exc.value.code == "NOT_FOUND"
        assert len(self.engine.list_elements()) == capacity


# ════════════════════ #21 Compute Pricing ════════════════════

class TestComputePricingEngine:
    def setup_method(self):
        self.engine = ComputePricingEngine()

    def test_set_pricing(self):
        tier = self.engine.set_pricing(
            "vcpu", 0.001, currency="USD",
            min_charge_seconds=5, description="cpu",
        )
        assert tier.id.startswith("tier-")
        assert tier.resource_type == "vcpu"
        assert tier.price_per_second == 0.001
        assert tier.currency == "USD"
        assert tier.min_charge_seconds == 5
        assert tier.description == "cpu"

    def test_set_pricing_invalid_resource_type(self):
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.set_pricing("ram", 0.001)
        assert exc.value.code == "INVALID_RESOURCE_TYPE"

    def test_set_pricing_negative_price(self):
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.set_pricing("vcpu", -0.001)
        assert exc.value.code == "INVALID_PRICE"

    def test_get_pricing(self):
        self.engine.set_pricing("vcpu", 0.001)
        tier = self.engine.get_pricing("vcpu")
        assert tier.resource_type == "vcpu"
        assert tier.price_per_second == 0.001

    def test_get_pricing_not_found(self):
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.get_pricing("vcpu")
        assert exc.value.code == "NOT_FOUND"

    def test_list_pricing(self):
        self.engine.set_pricing("vcpu", 0.001)
        self.engine.set_pricing("gpu_t4", 0.01)
        tiers = self.engine.list_pricing()
        assert len(tiers) == 2
        assert {t.resource_type for t in tiers} == {"vcpu", "gpu_t4"}

    def test_delete_pricing(self):
        self.engine.set_pricing("vcpu", 0.001)
        assert self.engine.delete_pricing("vcpu") is True
        assert self.engine.delete_pricing("vcpu") is False
        with pytest.raises(GanttMlDragPricingError):
            self.engine.get_pricing("vcpu")

    def test_start_metering(self):
        self.engine.set_pricing("vcpu", 0.001, currency="USD")
        meter = self.engine.start_metering("sess-1", "vcpu")
        assert meter.id.startswith("meter-")
        assert meter.session_id == "sess-1"
        assert meter.resource_type == "vcpu"
        assert meter.status == "running"
        assert meter.currency == "USD"
        assert meter.start_time > 0
        assert meter.duration_seconds == 0
        assert meter.cost == 0.0

    def test_start_metering_no_pricing(self):
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.start_metering("sess-1", "vcpu")
        assert exc.value.code == "NOT_FOUND"

    def test_stop_metering(self):
        self.engine.set_pricing("vcpu", 0.01, min_charge_seconds=1)
        meter = self.engine.start_metering("sess-1", "vcpu")
        stopped = self.engine.stop_metering(meter.id)
        assert stopped.status == "computed"
        assert stopped.end_time >= stopped.start_time
        # 不少于 min_charge_seconds
        assert stopped.duration_seconds >= 1
        # cost = duration * price
        assert stopped.cost == stopped.duration_seconds * 0.01

    def test_bill_meter(self):
        self.engine.set_pricing("vcpu", 0.01)
        meter = self.engine.start_metering("sess-1", "vcpu")
        self.engine.stop_metering(meter.id)
        billed = self.engine.bill_meter(meter.id)
        assert billed.status == "billed"
        assert self.engine.get_meter(meter.id).status == "billed"

    def test_bill_meter_not_computed(self):
        self.engine.set_pricing("vcpu", 0.01)
        meter = self.engine.start_metering("sess-1", "vcpu")
        # 仍处于 running 状态 -> 报错
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.bill_meter(meter.id)
        assert exc.value.code == "NOT_COMPUTED"

    def test_get_usage_summary(self):
        self.engine.set_pricing("vcpu", 0.01)
        self.engine.set_pricing("gpu_t4", 0.1)
        m1 = self.engine.start_metering("sess-1", "vcpu")
        self.engine.stop_metering(m1.id)
        m1 = self.engine.get_meter(m1.id)
        m2 = self.engine.start_metering("sess-1", "gpu_t4")
        self.engine.stop_metering(m2.id)
        m2 = self.engine.get_meter(m2.id)
        summary = self.engine.get_usage_summary("sess-1")
        assert summary["session_id"] == "sess-1"
        assert summary["meter_count"] == 2
        assert summary["total_cost"] == m1.cost + m2.cost
        assert summary["total_seconds"] == m1.duration_seconds + m2.duration_seconds
        assert set(summary["by_resource"].keys()) == {"vcpu", "gpu_t4"}
        assert summary["by_resource"]["vcpu"]["cost"] == m1.cost
        assert summary["by_resource"]["vcpu"]["seconds"] == m1.duration_seconds

    def test_fifo_eviction_meters(self):
        self.engine.set_pricing("vcpu", 0.01)
        capacity = self.engine._MAX_METERS
        first = self.engine.start_metering("sess-1", "vcpu")
        for i in range(capacity):
            self.engine.start_metering("sess-1", "vcpu")
        with pytest.raises(GanttMlDragPricingError) as exc:
            self.engine.get_meter(first.id)
        assert exc.value.code == "NOT_FOUND"
        assert len(self.engine.list_meters()) == capacity


# ════════════════════ Singleton getters ════════════════════

def test_singleton_getters():
    assert get_gantt_schedule_engine() is get_gantt_schedule_engine()
    assert get_ml_scheduling_engine() is get_ml_scheduling_engine()
    assert get_workshop_drag_engine() is get_workshop_drag_engine()
    assert get_compute_pricing_engine() is get_compute_pricing_engine()
