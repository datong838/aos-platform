from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.aip_d03_pilot import (
    D03_GRAPH_ID,
    D03InputGateError,
    build_d03_eval_suite,
    build_d03_graph_request,
    evaluate_d03_contract,
    validate_d03_inputs,
)
from aos_api.aip_logic_dry_run_models import LogicTokenUsage
from aos_api.aip_logic_graph_models import LogicGraphSnapshot, compute_logic_graph_hash
from aos_api.aip_logic_runtime_adapters import (
    LLMAdapterResult,
    RuntimeAdapterRegistry,
)

MODEL_ID = "agnes-2.5-flash@exact-r1"


def _snapshot() -> LogicGraphSnapshot:
    request = build_d03_graph_request(model_id=MODEL_ID)
    instant = datetime(2026, 8, 17, tzinfo=UTC)
    return LogicGraphSnapshot(
        id=D03_GRAPH_ID,
        name=request.name,
        description=request.description,
        status=request.status,
        schema_version=request.schema_version,
        revision=1,
        graph_hash=compute_logic_graph_hash(request),
        nodes=request.nodes,
        edges=request.edges,
        entry_node_ids=request.entry_node_ids,
        created_at=instant,
        updated_at=instant,
    )


def _registry(calls: list[str]) -> RuntimeAdapterRegistry:
    registry = RuntimeAdapterRegistry()

    def invoke(prompt, context):
        context.checkpoint()
        calls.append(prompt)
        if "__simulate_adapter_error__" in prompt:
            raise RuntimeError("isolated failure")
        return LLMAdapterResult(
            output="isolated draft",
            usage=LogicTokenUsage(
                model=MODEL_ID,
                input_tokens=12,
                output_tokens=4,
                total_tokens=16,
            ),
        )

    registry.register_llm(
        MODEL_ID,
        invoke,
        adapter_name="d03-isolated-contract-eval",
        read_only=True,
        dry_run_safe=True,
    )
    return registry


def test_d03_graph_is_exact_three_node_dag() -> None:
    request = build_d03_graph_request(model_id=MODEL_ID)
    assert request.id == D03_GRAPH_ID
    assert [node.kind for node in request.nodes] == ["input", "use_llm", "transform"]
    assert request.nodes[1].config["model"] == MODEL_ID
    assert request.entry_node_ids == ["input"]


def test_d03_contract_eval_passes_six_cases_without_production_write() -> None:
    calls: list[str] = []
    result = evaluate_d03_contract(
        _snapshot(),
        _registry(calls),
        now=datetime(2026, 8, 17, 12, tzinfo=UTC),
    )
    assert len(result.suite.cases) == 6
    assert result.report.gate_passed is True
    assert result.report.passed == 6
    assert result.report.failed == 0
    assert result.successful_run.production_written is False
    assert len(calls) == 2  # positive plus deliberate isolated adapter-failure case
    assert all("13800138000" not in prompt for prompt in calls)


def test_sensitive_input_is_rejected_before_adapter_boundary() -> None:
    case = next(
        case for case in build_d03_eval_suite().cases if case.id == "d03-sensitive"
    )
    with pytest.raises(D03InputGateError) as exc_info:
        validate_d03_inputs(case.inputs)
    assert exc_info.value.code == "D03_SENSITIVE_INPUT_DENIED"


@pytest.mark.parametrize("model_id", ["", "   "])
def test_d03_graph_requires_exact_model_id(model_id: str) -> None:
    with pytest.raises(ValueError, match="model_id is required"):
        build_d03_graph_request(model_id=model_id)
