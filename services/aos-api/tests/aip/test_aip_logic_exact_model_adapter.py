from __future__ import annotations

import pytest

from aos_api.aip_logic_exact_model_adapter import (
    ExactLogicModelBinding,
    register_exact_logic_model,
)
from aos_api.aip_logic_runtime_adapters import LogicAdapterError, RuntimeAdapterRegistry
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


class _ExactLlm:
    def __init__(self, response: dict | None = None) -> None:
        self.response = response or {
            "answer": '{"summary":"增长建议草案"}',
            "tokens": 12,
            "promptTokens": 7,
            "completionTokens": 5,
        }
        self.calls: list[tuple] = []

    def chat_exact(self, scope, route_id, prompt, **kwargs):
        self.calls.append((scope, route_id, prompt, kwargs))
        return self.response


def _binding() -> ExactLogicModelBinding:
    return ExactLogicModelBinding(
        scope=SCOPE,
        route_id="route-qyh-text-dev",
        lineage_id="lineage-r2-d03-eval",
        data_classification="approved_internal_knowledge",
        system_prompt="只基于给定事实生成草案。",
    )


def test_exact_logic_bridge_preserves_scope_route_lineage_and_usage() -> None:
    registry = RuntimeAdapterRegistry()
    llm = _ExactLlm()
    register_exact_logic_model(
        registry,
        model_alias="r2-d03-exact",
        binding=_binding(),
        llm=llm,
    )

    adapter_name, result = registry.invoke_llm(
        "r2-d03-exact", "公开商品增长摘要", timeout_seconds=1
    )

    assert adapter_name == "aip7-exact:route-qyh-text-dev"
    assert result.output == '{"summary":"增长建议草案"}'
    assert result.usage.model == "r2-d03-exact"
    assert result.usage.total_tokens == 12
    assert llm.calls == [
        (
            SCOPE,
            "route-qyh-text-dev",
            "公开商品增长摘要",
            {
                "lineage_id": "lineage-r2-d03-eval",
                "system_prompt": "只基于给定事实生成草案。",
                "data_classification": "approved_internal_knowledge",
            },
        )
    ]


def test_exact_logic_bridge_fails_closed_on_incomplete_usage() -> None:
    registry = RuntimeAdapterRegistry()
    register_exact_logic_model(
        registry,
        model_alias="r2-d03-exact",
        binding=_binding(),
        llm=_ExactLlm({"answer": "草案", "tokens": 12}),
    )

    with pytest.raises(LogicAdapterError, match="dry-run LLM adapter failed"):
        registry.invoke_llm("r2-d03-exact", "公开摘要", timeout_seconds=1)


@pytest.mark.parametrize(
    "field,value",
    [("route_id", ""), ("lineage_id", " "), ("data_classification", "")],
)
def test_exact_logic_binding_rejects_implicit_defaults(field: str, value: str) -> None:
    values = {
        "scope": SCOPE,
        "route_id": "route-qyh-text-dev",
        "lineage_id": "lineage-r2-d03-eval",
        "data_classification": "approved_internal_knowledge",
    }
    values[field] = value
    with pytest.raises(ValueError, match=f"{field} is required"):
        ExactLogicModelBinding(**values)
