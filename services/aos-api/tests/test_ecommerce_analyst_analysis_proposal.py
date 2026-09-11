import json

import pytest

from aos_api.ecommerce_analyst_analysis_proposal import parse_portrait_answer, parse_diagnosis_answer


def portrait():
    return dict(summary="回购占比下降，需核对同期口径", assumptions=["同一统计窗口"], uncertainty="尚不能归因为活动变化", metricIndices=[0], sourceIndices=[0])


def diagnosis():
    return dict(conclusion="先核查复购群体变化", attributionPath=["复购占比变化见来源0"], keyAssumptions=[], counterEvidence=[], alternativeExplanations=["可能存在样本构成变化"], uncertainty="相关性不构成因果证明", sourceIndices=[0])


def parse(kind, body, **counts):
    if kind == "portrait": return parse_portrait_answer(body, source_count=counts.get("sources", 1), metric_count=counts.get("metrics", 1))
    return parse_diagnosis_answer(body, source_count=counts.get("sources", 1))


@pytest.mark.parametrize("kind,factory", [("portrait", portrait), ("diagnosis", diagnosis)])
def test_valid_readable_output_preserves_uncertainty(kind, factory):
    proposal = parse(kind, json.dumps(factory(), ensure_ascii=False))
    assert proposal.uncertainty == factory()["uncertainty"]
    assert proposal.source_indices == [0]


@pytest.mark.parametrize("kind,factory", [("portrait", portrait), ("diagnosis", diagnosis)])
@pytest.mark.parametrize("key,value", [("tenant", {}), ("revision", 1), ("contentHash", "a" * 64), ("kind", "causal_claim"), ("methodRef", {}), ("reasoningChain", "private trace"), ("approvedAt", "today")])
def test_model_cannot_inject_authority_or_reasoning_chain(kind, factory, key, value):
    payload = factory()
    payload[key] = value
    with pytest.raises(ValueError): parse(kind, json.dumps(payload))


@pytest.mark.parametrize("kind,factory", [("portrait", portrait), ("diagnosis", diagnosis)])
@pytest.mark.parametrize("indices", [[], [-1], [1], [0, 0], [True], ["0"], [0.0]])
def test_source_indices_must_be_exact_unique_available_integers(kind, factory, indices):
    payload = factory()
    payload["sourceIndices"] = indices
    with pytest.raises(ValueError): parse(kind, json.dumps(payload))


@pytest.mark.parametrize("indices", [[], [1], [0, 0], [True], ["0"]])
def test_portrait_metric_indices_are_bound(indices):
    payload = portrait()
    payload["metricIndices"] = indices
    with pytest.raises(ValueError): parse("portrait", json.dumps(payload))


@pytest.mark.parametrize("kind,factory", [("portrait", portrait), ("diagnosis", diagnosis)])
@pytest.mark.parametrize("count", [0, 101, True, 1.0, "1"])
def test_invalid_source_inventory_is_rejected(kind, factory, count):
    with pytest.raises(ValueError): parse(kind, json.dumps(factory()), sources=count)


@pytest.mark.parametrize("kind,factory", [("portrait", portrait), ("diagnosis", diagnosis)])
@pytest.mark.parametrize("replacement", [" ", 12, None])
def test_blank_or_coerced_uncertainty_is_rejected(kind, factory, replacement):
    payload = factory()
    payload["uncertainty"] = replacement
    with pytest.raises(ValueError): parse(kind, json.dumps(payload))


@pytest.mark.parametrize("kind,factory", [("portrait", portrait), ("diagnosis", diagnosis)])
def test_strict_bounded_json_and_text_lists(kind, factory):
    raw = json.dumps(factory())
    for text in [raw[:-1] + ', "sourceIndices": [0]}', "[" * 2000, "NaN", "[]", "```json\n" + raw + "\n```", " " * 131073]:
        with pytest.raises(ValueError): parse(kind, text)
    payload = factory()
    field = "assumptions" if kind == "portrait" else "attributionPath"
    for value in [[" "], [123], ["x"] * 101]:
        payload[field] = value
        with pytest.raises(ValueError): parse(kind, json.dumps(payload))
