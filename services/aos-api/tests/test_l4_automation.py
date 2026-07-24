"""W2-W · L4 自动化收尾组测试：#82 L4 熔断 + #83 模型预热 + #86 三种提案通道."""
from __future__ import annotations

import pytest

from aos_api.l4_automation import (
    L4AutomationError,
    L4CircuitConfig,
    L4CircuitEngine,
    ModelWarmupEngine,
    ProposalChannel,
    ProposalChannelEngine,
)


# ════════════════════ #82 L4CircuitEngine ════════════════════

class _FakeClock:
    def __init__(self, t0: float = 1000.0) -> None:
        self.t = t0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class TestL4CircuitEngine:
    """L4 熔断引擎 15 项测试。"""

    def test_get_config_default(self) -> None:
        eng = L4CircuitEngine()
        cfg = eng.get_config()
        assert cfg.window_size == 100
        assert cfg.failure_threshold == 0.05
        assert cfg.recovery_threshold == 0.025
        assert cfg.cooldown_seconds == 60.0
        assert cfg.auto_degrade_to == "L3"

    def test_update_config(self) -> None:
        eng = L4CircuitEngine()
        new_cfg = L4CircuitConfig(
            window_size=50, failure_threshold=0.1,
            recovery_threshold=0.05, cooldown_seconds=30.0,
        )
        updated = eng.update_config(new_cfg)
        assert updated.window_size == 50
        assert eng.get_config().window_size == 50

    def test_get_state_initial(self) -> None:
        eng = L4CircuitEngine()
        state = eng.get_state()
        assert state.current_level == "L4"
        assert state.degraded is False
        assert state.failure_rate == 0.0

    def test_record_call_success(self) -> None:
        eng = L4CircuitEngine()
        state = eng.record_call(True)
        assert state.window_total == 1
        assert state.window_failures == 0
        assert state.failure_rate == 0.0

    def test_record_call_failure(self) -> None:
        eng = L4CircuitEngine()
        state = eng.record_call(False)
        assert state.window_failures == 1
        assert state.failure_rate == 1.0

    def test_window_overflow(self) -> None:
        eng = L4CircuitEngine()
        eng.update_config(L4CircuitConfig(
            window_size=5, failure_threshold=0.9,
            recovery_threshold=0.01, cooldown_seconds=1.0,
        ))
        for _ in range(10):
            eng.record_call(True)
        state = eng.get_state()
        assert state.window_total == 5

    def test_trigger_degrade(self) -> None:
        clk = _FakeClock()
        eng = L4CircuitEngine(clock=clk)
        eng.update_config(L4CircuitConfig(
            window_size=20, failure_threshold=0.5,
            recovery_threshold=0.1, cooldown_seconds=60.0,
        ))
        # 11 次失败（>50%）
        for _ in range(11):
            eng.record_call(False)
        state = eng.get_state()
        assert state.degraded is True
        assert state.current_level == "L3"
        alerts = eng.list_alerts()
        assert any(a.type == "degrade" for a in alerts)

    def test_no_duplicate_degrade_alert(self) -> None:
        clk = _FakeClock()
        eng = L4CircuitEngine(clock=clk)
        eng.update_config(L4CircuitConfig(
            window_size=20, failure_threshold=0.5,
            recovery_threshold=0.1, cooldown_seconds=60.0,
        ))
        for _ in range(11):
            eng.record_call(False)
        # 继续失败
        for _ in range(5):
            clk.advance(1.0)
            eng.record_call(False)
        alerts = eng.list_alerts()
        degrade_count = sum(1 for a in alerts if a.type == "degrade")
        assert degrade_count == 1

    def test_recover_after_cooldown(self) -> None:
        clk = _FakeClock()
        eng = L4CircuitEngine(clock=clk)
        eng.update_config(L4CircuitConfig(
            window_size=20, failure_threshold=0.5,
            recovery_threshold=0.1, cooldown_seconds=10.0,
        ))
        # 触发降级
        for _ in range(11):
            eng.record_call(False)
        assert eng.get_state().degraded is True
        # 等 cooldown 过
        clk.advance(20.0)
        # 持续成功降低失败率
        for _ in range(20):
            eng.record_call(True)
        state = eng.get_state()
        assert state.degraded is False
        assert state.current_level == "L4"
        alerts = eng.list_alerts()
        assert any(a.type == "recover" for a in alerts)

    def test_no_recover_within_cooldown(self) -> None:
        clk = _FakeClock()
        eng = L4CircuitEngine(clock=clk)
        eng.update_config(L4CircuitConfig(
            window_size=20, failure_threshold=0.5,
            recovery_threshold=0.1, cooldown_seconds=60.0,
        ))
        for _ in range(11):
            eng.record_call(False)
        # cooldown 未过
        clk.advance(10.0)
        for _ in range(20):
            eng.record_call(True)
        state = eng.get_state()
        # cooldown 内不恢复
        assert state.degraded is True

    def test_no_recover_above_threshold(self) -> None:
        clk = _FakeClock()
        eng = L4CircuitEngine(clock=clk)
        eng.update_config(L4CircuitConfig(
            window_size=20, failure_threshold=0.5,
            recovery_threshold=0.1, cooldown_seconds=1.0,
        ))
        for _ in range(11):
            eng.record_call(False)
        clk.advance(5.0)
        # 失败率仍高于 recovery_threshold（10% 失败 = 0.5 > 0.1）
        for _ in range(10):
            eng.record_call(True)
        for _ in range(10):
            eng.record_call(False)
        state = eng.get_state()
        assert state.degraded is True

    def test_force_degrade(self) -> None:
        eng = L4CircuitEngine()
        alert = eng.force_degrade("演练")
        assert alert.type == "degrade"
        assert eng.get_state().degraded is True

    def test_force_recover(self) -> None:
        eng = L4CircuitEngine()
        eng.force_degrade()
        alert = eng.force_recover()
        assert alert.type == "recover"
        assert eng.get_state().degraded is False

    def test_list_alerts(self) -> None:
        eng = L4CircuitEngine()
        eng.force_degrade()
        eng.force_recover()
        alerts = eng.list_alerts()
        assert len(alerts) >= 2

    def test_reset(self) -> None:
        eng = L4CircuitEngine()
        eng.record_call(False)
        eng.force_degrade()
        eng.reset()
        state = eng.get_state()
        assert state.window_total == 0
        assert state.degraded is False
        assert eng.list_alerts() == []


# ════════════════════ #83 ModelWarmupEngine ════════════════════

class TestModelWarmupEngine:
    """模型预热引擎 13 项测试。"""

    def test_register_model(self) -> None:
        eng = ModelWarmupEngine()
        s = eng.register_model("m1")
        assert s.model_id == "m1"
        assert s.state == "cold"

    def test_get_state_not_found(self) -> None:
        eng = ModelWarmupEngine()
        with pytest.raises(L4AutomationError) as exc:
            eng.get_state("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_states(self) -> None:
        eng = ModelWarmupEngine()
        eng.register_model("m1")
        eng.register_model("m2")
        items = eng.list_states()
        assert len(items) == 2

    def test_warmup_success_default_probe(self) -> None:
        eng = ModelWarmupEngine()
        eng.register_model("m1")
        result = eng.warmup("m1")
        assert result.success is True
        s = eng.get_state("m1")
        assert s.state == "ready"

    def test_warmup_failure_injected_probe(self) -> None:
        eng = ModelWarmupEngine()
        eng.register_model("m1")
        result = eng.warmup("m1", probe_callable=lambda: False)
        assert result.success is False
        s = eng.get_state("m1")
        assert s.state == "failed"
        assert s.failure_count == 1

    def test_warmup_failure_triggers_cooldown(self) -> None:
        clk = _FakeClock()
        eng = ModelWarmupEngine(clock=clk)
        eng.register_model("m1")
        eng.warmup("m1", probe_callable=lambda: False)
        with pytest.raises(L4AutomationError) as exc:
            eng.warmup("m1")
        assert exc.value.code == "IN_COOLDOWN"

    def test_warmup_multiple_failures_grow_cooldown(self) -> None:
        clk = _FakeClock()
        eng = ModelWarmupEngine(clock=clk)
        eng.register_model("m1")
        # 第一次失败
        eng.warmup("m1", probe_callable=lambda: False)
        first = eng.get_state("m1")
        first_cd = first.cooldown_until
        # 等 cooldown 过
        clk.advance(first_cd - clk.t + 1.0)
        # 第二次失败
        eng.warmup("m1", probe_callable=lambda: False)
        second = eng.get_state("m1")
        assert second.failure_count == 2
        # 第二次 cooldown 更长
        assert second.cooldown_until > first_cd

    def test_mark_ready(self) -> None:
        eng = ModelWarmupEngine()
        eng.register_model("m1")
        s = eng.mark_ready("m1")
        assert s.state == "ready"

    def test_mark_failed(self) -> None:
        eng = ModelWarmupEngine()
        eng.register_model("m1")
        s = eng.mark_failed("m1", "探测异常")
        assert s.state == "failed"
        assert s.failure_count == 1

    def test_remove_model(self) -> None:
        eng = ModelWarmupEngine()
        eng.register_model("m1")
        assert eng.remove_model("m1") is True
        with pytest.raises(L4AutomationError):
            eng.get_state("m1")

    def test_remove_model_not_found(self) -> None:
        eng = ModelWarmupEngine()
        with pytest.raises(L4AutomationError) as exc:
            eng.remove_model("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_probe_results(self) -> None:
        eng = ModelWarmupEngine()
        eng.register_model("m1")
        eng.warmup("m1")
        eng.warmup("m1")
        items = eng.list_probe_results(model_id="m1")
        assert len(items) == 2

    def test_warmup_unregistered_model(self) -> None:
        eng = ModelWarmupEngine()
        with pytest.raises(L4AutomationError) as exc:
            eng.warmup("nope")
        assert exc.value.code == "NOT_FOUND"


# ════════════════════ #86 ProposalChannelEngine ════════════════════

class TestProposalChannelEngine:
    """提案通道引擎 14 项测试。"""

    def test_list_channels_default_three(self) -> None:
        eng = ProposalChannelEngine()
        items = eng.list_channels()
        assert len(items) == 3
        types = {c.type for c in items}
        assert types == {"sync", "async_automate", "async_pipeline"}

    def test_get_channel_async_automate(self) -> None:
        eng = ProposalChannelEngine()
        ch = eng.get_channel("async_automate")
        assert ch.type == "async_automate"
        assert ch.name

    def test_get_channel_not_found(self) -> None:
        eng = ProposalChannelEngine()
        with pytest.raises(L4AutomationError) as exc:
            eng.get_channel("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_upsert_channel_disable(self) -> None:
        eng = ProposalChannelEngine()
        ch = ProposalChannel(
            type="sync", name="同步通道-禁用", enabled=False,
        )
        eng.upsert_channel(ch)
        got = eng.get_channel("sync")
        assert got.enabled is False

    def test_submit_sync_auto_complete(self) -> None:
        eng = ProposalChannelEngine()
        s = eng.submit(channel="sync", logic_id="L1", submitted_by="alice")
        assert s.status == "completed"
        assert s.approval_status == "approved"
        assert s.completed_at > 0

    def test_submit_async_automate_pending(self) -> None:
        eng = ProposalChannelEngine()
        s = eng.submit(channel="async_automate", logic_id="L1")
        assert s.status == "pending"
        assert s.approval_status == "pending"
        assert s.visible_until > s.submitted_at

    def test_submit_async_pipeline_pending(self) -> None:
        eng = ProposalChannelEngine()
        s = eng.submit(channel="async_pipeline", logic_id="L1")
        assert s.status == "pending"

    def test_submit_disabled_channel(self) -> None:
        eng = ProposalChannelEngine()
        eng.upsert_channel(ProposalChannel(
            type="sync", name="同步通道", enabled=False,
        ))
        with pytest.raises(L4AutomationError) as exc:
            eng.submit(channel="sync", logic_id="L1")
        assert exc.value.code == "CHANNEL_DISABLED"

    def test_submit_invalid_channel(self) -> None:
        eng = ProposalChannelEngine()
        with pytest.raises(L4AutomationError) as exc:
            eng.submit(channel="unknown", logic_id="L1")
        assert exc.value.code == "INVALID_CHANNEL"

    def test_submit_invalid_logic_id(self) -> None:
        eng = ProposalChannelEngine()
        with pytest.raises(L4AutomationError) as exc:
            eng.submit(channel="sync", logic_id="")
        assert exc.value.code == "INVALID_LOGIC_ID"

    def test_approve_proposal(self) -> None:
        eng = ProposalChannelEngine()
        s = eng.submit(channel="async_automate", logic_id="L1")
        approved = eng.approve(s.id, "bob")
        assert approved.approval_status == "approved"
        assert approved.approved_by == "bob"
        assert approved.status == "completed"

    def test_reject_proposal(self) -> None:
        eng = ProposalChannelEngine()
        s = eng.submit(channel="async_automate", logic_id="L1")
        rejected = eng.reject(s.id, "bob", "理由")
        assert rejected.approval_status == "rejected"
        assert rejected.status == "failed"
        assert rejected.error == "理由"

    def test_cancel_proposal(self) -> None:
        eng = ProposalChannelEngine()
        s = eng.submit(channel="async_automate", logic_id="L1")
        cancelled = eng.cancel(s.id)
        assert cancelled.status == "cancelled"

    def test_cleanup_expired(self) -> None:
        eng = ProposalChannelEngine()
        # 提交一个 visibility_hours=0 的提案（立即过期）
        s = eng.submit(
            channel="async_automate", logic_id="L1",
            visibility_hours=0.0,
        )
        # 因为 visible_until = now + 0*3600 = now，测试可能略晚一点
        # 强制重置 visible_until 为过去时间
        s.visible_until = 1.0  # 1970 年
        count = eng.cleanup_expired()
        assert count == 1
        s2 = eng.get_submission(s.id)
        assert s2.status == "cancelled"
        assert s2.error == "expired"
