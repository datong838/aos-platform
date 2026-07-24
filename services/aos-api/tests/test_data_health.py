"""W2-AB · Data Health 检查组测试（#133 / #134 / #135）.

覆盖 HealthCheckTypeEngine / HealthScheduleEngine / HealthCheckGroupEngine 三引擎。
"""
from __future__ import annotations

import time

import pytest

from aos_api.data_health import (
    DataHealthError,
    HealthCheckGroup,
    HealthCheckGroupEngine,
    HealthCheckType,
    HealthCheckTypeEngine,
    HealthSchedule,
    HealthScheduleEngine,
    get_health_check_group_engine,
    get_health_check_type_engine,
    get_health_schedule_engine,
)


# ════════════════════ HealthCheckTypeEngine ════════════════════

class TestHealthCheckType:
    def setup_method(self) -> None:
        self.eng = HealthCheckTypeEngine()

    def _mk(self, **kw: object) -> HealthCheckType:
        defaults: dict[str, object] = {
            "name": "hc1",
            "check_kind": "freshness",
            "target_dataset_rid": "ds-1",
            "configuration": {"threshold": 3600},
        }
        defaults.update(kw)
        return HealthCheckType(**defaults)

    def test_register_returns_with_id(self) -> None:
        c = self.eng.register(self._mk())
        assert c.id.startswith("hc-")

    def test_register_invalid_check_kind(self) -> None:
        with pytest.raises(DataHealthError) as exc:
            self.eng.register(self._mk(check_kind="unknown"))
        assert exc.value.code == "INVALID_CHECK_KIND"

    def test_register_missing_name(self) -> None:
        with pytest.raises(DataHealthError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_invalid_severity(self) -> None:
        with pytest.raises(DataHealthError) as exc:
            self.eng.register(self._mk(severity="critical"))
        assert exc.value.code == "INVALID_SEVERITY"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataHealthError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(name="a"))
        self.eng.register(self._mk(name="b", check_kind="volume"))
        assert len(self.eng.list()) == 2

    def test_list_filter_check_kind(self) -> None:
        self.eng.register(self._mk(name="a"))
        self.eng.register(self._mk(name="b", check_kind="volume"))
        items = self.eng.list(check_kind="volume")
        assert len(items) == 1
        assert items[0].check_kind == "volume"

    def test_list_enabled_only(self) -> None:
        self.eng.register(self._mk(name="a", enabled=False))
        self.eng.register(self._mk(name="b"))
        assert len(self.eng.list(enabled_only=True)) == 1

    def test_update(self) -> None:
        c = self.eng.register(self._mk())
        updated = self.eng.update(c.id, {"name": "renamed", "enabled": False})
        assert updated.name == "renamed"
        assert updated.enabled is False

    def test_delete(self) -> None:
        c = self.eng.register(self._mk())
        assert self.eng.delete(c.id) is True
        assert self.eng.delete(c.id) is False

    def test_run_freshness_passed(self) -> None:
        c = self.eng.register(self._mk())
        now = time.time()
        r = self.eng.run(c.id, measured_value=now)  # 延迟 0 <= 3600
        assert r.status == "passed"

    def test_run_freshness_failed(self) -> None:
        c = self.eng.register(self._mk())
        old_ts = time.time() - 7200  # 延迟 7200 > 3600
        r = self.eng.run(c.id, measured_value=old_ts)
        assert r.status == "failed"

    def test_run_disabled_skipped(self) -> None:
        c = self.eng.register(self._mk(enabled=False))
        r = self.eng.run(c.id, measured_value=time.time())
        assert r.status == "skipped"

    def test_list_results(self) -> None:
        c = self.eng.register(self._mk())
        self.eng.run(c.id, measured_value=time.time())
        self.eng.run(c.id, measured_value=time.time())
        assert len(self.eng.list_results()) == 2

    def test_results_cap_eviction(self) -> None:
        from aos_api.data_health import _MAX_RESULTS
        c = self.eng.register(self._mk())
        for _ in range(_MAX_RESULTS + 5):
            self.eng.run(c.id, measured_value=time.time())
        assert len(self.eng._results) == _MAX_RESULTS


# ════════════════════ HealthScheduleEngine ════════════════════

class TestHealthSchedule:
    def setup_method(self) -> None:
        self.eng = HealthScheduleEngine()

    def _mk_auto(self, **kw: object) -> HealthSchedule:
        defaults: dict[str, object] = {
            "check_id": "hc-1",
            "mode": "auto",
            "trigger_dataset_rid": "ds-1",
        }
        defaults.update(kw)
        return HealthSchedule(**defaults)

    def _mk_manual(self, **kw: object) -> HealthSchedule:
        defaults: dict[str, object] = {
            "check_id": "hc-1",
            "mode": "manual",
            "cron_expression": "*/5 * * * *",
        }
        defaults.update(kw)
        return HealthSchedule(**defaults)

    def test_register_auto(self) -> None:
        s = self.eng.register(self._mk_auto())
        assert s.id.startswith("hs-")
        assert s.mode == "auto"

    def test_register_manual(self) -> None:
        s = self.eng.register(self._mk_manual())
        assert s.mode == "manual"
        assert s.next_run_at > 0  # manual 应计算初始 next_run

    def test_register_invalid_mode(self) -> None:
        with pytest.raises(DataHealthError) as exc:
            self.eng.register(HealthSchedule(check_id="c", mode="bad"))
        assert exc.value.code == "INVALID_MODE"

    def test_register_auto_missing_trigger(self) -> None:
        with pytest.raises(DataHealthError) as exc:
            self.eng.register(HealthSchedule(check_id="c", mode="auto"))
        assert exc.value.code == "MISSING_TRIGGER_DATASET"

    def test_register_manual_missing_cron(self) -> None:
        with pytest.raises(DataHealthError) as exc:
            self.eng.register(HealthSchedule(check_id="c", mode="manual"))
        assert exc.value.code == "MISSING_CRON"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataHealthError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk_auto())
        self.eng.register(self._mk_manual())
        assert len(self.eng.list()) == 2

    def test_list_filter_mode(self) -> None:
        self.eng.register(self._mk_auto())
        self.eng.register(self._mk_manual())
        items = self.eng.list(mode="auto")
        assert len(items) == 1
        assert items[0].mode == "auto"

    def test_list_enabled_only(self) -> None:
        self.eng.register(self._mk_auto(enabled=False))
        self.eng.register(self._mk_auto())
        assert len(self.eng.list(enabled_only=True)) == 1

    def test_update(self) -> None:
        s = self.eng.register(self._mk_auto())
        updated = self.eng.update(s.id, {"enabled": False, "trigger_dataset_rid": "ds-2"})
        assert updated.enabled is False
        assert updated.trigger_dataset_rid == "ds-2"

    def test_delete(self) -> None:
        s = self.eng.register(self._mk_auto())
        assert self.eng.delete(s.id) is True
        assert self.eng.delete(s.id) is False

    def test_trigger_auto(self) -> None:
        s = self.eng.register(self._mk_auto())
        result = self.eng.trigger(s.id)
        assert result["triggered"] is True
        assert result["run_count"] == 1
        s2 = self.eng.get(s.id)
        assert s2.last_run_at > 0

    def test_trigger_manual_advances_next_run(self) -> None:
        s = self.eng.register(self._mk_manual())
        old_next = s.next_run_at
        time.sleep(0.01)
        result = self.eng.trigger(s.id)
        assert result["triggered"] is True
        s2 = self.eng.get(s.id)
        assert s2.next_run_at > old_next

    def test_trigger_disabled(self) -> None:
        s = self.eng.register(self._mk_auto(enabled=False))
        result = self.eng.trigger(s.id)
        assert result["triggered"] is False


# ════════════════════ HealthCheckGroupEngine ════════════════════

class TestHealthCheckGroup:
    def setup_method(self) -> None:
        self.eng = HealthCheckGroupEngine()

    def _mk(self, **kw: object) -> HealthCheckGroup:
        defaults: dict[str, object] = {
            "name": "hg1",
            "description": "test group",
        }
        defaults.update(kw)
        return HealthCheckGroup(**defaults)

    def test_register_returns_with_id(self) -> None:
        g = self.eng.register(self._mk())
        assert g.id.startswith("hg-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(DataHealthError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_name_duplicate(self) -> None:
        self.eng.register(self._mk(name="dup"))
        with pytest.raises(DataHealthError) as exc:
            self.eng.register(self._mk(name="dup"))
        assert exc.value.code == "NAME_DUPLICATE"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataHealthError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(name="a"))
        self.eng.register(self._mk(name="b"))
        assert len(self.eng.list()) == 2

    def test_list_enabled_only(self) -> None:
        self.eng.register(self._mk(name="a", enabled=False))
        self.eng.register(self._mk(name="b"))
        assert len(self.eng.list(enabled_only=True)) == 1

    def test_update(self) -> None:
        g = self.eng.register(self._mk())
        updated = self.eng.update(g.id, {"description": "updated", "enabled": False})
        assert updated.description == "updated"
        assert updated.enabled is False

    def test_delete(self) -> None:
        g = self.eng.register(self._mk())
        assert self.eng.delete(g.id) is True
        assert self.eng.delete(g.id) is False

    def test_attach_check(self) -> None:
        g = self.eng.register(self._mk())
        result = self.eng.attach_check(g.id, "hc-1")
        assert "hc-1" in result.check_ids

    def test_detach_check(self) -> None:
        g = self.eng.register(self._mk(check_ids=["hc-1", "hc-2"]))
        result = self.eng.detach_check(g.id, "hc-1")
        assert "hc-1" not in result.check_ids
        assert "hc-2" in result.check_ids

    def test_attach_idempotent(self) -> None:
        g = self.eng.register(self._mk(check_ids=["hc-1"]))
        result = self.eng.attach_check(g.id, "hc-1")
        assert result.check_ids.count("hc-1") == 1

    def test_monitor(self) -> None:
        # 注册一个检查，跑一次 passed —— 用单例引擎（monitor 内部也用单例）
        check_eng = get_health_check_type_engine()
        c = check_eng.register(HealthCheckType(
            name="c1", check_kind="freshness", target_dataset_rid="ds",
            configuration={"threshold": 3600},
        ))
        check_eng.run(c.id, measured_value=time.time())

        g = self.eng.register(self._mk(check_ids=[c.id]))
        summary = self.eng.monitor(g.id)
        assert summary.total_checks == 1
        assert summary.enabled_checks == 1
        assert summary.last_results.get(c.id) == "passed"
        assert summary.pass_rate == 1.0

    def test_send_notification(self) -> None:
        g = self.eng.register(self._mk(notification_config={
            "channels": ["email", "webhook"],
            "severity_filter": ["error", "warning"],
        }))
        record = self.eng.send_notification(g.id, {"severity": "error", "msg": "fail"})
        assert "email" in record["dispatched_channels"]
        assert "webhook" in record["dispatched_channels"]

    def test_send_notification_filtered(self) -> None:
        g = self.eng.register(self._mk(notification_config={
            "channels": ["email"],
            "severity_filter": ["error"],
        }))
        # severity=warning 不在 filter 中 → 不派发
        record = self.eng.send_notification(g.id, {"severity": "warning"})
        assert record["dispatched_channels"] == []


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_check_type_singleton(self) -> None:
        a = get_health_check_type_engine()
        b = get_health_check_type_engine()
        assert a is b

    def test_schedule_singleton(self) -> None:
        a = get_health_schedule_engine()
        b = get_health_schedule_engine()
        assert a is b

    def test_group_singleton(self) -> None:
        a = get_health_check_group_engine()
        b = get_health_check_group_engine()
        assert a is b


# ════════════════════ 扩展：检查类型多种 run 场景 ════════════════════

class TestExtendedCheckRuns:
    def test_volume_check_passed(self) -> None:
        eng = HealthCheckTypeEngine()
        c = eng.register(HealthCheckType(
            name="v1", check_kind="volume", target_dataset_rid="ds",
            configuration={"threshold": 100},
        ))
        r = eng.run(c.id, measured_value=150)
        assert r.status == "passed"

    def test_volume_check_failed(self) -> None:
        eng = HealthCheckTypeEngine()
        c = eng.register(HealthCheckType(
            name="v1", check_kind="volume", target_dataset_rid="ds",
            configuration={"threshold": 100},
        ))
        r = eng.run(c.id, measured_value=50)
        assert r.status == "failed"

    def test_schema_check_passed(self) -> None:
        eng = HealthCheckTypeEngine()
        c = eng.register(HealthCheckType(
            name="s1", check_kind="schema", target_dataset_rid="ds",
            configuration={"expected_columns": ["id", "name", "email"]},
        ))
        r = eng.run(c.id, measured_value=["id", "name", "email"])
        assert r.status == "passed"

    def test_schema_check_missing_columns(self) -> None:
        eng = HealthCheckTypeEngine()
        c = eng.register(HealthCheckType(
            name="s1", check_kind="schema", target_dataset_rid="ds",
            configuration={"expected_columns": ["id", "name", "email"]},
        ))
        r = eng.run(c.id, measured_value=["id", "name"])
        assert r.status == "failed"
        assert "缺失列" in r.message

    def test_content_check_passed(self) -> None:
        eng = HealthCheckTypeEngine()
        c = eng.register(HealthCheckType(
            name="c1", check_kind="content", target_dataset_rid="ds",
            configuration={"rules": [
                {"field": "count", "op": "ge", "value": 10},
                {"field": "status", "op": "eq", "value": "ok"},
            ]},
        ))
        r = eng.run(c.id, measured_value={"count": 20, "status": "ok"})
        assert r.status == "passed"

    def test_content_check_failed(self) -> None:
        eng = HealthCheckTypeEngine()
        c = eng.register(HealthCheckType(
            name="c1", check_kind="content", target_dataset_rid="ds",
            configuration={"rules": [
                {"field": "count", "op": "ge", "value": 10},
            ]},
        ))
        r = eng.run(c.id, measured_value={"count": 5})
        assert r.status == "failed"

    def test_freshness_duration_passed(self) -> None:
        eng = HealthCheckTypeEngine()
        c = eng.register(HealthCheckType(
            name="fd1", check_kind="freshness_duration", target_dataset_rid="ds",
            configuration={"threshold": 24},  # 24 小时
        ))
        recent = time.time() - 3600  # 1 小时前
        r = eng.run(c.id, measured_value=recent)
        assert r.status == "passed"

    def test_freshness_duration_failed(self) -> None:
        eng = HealthCheckTypeEngine()
        c = eng.register(HealthCheckType(
            name="fd1", check_kind="freshness_duration", target_dataset_rid="ds",
            configuration={"threshold": 1},  # 1 小时
        ))
        old = time.time() - 7200  # 2 小时前
        r = eng.run(c.id, measured_value=old)
        assert r.status == "failed"

    def test_run_missing_measured_value(self) -> None:
        eng = HealthCheckTypeEngine()
        c = eng.register(HealthCheckType(
            name="f1", check_kind="freshness", target_dataset_rid="ds",
            configuration={"threshold": 3600},
        ))
        r = eng.run(c.id, measured_value=None)
        assert r.status == "errored"

    def test_list_results_filter_status(self) -> None:
        eng = HealthCheckTypeEngine()
        c = eng.register(HealthCheckType(
            name="f1", check_kind="freshness", target_dataset_rid="ds",
            configuration={"threshold": 3600},
        ))
        eng.run(c.id, measured_value=time.time())  # passed
        eng.run(c.id, measured_value=time.time() - 7200)  # failed
        passed = eng.list_results(status="passed")
        failed = eng.list_results(status="failed")
        assert len(passed) == 1
        assert len(failed) == 1

    def test_update_invalid_check_kind(self) -> None:
        eng = HealthCheckTypeEngine()
        c = eng.register(HealthCheckType(
            name="c", check_kind="freshness", target_dataset_rid="ds",
        ))
        with pytest.raises(DataHealthError) as exc:
            eng.update(c.id, {"check_kind": "bad"})
        assert exc.value.code == "INVALID_CHECK_KIND"

    def test_monitor_with_missing_check(self) -> None:
        eng = HealthCheckGroupEngine()
        g = eng.register(HealthCheckGroup(name="g", check_ids=["missing-id"]))
        summary = eng.monitor(g.id)
        assert summary.last_results.get("missing-id") == "missing"
        assert summary.total_checks == 1

    def test_schedule_update_cron_recomputes_next_run(self) -> None:
        eng = HealthScheduleEngine()
        s = eng.register(HealthSchedule(
            check_id="c", mode="manual", cron_expression="*/5 * * * *",
        ))
        old_next = s.next_run_at
        time.sleep(0.01)
        eng.update(s.id, {"cron_expression": "*/10 * * * *"})
        s2 = eng.get(s.id)
        # 更新后 next_run 应基于新 cron 重新计算
        assert s2.next_run_at > 0

    def test_compute_next_run_auto_returns_zero(self) -> None:
        eng = HealthScheduleEngine()
        s = eng.register(HealthSchedule(
            check_id="c", mode="auto", trigger_dataset_rid="ds",
        ))
        assert eng.compute_next_run(s.id) == 0.0

    def test_group_update_name_duplicate(self) -> None:
        eng = HealthCheckGroupEngine()
        eng.register(HealthCheckGroup(name="g1"))
        g2 = eng.register(HealthCheckGroup(name="g2"))
        with pytest.raises(DataHealthError) as exc:
            eng.update(g2.id, {"name": "g1"})
        assert exc.value.code == "NAME_DUPLICATE"
