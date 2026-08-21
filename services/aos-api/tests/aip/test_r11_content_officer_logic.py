from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.aip_content_officer_logic import (
    CONTENT_OFFICER_LOGIC_IDS,
    ContentOfficerInputGateError,
    build_content_officer_eval_suite,
    build_content_officer_graph_request,
    content_officer_definition,
    evaluate_content_officer_contract,
    validate_content_officer_inputs,
)
from aos_api.aip_logic_dry_run_models import LogicTokenUsage
from aos_api.aip_logic_graph_models import LogicGraphSnapshot, compute_logic_graph_hash
from aos_api.aip_logic_runtime_adapters import (
    LLMAdapterResult,
    LogicAdapterError,
    RuntimeAdapterRegistry,
)


EXPECTED_IDS = ("C01", "C03", "C04", "C05", "C06", "C07", "C08")


def _registry(model_alias: str) -> RuntimeAdapterRegistry:
    registry = RuntimeAdapterRegistry(max_concurrency=1)

    def invoke(prompt, context):
        context.checkpoint()
        if "__simulate_adapter_error__" in prompt:
            raise LogicAdapterError("LLM_ADAPTER_FAILED", "isolated adapter failure")
        return LLMAdapterResult(
            output="isolated content-officer draft; not Provider evidence",
            usage=LogicTokenUsage(
                model=model_alias, input_tokens=14, output_tokens=7, total_tokens=21
            ),
        )

    registry.register_llm(
        model_alias,
        invoke,
        adapter_name="r11-content-officer-isolated-contract-eval",
        read_only=True,
        dry_run_safe=True,
    )
    return registry


def _snapshot(logic_id: str, model_alias: str) -> LogicGraphSnapshot:
    request = build_content_officer_graph_request(logic_id, model_id=model_alias)
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


def test_r11_definitions_are_canonical_and_preserve_c02() -> None:
    assert CONTENT_OFFICER_LOGIC_IDS == EXPECTED_IDS
    assert "C02" not in CONTENT_OFFICER_LOGIC_IDS
    assert [content_officer_definition(item).name for item in EXPECTED_IDS] == [
        "热点竞品与获客机会研究",
        "文案与种草内容生产",
        "短视频策划",
        "多平台适配",
        "事实品牌与合规审核",
        "互动线索识别与交接",
        "内容到成交归因与优化",
    ]
    assert content_officer_definition("C07").capability_keys == (
        "material.collect",
        "copy.generate",
    )


@pytest.mark.parametrize("logic_id", EXPECTED_IDS)
def test_r11_graphs_are_draft_only_and_have_no_tool_action_or_media_nodes(
    logic_id: str,
) -> None:
    request = build_content_officer_graph_request(
        logic_id, model_id="exact-model@1#hash"
    )
    definition = content_officer_definition(logic_id)
    assert request.id == f"ecommerce.logic.{logic_id}"
    assert [node.kind for node in request.nodes] == ["input", "use_llm", "transform"]
    assert request.nodes[-1].config == {
        "expression": f'"{definition.output_contract}"'
    }
    assert all(
        node.kind
        not in {"use_tool", "apply_action", "execute", "render_media", "publish"}
        for node in request.nodes
    )
    assert "禁止" in request.description


@pytest.mark.parametrize("logic_id", EXPECTED_IDS)
def test_r11_contract_eval_passes_all_cases_without_production_write(
    logic_id: str,
) -> None:
    alias = "exact-model@1#hash"
    result = evaluate_content_officer_contract(
        logic_id,
        _snapshot(logic_id, alias),
        _registry(alias),
        now=datetime(2026, 8, 21, tzinfo=UTC),
    )
    assert result.report.gate_passed is True
    assert result.report.passed == result.report.total
    assert result.report.failed == 0
    assert result.successful_run.production_written is False
    assert (
        result.successful_run.node_results[-1].output
        == content_officer_definition(logic_id).output_contract
    )


@pytest.mark.parametrize("logic_id", EXPECTED_IDS)
def test_r11_pii_injection_and_external_actions_are_blocked(logic_id: str) -> None:
    inputs = build_content_officer_eval_suite(logic_id).cases[0].inputs
    with pytest.raises(ContentOfficerInputGateError) as pii:
        validate_content_officer_inputs(
            logic_id, {**inputs, "summary": "联系 13800138000"}
        )
    assert pii.value.code == f"{logic_id}_UNSAFE_INPUT_DENIED"
    with pytest.raises(ContentOfficerInputGateError) as action:
        validate_content_officer_inputs(
            logic_id, {**inputs, "requested_mode": "publish_and_contact"}
        )
    assert action.value.code == f"{logic_id}_EXTERNAL_ACTION_DENIED"


def test_r11_c01_requires_fresh_research_evidence() -> None:
    inputs = build_content_officer_eval_suite("C01").cases[0].inputs
    with pytest.raises(ContentOfficerInputGateError) as stale:
        validate_content_officer_inputs(
            "C01", {**inputs, "source_freshness_state": "stale"}
        )
    assert stale.value.code == "C01_SOURCE_STALE"


def test_r11_c03_requires_fact_pack_and_copyright_clearance() -> None:
    inputs = build_content_officer_eval_suite("C03").cases[0].inputs
    scenarios = [
        ({"fact_pack_ref": ""}, "C03_CONTENT_REFERENCE_REQUIRED"),
        ({"copyright_state": "unknown"}, "C03_COPYRIGHT_NOT_CLEARED"),
    ]
    for update, code in scenarios:
        with pytest.raises(ContentOfficerInputGateError) as exc:
            validate_content_officer_inputs("C03", {**inputs, **update})
        assert exc.value.code == code


def test_r11_c04_requires_licensed_assets_and_denies_rendering() -> None:
    inputs = build_content_officer_eval_suite("C04").cases[0].inputs
    with pytest.raises(ContentOfficerInputGateError) as license_gate:
        validate_content_officer_inputs("C04", {**inputs, "license_refs": []})
    assert license_gate.value.code == "C04_ASSET_LICENSE_REQUIRED"
    with pytest.raises(ContentOfficerInputGateError) as render:
        validate_content_officer_inputs(
            "C04", {**inputs, "external_action_state": "render_video"}
        )
    assert render.value.code == "C04_EXTERNAL_ACTION_DENIED"


def test_r11_c05_requires_fresh_supported_platform_rules() -> None:
    inputs = build_content_officer_eval_suite("C05").cases[0].inputs
    with pytest.raises(ContentOfficerInputGateError) as stale:
        validate_content_officer_inputs(
            "C05", {**inputs, "platform_rule_state": "stale"}
        )
    assert stale.value.code == "C05_PLATFORM_RULE_STALE"


def test_r11_c06_hard_gates_block_fact_or_compliance_failures() -> None:
    inputs = build_content_officer_eval_suite("C06").cases[0].inputs
    for update in ({"factuality_state": "failed"}, {"compliance_state": "failed"}):
        with pytest.raises(ContentOfficerInputGateError) as exc:
            validate_content_officer_inputs("C06", {**inputs, **update})
        assert exc.value.code == "C06_HARD_GATE_FAILED"


def test_r11_c07_minimizes_pii_and_never_auto_contacts() -> None:
    inputs = build_content_officer_eval_suite("C07").cases[0].inputs
    with pytest.raises(ContentOfficerInputGateError) as pii:
        validate_content_officer_inputs(
            "C07", {**inputs, "pii_minimization_state": "raw"}
        )
    assert pii.value.code == "C07_PII_NOT_MINIMIZED"
    with pytest.raises(ContentOfficerInputGateError) as contact:
        validate_content_officer_inputs(
            "C07", {**inputs, "external_action_state": "send_private_message"}
        )
    assert contact.value.code == "C07_EXTERNAL_ACTION_DENIED"


def test_r11_c08_requires_closed_reconciled_sufficient_review() -> None:
    inputs = build_content_officer_eval_suite("C08").cases[0].inputs
    scenarios = [
        ({"attribution_window_state": "open"}, "C08_WINDOW_NOT_CLOSED"),
        ({"reconciliation_cutoff_state": "mismatched"}, "C08_CUTOFF_MISMATCH"),
        ({"sample_size": 12}, "C08_SAMPLE_INSUFFICIENT"),
        ({"memory_promotion_state": "promoted"}, "C08_MEMORY_PROMOTION_DENIED"),
    ]
    for update, code in scenarios:
        with pytest.raises(ContentOfficerInputGateError) as exc:
            validate_content_officer_inputs("C08", {**inputs, **update})
        assert exc.value.code == code


def test_r11_case_inventory_is_logic_specific_and_unique() -> None:
    counts = {
        logic_id: len(build_content_officer_eval_suite(logic_id).cases)
        for logic_id in EXPECTED_IDS
    }
    assert counts == {
        "C01": 7,
        "C03": 8,
        "C04": 8,
        "C05": 7,
        "C06": 8,
        "C07": 8,
        "C08": 10,
    }
    for logic_id in EXPECTED_IDS:
        cases = build_content_officer_eval_suite(logic_id).cases
        assert len({case.id for case in cases}) == len(cases)
