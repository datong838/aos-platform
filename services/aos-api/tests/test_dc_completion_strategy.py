"""W3 Task 1.1 · Completion Strategy 完成策略引擎测试（220w L156）.

覆盖四种触发策略：ON_SUCCESS / ON_FAILURE / ALWAYS / NEVER
+ cooldown 冷却 + max_retries 重试 + evaluate 评估逻辑
"""
from __future__ import annotations

import pytest

from aos_api.dc_completion_strategy import (
    CompletionStrategy,
    CompletionStrategyEngine,
    CompletionStrategyError,
    get_engine,
)


class TestCompletionStrategy:
    def setup_method(self) -> None:
        self.eng = CompletionStrategyEngine()
        self.eng._strategies = {}

    def _mk(self, **kw: object) -> CompletionStrategy:
        defaults: dict[str, object] = {
            "name": "trigger-downstream",
            "trigger": "ON_SUCCESS",
            "downstream_task_ids": ["task-A", "task-B"],
            "cooldown_seconds": 60,
            "max_retries": 3,
        }
        defaults.update(kw)
        return CompletionStrategy(**defaults)

    # ── register / get ──

    def test_register_returns_id(self) -> None:
        s = self.eng.register(self._mk())
        assert s.strategy_id.startswith("cs-")
        assert s.name == "trigger-downstream"

    def test_get_strategy(self) -> None:
        s = self.eng.register(self._mk())
        got = self.eng.get(s.strategy_id)
        assert got.strategy_id == s.strategy_id

    def test_get_not_found(self) -> None:
        with pytest.raises(CompletionStrategyError) as exc:
            self.eng.get("cs-nonexistent")
        assert exc.value.code == "NOT_FOUND"

    # ── list ──

    def test_list_all(self) -> None:
        self.eng.register(self._mk(name="a"))
        self.eng.register(self._mk(name="b"))
        assert len(self.eng.list()) == 2

    def test_list_filter_trigger(self) -> None:
        self.eng.register(self._mk(name="a", trigger="ON_SUCCESS"))
        self.eng.register(self._mk(name="b", trigger="ON_FAILURE"))
        items = self.eng.list(trigger="ON_SUCCESS")
        assert len(items) == 1
        assert items[0].trigger == "ON_SUCCESS"

    def test_list_filter_enabled(self) -> None:
        self.eng.register(self._mk(name="a", enabled=True))
        self.eng.register(self._mk(name="b", enabled=False))
        items = self.eng.list(enabled=True)
        assert len(items) == 1
        assert items[0].enabled is True

    # ── update / delete ──

    def test_update(self) -> None:
        s = self.eng.register(self._mk())
        updated = self.eng.update(s.strategy_id, {"name": "new-name", "max_retries": 5})
        assert updated.name == "new-name"
        assert updated.max_retries == 5

    def test_update_not_found(self) -> None:
        with pytest.raises(CompletionStrategyError):
            self.eng.update("cs-x", {"name": "y"})

    def test_delete(self) -> None:
        s = self.eng.register(self._mk())
        self.eng.delete(s.strategy_id)
        with pytest.raises(CompletionStrategyError):
            self.eng.get(s.strategy_id)

    # ── 校验 ──

    def test_invalid_trigger(self) -> None:
        with pytest.raises(CompletionStrategyError) as exc:
            self.eng.register(self._mk(trigger="INVALID"))
        assert exc.value.code == "INVALID_TRIGGER"

    def test_missing_name(self) -> None:
        with pytest.raises(CompletionStrategyError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    # ── evaluate 评估逻辑 ──

    def test_evaluate_on_success(self) -> None:
        s = self.eng.register(self._mk(trigger="ON_SUCCESS", downstream_task_ids=["t1", "t2"]))
        triggered = self.eng.evaluate("task-0", "SUCCESS")
        assert "t1" in triggered
        assert "t2" in triggered

    def test_evaluate_on_failure_skips(self) -> None:
        self.eng.register(self._mk(trigger="ON_SUCCESS", downstream_task_ids=["t1"]))
        triggered = self.eng.evaluate("task-0", "FAILURE")
        assert "t1" not in triggered

    def test_evaluate_on_failure_triggers(self) -> None:
        self.eng.register(self._mk(trigger="ON_FAILURE", downstream_task_ids=["retry"]))
        triggered = self.eng.evaluate("task-0", "FAILURE")
        assert "retry" in triggered

    def test_evaluate_always(self) -> None:
        self.eng.register(self._mk(trigger="ALWAYS", downstream_task_ids=["t"], cooldown_seconds=0))
        assert "t" in self.eng.evaluate("task-0", "SUCCESS")
        assert "t" in self.eng.evaluate("task-0", "FAILURE")

    def test_evaluate_never(self) -> None:
        self.eng.register(self._mk(trigger="NEVER", downstream_task_ids=["t"]))
        triggered = self.eng.evaluate("task-0", "SUCCESS")
        assert "t" not in triggered

    def test_evaluate_disabled(self) -> None:
        s = self.eng.register(self._mk(trigger="ON_SUCCESS", downstream_task_ids=["t"], enabled=False))
        triggered = self.eng.evaluate("task-0", "SUCCESS")
        assert "t" not in triggered

    def test_evaluate_cooldown(self) -> None:
        """连续触发时冷却期内应跳过."""
        s = self.eng.register(self._mk(trigger="ON_SUCCESS", downstream_task_ids=["t"], cooldown_seconds=3600))
        # 第一次触发
        triggered1 = self.eng.evaluate("task-0", "SUCCESS")
        assert "t" in triggered1
        # 冷却期内再次触发
        triggered2 = self.eng.evaluate("task-0", "SUCCESS")
        assert "t" not in triggered2

    # ── LRU 淘汰 ──

    def test_capacity_limit(self) -> None:
        for i in range(205):
            self.eng.register(self._mk(name=f"s-{i}"))
        assert len(self.eng._strategies) <= 200


class TestCompletionStrategySingleton:
    def test_get_engine_returns_same_instance(self) -> None:
        e1 = get_engine()
        e2 = get_engine()
        assert e1 is e2
