"""Explicit bridge from AIP Logic dry-runs to the exact AIP-7 model runtime."""
from __future__ import annotations

from dataclasses import dataclass

from aos_api.aip_llm_adapter import LLMAdapter
from aos_api.aip_logic_dry_run_models import LogicTokenUsage
from aos_api.aip_logic_runtime_adapters import (
    AdapterExecutionContext,
    LLMAdapterResult,
    RuntimeAdapterRegistry,
)
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class ExactLogicModelBinding:
    """Frozen, tenant-scoped configuration for one bounded Logic invocation."""

    scope: TenantScope
    route_id: str
    lineage_id: str
    data_classification: str
    system_prompt: str = ""

    def __post_init__(self) -> None:
        for name in ("route_id", "lineage_id", "data_classification"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")


def register_exact_logic_model(
    registry: RuntimeAdapterRegistry,
    *,
    model_alias: str,
    binding: ExactLogicModelBinding,
    llm: LLMAdapter | None = None,
) -> None:
    """Register one fail-closed adapter; no implicit route or tenant fallback."""

    alias = model_alias.strip()
    if not alias:
        raise ValueError("model_alias is required")
    adapter = llm or LLMAdapter()

    def invoke(prompt: str, context: AdapterExecutionContext) -> LLMAdapterResult:
        context.checkpoint()
        response = adapter.chat_exact(
            binding.scope,
            binding.route_id,
            prompt,
            lineage_id=binding.lineage_id,
            system_prompt=binding.system_prompt,
            data_classification=binding.data_classification,
        )
        context.checkpoint()
        prompt_tokens = response.get("promptTokens")
        completion_tokens = response.get("completionTokens")
        total_tokens = response.get("tokens")
        if (
            not all(
                isinstance(value, int) and not isinstance(value, bool) and value >= 0
                for value in (prompt_tokens, completion_tokens, total_tokens)
            )
            or total_tokens != prompt_tokens + completion_tokens
        ):
            raise ValueError("exact model usage is incomplete")
        return LLMAdapterResult(
            output=response["answer"],
        usage=LogicTokenUsage(
            model=alias,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            total_tokens=total_tokens,
        ),
        )

    registry.register_llm(
        alias,
        invoke,
        adapter_name=f"aip7-exact:{binding.route_id}",
        read_only=True,
        dry_run_safe=True,
    )
