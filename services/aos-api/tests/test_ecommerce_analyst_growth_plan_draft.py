"""Untrusted model output must remain sourced proposals, never authority."""
import json

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_analyst_growth_plan_draft import parse_growth_plan_answer
from aos_api.ecommerce_analyst_authority_contracts import GrowthPlanRevision
from test_ecommerce_analyst_authority_contracts import plan, ref


def answer():
    return dict(objective="核查复购下降", constraints=["先核实样本"],
                expectedEffect="识别可验证的改善机会", confidence=0.6,
                stopConditions=["来源过期即停止"],
                items=[dict(title="检查回购间隔", objective="比较同口径人群",
                            sourceIndices=[0])])


def test_valid_answer_retains_readable_text_and_source_indices():
    parsed = parse_growth_plan_answer(json.dumps(answer()), source_count=1)
    assert parsed.items[0].title == "检查回购间隔"
    assert parsed.items[0].source_indices == [0]


@pytest.mark.parametrize("key,value", [("lifecycle", "approved"), ("budget", "0"),
    ("tenant", {}), ("approvedAt", "2026-09-11"), ("contentHash", "a" * 64)])
def test_model_cannot_supply_authority(key, value):
    payload = answer()
    payload[key] = value
    with pytest.raises(ValueError):
        parse_growth_plan_answer(json.dumps(payload), source_count=1)


@pytest.mark.parametrize("indices", [[], [1], [-1], [0, 0], [True], ["0"]])
def test_sources_must_be_unique_in_range_integer_indices(indices):
    payload = answer()
    payload["items"][0]["sourceIndices"] = indices
    with pytest.raises(ValueError):
        parse_growth_plan_answer(json.dumps(payload), source_count=1)


@pytest.mark.parametrize("field,value", [("objective", "  "), ("constraints", ["\n"]),
    ("confidence", float("nan")), ("confidence", float("inf")),
    ("confidence", "0.6"), ("confidence", True), ("items", []),
    ("stopConditions", [])])
def test_rejects_empty_or_coerced_or_nonfinite_values(field, value):
    payload = answer()
    payload[field] = value
    with pytest.raises(ValueError):
        parse_growth_plan_answer(json.dumps(payload), source_count=1)


def test_rejects_duplicate_keys_and_unbounded_payloads():
    raw = json.dumps(answer())
    for invalid in [raw.replace('"confidence": 0.6', '"confidence": 0.6, "confidence": 0.7'),
                    ' ' * 131073, '[]', '```json\n' + raw + '\n```']:
        with pytest.raises(ValueError):
            parse_growth_plan_answer(invalid, source_count=1)
    with pytest.raises(ValueError):
        parse_growth_plan_answer(raw, source_count=0)


def test_legacy_plan_serialization_has_no_new_empty_fields():
    legacy = GrowthPlanRevision.model_validate(plan(lifecycle="draft"))
    for aliases in [True, False]:
        payload = legacy.model_dump(mode="json", by_alias=aliases)
        assert "generationArtifactRef" not in payload and "generation_artifact_ref" not in payload
        assert "evidenceRefs" not in payload["items"][0]
        assert "evidence_refs" not in payload["items"][0]


def test_new_provenance_roundtrips_and_enforces_reference_types():
    payload = plan(lifecycle="draft")
    payload["generationArtifactRef"] = ref("Artifact", "generated-1")
    payload["items"][0]["evidenceRefs"] = [ref("EvidenceBundleRevision", "bundle-1")]
    parsed = GrowthPlanRevision.model_validate(payload)
    assert parsed.model_dump(mode="json", by_alias=True)["generationArtifactRef"] == payload["generationArtifactRef"]
    assert parsed.items[0].evidence_refs[0].resource_id == "bundle-1"
    payload["items"][0]["evidenceRefs"] *= 2
    with pytest.raises(ValidationError):
        GrowthPlanRevision.model_validate(payload)
    payload["items"][0]["evidenceRefs"] = [ref("Task", "wrong")]
    with pytest.raises(ValidationError):
        GrowthPlanRevision.model_validate(payload)
    payload["items"][0]["evidenceRefs"] = []
    payload["generationArtifactRef"] = ref("GrowthPlanRevision", "wrong")
    with pytest.raises(ValidationError):
        GrowthPlanRevision.model_validate(payload)
