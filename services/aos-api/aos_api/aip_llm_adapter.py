"""AIP LLM adapter with exact AIP-7 runtime resolution and no implicit mock success."""
from __future__ import annotations

from typing import Any

from aos_api.aip_exact_provider_invoker import (
    ExactProviderInvocationError,
    ExactProviderInvoker,
)
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_task_model import ThinkResult
from aos_api.tenant_scope import TenantScope
from aos_api.aip_provider_usage_bridge import AipProviderUsageBridge


class LLMRuntimeBlocked(RuntimeError):
    """The exact model runtime or provider invocation is not safe to execute."""

    def __init__(self, code: str) -> None:
        self.code = str(code)
        super().__init__(self.code)


class LLMAdapter:
    def __init__(self, *, resolver: AipModelRuntimeResolver | None = None, provider_invoker: Any | None = None, usage_bridge: AipProviderUsageBridge | None = None) -> None:
        self._resolver = resolver or AipModelRuntimeResolver()
        self._provider_invoker = provider_invoker or ExactProviderInvoker()
        self._usage_bridge = usage_bridge or AipProviderUsageBridge()

    def chat_exact(
        self,
        scope: TenantScope,
        route_id: str,
        query: str,
        *,
        lineage_id: str,
        system_prompt: str = "",
        data_classification: str | None = None,
    ) -> dict[str, Any]:
        if not lineage_id.strip():
            raise LLMRuntimeBlocked("lineage_id_required")
        if not data_classification:
            raise LLMRuntimeBlocked("data_classification_required")
        resolution = self._resolver.resolve(scope, route_id)
        if resolution.readiness is not ModelRuntimeReadiness.READY:
            blockers = ",".join(resolution.blocker_codes) or "model_runtime_not_ready"
            raise LLMRuntimeBlocked(blockers)
        full_query = f"{system_prompt}\n\n{query}" if system_prompt else query
        try:
            response = self._provider_invoker(
                resolution,
                full_query,
                data_classification,
            )
        except ExactProviderInvocationError as exc:
            raise LLMRuntimeBlocked(exc.code) from None
        answer = response.get("answer")
        if not isinstance(answer, str) or not answer:
            raise LLMRuntimeBlocked("provider_response_answer_missing")
        provider = str(response.get("provider") or "")
        route = str(response.get("route") or "")
        if provider.lower().startswith("mock") or "mock" in route.lower():
            raise LLMRuntimeBlocked("implicit_mock_provider_forbidden")
        tokens = response.get("tokens")
        if not isinstance(tokens, int) or tokens < 0:
            raise LLMRuntimeBlocked("provider_usage_unknown")
        try:
            usage_receipt_ids = self._usage_bridge.record(
                scope, lineage_id, resolution, response
            )
        except Exception as exc:
            raise LLMRuntimeBlocked("provider_usage_authority_write_failed") from exc
        return {
            **response,
            "answer": answer,
            "tokens": tokens,
            "routeRef": resolution.route.model_dump(mode="json", by_alias=True),
            "policyRef": resolution.policy.model_dump(mode="json", by_alias=True),
            "modelRef": resolution.selected_model.model_dump(mode="json", by_alias=True),
            "providerRef": resolution.selected_provider.model_dump(mode="json", by_alias=True),
            "priceSnapshotRef": resolution.selected_price_snapshot.model_dump(mode="json", by_alias=True),
            "usageReceiptIds": usage_receipt_ids,
        }

    def chat(self, query: str, **_: Any) -> dict[str, Any]:
        raise LLMRuntimeBlocked("exact_scope_and_model_route_required")

    def think_exact(
        self,
        scope: TenantScope,
        route_id: str,
        task_type: str,
        step_name: str,
        context: dict[str, Any],
        memory: dict[str, Any] | None = None,
        lineage_id: str = "",
        data_classification: str | None = None,
    ) -> ThinkResult:
        memory_lines: list[str] = []
        for layer, items in (memory or {}).items():
            if items:
                memory_lines.append(f"[{layer}] {items}")
        query = (
            f"任务类型: {task_type}\n当前步骤: {step_name}\n上下文: {context}\n"
            f"相关记忆:\n{chr(10).join(memory_lines)}\n请给出执行指令。"
        )
        response = self.chat_exact(
            scope, route_id, query, lineage_id=lineage_id,
            system_prompt="你是任务执行引擎。只基于给定事实分析当前步骤。",
            data_classification=data_classification,
        )
        return ThinkResult(
            instruction=response["answer"], memory_used=list((memory or {}).keys()),
            confidence=0.8, tokens_used=response["tokens"],
        )


_llm_adapter: LLMAdapter | None = None


def get_llm_adapter() -> LLMAdapter:
    global _llm_adapter
    if _llm_adapter is None:
        _llm_adapter = LLMAdapter()
    return _llm_adapter
