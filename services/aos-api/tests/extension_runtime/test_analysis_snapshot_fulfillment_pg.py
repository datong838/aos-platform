"""Original Requirement/Fulfillment stores over twelve source owners; named origin."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import pytest

from test_analysis_snapshot_readiness_pg import (
    database,pytestmark,ledger,owner_case,claim_case,executor_case,group_claim_case,
    prepared_case,assessment_case,journal_case,object_case,completed_group,bridge_case,
    business_case,fact_case,evidence_case,query_case,readiness_case,receipt_case,
)
from test_analysis_snapshot_quality_evidence_pg import quality_case as original_quality
from test_analysis_snapshot_readiness_twelve_pg import business_evidence_case as twelve_business
from aos_api.ecommerce_analysis_snapshot_brief import AnalysisSnapshotBrief
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
from aos_api.data_requirement_store import DataRequirementStore,canonical_revision_content_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_analysis_snapshot_bundle import AnalysisSnapshotBundle
from aos_api.ecommerce_analysis_snapshot_fulfillment import AnalysisSnapshotFulfillment


@pytest.fixture
def quality_case(query_case,monkeypatch,request):
    case=original_quality.__wrapped__(query_case,monkeypatch)
    pending=case[-1]
    from aos_api.ecommerce_growth_runtime_adapters import DataRequirementRequestHostService
    pending['requirement']['createdBy']=DataRequirementRequestHostService.executor_identity
    pending['requirement']['requestedOutputs']=getattr(request,'param',['EvidenceBundleRevision'])
    req=DataRequirementRevisionRecord.model_validate(pending['requirement'])
    pending['requirement']['contentHash']=canonical_revision_content_hash(req)
    return case


@pytest.fixture
def business_evidence_case(quality_case,monkeypatch):
    configured=twelve_business.__wrapped__(quality_case,monkeypatch)
    case,business,_=configured;conn=case[0];pending=case[-1]
    # Establish the named paused origin BEFORE any source evidence is captured.
    # Runtime is part of the original field-context hash and cannot change later.
    from tests.test_aip_business_investigation_evidence import runtime
    value=runtime().model_dump(mode='json',by_alias=True);req=pending['requirement']
    for key,reqkey in [('caseRef','caseRef'),('businessInvestigationRunRef','runRef')]:
        value[key]={k:v for k,v in req[reqkey].items() if k in ('resourceType','resourceId','revision','contentHash')}
        value[key]['contentHash']=value[key]['contentHash'][7:]
    checkpoint=req['checkpointRef']
    value['checkpointRef']=dict(resourceId=checkpoint['resourceId'],sequence=checkpoint['revision'],stateHash=checkpoint['contentHash'][7:])
    pending['runtime']=value
    conn.execute('RESET ROLE')
    path=Path(__file__).resolve().parents[2]/'alembic/versions/w2_001_brief_evidence.py'
    spec=importlib.util.spec_from_file_location('fulfillment_brief_ddl',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=NS(execute=conn.execute);module.upgrade()
    conn.execute('SET ROLE aos_runtime')
    conn.execute("INSERT INTO aip_task(org_id,project_id,task_id,task_type,title,status,idempotency_key,request_hash,created_by,version) VALUES(%s,%s,'task-1','analysis','fixture','paused','fixture-task',repeat('1',64),'fixture',2)",business.scope.key)
    import aos_api.ecommerce_analysis_snapshot_brief as target
    import aos_api.ecommerce_analysis_snapshot_business_evidence as origin
    monkeypatch.setattr(target,'HostTransaction',origin.HostTransaction)
    return configured


@pytest.fixture
def fulfillment_case(receipt_case,business_evidence_case,monkeypatch):
    conn,state,readiness,call=receipt_case
    case,business,_=business_evidence_case
    evidence=call['business_ref'];brief=AnalysisSnapshotBrief(business)
    root=Path(__file__).resolve().parents[2]/'alembic/versions';schema=business.source._schema
    conn.execute('RESET ROLE')
    def execute(statement):
        return conn.execute(statement.replace('public.canonical_asset_registry_jsonb',f'"{schema}".canonical_asset_registry_jsonb')
            .replace('search_path=pg_catalog,public',f'search_path=pg_catalog,"{schema}",public')
            .replace('search_path = pg_catalog, public',f'search_path = pg_catalog,"{schema}",public'))
    for filename in ('w2_005_evidence_revoke_disclosure.py','biw2_001_data_requirement_authority.py',
                     'biw2_002_data_requirement_cas.py','biw2_003_data_fulfillment_binding.py','ar2_008_fulfillment_authority_payload.py'):
        spec=importlib.util.spec_from_file_location('fulfillment_ddl',root/filename)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.op=NS(execute=execute);module.upgrade()
    conn.execute('SET ROLE aos_runtime')
    req=DataRequirementRevisionRecord.model_validate(case[-1]['requirement'])
    with conn.transaction():
        DataRequirementStore(TransactionBoundConnectFactory(HostTransaction(conn),business.scope)).request(
            business.scope,req.created_by,'fixture-original-request',req,expected_version=0)
    bundle=AnalysisSnapshotBundle(brief)
    bundle_ref=bundle.prepare_current(conn,business_ref=evidence)
    ready=readiness.put_current(conn,**call)
    owner=AnalysisSnapshotFulfillment(bundle,readiness)
    return conn,state,owner,dict(business_ref=evidence,bundle_ref=bundle_ref,readiness_ref=ready.receipt_ref,policy_ref=call['policy_ref'])


def test_original_fulfillment_is_current_and_idempotent(fulfillment_case):
    conn,state,owner,call=fulfillment_case
    first=owner.put_current(conn,**call)
    again=owner.put_current(conn,**call)
    assert first==again and first.status.value=='fulfilled'
    assert first.created_by==owner.source.analysis.source.actor
    current=DataRequirementStore(TransactionBoundConnectFactory(HostTransaction(conn),owner.scope)).get_current(
        owner.scope,first.requirement_ref.resource_id)
    assert current.created_by!=first.created_by
    assert first.artifact_refs==[call['bundle_ref']]
    assert owner.read_current(conn,reference=owner.reference(first),**call)==first
    assert conn.execute('SELECT count(*) AS n FROM data_fulfillment_receipt').fetchone()['n']==1
    assert conn.execute("SELECT status FROM aip_task WHERE task_id='task-1'").fetchone()['status']=='paused'
    assert state['calls']==1


def test_late_binding_revocation_rolls_back_fulfillment(fulfillment_case,monkeypatch):
    from aos_api.data_fulfillment_store import DataFulfillmentStore
    conn,state,owner,call=fulfillment_case
    original=DataFulfillmentStore.bind
    def bind(self,*args,**kwargs):
        result=original(self,*args,**kwargs);state['binding_denied']=True;return result
    monkeypatch.setattr(DataFulfillmentStore,'bind',bind)
    with pytest.raises(ValueError):owner.put_current(conn,**call)
    assert conn.execute('SELECT count(*) AS n FROM data_fulfillment_receipt').fetchone()['n']==0


@pytest.mark.parametrize('quality_case',[['EvidenceBundleRevision','DataProductRevision']],indirect=True)
def test_bundle_does_not_fulfill_additional_requested_outputs(fulfillment_case):
    conn,_,owner,call=fulfillment_case
    with pytest.raises(ValueError,match='current requirement does not permit'):
        owner.put_current(conn,**call)
    assert conn.execute('SELECT count(*) AS n FROM data_fulfillment_receipt').fetchone()['n']==0


@pytest.mark.parametrize('fault',['canary','bundle-revoke','wrong-receipt','requirement'])
def test_saved_fulfillment_requires_current_exact_authority(fulfillment_case,fault):
    conn,_,owner,call=fulfillment_case
    saved=owner.put_current(conn,**call)
    reference=owner.reference(saved)
    if fault=='canary':
        conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    elif fault=='bundle-revoke':
        # Revoke the original business evidence through the existing fixture's
        # original immutable revoke-event path; the bundle must become unusable.
        from test_analysis_snapshot_source_evidence_pg import revoke
        revoke(conn,owner.source,call['business_ref'])
    elif fault=='wrong-receipt':
        reference=reference.model_copy(update={'content_hash':'sha256:'+'f'*64})
    elif fault=='requirement':
        from aos_api.business_investigation_shared_contracts import DataRequirementStatus
        store=DataRequirementStore(TransactionBoundConnectFactory(HostTransaction(conn),owner.scope))
        with conn.transaction():
            req=store.get_current(owner.scope,saved.requirement_ref.resource_id)
            revised=req.model_copy(update=dict(revision=2,status=DataRequirementStatus.CANCELLED,prior_ref=saved.requirement_ref))
            revised=DataRequirementRevisionRecord.model_validate(revised.model_dump())
            revised=revised.model_copy(update={'content_hash':canonical_revision_content_hash(revised)})
            store.cancel(owner.scope,req.created_by,'fixture-cancel',revised,expected_version=1)
    with pytest.raises((ValueError,LookupError,PermissionError)):
        owner.read_current(conn,reference=reference,**call)


def test_expiry_after_outer_guard_rolls_back_saved_fulfillment(fulfillment_case,monkeypatch):
    from datetime import timedelta
    conn,_,owner,call=fulfillment_case
    progress=dict(depth=0,finished=False,saved=0)
    original=owner.source._projections.run_current
    def run(*args,**kwargs):
        progress['depth']+=1
        try:
            result=original(*args,**kwargs)
        finally:
            progress['depth']-=1
        if progress['depth']==0:
            progress['saved']=conn.execute('SELECT count(*) AS n FROM data_fulfillment_receipt').fetchone()['n']
            progress['finished']=True
        return result
    monkeypatch.setattr(owner.source._projections,'run_current',run)
    original_execute=HostTransaction.execute
    def execute(self,query,params=()):
        result=original_execute(self,query,params)
        if progress['finished'] and query=='SELECT clock_timestamp() AS now':
            # Named expiry fault only after the actual outer guard and save.
            now=result.fetchone()['now']+timedelta(days=2)
            return NS(fetchone=lambda:dict(now=now))
        return result
    monkeypatch.setattr(HostTransaction,'execute',execute)
    with pytest.raises(ValueError,match='expired before transaction completion'):
        owner.put_current(conn,**call)
    assert progress['saved']==1
    assert conn.execute('SELECT count(*) AS n FROM data_fulfillment_receipt').fetchone()['n']==0
