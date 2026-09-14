"""Actual completed group; named original analysis/pending context doubles."""
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import pytest
from test_analysis_snapshot_context_pg import (
    database, pytestmark, ledger, owner_case, claim_case, executor_case, group_claim_case,
    prepared_case, assessment_case, journal_case, object_case, completed_group, bridge_case,
)
from aos_api.ecommerce_analysis_pending_data_context import AnalysisPendingDataContext
from aos_api.ecommerce_analysis_business_cohort_context import AnalysisBusinessCohortContext
from aos_api.pipeline_snapshot_relationships import compile_relationship_policy


@pytest.fixture
def business_case(bridge_case, monkeypatch):
    conn, args, state, context, snapshot, call = bridge_case
    relationship = compile_relationship_policy(json.loads(state['policy_raw']))
    document = dict(schemaVersion='aos.snapshot-business-cohort/v1', relationshipPolicyHash=relationship.content_hash,
        purposeCode='initial_store_analysis', windowBoundary='start-inclusive-end-exclusive',
        rules=[dict(objectType=ot,basis='snapshot',statusFilter=None) for ot in relationship.object_types])
    raw = json.dumps(document).encode()
    ref = args['policy_ref'].model_copy(update={'resource_type':'SnapshotBusinessCohortPolicy',
        'resource_id':'content/policies/cohort.json','content_hash':'sha256:'+hashlib.sha256(raw).hexdigest()})
    artifacts = snapshot.analysis.source.reader._journal._claims._controls._selections._artifacts
    original = artifacts.read_artifact
    state['cohort_raw'] = raw
    artifacts.read_artifact = lambda selected,path,limit:state['cohort_raw'] if path == ref.resource_id else original(selected,path,limit)
    cutoff = datetime.fromisoformat(context['analysisReceipt']['cutoffAt'])
    pending = dict(analysisContext=deepcopy(context),requirement=dict(purposeCode='initial_store_analysis',
        cutoffAt=cutoff.isoformat(),timeWindow=dict(startAt=(cutoff-timedelta(days=30)).isoformat(),endAt=cutoff.isoformat())))
    def named_pending(self, db, *, receipt_ref, execute):
        assert db is conn and receipt_ref == call['receipt_ref']
        return execute(deepcopy(pending))
    monkeypatch.setattr(AnalysisPendingDataContext,'run_current',named_pending)
    return conn,state,pending,AnalysisBusinessCohortContext(snapshot.analysis),call|{'cohort_ref':ref}


def test_original_window_and_installed_policy_select_original_group(business_case):
    conn,state,pending,owner,call = business_case
    with conn.transaction(): first = owner.run_current(conn,**call,execute=lambda x:x)
    with conn.transaction(): again = owner.run_current(conn,**call,execute=lambda x:x)
    assert first == again
    assert first['requirement']['timeWindow'] == pending['requirement']['timeWindow']
    assert first['cohorts']['Shop']['observedRows'] == 1
    assert first['cohorts']['Shop']['eligibleRows'] == 1
    assert state['calls'] == 1


@pytest.mark.parametrize('fault',['context','cutoff','purpose','policy-bytes','policy-type'])
def test_no_caller_substitution_for_original_authority(business_case,fault):
    conn,state,pending,owner,call = business_case
    if fault=='context':pending['analysisContext']['origin']['runId']='unrelated'
    if fault=='cutoff':pending['requirement']['cutoffAt']='2020-01-01T00:00:00+00:00'
    if fault=='purpose':pending['requirement']['purposeCode']='other_purpose'
    if fault=='policy-bytes':state['cohort_raw']=b'{}'
    if fault=='policy-type':call['cohort_ref']=call['cohort_ref'].model_copy(update={'resource_type':'WrongPolicy'})
    with pytest.raises((ValueError,PermissionError)),conn.transaction():
        owner.run_current(conn,**call,execute=lambda x:pytest.fail('substitution accepted'))
    assert state['calls']==1


@pytest.mark.parametrize('fault',['output','release','policy','deferred'])
def test_current_guards_survive_consumer(business_case,fault):
    conn,state,_,owner,call=business_case
    def consume(value):
        if fault=='output':value['cohorts'].clear()
        if fault=='release':state['policy_denied']=True
        if fault=='policy':state['cohort_raw']=b'{}'
        if fault=='deferred':return (item for item in [value])
    with pytest.raises((ValueError,PermissionError)),conn.transaction():owner.run_current(conn,**call,execute=consume)
