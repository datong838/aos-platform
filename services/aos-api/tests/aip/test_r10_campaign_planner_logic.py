from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.aip_campaign_planner_logic import (
    CAMPAIGN_PLANNER_LOGIC_IDS,
    CampaignPlannerInputGateError,
    build_campaign_planner_eval_suite,
    build_campaign_planner_graph_request,
    campaign_planner_definition,
    evaluate_campaign_planner_contract,
    validate_campaign_planner_inputs,
)
from aos_api.aip_logic_dry_run_models import LogicTokenUsage
from aos_api.aip_logic_graph_models import LogicGraphSnapshot, compute_logic_graph_hash
from aos_api.aip_logic_runtime_adapters import (
    LLMAdapterResult,
    LogicAdapterError,
    RuntimeAdapterRegistry,
)


EXPECTED_IDS = ("A01", "A03", "A04", "A05", "A06")


def _registry(model_alias: str) -> RuntimeAdapterRegistry:
    registry = RuntimeAdapterRegistry(max_concurrency=1)

    def invoke(prompt, context):
        context.checkpoint()
        if "__simulate_adapter_error__" in prompt:
            raise LogicAdapterError("LLM_ADAPTER_FAILED", "isolated adapter failure")
        return LLMAdapterResult(
            output="isolated campaign-planner draft; not Provider evidence",
            usage=LogicTokenUsage(
                model=model_alias, input_tokens=14, output_tokens=7, total_tokens=21
            ),
        )

    registry.register_llm(
        model_alias,
        invoke,
        adapter_name="r10-campaign-planner-isolated-contract-eval",
        read_only=True,
        dry_run_safe=True,
    )
    return registry


def _snapshot(logic_id: str, model_alias: str) -> LogicGraphSnapshot:
    request = build_campaign_planner_graph_request(logic_id, model_id=model_alias)
    now = datetime(2026, 8, 21, tzinfo=UTC)
    return LogicGraphSnapshot(
        id=request.id or "",
        name=request.name,
        description=request.description,
        status=request.status,
        schema_version=request.schema_version,
        revision=1,
        graph_hash=compute_logic_graph_hash(request),
        nodes=request.nodes,
        edges=request.edges,
        entry_node_ids=request.entry_node_ids,
        created_at=now,
        updated_at=now,
    )


def test_r10_definitions_are_exact_and_preserve_a02() -> None:
    assert CAMPAIGN_PLANNER_LOGIC_IDS == EXPECTED_IDS
    assert "A02" not in CAMPAIGN_PLANNER_LOGIC_IDS
    assert len({campaign_planner_definition(item).graph_id for item in EXPECTED_IDS}) == 5
    assert len({campaign_planner_definition(item).output_contract for item in EXPECTED_IDS}) == 5
    assert campaign_planner_definition("A01").capability_keys == (
        "material.collect",
        "performance.review",
    )
    assert campaign_planner_definition("A03").capability_keys == (
        "strategy.plan",
        "performance.review",
    )


@pytest.mark.parametrize("logic_id", EXPECTED_IDS)
def test_r10_graphs_are_draft_only_and_have_no_tool_or_action_nodes(logic_id: str) -> None:
    request = build_campaign_planner_graph_request(logic_id, model_id="exact-model@1#hash")
    definition = campaign_planner_definition(logic_id)
    assert request.id == f"ecommerce.logic.{logic_id}"
    assert [node.kind for node in request.nodes] == ["input", "use_llm", "transform"]
    assert request.nodes[-1].config == {"expression": f'"{definition.output_contract}"'}
    assert all(node.kind not in {"use_tool", "apply_action", "execute"} for node in request.nodes)
    assert "禁止" in request.description


@pytest.mark.parametrize("logic_id", EXPECTED_IDS)
def test_r10_contract_eval_passes_all_cases_without_production_write(logic_id: str) -> None:
    alias = "exact-model@1#hash"
    result = evaluate_campaign_planner_contract(
        logic_id,
        _snapshot(logic_id, alias),
        _registry(alias),
        now=datetime(2026, 8, 21, tzinfo=UTC),
    )
    assert result.report.gate_passed is True
    assert result.report.passed == result.report.total
    assert result.report.failed == 0
    assert result.successful_run.production_written is False
    assert result.successful_run.node_results[-1].output == campaign_planner_definition(logic_id).output_contract


@pytest.mark.parametrize("logic_id", EXPECTED_IDS)
def test_r10_pii_injection_and_external_actions_are_blocked(logic_id: str) -> None:
    inputs = build_campaign_planner_eval_suite(logic_id).cases[0].inputs
    with pytest.raises(CampaignPlannerInputGateError) as pii:
        validate_campaign_planner_inputs(logic_id, {**inputs, "summary": "联系 13800138000"})
    assert pii.value.code == f"{logic_id}_UNSAFE_INPUT_DENIED"
    with pytest.raises(CampaignPlannerInputGateError) as action:
        validate_campaign_planner_inputs(
            logic_id, {**inputs, "requested_mode": "launch_campaign_and_change_price"}
        )
    assert action.value.code == f"{logic_id}_EXTERNAL_ACTION_DENIED"


def test_r10_a01_requires_baseline_and_fresh_metric_cutoff() -> None:
    inputs = build_campaign_planner_eval_suite("A01").cases[0].inputs
    with pytest.raises(CampaignPlannerInputGateError) as baseline:
        validate_campaign_planner_inputs("A01", {**inputs, "baseline_ref": ""})
    assert baseline.value.code == "A01_BASELINE_REQUIRED"
    with pytest.raises(CampaignPlannerInputGateError) as stale:
        validate_campaign_planner_inputs("A01", {**inputs, "metric_freshness_state": "stale"})
    assert stale.value.code == "A01_METRIC_STALE"


def test_r10_a03_enforces_budget_margin_inventory_and_fulfillment() -> None:
    inputs = build_campaign_planner_eval_suite("A03").cases[0].inputs
    scenarios = [
        ({"budget_requested": 12000.0}, "A03_BUDGET_EXCEEDED"),
        ({"projected_margin_rate": -0.01}, "A03_MARGIN_FLOOR_BREACHED"),
        ({"inventory_freshness_state": "stale"}, "A03_BUSINESS_FACT_STALE"),
        ({"fulfillment_readiness_state": "blocked"}, "A03_FULFILLMENT_NOT_READY"),
    ]
    for update, code in scenarios:
        with pytest.raises(CampaignPlannerInputGateError) as exc:
            validate_campaign_planner_inputs("A03", {**inputs, **update})
        assert exc.value.code == code


def test_r10_a04_requires_frozen_assignment_and_ready_dependencies() -> None:
    inputs = build_campaign_planner_eval_suite("A04").cases[0].inputs
    with pytest.raises(CampaignPlannerInputGateError) as assignment:
        validate_campaign_planner_inputs("A04", {**inputs, "assignment_state": "draft"})
    assert assignment.value.code == "A04_ASSIGNMENT_NOT_FROZEN"
    with pytest.raises(CampaignPlannerInputGateError) as capacity:
        validate_campaign_planner_inputs("A04", {**inputs, "capacity_state": "blocked"})
    assert capacity.value.code == "A04_ORCHESTRATION_NOT_READY"


def test_r10_a05_stop_loss_trigger_requires_pause_and_human_handoff() -> None:
    inputs = build_campaign_planner_eval_suite("A05").cases[0].inputs
    with pytest.raises(CampaignPlannerInputGateError) as exc:
        validate_campaign_planner_inputs(
            "A05",
            {
                **inputs,
                "stop_loss_state": "triggered",
                "campaign_runtime_state": "running",
                "human_required": False,
            },
        )
    assert exc.value.code == "A05_STOP_LOSS_HANDOFF_REQUIRED"


def test_r10_a06_requires_completed_reconciled_sufficient_review() -> None:
    inputs = build_campaign_planner_eval_suite("A06").cases[0].inputs
    scenarios = [
        ({"campaign_completion_state": "running"}, "A06_CAMPAIGN_NOT_COMPLETED"),
        ({"reconciliation_cutoff_state": "mismatched"}, "A06_CUTOFF_MISMATCH"),
        ({"sample_size": 12}, "A06_SAMPLE_INSUFFICIENT"),
        ({"memory_promotion_state": "promoted"}, "A06_MEMORY_PROMOTION_DENIED"),
    ]
    for update, code in scenarios:
        with pytest.raises(CampaignPlannerInputGateError) as exc:
            validate_campaign_planner_inputs("A06", {**inputs, **update})
        assert exc.value.code == code


def test_r10_case_inventory_is_logic_specific_and_unique() -> None:
    counts = {
        logic_id: len(build_campaign_planner_eval_suite(logic_id).cases)
        for logic_id in EXPECTED_IDS
    }
    assert counts == {"A01": 8, "A03": 10, "A04": 8, "A05": 8, "A06": 10}
    for logic_id in EXPECTED_IDS:
        cases = build_campaign_planner_eval_suite(logic_id).cases
        assert len({case.id for case in cases}) == len(cases)
