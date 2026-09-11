"""AIP TAOR Loop — Think→Act→Verify→Observe 循环控制器.

Phase 1 核心：将 aip_logic_engine 的 mock execute_flow 替换为真实 TAOR 循环。
来源：方案文档 01-Plan-Mode与TAOR循环设计.md §六 Verification Loops 升级。
"""
from __future__ import annotations

import time
from copy import deepcopy
from typing import Any, Protocol

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
from aos_api.aip_task_models import RunControlResult, TaskTimeline
from aos_api.aip_task_store import (
    AipTaskStore,
    AipTaskStoreError,
    AipTaskTransitionBlocked,
    _canonical_hash,
)
from aos_api.tenant_scope import TenantScope
from aos_api.aip_taor_lease_adapter import LeaseMaintainedTaorAdapter


class CanonicalTaorAdapter(Protocol):
    """Capability adapter boundary; the runtime intentionally has no default/mock adapter."""

    def think(self, step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]: ...

    def act(self, step: dict[str, Any], thought: dict[str, Any]) -> dict[str, Any]: ...

    def verify(self, step: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]: ...

    def observe(
        self,
        step: dict[str, Any],
        action: dict[str, Any],
        verification: dict[str, Any],
    ) -> dict[str, Any]: ...


class CanonicalTaorRunner:
    """PostgreSQL-backed TAOR runner for an exact approved PlanRevision."""

    def __init__(self, store: AipTaskStore | None = None) -> None:
        self.store = store or AipTaskStore()

    def run(
        self,
        scope: TenantScope,
        run_id: str,
        *,
        actor: str,
        worker_id: str,
        adapter: CanonicalTaorAdapter,
        lease_seconds: int = 30,
        renew_step_lease: bool = False,
        stop_after_step: str | None = None,
    ) -> RunControlResult:
        if type(renew_step_lease) is not bool or (
            renew_step_lease and (type(lease_seconds) is not int or lease_seconds < 1)
        ):
            raise ValueError("lease renewal requires an explicit boolean and positive integer duration")
        timeline = self.store.timeline(scope, run_id)
        self._validate_bindings(timeline.model_dump(mode="json", by_alias=True))
        keys = [step.step_key for step in timeline.plan.steps]
        if stop_after_step is not None and (
            not isinstance(stop_after_step, str) or not stop_after_step.strip()
            or keys.count(stop_after_step) != 1
        ):
            raise ValueError("stage boundary must identify one exact plan step")
        if timeline.run.status.value == "queued":
            started = self.store.start_run(
                scope,
                run_id,
                expected_run_version=timeline.run.version,
                expected_task_version=timeline.task.version,
                actor=actor,
                idempotency_key=f"taor-start:{run_id}",
                reason="canonical TAOR worker start",
            )
            timeline = self.store.timeline(scope, started.run.id)
        elif timeline.run.status.value != "running" or timeline.task.status is not TaskStatus.EXECUTING:
            raise AipTaskTransitionBlocked("run must be queued or actively executing")

        completed = self._completed_observations(scope, timeline)
        if stop_after_step in completed:
            prefix = keys[:keys.index(stop_after_step) + 1]
            if not all(key in completed for key in prefix):
                raise AipTaskTransitionBlocked("completed boundary has unfinished predecessors")
            if stop_after_step != keys[-1]:
                return RunControlResult(task=timeline.task, run=timeline.run)
        context: dict[str, Any] = {
            "taskRef": timeline.task.id,
            "taskGoal": dict(timeline.task.goal),
            "runRef": timeline.run.id,
            "planRevisionRef": timeline.plan.id,
            "planContentHash": timeline.plan.content_hash,
            "logicGraphRef": timeline.run.logic_graph_id,
            "logicRevision": timeline.run.logic_revision,
        }
        for plan_step in timeline.plan.steps:
            if plan_step.step_key in completed:
                context[f"step:{plan_step.step_key}"] = completed[plan_step.step_key]
                continue
            step = plan_step.model_dump(mode="json", by_alias=True)
            lease = self.store.claim_step(
                scope,
                run_id,
                plan_step.step_key,
                worker_id,
                lease_seconds=lease_seconds,
            )
            step_adapter = adapter
            if renew_step_lease:
                step_adapter = LeaseMaintainedTaorAdapter(
                    adapter,
                    lambda: self.store.heartbeat_step(
                        scope, lease.step_run_id, worker_id, lease.fence, lease_seconds=lease_seconds
                    ),
                    lease_seconds,
                )
            try:
                thought = step_adapter.think(step, dict(context))
                self.store.record_step_phase(
                    scope, lease.step_run_id, worker_id, lease.fence, actor, "think", thought
                )
                action = step_adapter.act(step, thought)
                self.store.record_step_phase(
                    scope, lease.step_run_id, worker_id, lease.fence, actor, "act", action
                )
                verification = step_adapter.verify(step, action)
                if verification.get("passed") is not True:
                    error = {
                        "code": "AIP_VERIFY_FAILED",
                        "message": str(verification.get("message") or "step verification failed"),
                        "verification": verification,
                    }
                    self.store.record_step_phase(
                        scope, lease.step_run_id, worker_id, lease.fence, actor, "verify", verification
                    )
                    return self.store.fail_step(
                        scope, lease.step_run_id, worker_id, lease.fence, actor, error
                    )
                self.store.record_step_phase(
                    scope, lease.step_run_id, worker_id, lease.fence, actor, "verify", verification
                )
                observation = step_adapter.observe(step, action, verification)
                artifact_ids = self._persist_artifacts(
                    scope, run_id, actor, observation.get("artifacts", [])
                )
                persisted_observation = {**observation, "artifactRefs": artifact_ids}
                self.store.record_step_phase(
                    scope,
                    lease.step_run_id,
                    worker_id,
                    lease.fence,
                    actor,
                    "observe",
                    persisted_observation,
                )
                self.store.complete_step(
                    scope, lease.step_run_id, worker_id, lease.fence, actor
                )
                paused = self.store.timeline(scope, run_id)
                if paused.run.status.value == "paused":
                    return RunControlResult(task=paused.task, run=paused.run)
                if plan_step.step_key == stop_after_step and stop_after_step != keys[-1]:
                    return RunControlResult(task=paused.task, run=paused.run)
                context[f"step:{plan_step.step_key}"] = persisted_observation
            except AipTaskStoreError:
                raise
            except Exception as exc:
                return self.store.fail_step(
                    scope,
                    lease.step_run_id,
                    worker_id,
                    lease.fence,
                    actor,
                    {
                        "code": "AIP_ADAPTER_FAILED",
                        "message": str(exc),
                        "retryable": False,
                    },
                )
        return self.store.complete_run(scope, run_id)

    @staticmethod
    def _completed_observations(
        scope: TenantScope, timeline: TaskTimeline
    ) -> dict[str, dict[str, Any]]:
        """Restore historical outputs, not current business authorization."""
        plan_keys = {step.step_key for step in timeline.plan.steps}
        result: dict[str, dict[str, Any]] = {}
        evidence_by_id: dict[str, list[dict[str, Any]]] = {}
        for evidence in timeline.evidence:
            evidence_by_id.setdefault(evidence.get("evidence_id"), []).append(evidence)
        for row in timeline.steps:
            if row.get("status") != "succeeded":
                continue
            key = row.get("step_key")
            ref = row.get("observe_ref")
            if (
                key not in plan_keys or key in result
                or (row.get("org_id"), row.get("project_id")) != scope.key
                or row.get("run_id") != timeline.run.id
                or not isinstance(row.get("step_run_id"), str) or not row["step_run_id"]
                or not isinstance(ref, dict)
                or not isinstance(ref.get("evidenceId"), str) or not ref["evidenceId"]
            ):
                raise AipTaskTransitionBlocked("completed step has invalid observation lineage")
            matches = evidence_by_id.get(ref["evidenceId"], [])
            if len(matches) != 1:
                raise AipTaskTransitionBlocked("completed observation evidence is missing or ambiguous")
            evidence = matches[0]
            payload = evidence.get("payload")
            if (
                (evidence.get("org_id"), evidence.get("project_id")) != scope.key
                or evidence.get("run_id") != timeline.run.id
                or evidence.get("evidence_type") != "taor.observe"
                or not isinstance(payload, dict)
                or payload.get("stepRunId") != row["step_run_id"]
                or payload.get("stepKey") != key
                or not isinstance(payload.get("payload"), dict)
                or evidence.get("content_hash") != _canonical_hash(payload)
            ):
                raise AipTaskTransitionBlocked("completed observation evidence failed integrity checks")
            result[key] = deepcopy(payload["payload"])
        return result

    def _persist_artifacts(
        self,
        scope: TenantScope,
        run_id: str,
        actor: str,
        artifacts: Any,
    ) -> list[str]:
        if not isinstance(artifacts, list):
            raise ValueError("observe artifacts must be a list")
        result: list[str] = []
        for artifact in artifacts:
            if not isinstance(artifact, dict) or not str(artifact.get("type", "")).strip():
                raise ValueError("each observed artifact must contain a type")
            result.append(
                self.store.record_artifact(
                    scope,
                    run_id,
                    actor,
                    str(artifact["type"]),
                    artifact,
                )
            )
        return result

    @staticmethod
    def _validate_bindings(timeline: dict[str, Any]) -> None:
        run = timeline["run"]
        if bool(run.get("logicGraphId")) != bool(run.get("logicRevision")):
            raise AipTaskTransitionBlocked(
                "logicGraphId and logicRevision must be bound together"
            )
        for step in timeline["plan"]["steps"]:
            capability = step.get("capabilityRef")
            if capability is not None and not capability.get("revision"):
                raise AipTaskTransitionBlocked(
                    "executable capabilityRef must bind an exact revision"
                )


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
    raise RuntimeError(
        "legacy in-memory TAOR controller is disabled; use CanonicalTaorRunner"
    )
