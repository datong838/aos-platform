"""Explicit snapshot measurement DTO; does not authenticate source or authorize work."""
from datetime import timedelta
import pytest
from aos_api.data_requirement_quality import SnapshotQueryQualityMeasurement,_MEASUREMENT_ADAPTER
from aos_api.data_requirement_quality_evidence import QualityEvidenceInput,canonical_quality_evidence
from tests.test_data_requirement_quality import measurement,policy,assess
from tests.test_data_requirement_store import NOW,SCOPE,requirement,ref


def snapshot():
    raw=measurement().model_dump()
    for key in ('schema_version','hydration_ref','mapping_refs'):raw.pop(key)
    raw['source_refs']=[ref('Evidence','evidence-analysis-snapshot-source-'+'a'*64)]
    raw['source_refs'][0]['contentHash']='sha256:'+'a'*64
    raw['query_result_ref']=ref('QueryResultRevision','query')
    return SnapshotQueryQualityMeasurement.model_validate(raw)


def test_explicit_variant_roundtrip_and_original_evidence_compatibility():
    item=snapshot()
    assert _MEASUREMENT_ADAPTER.validate_json(item.model_dump_json())==item
    assert assess(item).satisfied
    value=QualityEvidenceInput(requirement=requirement(),measurement=item,population_policy=policy(),
        evaluated_at=NOW,actor='test',run_id=None)
    body,digest=canonical_quality_evidence(SCOPE,value)
    assert QualityEvidenceInput.model_validate(body['input']).measurement==item
    assert len(digest)==64 and body['factIds']==[]


@pytest.mark.parametrize('fault',['object','other-evidence','hash','revision','receipt','empty','duplicate','query-type','query-string-revision','query-receipt'])
def test_exact_complete_snapshot_provenance_required(fault):
    raw=snapshot().model_dump()
    source=raw['source_refs'][0]
    if fault=='object':source['resource_type']='EcommerceObjectRevision'
    if fault=='other-evidence':source['resource_id']='other-evidence'
    if fault=='hash':source['content_hash']='sha256:'+'b'*64
    if fault=='revision':source['revision']='1'
    if fault=='receipt':source['receipt_id']='made-up'
    if fault=='empty':raw['source_refs']=[]
    if fault=='duplicate':raw['source_refs']*=2
    if fault=='query-type':raw['query_result_ref']['resource_type']='Evidence'
    if fault=='query-string-revision':raw['query_result_ref']['revision']='1'
    if fault=='query-receipt':raw['query_result_ref']['receipt_id']='made-up'
    with pytest.raises(ValueError):SnapshotQueryQualityMeasurement.model_validate(raw)


def test_snapshot_empty_and_weak_facts_are_never_averaged_into_pass():
    item=snapshot();first,second=item.facts
    first.observed_count=first.eligible_count=first.valid_count=first.excluded_count=first.duplicate_count=0
    second.valid_count=94
    assert set(assess(item).reasons)=={'EMPTY_DENOMINATOR:Order','QUALITY_BELOW_THRESHOLD:Product'}


def test_snapshot_query_generation_does_not_refresh_source_age():
    item=snapshot();item.source_observed_at=NOW-timedelta(hours=1)
    assert assess(item).reasons==('MEASUREMENT_STALE',)
