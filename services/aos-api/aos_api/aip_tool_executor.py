"""AIP Tool Executor — 工具执行器.

根据 action_type 分发到不同的执行器：
- llm_call → LLM Adapter
- tool_call → 工具调用（Ontology 查询等）
- ontology_query → Ontology 查询
- action_writeback → 写回操作

Phase 1 只实现 llm_call 和基本 tool_call。
"""
from __future__ import annotations

import time
from typing import Any

from aos_api.aip_task_model import ActResult, ActionRequest, Artifact
from aos_api.aip_llm_adapter import get_llm_adapter


class ToolExecutor:
    """工具执行器 — 根据 action_type 分发。

    遵循 Context Engineering 新规则：
    - 工具接口设计 > 规则列表
    - 好的 action_type 枚举值本身就暗示了风险
    """

    def execute(
        self,
        action: ActionRequest,
        think_instruction: str = "",
        context: dict[str, Any] | None = None,
    ) -> ActResult:
        """执行动作，返回 ActResult。"""
        ctx = context or {}
        start = time.time()

        try:
            if action.action_type == "llm_call":
                return self._exec_llm(action, think_instruction, ctx, start)
            elif action.action_type == "tool_call":
                return self._exec_tool(action, think_instruction, ctx, start)
            elif action.action_type == "ontology_query":
                return self._exec_ontology(action, think_instruction, ctx, start)
            elif action.action_type == "action_writeback":
                return self._exec_writeback(action, think_instruction, ctx, start)
            else:
                return self._exec_generic(action, think_instruction, ctx, start)
        except Exception as exc:
            return ActResult(
                output=f"[执行失败: {exc}]",
                success=False,
                error=str(exc),
                elapsed_ms=int((time.time() - start) * 1000),
            )

    # ── llm_call ──

    def _exec_llm(
        self, action: ActionRequest, instruction: str, ctx: dict[str, Any], start: float
    ) -> ActResult:
        """LLM 调用 — 通过 LLM Adapter。"""
        prompt = action.params.get("prompt", instruction)
        system_prompt = action.params.get("system_prompt", "")
        model = action.params.get("model")

        adapter = get_llm_adapter()
        resp = adapter.chat(prompt, system_prompt=system_prompt, model=model)

        elapsed = int((time.time() - start) * 1000)
        artifact = Artifact(
            type="text",
            content=resp["answer"],
            metadata={"provider": resp["provider"], "model": resp["model"]},
        )

        return ActResult(
            output=resp["answer"],
            artifacts=[artifact],
            tokens_used=resp["tokens"],
            elapsed_ms=elapsed,
            success="error" not in resp,
            error=resp.get("error"),
        )

    # ── tool_call ──

    def _exec_tool(
        self, action: ActionRequest, instruction: str, ctx: dict[str, Any], start: float
    ) -> ActResult:
        """工具调用 — Phase 1 暂返回模拟结果。

        Phase 2 将对接 Action Engine 和 Function Engine。
        """
        tool_name = action.params.get("tool", "unknown")
        tool_args = action.params.get("args", {})

        elapsed = int((time.time() - start) * 1000)

        # Phase 1: 返回结构化模拟结果
        return ActResult(
            output=f"[Tool {tool_name} called with {tool_args}]",
            artifacts=[Artifact(type="json", content=f'{{"tool": "{tool_name}", "args": {tool_args}}}')],
            tokens_used=20,
            elapsed_ms=elapsed,
        )

    # ── ontology_query ──

    def _exec_ontology(
        self, action: ActionRequest, instruction: str, ctx: dict[str, Any], start: float
    ) -> ActResult:
        """Ontology 查询 — Phase 1 暂返回模拟结果。

        Phase 2 将对接 Ontology Manager。
        """
        ot_type = action.params.get("object_type", "Customer")
        query = action.params.get("query", "")

        elapsed = int((time.time() - start) * 1000)

        return ActResult(
            output=f"[Ontology query: {ot_type} where {query}]",
            artifacts=[Artifact(type="json", content=f'{{"ot": "{ot_type}", "query": "{query}"}}')],
            tokens_used=15,
            elapsed_ms=elapsed,
        )

    # ── action_writeback ──

    def _exec_writeback(
        self, action: ActionRequest, instruction: str, ctx: dict[str, Any], start: float
    ) -> ActResult:
        """写回操作 — Phase 1 暂返回模拟结果。

        Phase 2 将对接 Action Engine。
        高风险操作，需要权限门控。
        """
        elapsed = int((time.time() - start) * 1000)

        return ActResult(
            output=f"[Writeback: {action.params}]",
            artifacts=[Artifact(type="json", content=str(action.params))],
            tokens_used=10,
            elapsed_ms=elapsed,
        )

    # ── generic ──

    def _exec_generic(
        self, action: ActionRequest, instruction: str, ctx: dict[str, Any], start: float
    ) -> ActResult:
        """通用执行。"""
        elapsed = int((time.time() - start) * 1000)
        return ActResult(
            output=f"[Generic action: {action.action_type}]",
            tokens_used=10,
            elapsed_ms=elapsed,
        )


# ── Singleton ──

_executor: ToolExecutor | None = None


def get_executor() -> ToolExecutor:
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor
