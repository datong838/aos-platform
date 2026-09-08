import pytest
from pydantic import ValidationError

from aos_api.data_requirement_quality import CanonicalQueryQualityMeasurement, evaluate_quality
from aos_api.data_requirement_quality_evidence import QualityEvidenceInput, canonical_quality_evidence
from tests.test_data_requirement_quality import NOW, SCOPE, measurement, policy, ref, requirement
from tests.test_data_requirement_quality_evidence import evidence_input


def query_measurement():
    raw = measurement().model_dump()
    raw.pop("hydration_ref")
    raw.pop("mapping_refs")
    raw.update(schema_version="aos.data-requirement-query-quality-measurement/v1",
               query_result_ref=ref("QueryResultRevision", "query-1"),
               source_refs=[ref("EcommerceObjectRevision", "Order/niushop:1:1")])
    return CanonicalQueryQualityMeasurement.model_validate(raw)


def test_canonical_query_branch_requires_no_fake_hydration():
    item = query_measurement()
    result = evaluate_quality(SCOPE, requirement(), item, evaluated_at=NOW, population_policy=policy())
    assert result.satisfied
    value = QualityEvidenceInput(requirement=requirement(), measurement=item, population_policy=policy(),
                                 evaluated_at=NOW, actor="user:query-owner", run_id=None)
    body, digest = canonical_quality_evidence(SCOPE, value)
    stored = QualityEvidenceInput.model_validate(body["input"])
    assert isinstance(stored.measurement, CanonicalQueryQualityMeasurement)
    assert canonical_quality_evidence(SCOPE, stored) == (body, digest)
    assert "hydrationRef" not in body["input"]["measurement"]
    assert body["factIds"] == []


@pytest.mark.parametrize("defect", ["hydration", "mapping", "kind", "source", "missing", "schema"])
def test_branches_cannot_mix_or_change_reference_types(defect):
    raw = query_measurement().model_dump()
    if defect == "hydration": raw["hydration_ref"] = ref("SemanticHydrationReceipt", "fake")
    if defect == "mapping": raw["mapping_refs"] = [ref("SourceMappingRevision", "fake")]
    if defect == "kind": raw["query_result_ref"] = ref("DataProductRevision", "query-1")
    if defect == "source": raw["source_refs"] = [ref("FactRevision", "fake")]
    if defect == "missing": raw.pop("query_result_ref")
    if defect == "schema": raw["schema_version"] = "aos.data-requirement-quality-measurement/v1"
    with pytest.raises(ValidationError): CanonicalQueryQualityMeasurement.model_validate(raw)


def test_existing_hydration_branch_keeps_original_serialization():
    value = evidence_input()
    body, digest = canonical_quality_evidence(SCOPE, value)
    # Captured at 4463f3f6 before the union refactor, not recomputed expectation.
    assert digest == "250a28bed2d96cef073d288d138f346bb4a7b63d062ab45d50c900ffd662adfa"
    assert body["input"]["measurement"]["schemaVersion"] == "aos.data-requirement-quality-measurement/v1"
    assert "queryResultRef" not in body["input"]["measurement"]
    assert canonical_quality_evidence(SCOPE, QualityEvidenceInput.model_validate(body["input"])) == (body, digest)
