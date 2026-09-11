from contextlib import contextmanager
from datetime import timedelta
import pytest
import aos_api.ecommerce_analyst_stage_review_command as module
from aos_api.ecommerce_analyst_stage_decision_store import AnalystStageDecisionStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from test_ecommerce_analyst_stage_decision_store import migrate,item,hashed
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database,SCOPE


def harness(monkeypatch,connect,fail=None):
    with connect(SCOPE) as conn:
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    value=hashed(item().model_copy(update={'created_at':now-timedelta(seconds=1),'expires_at':now+timedelta(hours=1)}))
    calls=[]
    def check(name,result=None):
        def apply(tx,scope,*args,**kwargs):
            assert type(tx) is HostTransaction and scope==SCOPE
            calls.append(name)
            if fail==name:raise ValueError('blocked '+name)
            return result
        return apply
    monkeypatch.setattr(module,'require_stage_review_authority',check('reviewer',value.reviewer))
    monkeypatch.setattr(module,'_compiled_responsibility',check('compiled'))
    monkeypatch.setattr(module,'require_stage_review_runtime',check('runtime',{}))
    monkeypatch.setattr(module,'_sources_and_eval',check('sources'))
    return value,calls,module.AnalystStageReviewCommandService(
        connect,derive_structure_case=lambda query,stage: {'query':query,'stage':stage})


def decide(service,value,key='accept',version=0):
    return service.decide(SCOPE,value,actor=value.created_by,key=key,expected_version=version,markings=['internal'])


def test_real_owner_accept_replay_and_revoke_without_source_reexecution(monkeypatch):
    with disposable_database() as connect:
        migrate(connect);value,calls,service=harness(monkeypatch,connect)
        ref=decide(service,value)
        assert calls==['reviewer','compiled','runtime','sources']
        calls.clear();assert decide(service,value)==ref
        assert calls==['reviewer']
        calls.clear()
        revoked=hashed(value.model_copy(update={'revision':2,'version':2,'prior_ref':ref,'decision':'revoke','expires_at':None}))
        new=decide(service,revoked,'revoke',1)
        assert calls==['reviewer','compiled']
        with connect(SCOPE) as conn:
            owner=AnalystStageDecisionStore(HostTransaction(conn),SCOPE)
            assert owner.read_current(new)==revoked
            with pytest.raises(ValueError):owner.read_current(ref)
        assert decide(service,value)==ref  # Historical receipt, never new permission.
        with pytest.raises(ValueError,match='replay command drifted'):decide(service,hashed(value.model_copy(update={'reason':'other'})))


@pytest.mark.parametrize('gate',['reviewer','compiled','runtime','sources'])
def test_any_failed_gate_leaves_no_decision(monkeypatch,gate):
    with disposable_database() as connect:
        migrate(connect);value,calls,service=harness(monkeypatch,connect,gate)
        with pytest.raises(ValueError,match='blocked'):decide(service,value)
        with connect(SCOPE) as conn:
            assert conn.execute('SELECT count(*) AS n FROM ecommerce_analyst_stage_decision_head').fetchone()['n']==0


def test_outer_failure_rolls_back_owner_and_receipt(monkeypatch):
    with disposable_database() as connect:
        migrate(connect);value,calls,_=harness(monkeypatch,connect)
        @contextmanager
        def abort(scope):
            with connect(scope) as conn:
                yield conn
                raise RuntimeError('outer transaction failed')
        with pytest.raises(RuntimeError,match='outer transaction'):decide(module.AnalystStageReviewCommandService(
            abort,derive_structure_case=lambda query,stage: {'query':query,'stage':stage}),value)
        with connect(SCOPE) as conn:
            assert conn.execute('SELECT count(*) AS n FROM ecommerce_analyst_stage_decision_revision').fetchone()['n']==0
            assert conn.execute("SELECT count(*) AS n FROM ecommerce_analyst_authority_receipt WHERE operation='analyst.stage_decision_publish'").fetchone()['n']==0


def test_expired_accept_cannot_be_persisted(monkeypatch):
    with disposable_database() as connect:
        migrate(connect);value,calls,service=harness(monkeypatch,connect)
        expired=hashed(value.model_copy(update={'created_at':value.created_at-timedelta(hours=2),'expires_at':value.created_at-timedelta(hours=1)}))
        with pytest.raises(ValueError,match='effective now'):decide(service,expired)


def test_uncompiled_task_cannot_choose_own_responsibility():
    from types import SimpleNamespace
    class Empty:
        def execute(self,*args):return SimpleNamespace(fetchall=lambda:[])
    with pytest.raises(ValueError,match='original business compilation'):module._compiled_responsibility(HostTransaction(Empty()),SCOPE,item())


def sources(monkeypatch):
    from types import SimpleNamespace
    from aos_api.aip_contracts import ArtifactRef
    from aos_api.aip_eval_contracts import AssetRevisionRef,AssetType,EvalCaseKind
    from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
    from aos_api.aip_production_contracts import EvalContractRevision
    from aos_api.ecommerce_analyst_authority_store import canonical_hash
    from test_ecommerce_analyst_portrait_sources import eval_body
    from test_ecommerce_analyst_growth_plan_draft import generation
    from test_aip_business_investigation_eval import request
    _,attempt,_=generation();value=item();artifact=attempt.output_artifact_ref
    value=value.model_copy(update={'artifact_ref':AnalystExactRef(resourceType='Artifact',resourceId=artifact.artifact_id,revision=1,contentHash=artifact.content_hash)})
    body=eval_body().model_copy(update={'gate_policy':{'subjectKind':'agent_text_output','subjectInputMode':'text-envelope-v1','stagePolicyRef':request().gate_policy_ref.model_dump(mode='json',by_alias=True)}})
    contract=EvalContractRevision(**body.model_dump(),tenant=attempt.tenant,contractId='contract',revision=2,version=2,
        contentHash=canonical_hash(body.model_dump(mode='json',by_alias=True)),lifecycle='frozen',readiness='ready',blockers=[],createdBy='compiler',createdAt=attempt.completed_at)
    ref=AnalystExactRef(resourceType='EvalContractRevision',resourceId=contract.contract_id,revision=2,contentHash=contract.content_hash)
    subject=SimpleNamespace(generation_artifact_ref=value.artifact_ref,created_at=attempt.completed_at,created_by=attempt.created_by,eval_ref=ref,cutoff_at=attempt.completed_at)
    skill=SimpleNamespace(asset_type='SkillTemplate',asset_id='ecommerce.skill.D01',revision=1,content_hash='7'*64)
    agent=SimpleNamespace(agent_run_id=attempt.agent_run_id,task_run_id=value.task_run_id,request=SimpleNamespace(skill=skill,model_route=attempt.route_ref,policy=attempt.policy_ref))
    target=AssetRevisionRef(assetType=AssetType.SKILL_TEMPLATE,assetId=skill.asset_id,revision='1',contentHash=skill.content_hash)
    case_input={'schemaVersion':'aos.analyst-structure-case/v1','stage':'portrait','sourceRefs':[],'metricSources':[]}
    eval_case=SimpleNamespace(case_id='case-1',kind=EvalCaseKind.POSITIVE,required=True,
        input_artifact=ArtifactRef(artifactId='case-input',artifactType='eval_input',revision='1',contentHash=canonical_hash(case_input)),
        expected_artifact=ArtifactRef(artifactId='case-expected',artifactType='eval_expected',revision='1',contentHash='6'*64))
    suite=SimpleNamespace(suite_id=contract.suite_ref.resource_id,revision=contract.suite_ref.revision,
        content_hash=contract.suite_ref.content_hash,target=target,cases=[eval_case])
    report=SimpleNamespace(created_at=attempt.completed_at,
        suite_ref=SimpleNamespace(asset_id=contract.suite_ref.resource_id,revision=str(contract.suite_ref.revision),content_hash=contract.suite_ref.content_hash),
        target=target,results=[SimpleNamespace(case_id='case-1')])
    state=dict(subject=subject,attempt=attempt,agent=agent,contract=contract,head=2,raw=True,
        query=True,derive=True,query_body='original query',output_request_hash=attempt.request_hash,
        case_input=case_input,suite=suite,
        gate=SimpleNamespace(invalidated_by=None),report=report)
    class Connection:
        def execute(self,sql,params=None):
            if 'clock_timestamp' in sql:row={'now':attempt.completed_at+timedelta(minutes=1)}
            elif "artifact_type='agent_query_input'" in sql:
                rows=([{'artifact_id':'query-artifact','content_hash':'5'*64}] if state['query'] else [])
                return SimpleNamespace(fetchall=lambda:rows)
            elif 'FROM aip_artifact' in sql:row=dict(run_id=value.task_run_id,source=dict(
                attemptId=attempt.attempt_id,agentRunId=attempt.agent_run_id,requestHash=state['output_request_hash']))
            elif 'aip_eval_contract_head' in sql:row={'current_revision':state['head']}
            else:row={}
            return SimpleNamespace(fetchone=lambda:row)
    monkeypatch.setattr(module,'_subject',lambda *args:state['subject'])
    monkeypatch.setattr(module,'AipAgentRunExecutionService',lambda *args:SimpleNamespace(get=lambda *args:state['attempt']))
    monkeypatch.setattr(module,'AipAgentRunService',lambda *args:SimpleNamespace(get=lambda *args:state['agent']))
    monkeypatch.setattr(module,'AipProductionContractStore',lambda *args:SimpleNamespace(get_eval_contract=lambda *args,**kwargs:state['contract']))
    monkeypatch.setattr(module,'AipEvalPackRegistry',lambda *args:SimpleNamespace(get_suite_revision=lambda *args:state['suite']))
    monkeypatch.setattr(module,'AipEvalAuthorityStore',lambda *args:SimpleNamespace(require_exact_passed=lambda *args,**kwargs:state['gate']))
    monkeypatch.setattr(module.AipReleasePublicationService,'_verify_gate_evidence',lambda *args:None)
    monkeypatch.setattr(module,'read_stage_eval_report',lambda *args,**kwargs:state['report'])
    def text(*args,**kwargs):
        if not state['raw']:raise ValueError('raw text denied')
        return 'internal fixture'
    monkeypatch.setattr(module,'read_agent_text',text)
    def query(*args,**kwargs):
        if not state['query']:raise ValueError('query denied')
        return state['query_body']
    monkeypatch.setattr(module,'read_agent_query',query)
    plan={'steps':[{'stepKey':'portrait','gateRefs':[ref.model_dump(mode='json',by_alias=True)]}]}
    derive=lambda query,stage: state['case_input'] if state['derive'] and query==state['query_body'] and stage=='portrait' else None
    return lambda:module._sources_and_eval(HostTransaction(Connection()),SCOPE,value,plan,['internal'],derive),state,plan


def test_sources_require_explicit_text_protocol_and_current_contract(monkeypatch):
    run,state,plan=sources(monkeypatch)
    assert run() is None


@pytest.mark.parametrize('fault',['artifact','unknown','receipt','wrong_skill','source_request','raw','query','derive','head','contract','input_mode','gate','suite','case_hash','case_count','suite_target','chronology','target_kind','target_id','target_revision','target_hash','no_gate'])
def test_source_and_eval_mismatches_block(monkeypatch,fault):
    run,state,plan=sources(monkeypatch)
    if fault=='artifact':state['subject'].generation_artifact_ref=None
    elif fault=='unknown':state['attempt']=state['attempt'].model_copy(update={'status':'unknown'})
    elif fault=='receipt':state['attempt']=state['attempt'].model_copy(update={'provider_receipt_id':None})
    elif fault=='wrong_skill':state['agent'].request.skill.asset_id='other'
    elif fault=='source_request':state['output_request_hash']='9'*64
    elif fault=='raw':state['raw']=False
    elif fault=='query':state['query']=False
    elif fault=='derive':state['derive']=False
    elif fault=='head':state['head']=3
    elif fault=='contract':state['contract']=state['contract'].model_copy(update={'lifecycle':'draft'})
    elif fault=='input_mode':state['contract'].gate_policy.pop('subjectInputMode')
    elif fault=='gate':state['gate'].invalidated_by='revoked'
    elif fault=='suite':state['report'].suite_ref.asset_id='other'
    elif fault=='case_hash':state['suite'].cases[0].input_artifact=state['suite'].cases[0].input_artifact.model_copy(update={'content_hash':'8'*64})
    elif fault=='case_count':state['suite'].cases=[]
    elif fault=='suite_target':state['suite'].target=state['suite'].target.model_copy(update={'content_hash':'8'*64})
    elif fault=='chronology':state['report'].created_at-=timedelta(seconds=1)
    elif fault=='target_kind':state['report'].target=state['report'].target.model_copy(update={'asset_type':'logic_graph'})
    elif fault=='target_id':state['report'].target=state['report'].target.model_copy(update={'asset_id':'other'})
    elif fault=='target_revision':state['report'].target=state['report'].target.model_copy(update={'revision':'2'})
    elif fault=='target_hash':state['report'].target=state['report'].target.model_copy(update={'content_hash':'8'*64})
    else:plan['steps'][0]['gateRefs']=[]
    with pytest.raises(ValueError):run()


def test_stage_review_requires_explicit_installed_package_deriver():
    with pytest.raises(TypeError,match='case deriver'):
        module.AnalystStageReviewCommandService(lambda scope: None,derive_structure_case=None)
