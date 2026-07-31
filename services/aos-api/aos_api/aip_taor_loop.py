"""AIP TAOR Loop — Think→Act→Verify→Observe 循环控制器.

Phase 1 核心：将 aip_logic_engine 的 mock execute_flow 替换为真实 TAOR 循环。
来源：方案文档 01-Plan-Mode与TAOR循环设计.md §六 Verification Loops 升级。
"""
from __future__ import annotations

import time
from typing import Any

from aos_api.aip_task_model import (
    ActResult,
    Artifact,
    Checkpoint,
    Task,
    TaskResult,
    TaskStep,
    ThinkResult,
    VerifyResult,
)
from aos_api.aip_hooks import get_hooks
from aos_api.aip_llm_adapter import get_llm_adapter
from aos_api.aip_tool_executor import get_executor
from aos_api.aip_verify_skills import get_verify_registry
from aos_api.public_contracts import TaskStatus


class TAORLoopController:
    """TAOR 循环控制器 — Think → Act → Verify → Observe。

    设计原则：
    - Plan Mode: 执行前生成计划，用户可审批
    - Verification Loop: 每步执行后验证，失败自动修复
    - Progressive Disclosure: 按步骤类型按需加载记忆
    """

    def __init__(self) -> None:
        self._llm = get_llm_adapter()
        self._executor = get_executor()
        self._verify = get_verify_registry()
        self._hooks = get_hooks()

    # ── 主循环 ──

    def run(self, task: Task, context: dict[str, Any] | None = None) -> TaskResult:
        """执行任务的 TAOR 循环。

        前提：task.plan 已审批通过（status="approved"）。
        """
        if not task.plan or task.plan.status != "approved":
            return TaskResult(
                task_id=task.id,
                status="failed",
                error="计划未审批或不存在",
            )

        ctx = dict(context or {})
        ctx.update(task.context)
        task.transition(TaskStatus.EXECUTING)

        steps_completed = 0
        steps_failed = 0
        all_artifacts: list[Artifact] = []

        for idx, step in enumerate(task.plan.steps):
            step.status = "running"

            # ── before_step hook ──
            self._hooks.trigger("before_step", task=task, step=step)

            # TAOR 循环（含重试）
            result = self._taor_cycle(task, step, ctx, idx)

            if result.is_fatal:
                step.status = "failed"
                steps_failed += 1
                self._hooks.trigger("on_error", task=task, step=step, error=result.verify_issues[-1] if result.verify_issues else "fatal error")
                task.transition(TaskStatus.FAILED)
                task.error = result.verify_issues[-1] if result.verify_issues else "fatal error"
                break
            elif result.success:
                step.status = "completed"
                steps_completed += 1
                all_artifacts.extend(step.artifacts)

                # ── Checkpoint ──
                ckpt = Checkpoint(
                    task_id=task.id,
                    step_index=idx,
                    step_name=step.name,
                    state="completed",
                    context_snapshot=dict(ctx),
                    artifacts=step.artifacts,
                )
                task.checkpoints.append(ckpt)
                self._hooks.trigger("on_checkpoint", task=task, step=step, checkpoint=ckpt)
            else:
                step.status = "failed"
                steps_failed += 1
                self._hooks.trigger("on_error", task=task, step=step, error="max retries exceeded")

            # ── after_step hook ──
            self._hooks.trigger("after_step", task=task, step=step)

            task.total_tokens += step.tokens_used
            task.total_elapsed_ms += step.elapsed_ms
            task.touch()

        # ── 完成 ──
        if task.status != TaskStatus.FAILED:
            task.transition(TaskStatus.COMPLETED)
        task.artifacts.extend(all_artifacts)
        task.touch()

        return TaskResult(
            task_id=task.id,
            status=task.status,
            artifacts=all_artifacts,
            total_tokens=task.total_tokens,
            total_elapsed_ms=task.total_elapsed_ms,
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            error=task.error,
        )

    # ── 单步 TAOR 循环 ──

    def _taor_cycle(
        self, task: Task, step: TaskStep, ctx: dict[str, Any], idx: int
    ) -> _CycleResult:
        """单步 TAOR 循环 — 含重试逻辑。"""
        max_retries = step.max_retries

        for attempt in range(max_retries + 1):
            step.retry_count = attempt

            # ── Think ──
            think = self._think(task, step, ctx)

            # ── Act ──
            act = self._act(task, step, think, ctx)

            # ── Verify ──
            verify = self._verify_step(task, step, act, ctx)

            if verify.passed:
                step.think_output = think.instruction
                step.act_output = act.output
                step.verify_passed = True
                step.tokens_used = think.tokens_used + act.tokens_used
                step.elapsed_ms = act.elapsed_ms
                step.artifacts = act.artifacts
                return _CycleResult(success=True)

            # 验证失败
            step.verify_issues = verify.issues

            if verify.is_fatal:
                return _CycleResult(
                    success=False, is_fatal=True, verify_issues=verify.issues
                )

            if attempt < max_retries and verify.should_retry:
                # 重试
                continue

            # 重试耗尽
            return _CycleResult(
                success=False, is_fatal=False, verify_issues=verify.issues
            )

        return _CycleResult(success=False, verify_issues=["max retries exceeded"])

    # ── Think ──

    def _think(self, task: Task, step: TaskStep, ctx: dict[str, Any]) -> ThinkResult:
        """Think 阶段 — LLM 分析当前步骤该怎么执行。

        Progressive Disclosure：按步骤类型决定加载哪些记忆。
        """
        memory: dict[str, Any] = {}

        # 始终加载 Working Memory（当前任务上下文）
        memory["working"] = {
            "task_type": task.type,
            "step_name": step.name,
            "context_keys": list(ctx.keys())[:10],
        }

        # LLM 调用和分支判断需要 Semantic Memory
        if step.action.action_type in ("llm_call", "branch"):
            memory["semantic"] = []  # Phase 2 接入 RAG

        # LLM 调用和写回操作需要 Episodic Memory
        if step.action.action_type in ("llm_call", "action_writeback"):
            memory["episodic"] = []  # Phase 2 接入记忆检索

        return self._llm.think(
            task_type=task.type,
            step_name=step.name,
            context=ctx,
            memory=memory,
        )

    # ── Act ──

    def _act(
        self, task: Task, step: TaskStep, think: ThinkResult, ctx: dict[str, Any]
    ) -> ActResult:
        """Act 阶段 — 执行具体动作。"""
        return self._executor.execute(
            action=step.action,
            think_instruction=think.instruction,
            context=ctx,
        )

    # ── Verify ──

    def _verify_step(
        self, task: Task, step: TaskStep, act: ActResult, ctx: dict[str, Any]
    ) -> VerifyResult:
        """Verify 阶段 — 执行验证技能链。

        来源：Claude Blog — Verification Loops。
        替代原方案中的 Reflection 自审。
        """
        return self._verify.verify(
            action_type=step.action.action_type,
            act_result=act,
            context=ctx,
        )

    # ── Observe ──

    def _observe(
        self, task: Task, step: TaskStep, act: ActResult, verify: VerifyResult
    ) -> None:
        """Observe 阶段 — 更新任务上下文。"""
        # 将产出写入上下文
        if act.artifacts:
            for art in act.artifacts:
                task.context[f"step_{step.id}_artifact"] = art.content

        # 记录验证结果
        if verify.issues:
            task.context[f"step_{step.id}_issues"] = verify.issues


class _CycleResult:
    """单步循环结果。"""

    def __init__(
        self,
        success: bool = False,
        is_fatal: bool = False,
        verify_issues: list[str] | None = None,
    ) -> None:
        self.success = success
        self.is_fatal = is_fatal
        self.verify_issues = verify_issues or []


# ── Singleton ──

_controller: TAORLoopController | None = None


def get_controller() -> TAORLoopController:
    global _controller
    if _controller is None:
        _controller = TAORLoopController()
    return _controller
