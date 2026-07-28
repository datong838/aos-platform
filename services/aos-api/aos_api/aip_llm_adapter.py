"""AIP LLM Adapter — 封装 llm_gateway，提供 TAOR 循环的 LLM 调用接口.

对接平台已有 llm_gateway.chat()，不重写底层调用。
支持 mock 降级（当 LLM 不可用时返回模拟响应）。
"""
from __future__ import annotations

import time
from typing import Any

from aos_api.aip_task_model import ThinkResult


class LLMAdapter:
    """LLM 适配器 — 封装 llm_gateway.chat()。

    设计原则（来源 Claude Blog Context Engineering 新规则）：
    - 工具描述写清楚，不在 Prompt 里重复
    - System Prompt 极简 — 只给判断边界，不给规则列表
    """

    def chat(
        self,
        query: str,
        *,
        system_prompt: str = "",
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> dict[str, Any]:
        """调用 LLM，返回 {answer, provider, model, tokens}。

        底层走 llm_gateway.chat()，自动处理 mock 降级。
        """
        full_query = f"{system_prompt}\n\n{query}" if system_prompt else query

        try:
            from aos_api import llm_gateway

            resp = llm_gateway.chat(full_query, model=model)
            answer = resp.get("answer", "")
            provider = resp.get("provider", resp.get("model", "unknown"))
            # llm_gateway 不返回 token 数，用字符数估算
            tokens = max(len(answer) // 4, 10)

            return {
                "answer": answer,
                "provider": provider,
                "model": resp.get("model", ""),
                "tokens": tokens,
                "route": resp.get("route", "unknown"),
            }
        except Exception as exc:
            # mock 降级 — 保留向后兼容
            return {
                "answer": f"[LLM fallback: {query[:60]}]",
                "provider": "mock",
                "model": "mock",
                "tokens": 10,
                "route": "mock-fallback",
                "error": str(exc),
            }

    def think(
        self,
        task_type: str,
        step_name: str,
        context: dict[str, Any],
        memory: dict[str, Any] | None = None,
    ) -> ThinkResult:
        """Think 阶段 — 让 LLM 分析当前步骤该怎么执行。

        System Prompt 极简原则：只给角色和判断边界。
        """
        mem_str = ""
        if memory:
            parts = []
            for layer, items in memory.items():
                if items:
                    parts.append(f"[{layer}]")
                    if isinstance(items, list):
                        for item in items[:3]:
                            parts.append(f"  - {item}")
                    else:
                        parts.append(f"  {items}")
            mem_str = "\n".join(parts)

        query = (
            f"任务类型: {task_type}\n"
            f"当前步骤: {step_name}\n"
            f"上下文: {context}\n"
            f"{'相关记忆:' + chr(10) + mem_str if mem_str else ''}\n"
            f"请分析当前步骤应该怎么执行，给出执行指令。"
        )

        system = (
            "你是任务执行引擎。分析当前步骤，给出简洁的执行指令。"
            "用你的判断力决定最佳执行方式。"
        )

        resp = self.chat(query, system_prompt=system, temperature=0.2)
        return ThinkResult(
            instruction=resp["answer"],
            memory_used=list((memory or {}).keys()),
            confidence=0.8 if resp["provider"] != "mock" else 0.3,
            tokens_used=resp["tokens"],
        )


# ── Singleton ──

_llm_adapter: LLMAdapter | None = None


def get_llm_adapter() -> LLMAdapter:
    global _llm_adapter
    if _llm_adapter is None:
        _llm_adapter = LLMAdapter()
    return _llm_adapter
