"""Phase 3 · AIP Logic 引擎.

逻辑执行（DAG 分支/汇聚）+ 自动化触发器。
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()


class LogicBlock(BaseModel):
    id: str = Field(default_factory=lambda: "blk-" + uuid.uuid4().hex[:6])
    kind: str = "task"  # task | branch | handoff | llm | tool
    name: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    inputs: list[str] = Field(default_factory=list)  # 依赖的 block ids


class LogicFlow(BaseModel):
    id: str = Field(default_factory=lambda: "aip-logic-" + uuid.uuid4().hex[:8])
    name: str = ""
    description: str = ""
    blocks: list[LogicBlock] = Field(default_factory=list)
    status: str = "draft"  # draft | active | archived
    version: int = 1
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class Automation(BaseModel):
    id: str = Field(default_factory=lambda: "aip-auto-" + uuid.uuid4().hex[:8])
    name: str = ""
    trigger_type: str = "schedule"  # schedule | event | webhook | manual
    trigger_config: dict[str, Any] = Field(default_factory=dict)
    flow_id: str = ""
    status: str = "active"  # active | paused
    last_run: float | None = None
    run_count: int = 0
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class LogicEngine:
    """AIP Logic 引擎。"""

    _instance: "LogicEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "LogicEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._flows: dict[str, LogicFlow] = {}
                    cls._instance._automations: dict[str, Automation] = {}
        return cls._instance

    # ── Flows ──
    def create_flow(self, name: str, blocks: list[dict[str, Any]] | None = None, **kwargs: Any) -> LogicFlow:
        with _LOCK:
            blks = [LogicBlock(**b) for b in (blocks or [])]
            flow = LogicFlow(name=name, blocks=blks, **kwargs)
            self._flows[flow.id] = flow
            return flow

    def get_flow(self, flow_id: str) -> LogicFlow | None:
        return self._flows.get(flow_id)

    def list_flows(self, status: str | None = None) -> list[LogicFlow]:
        items = list(self._flows.values())
        if status:
            items = [f for f in items if f.status == status]
        return items

    def update_flow(self, flow_id: str, **kwargs: Any) -> LogicFlow:
        with _LOCK:
            flow = self._flows.get(flow_id)
            if flow is None:
                raise KeyError(f"Flow {flow_id} not found")
            for k, v in kwargs.items():
                if hasattr(flow, k):
                    setattr(flow, k, v)
            flow.updated_at = time.time()
            return flow

    def delete_flow(self, flow_id: str) -> bool:
        with _LOCK:
            return self._flows.pop(flow_id, None) is not None

    # ── Execute DAG ──
    def execute_flow(self, blocks: list[LogicBlock], context: dict[str, Any] | None = None) -> dict[str, Any]:
        """执行 DAG，支持 branch 和 handoff。

        Harness 模式（AIP_HARNESS_MODE=1）走真实 TAOR 循环；
        默认保留 mock 向后兼容。
        """
        import os

        if os.environ.get("AIP_HARNESS_MODE") == "1":
            return self._execute_harness(blocks, context)
        return self._execute_mock(blocks, context)

    def _execute_mock(self, blocks: list[LogicBlock], context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Mock 执行（向后兼容）。"""
        ctx = dict(context or {})
        results: list[dict[str, Any]] = []
        total_tokens = 0

        for block in blocks:
            result: dict[str, Any] = {"block_id": block.id, "kind": block.kind, "name": block.name}

            if block.kind == "branch":
                # 评估条件选择路径
                condition = block.config.get("condition", "true")
                paths = block.config.get("paths", ["default"])
                chosen = self._eval_branch(condition, ctx, paths)
                result["branch_path"] = chosen
                result["cot"] = [f"Evaluating condition: {condition}", f"Selected path: {chosen}"]
                ctx["__branch_path"] = chosen
                total_tokens += 45

            elif block.kind == "handoff":
                # 汇聚多个分支上下文
                merged = {"context_size": len(ctx), "keys": list(ctx.keys())[:5]}
                result["merged_context"] = merged
                result["cot"] = ["Merging upstream contexts", f"Context keys: {len(ctx)}"]
                ctx["__handoff"] = True
                total_tokens += 30

            elif block.kind == "llm":
                # 模拟 LLM 调用
                prompt = block.config.get("prompt", "")
                result["output"] = f"[LLM response for: {prompt[:50]}]"
                result["cot"] = [f"Constructing prompt", "Model: gpt-4o", "Generating response"]
                result["tokens"] = 120
                total_tokens += 120

            elif block.kind == "tool":
                tool_name = block.config.get("tool", "unknown")
                result["output"] = f"[Tool {tool_name} executed]"
                result["cot"] = [f"Invoking tool: {tool_name}", "Result received"]
                total_tokens += 20

            else:
                # 普通任务块
                result["output"] = f"[Task '{block.name}' completed]"
                result["cot"] = ["Processing task block"]
                total_tokens += 15

            results.append(result)

        return {
            "results": results,
            "total_tokens": total_tokens,
            "elapsed_ms": total_tokens * 3,
            "final_context_keys": list(ctx.keys()),
        }

    def _execute_harness(self, blocks: list[LogicBlock], context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Harness 模式 — 走真实 TAOR 循环。

        将 LogicBlock 转换为 Task + ExecutionPlan，调用 TAORLoopController。
        """
        from aos_api.aip_task_model import (
            ActionRequest, ExecutionPlan, Task, TaskStep,
        )
        from aos_api.aip_taor_loop import get_controller

        # 构建 Task + Plan
        steps: list[TaskStep] = []
        for blk in blocks:
            action_type = "llm_call"
            if blk.kind == "tool":
                action_type = "tool_call"
            elif blk.kind == "branch":
                action_type = "llm_call"  # branch 用 LLM 判断
            elif blk.kind == "task":
                action_type = "tool_call"

            step = TaskStep(
                name=blk.name or blk.id,
                action=ActionRequest(
                    action_type=action_type,
                    params=blk.config,
                ),
                action_config=blk.config,
            )
            steps.append(step)

        plan = ExecutionPlan(steps=steps, status="approved")
        task = Task(
            type="logic_flow",
            title="Harness execution",
            plan=plan,
            context=dict(context or {}),
        )

        controller = get_controller()
        result = controller.run(task, context)

        # 转换为与 mock 兼容的返回格式
        results = []
        for idx, step in enumerate(steps):
            results.append({
                "block_id": blocks[idx].id if idx < len(blocks) else f"step-{idx}",
                "kind": blocks[idx].kind if idx < len(blocks) else "task",
                "name": step.name,
                "output": step.act_output,
                "cot": [step.think_output[:200]] if step.think_output else [],
                "tokens": step.tokens_used,
                "verify_passed": step.verify_passed,
                "verify_issues": step.verify_issues,
            })

        return {
            "results": results,
            "total_tokens": result.total_tokens,
            "elapsed_ms": result.total_elapsed_ms,
            "final_context_keys": list(task.context.keys()),
            "task_id": task.id,
            "task_status": result.status,
            "steps_completed": result.steps_completed,
            "steps_failed": result.steps_failed,
            "mode": "harness",
        }

    def _eval_branch(self, condition: str, ctx: dict[str, Any], paths: list[str]) -> str:
        """简单条件评估。"""
        if "success" in condition.lower() or "true" in condition.lower():
            return paths[0] if paths else "default"
        if len(paths) > 1:
            return paths[1]
        return paths[0] if paths else "default"

    # ── Automations ──
    def create_automation(self, name: str, trigger_type: str = "schedule", **kwargs: Any) -> Automation:
        with _LOCK:
            auto = Automation(name=name, trigger_type=trigger_type, **kwargs)
            self._automations[auto.id] = auto
            return auto

    def get_automation(self, auto_id: str) -> Automation | None:
        return self._automations.get(auto_id)

    def list_automations(self, status: str | None = None, trigger_type: str | None = None) -> list[Automation]:
        items = list(self._automations.values())
        if status:
            items = [a for a in items if a.status == status]
        if trigger_type:
            items = [a for a in items if a.trigger_type == trigger_type]
        return items

    def update_automation(self, auto_id: str, **kwargs: Any) -> Automation:
        with _LOCK:
            auto = self._automations.get(auto_id)
            if auto is None:
                raise KeyError(f"Automation {auto_id} not found")
            for k, v in kwargs.items():
                if hasattr(auto, k):
                    setattr(auto, k, v)
            auto.updated_at = time.time()
            return auto

    def delete_automation(self, auto_id: str) -> bool:
        with _LOCK:
            return self._automations.pop(auto_id, None) is not None

    def reset(self) -> None:
        with _LOCK:
            self._flows.clear()
            self._automations.clear()


def get_engine() -> LogicEngine:
    return LogicEngine()
