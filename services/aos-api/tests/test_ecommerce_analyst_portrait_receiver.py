from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
import os
import pytest
import aos_api.ecommerce_analyst_portrait_receiver as module
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from test_ecommerce_analyst_portrait_inputs import setup as input_setup
from test_ecommerce_analyst_portrait_generation import completed


def setup(monkeypatch):
    input_args,inputs,_=input_setup(monkeypatch)
    attempt,answer=completed(inputs);scope=inputs['scope'];run=input_args['run']
    run.agent_run_id=attempt.agent_run_id;run.task_run_id='task-run'
    run.request.model_route=attempt.route_ref;run.request.policy=attempt.policy_ref
    state=dict(attempt=attempt,run=run,saved=None,receipt=None,denied=False,reads=0,publications=0,
        artifact=dict(run_id='task-run',source=dict(agentRunId=attempt.agent_run_id,attemptId=attempt.attempt_id)))
    class Connection:
        def execute(self,sql,params):
            if 'pg_advisory_xact_lock' in sql:return None
            assert params==(*scope.key,attempt.output_artifact_ref.artifact_id)
            return SimpleNamespace(fetchone=lambda:state['artifact'])
    conn=Connection()
    @contextmanager
    def connect(requested):
        assert requested==scope
        yield conn
    class Attempts:
        def __init__(self,factory):self.factory=factory
        def get(self,scope,key):
            with self.factory(scope) as bound:assert bound is conn
            return state['attempt']
    class Runs:
        def __init__(self,factory):pass
        def get(self,scope,key):return state['run']
    class Owner:
        def __init__(self,factory):
            from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
            assert isinstance(factory,TransactionBoundConnectFactory)
        def find_insight_publication_receipt(self,*args):return state['receipt']
        def get_insight_exact(self,*args):return state['saved']
        def publish_insight(self,scope,actor,key,item,expected_version):
            assert expected_version==0
            state['saved']=item;state['publications']+=1
            state['receipt']=AnalystExactRef(resourceType='InsightRevision',resourceId=item.insight_id,revision=1,contentHash=item.content_hash)
            return state['receipt']
    def read_text(c,s,ref,markings):
        assert c is conn and s==scope
        if 'internal' not in markings:raise ValueError('output forbidden')
        return answer
    def read_inputs(**kwargs):
        assert kwargs['conn'] is conn
        state['reads']+=1
        if state['denied']:raise ValueError('inputs denied')
        return inputs
    monkeypatch.setattr(module,'AipAgentRunExecutionService',Attempts)
    monkeypatch.setattr(module,'AipAgentRunService',Runs)
    monkeypatch.setattr(module,'EcommerceAnalystAuthorityStore',Owner)
    monkeypatch.setattr(module,'read_agent_text',read_text)
    monkeypatch.setattr(module,'read_portrait_inputs',read_inputs)
    kwargs={k:input_args[k] for k in ('method_ref','eval_ref','metric_sources','cutoff_at','markings','now','max_source_age','max_bytes')}
    kwargs.update(attempt_id=attempt.attempt_id,actor='compiler')
    return module.PortraitReceiver(connect),scope,state,kwargs,inputs,attempt,answer


def test_history_replay_reads_original_output_without_new_source_grant(monkeypatch):
    receiver,scope,state,args,*_=setup(monkeypatch)
    ref=receiver.recover(scope,**args)
    state['denied']=True
    assert receiver.recover(scope,**dict(args,metric_sources=[],now=args['now']+timedelta(days=3)))==ref
    assert state['reads']==1 and state['publications']==1
    with pytest.raises(ValueError,match='output forbidden'):receiver.recover(scope,**dict(args,markings=['public']))


@pytest.mark.parametrize('fault',['unknown','actor','tenant','receipt','usage','skill','route','artifact','provenance','denied','future','request'])
def test_unproven_result_never_published(monkeypatch,fault):
    receiver,scope,state,args,*_=setup(monkeypatch);attempt=state['attempt']
    if fault=='unknown':state['attempt']=attempt.model_copy(update={'status':'unknown'})
    if fault=='actor':args['actor']='other'
    if fault=='tenant':state['attempt']=attempt.model_copy(update={'tenant':attempt.tenant.model_copy(update={'org_id':'other'})})
    if fault=='receipt':state['attempt']=attempt.model_copy(update={'provider_receipt_id':None})
    if fault=='usage':state['attempt']=attempt.model_copy(update={'usage_receipt_ids':[]})
    if fault=='skill':state['run'].request.skill.asset_id='ecommerce.skill.D02'
    if fault=='route':state['run'].request.model_route=None
    if fault=='artifact':state['artifact']=None
    if fault=='provenance':state['artifact']['source']['attemptId']='other'
    if fault=='denied':state['denied']=True
    if fault=='future':args['now']-=timedelta(days=1)
    if fault=='request':state['attempt']=attempt.model_copy(update={'request_hash':'d'*64})
    with pytest.raises(ValueError):receiver.recover(scope,**args)
    assert state['publications']==0


@pytest.mark.parametrize('fault',['method','eval','cutoff','artifact'])
def test_replay_identity_drift_rejected(monkeypatch,fault):
    receiver,scope,state,args,*_=setup(monkeypatch)
    receiver.recover(scope,**args)
    if fault in ('method','eval'):args[fault+'_ref']=args[fault+'_ref'].model_copy(update={'content_hash':'d'*64})
    if fault=='cutoff':args['cutoff_at']-=timedelta(seconds=1)
    if fault=='artifact':state['saved']=state['saved'].model_copy(update={'generation_artifact_ref':None})
    with pytest.raises(ValueError):receiver.recover(scope,**args)
    assert state['publications']==1


@pytest.mark.skipif(os.getenv('AOS_GROWTH_DRAFT_FULL_GRAPH_TEST')!='1',reason='explicit disposable database')
def test_real_insight_owner_publication_replay_and_rollback(monkeypatch):
    from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore,AnalystAuthorityNotFound
    from aos_api.ecommerce_analyst_portrait_generation import insight_from_completed_generation
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database
    _,scope,_,_,inputs,attempt,answer=setup(monkeypatch)
    value=insight_from_completed_generation(attempt=attempt,answer=answer,actor='compiler',**inputs)
    with disposable_database() as connect:
        owner=EcommerceAnalystAuthorityStore(connect)
        with pytest.raises(RuntimeError,match='rollback'):
            with connect(scope) as conn:
                @contextmanager
                def bound(requested):
                    assert requested==scope
                    yield conn
                EcommerceAnalystAuthorityStore(TransactionBoundConnectFactory(HostTransaction(conn),scope)).publish_insight(scope,'compiler','rolled-back',value,expected_version=0)
                raise RuntimeError('rollback')
        assert owner.find_insight_publication_receipt(scope,'rolled-back') is None
        ref=owner.publish_insight(scope,'compiler','portrait-test',value,expected_version=0)
        assert owner.get_insight_exact(scope,ref)==value
        assert owner.find_insight_publication_receipt(scope,'portrait-test')==ref
        assert owner.publish_insight(scope,'compiler','portrait-test',value,expected_version=0)==ref
        with pytest.raises(AnalystAuthorityNotFound):
            EcommerceAnalystAuthorityStore(lambda requested:connect(scope)).get_insight_exact(type(scope)('dev-org','dev-project'),ref)


@pytest.mark.parametrize('fault',[None,'body','identity','scope','kind','hash'])
def test_exact_insight_owner_rejects_payload_drift(monkeypatch,fault):
    from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore,AnalystAuthorityStoreError
    from aos_api.ecommerce_analyst_portrait_generation import insight_from_completed_generation
    from test_ecommerce_analyst_authority_store import Connection,factory
    _,scope,_,_,inputs,attempt,answer=setup(monkeypatch)
    item=insight_from_completed_generation(attempt=attempt,answer=answer,actor='compiler',**inputs)
    ref=AnalystExactRef(resourceType='InsightRevision',resourceId=item.insight_id,revision=1,contentHash=item.content_hash)
    payload=item.model_dump(mode='json',by_alias=True)
    if fault=='body':payload['summary']='changed'
    if fault=='identity':payload['insightId']='other'
    if fault=='scope':payload['tenant']['orgId']='other'
    if fault=='kind':ref=ref.model_copy(update={'resource_type':'DecisionSummaryRevision'})
    if fault=='hash':payload['contentHash']='d'*64
    owner=EcommerceAnalystAuthorityStore(factory(Connection(rows=[dict(payload=payload,content_hash=item.content_hash)])))
    if fault:
        with pytest.raises(AnalystAuthorityStoreError):owner.get_insight_exact(scope,ref)
    else:assert owner.get_insight_exact(scope,ref)==item
