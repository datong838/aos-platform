"""Actual completed snapshot; named analysis/pending doubles as upstream fixture."""
from copy import deepcopy
import hashlib
import json
import pytest
from test_analysis_business_cohort_context_pg import (
    database,pytestmark,ledger,owner_case,claim_case,executor_case,group_claim_case,
    prepared_case,assessment_case,journal_case,object_case,completed_group,bridge_case,business_case,
)
from aos_api.ecommerce_analysis_fact_quality_context import AnalysisFactQualityContext
from aos_api.pipeline_snapshot_relationships import compile_relationship_policy
from aos_api.pipeline_snapshot_relationship_quality import compile_relationship_quality_policy
from aos_api.pipeline_snapshot_business_cohort import compile_business_cohort_policy


@pytest.fixture
def fact_case(business_case):
    conn,state,pending,business,call=business_case
    artifacts=business.analysis.source.reader._journal._claims._controls._selections._artifacts
    original=artifacts.read_artifact
    relation=compile_relationship_policy(json.loads(state['policy_raw']))
    quality=compile_relationship_quality_policy(json.loads(original(None,call['quality_ref'].resource_id,256000)),relationship_policy=relation)
    cohort=compile_business_cohort_policy(json.loads(state['cohort_raw']),relationship_policy=relation)
    document=dict(schemaVersion='aos.snapshot-fact-quality/v1',cohortPolicyHash=cohort.content_hash,
        relationshipQualityPolicyHash=quality.content_hash,purposeCode=cohort.purpose_code,
        facts=[dict(objectType=ot,fields=[dict(property='name',kind='nonblank-string')]) for ot in relation.object_types])
    raw=json.dumps(document).encode();state['field_raw']=raw
    ref=call['cohort_ref'].model_copy(update={'resource_type':'SnapshotFactQualityPolicy',
        'resource_id':'content/policies/fields.json','content_hash':'sha256:'+hashlib.sha256(raw).hexdigest()})
    artifacts.read_artifact=lambda selected,path,limit:state['field_raw'] if path==ref.resource_id else original(selected,path,limit)
    pending['requirement']['requiredFacts']=list(relation.object_types)
    return conn,state,pending,AnalysisFactQualityContext(business.analysis),call|{'field_ref':ref}


def test_current_installed_fields_measure_original_rows_without_reread(fact_case):
    conn,state,pending,owner,call=fact_case
    with conn.transaction():first=owner.run_current(conn,**call,execute=lambda x:x)
    with conn.transaction():again=owner.run_current(conn,**call,execute=lambda x:x)
    assert first==again and state['calls']==1
    assert set(first['measurement']['facts'])==set(pending['requirement']['requiredFacts'])
    assert all(f['counts']['observedCount']==1 for f in first['measurement']['facts'].values())
    assert all(f['counts']['validCount']==1 for f in first['measurement']['facts'].values())


@pytest.mark.parametrize('fault',['required-facts','policy-bytes','policy-type'])
def test_field_policy_cannot_be_substituted(fact_case,fault):
    conn,state,pending,owner,call=fact_case
    if fault=='required-facts':pending['requirement']['requiredFacts']=['unrelated']
    if fault=='policy-bytes':state['field_raw']=b'{}'
    if fault=='policy-type':call['field_ref']=call['field_ref'].model_copy(update={'resource_type':'WrongPolicy'})
    with pytest.raises((ValueError,PermissionError)),conn.transaction():
        owner.run_current(conn,**call,execute=lambda x:pytest.fail('wrong field policy accepted'))


@pytest.mark.parametrize('fault',['output','release','policy','deferred'])
def test_field_consumer_retains_current_guards(fact_case,fault):
    conn,state,_,owner,call=fact_case
    def consume(value):
        if fault=='output':value['measurement']['facts'].clear()
        if fault=='release':state['policy_denied']=True
        if fault=='policy':state['field_raw']=b'{}'
        if fault=='deferred':return (item for item in [value])
    with pytest.raises((ValueError,PermissionError)),conn.transaction():owner.run_current(conn,**call,execute=consume)
