from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import pytest

from aos_api.pipeline_snapshot_relationships import compile_relationship_policy
from aos_api.pipeline_snapshot_relationship_quality import compile_relationship_quality_policy
from aos_api.pipeline_snapshot_business_cohort import compile_business_cohort_policy
from aos_api.pipeline_snapshot_fact_quality import compile_fact_quality_policy
from aos_api.pipeline_snapshot_readiness_policy import compile_snapshot_readiness_policy
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES


def setup():
    root=Path(__file__).resolve().parents[3]/'bundles/candidates/ecommerce/platform.ecommerce.niushop/1.21.0/content/policies'
    def read(name):return json.loads((root/name).read_text())
    relation=compile_relationship_policy(read('snapshot-relationships.v1.json'))
    quality=compile_relationship_quality_policy(read('relationship-quality.v1.json'),relationship_policy=relation)
    cohort=compile_business_cohort_policy(read('business-cohort.v1.json'),relationship_policy=relation)
    fields=compile_fact_quality_policy(read('fact-quality.v1.json'),relationship_policy=relation,cohort_policy=cohort,quality_policy=quality)
    document=dict(schemaVersion='aos.snapshot-readiness-policy/v1',fieldPolicyHash=fields.content_hash,
        relationshipQualityPolicyHash=quality.content_hash,purposeCode='initial_store_analysis',
        freshnessMode='requirement-oldest-observation',reconciliationMode='current-original-base-and-derived',
        queryBindingId='ecommerce.data_advisor.strategy.plan.r2',
        sources=[dict(pipelineId=s.pipeline_id,objectType=s.object_type) for s in CANONICAL_QYH_SOURCES])
    return fields,quality,document


def test_complete_policy_is_deterministic_and_not_a_readiness_decision():
    fields,quality,doc=setup();before=deepcopy(doc)
    result=compile_snapshot_readiness_policy(doc,field_policy=fields,quality_policy=quality)
    assert result==compile_snapshot_readiness_policy(doc,field_policy=fields,quality_policy=quality)
    assert len(result.sources)==12 and result.sources[10]==('P11-product-review-qyh','ProductReview')
    assert result.content_hash.startswith('sha256:') and not hasattr(result,'ready')
    assert doc==before


@pytest.mark.parametrize('fault',['schema','field-hash','quality-hash','purpose','freshness','reconciliation','extra',
    'missing','duplicate','order','wrong-type','extra-source-field','source-shape','binding-empty','binding-space',
    'binding-url','binding-long','binding-bool'])
def test_policy_rejects_incomplete_or_reinterpreted_authority(fault):
    fields,quality,doc=setup()
    values={'schema':('schemaVersion','v2'),'field-hash':('fieldPolicyHash','sha256:'+'0'*64),
        'quality-hash':('relationshipQualityPolicyHash','sha256:'+'0'*64),'purpose':('purposeCode','sales'),
        'freshness':('freshnessMode','query-time'),'reconciliation':('reconciliationMode','event-count'),
        'extra':('ready',True),'binding-empty':('queryBindingId',''),'binding-space':('queryBindingId',' x '),
        'binding-url':('queryBindingId','https://example.org'),'binding-long':('queryBindingId','x'*201),
        'binding-bool':('queryBindingId',True)}
    if fault in values:doc[values[fault][0]]=values[fault][1]
    if fault=='missing':doc['sources'].pop()
    if fault=='duplicate':doc['sources'][-1]=doc['sources'][0]
    if fault=='order':doc['sources'].reverse()
    if fault=='wrong-type':doc['sources'][10]['objectType']='Review'
    if fault=='extra-source-field':doc['sources'][0]['pass']=True
    if fault=='source-shape':doc['sources'][0]=True
    with pytest.raises(ValueError):compile_snapshot_readiness_policy(doc,field_policy=fields,quality_policy=quality)


@pytest.mark.parametrize('fault',['missing-fact','duplicate-fact','quality-binding','unsupported-purpose'])
def test_original_compiled_inputs_must_cover_same_twelve_facts(fault):
    fields,quality,doc=setup()
    if fault=='missing-fact':fields=replace(fields,facts=fields.facts[:-1])
    if fault=='duplicate-fact':fields=replace(fields,facts=fields.facts[:-1]+(fields.facts[0],))
    if fault=='quality-binding':fields=replace(fields,quality_policy_hash='sha256:'+'f'*64)
    if fault=='unsupported-purpose':quality=replace(quality,purposes=())
    with pytest.raises(ValueError):compile_snapshot_readiness_policy(doc,field_policy=fields,quality_policy=quality)
