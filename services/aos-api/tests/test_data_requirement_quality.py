"""Internal measurement checks: never a caller-provided fulfillment authority."""
from datetime import timedelta

import pytest
from pydantic import ValidationError

from aos_api.data_requirement_quality import QualityMeasurement, ResolvedPopulationPolicy, evaluate_quality
from aos_api.data_requirement_store import canonical_revision_content_hash
from tests.test_data_requirement_store import NOW, SCOPE, ref, requirement


def measurement(**changes):
    req = requirement()
    raw = dict(
        tenant=req.tenant.model_dump(), requirement_ref=ref("DataRequirementRevision", req.requirement_id),
        channel_ref=req.channel_ref.model_dump(), entity_ref=req.entity_ref.model_dump(),
        time_window=req.time_window.model_dump(), cutoff_at=req.cutoff_at, grain=req.grain,
        source_refs=[ref("DataProductRevision", "source")],
        hydration_ref=ref("SemanticHydrationReceipt", "hydration"),
        mapping_refs=[ref("SourceMappingRevision", "mapping")],
        query_version=dict(identity="order-product-quality", revision="1", content_hash="sha256:" + "c" * 64),
        rule_version=dict(identity="required-fields", revision="1", content_hash="sha256:" + "d" * 64),
        population_policy_version=dict(identity="distinct-days", revision="1", content_hash="sha256:" + "e" * 64),
        population_unit="day", distinct_population_count=20,
        source_observed_at=NOW, measured_at=NOW,
        facts=[dict(fact_id=name, observed_count=102, eligible_count=100,
                    valid_count=95, excluded_count=1, duplicate_count=1) for name in req.required_facts],
    )
    raw["requirement_ref"]["contentHash"] = req.content_hash
    raw.update(changes)
    return QualityMeasurement.model_validate(raw)


def policy():
    return ResolvedPopulationPolicy(version=dict(identity="distinct-days", revision="1",
        content_hash="sha256:" + "e" * 64), grain="day", population_unit="day")


def assess(item=None, **changes):
    return evaluate_quality(SCOPE, requirement(), item or measurement(), evaluated_at=NOW,
                            population_policy=policy(), **changes)


def test_exact_threshold_and_population_boundary_pass_without_rounding():
    result = assess()
    assert result.satisfied and result.reasons == ()
    assert result.freshness_expires_at == NOW + timedelta(hours=1)


def test_low_fact_cannot_be_hidden_by_average_or_population_sum():
    item = measurement()
    item.facts[0].valid_count = 94
    item.facts[1].valid_count = 100
    item.distinct_population_count = 19
    result = assess(item)
    assert not result.satisfied
    assert set(result.reasons) == {"QUALITY_BELOW_THRESHOLD:Order", "POPULATION_BELOW_MINIMUM"}


def test_zero_denominator_and_missing_fact_are_not_success():
    item = measurement()
    item.facts = item.facts[:1]
    item.facts[0].observed_count = item.facts[0].eligible_count = item.facts[0].valid_count = 0
    item.facts[0].excluded_count = item.facts[0].duplicate_count = 0
    assert set(assess(item).reasons) == {"EMPTY_DENOMINATOR:Order", "MISSING_FACT:Product"}


@pytest.mark.parametrize("field,value", [("eligible_count", True), ("valid_count", "95"),
    ("excluded_count", -1), ("observed_count", 103), ("valid_count", 101)])
def test_invalid_counts_rejected_even_after_model_copy(field, value):
    item = measurement()
    item.facts[0] = item.facts[0].model_copy(update={field: value})
    with pytest.raises((ValidationError, ValueError)):
        assess(item)


@pytest.mark.parametrize("field", ["tenant", "requirement_ref", "channel_ref", "entity_ref",
                                 "time_window", "cutoff_at", "grain", "population_unit"])
def test_scope_drift_rejected(field):
    item = measurement()
    if field == "tenant": item.tenant.org_id = "dev-org"
    elif field.endswith("_ref"): getattr(item, field).content_hash = "sha256:" + "f" * 64
    elif field == "time_window": item.time_window.start_at -= timedelta(days=1)
    elif field == "cutoff_at": item.cutoff_at -= timedelta(seconds=1)
    else: setattr(item, field, "order")
    with pytest.raises(ValueError, match="scope"):
        assess(item)


def test_expiry_uses_source_age_not_measurement_refresh_and_is_exclusive():
    item = measurement(source_observed_at=NOW - timedelta(hours=1))
    assert assess(item).reasons == ("MEASUREMENT_STALE",)
    req = requirement().model_copy(update={"expires_at": NOW + timedelta(seconds=5)})
    req.content_hash = canonical_revision_content_hash(req)
    item = measurement()
    item.requirement_ref.content_hash = req.content_hash
    result = evaluate_quality(SCOPE, req, item, evaluated_at=NOW, population_policy=policy())
    assert result.freshness_expires_at == req.expires_at


@pytest.mark.parametrize("field", ["source_refs", "mapping_refs"])
def test_missing_or_duplicate_lineage_rejected(field):
    with pytest.raises(ValidationError): measurement(**{field: []})
    item = measurement()
    setattr(item, field, getattr(item, field) * 2)
    with pytest.raises(ValueError): assess(item)


def test_future_naive_and_duplicate_fact_rejected():
    with pytest.raises(ValueError): assess(measurement(measured_at=NOW + timedelta(seconds=1)))
    with pytest.raises(ValueError): measurement(source_observed_at=NOW.replace(tzinfo=None))
    item = measurement()
    item.facts.append(item.facts[0])
    with pytest.raises(ValueError): assess(item)


def test_unrequested_fact_and_closed_requirement_do_not_pass():
    item = measurement()
    item.facts[0].fact_id = "Other"
    with pytest.raises(ValueError): assess(item)
    req = requirement(status="cancelled")
    item = measurement()
    item.requirement_ref.content_hash = req.content_hash
    with pytest.raises(ValueError, match="eligible"):
        evaluate_quality(SCOPE, req, item, evaluated_at=NOW, population_policy=policy())


def test_population_unit_can_differ_from_aggregation_grain_only_by_resolved_policy():
    item = measurement(population_unit="customer")
    expected = policy().model_copy(update={"population_unit": "customer"})
    result = evaluate_quality(SCOPE, requirement(), item, evaluated_at=NOW, population_policy=expected)
    assert result.satisfied
    item.population_policy_version.revision = "2"
    with pytest.raises(ValueError, match="scope"):
        evaluate_quality(SCOPE, requirement(), item, evaluated_at=NOW, population_policy=expected)


def test_large_population_below_threshold_by_one_is_not_rounded_up():
    item = measurement()
    fact = item.facts[0]
    fact.observed_count = fact.eligible_count = 9_000_000_000_000_000_000
    fact.excluded_count = fact.duplicate_count = 0
    fact.valid_count = 8_549_999_999_999_999_999
    assert assess(item).reasons == ("QUALITY_BELOW_THRESHOLD:Order",)
    fact.valid_count += 1
    assert assess(item).satisfied


def test_false_population_naive_evaluation_and_source_future_are_rejected():
    with pytest.raises(ValidationError): measurement(distinct_population_count=True)
    with pytest.raises(ValidationError): measurement(source_observed_at=NOW + timedelta(seconds=1))
    with pytest.raises(ValueError, match="timezone"):
        evaluate_quality(SCOPE, requirement(), measurement(), evaluated_at=NOW.replace(tzinfo=None),
                         population_policy=policy())


def test_requirement_mutation_cannot_keep_original_hash():
    req = requirement().model_copy(update={"quality_threshold": 0.0})
    with pytest.raises(ValueError, match="content hash"):
        evaluate_quality(SCOPE, req, measurement(), evaluated_at=NOW, population_policy=policy())
