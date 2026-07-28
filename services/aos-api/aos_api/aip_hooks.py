"""AIP Hooks — Hook 系统.

提供 before_step / after_step / on_error 钩子。
支持注册多个回调，按顺序执行。
"""
from __future__ import annotations

import time
from typing import Any, Callable

from aos_api.aip_task_model import Task, TaskStep


HookCallback = Callable[..., None]


class HookSystem:
    """Hook 系统 — 在 TAOR 循环的关键节点触发回调。

    钩子类型：
    - before_step: 步骤执行前
    - after_step: 步骤执行后
    - on_error: 步骤失败时
    - on_checkpoint: 检查点保存时
    - on_plan_approved: 计划审批通过时
    """

    def __init__(self) -> None:
        self._hooks: dict[str, list[HookCallback]] = {
            "before_step": [],
            "after_step": [],
            "on_error": [],
            "on_checkpoint": [],
            "on_plan_approved": [],
        }

    def register(self, event: str, callback: HookCallback) -> None:
        if event in self._hooks:
            self._hooks[event].append(callback)

    def unregister(self, event: str, callback: HookCallback) -> None:
        if event in self._hooks and callback in self._hooks[event]:
            self._hooks[event].remove(callback)

    def trigger(self, event: str, **kwargs: Any) -> None:
        for cb in self._hooks.get(event, []):
            try:
                cb(**kwargs)
            except Exception:
                pass  # Hook 失败不影响主流程


# ── 默认 Hook 实现 ──

def _log_before_step(task: Task, step: TaskStep, **_: Any) -> None:
    """日志 Hook — 记录步骤开始。"""
    from aos_api.logging_facade import get_logger

    log = get_logger("aos-api.aip_taor")
    log.info("step_start task=%s step=%s action=%s", task.id, step.name, step.action.action_type)


def _log_after_step(task: Task, step: TaskStep, **_: Any) -> None:
    """日志 Hook — 记录步骤完成。"""
    from aos_api.logging_facade import get_logger

    log = get_logger("aos-api.aip_taor")
    log.info(
        "step_done task=%s step=%s tokens=%d elapsed=%dms",
        task.id, step.name, step.tokens_used, step.elapsed_ms,
    )


def _log_error(task: Task, step: TaskStep, error: str, **_: Any) -> None:
    """日志 Hook — 记录步骤失败。"""
    from aos_api.logging_facade import get_logger

    log = get_logger("aos-api.aip_taor")
    log.warning("step_error task=%s step=%s error=%s", task.id, step.name, error)


# ── Singleton ──

_hooks: HookSystem | None = None


def get_hooks() -> HookSystem:
    global _hooks
    if _hooks is None:
        _hooks = HookSystem()
        # 注册默认日志 Hook
        _hooks.register("before_step", _log_before_step)
        _hooks.register("after_step", _log_after_step)
        _hooks.register("on_error", _log_error)
    return _hooks
