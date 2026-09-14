"""Actual business Evidence over current original source/query/quality fixtures."""
import hashlib
import json
import pytest
from test_analysis_snapshot_quality_evidence_pg import (
    database,pytestmark,ledger,owner_case,claim_case,executor_case,group_claim_case,prepared_case,
    assessment_case,journal_case,object_case,completed_group,bridge_case,business_case,fact_case,evidence_case,query_case,quality_case,prepare,revoke,
)
from aos_api.ecommerce_analysis_snapshot_business_evidence import AnalysisSnapshotBusinessEvidence


@pytest.fixture
def business_evidence_case(quality_case,monkeypatch):
    conn,state,source,_,_,call,_=quality_case
    field=json.loads(state['field_raw'])
    from aos_api.ec_ingress_journal import _digest
    document=dict(schemaVersion='aos.snapshot-business-facts/v1',fieldPolicyHash='sha256:'+_digest(field),
        purposeCode=field['purposeCode'],facts=[dict(objectType=ot,mode='records',fields=['name']) for ot in ('Shop','Weapp')])
    state['business_raw']=json.dumps(document).encode()
    policy=call['field_ref'].model_copy(update={'resource_type':'SnapshotBusinessFactPolicy','resource_id':'content/policies/business.json',
        'content_hash':'sha256:'+hashlib.sha256(state['business_raw']).hexdigest()})
    artifacts=source._claims._controls._selections._artifacts;original=artifacts.read_artifact
    artifacts.read_artifact=lambda selected,path,limit:state['business_raw'] if path==policy.resource_id else original(selected,path,limit)
    import aos_api.ecommerce_analysis_snapshot_business_evidence as module
    import aos_api.ecommerce_analysis_snapshot_quality_evidence as quality_module
    monkeypatch.setattr(module,'HostTransaction',quality_module.HostTransaction)
    return quality_case,AnalysisSnapshotBusinessEvidence(source),policy


def inputs(case):
    quality_case,owner,policy=case
    source,query,quality=prepare(quality_case)
    return dict(evidence_ref=source,query_ref=query,quality_ref=quality,policy_ref=policy)


def test_actual_business_content_exact_replay_and_fact_coverage(business_evidence_case):
    case,owner,_=business_evidence_case;conn,state=case[:2]
    call=inputs(business_evidence_case)
    ref=owner.put_current(conn,**call)
    assert owner.put_current(conn,**call)==ref
    body=owner.read_current(conn,reference=ref)
    assert body['factIds']==['Shop','Weapp']
    assert body['content']['facts']['Shop']['records'][0]['values']['name']
    assert body['content']['factIds']==[] and state['calls']==1


@pytest.mark.parametrize('kind',['source','quality','business'])
def test_revoked_dependency_or_business_evidence_rejected(business_evidence_case,kind):
    case,owner,_=business_evidence_case;conn,_,source=case[:3]
    call=inputs(business_evidence_case);ref=owner.put_current(conn,**call)
    revoke(conn,source,ref if kind=='business' else call['evidence_ref' if kind=='source' else 'quality_ref'])
    with pytest.raises(ValueError):owner.read_current(conn,reference=ref)


def test_business_policy_drift_after_persistence_rolls_back(business_evidence_case,monkeypatch):
    case,owner,_=business_evidence_case;conn,state=case[:2];call=inputs(business_evidence_case)
    original=owner._persist
    def persist(db,body):
        ref=original(db,body);state['business_raw']=b'{}';return ref
    monkeypatch.setattr(owner,'_persist',persist)
    with pytest.raises(ValueError):owner.put_current(conn,**call)
    assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='analysis-snapshot-business-facts'").fetchone()['n']==0


def test_canary_cannot_read_business_content(business_evidence_case):
    case,owner,_=business_evidence_case;conn=case[0];ref=owner.put_current(conn,**inputs(business_evidence_case))
    with conn.transaction():
        conn.execute("SELECT set_config('aos.org_id','dev-org',true),set_config('aos.project_id','dev-project',true)")
        with pytest.raises((LookupError,PermissionError)):owner.read_current(conn,reference=ref)


def test_low_fact_keeps_content_but_does_not_claim_full_coverage(business_evidence_case):
    from aos_api.ec_ingress_journal import _digest
    case,owner,policy=business_evidence_case;conn,state,_,_,_,source_call,_=case
    field=json.loads(state['field_raw'])
    next(f for f in field['facts'] if f['objectType']=='Weapp')['fields'].append(dict(property='missingField',kind='nonblank-string'))
    state['field_raw']=json.dumps(field).encode()
    source_call['field_ref']=source_call['field_ref'].model_copy(update={'content_hash':'sha256:'+hashlib.sha256(state['field_raw']).hexdigest()})
    business=json.loads(state['business_raw']);business['fieldPolicyHash']='sha256:'+_digest(field)
    state['business_raw']=json.dumps(business).encode()
    policy=policy.model_copy(update={'content_hash':'sha256:'+hashlib.sha256(state['business_raw']).hexdigest()})
    ref=owner.put_current(conn,**inputs((case,owner,policy)))
    body=owner.read_current(conn,reference=ref)
    assert body['factIds']==['Shop'] and 'QUALITY_BELOW_THRESHOLD:Weapp' in body['qualityReasons']
    assert body['content']['facts']['Weapp']['records'][0]['values']['name']


@pytest.mark.parametrize('fault',['quality-revoked','body'])
def test_late_mutations_cannot_commit_business_evidence(business_evidence_case,monkeypatch,fault):
    case,owner,_=business_evidence_case;conn,_,source=case[:3];call=inputs(business_evidence_case)
    original=owner._persist
    def persist(db,body):
        ref=original(db,body)
        if fault=='quality-revoked':revoke(conn,source,call['quality_ref'])
        else:body['factIds']=['InventedFact']
        return ref
    monkeypatch.setattr(owner,'_persist',persist)
    with pytest.raises(ValueError):owner.put_current(conn,**call)
    assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='analysis-snapshot-business-facts'").fetchone()['n']==0
