from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import pytest
from aos_api.aip_eval_runner import AipEvalRunner,ResolvedArtifact,TargetExecution
from aos_api.aip_eval_authority_store import AipEvalAuthorityConflict
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
from aos_api.aip_eval_contracts import EvalSubjectArtifactRef,EvalGatePolicyRef
from aos_api.aip_agent_text_output import read_agent_text
from aos_api.aip_task_store import AipTaskStore
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database,SCOPE
from test_ecommerce_analyst_method_authority import apply_migrations
from test_aip_text_stage_eval_subject import setup

TEXT='本次商品资料尚不支持销量增长结论。'


def helpers(monkeypatch):
    path=Path(__file__).parent/'aip/test_aip_eval_runner.py'
    spec=importlib.util.spec_from_file_location('text_eval_fixture_helpers',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'SCOPE',SCOPE)
    return module


@pytest.mark.parametrize('fault',[None,'body','reference','access','oversize'])
def test_actual_eval_executes_subject_text_and_never_records_it_in_report(monkeypatch,fault):
    h=helpers(monkeypatch)
    with disposable_database() as connect:
        apply_migrations(connect)
        _,step=setup(connect)
        identity=AipTaskStore(connect).record_artifact(SCOPE,step.run_id,'tester','agent_text_output',
            {'contentHash':sha256(TEXT.encode()).hexdigest(),'marking':['internal']},text_content=TEXT)
        subject=EvalSubjectArtifactRef(resourceId=identity,contentHash=sha256(TEXT.encode()).hexdigest())
        h._seed(AipEvalPackRegistry(connect_factory=connect))
        contract=h._contract().model_copy(update={'gate_policy':{'subjectKind':'agent_text_output','subjectInputMode':'text-envelope-v1'}})
        runner=AipEvalRunner(connect_factory=connect,production_contract_store=SimpleNamespace(get_eval_contract=lambda *args:contract))
        received=[]
        def resolve(ref):
            if ref.artifact_type!='agent_text_output':return h._resolver(ref)
            with connect(SCOPE) as conn:
                text=read_agent_text(conn,SCOPE,ref,markings=['public'] if fault=='access' else ['internal'])
            if fault=='body':text+='changed'
            if fault=='oversize':text='x'*2097153
            if fault=='reference':ref=ref.model_copy(update={'artifact_id':'other'})
            return ResolvedArtifact(reference=ref,value=text)
        def target(ref,value):
            received.append(value)
            assert value['schemaVersion']=='aos.eval-text-subject-input/v1'
            assert value['subjectText']==TEXT
            assert value['subjectArtifactRef']==subject.model_dump(mode='json',by_alias=True)
            return h._target(ref,value['caseInput'])
        def run():
            return runner.run_by_contract(SCOPE,contract_id=contract.contract_id,contract_revision=contract.revision,
                contract_content_hash=contract.content_hash,idempotency_key='actual-text-eval',actor='tester',
                resolve_artifact=resolve,execute_target=target,execute_judge=h._judge,subject_artifact_ref=subject,stage_attempt_ref=step,
                gate_policy_ref=EvalGatePolicyRef(resourceId='fixture-policy',revision=1,contentHash='d'*64),evidence_cutoff_at=h.NOW)
        if fault is None:
            result=run()
            assert result.gate_passed and len(received)==1
            assert TEXT not in result.model_dump_json()
            assert runner.get_report(SCOPE,result.report_id)==result
        else:
            with pytest.raises((ValueError,AipEvalAuthorityConflict)):run()
            assert received==[]
        with connect(SCOPE) as conn:
            row=conn.execute("SELECT status FROM aip_eval_run WHERE idempotency_key='actual-text-eval'").fetchone()
            count=conn.execute("SELECT count(*) AS n FROM aip_eval_report_revision WHERE org_id=%s AND project_id=%s AND run_id IN (SELECT run_id FROM aip_eval_run WHERE org_id=%s AND project_id=%s AND idempotency_key='actual-text-eval')",(*SCOPE.key,*SCOPE.key)).fetchone()['n']
            assert row['status']==('succeeded' if fault is None else 'failed')
            assert count==(1 if fault is None else 0)


def test_existing_non_subject_eval_still_receives_original_case(monkeypatch):
    h=helpers(monkeypatch)
    with disposable_database() as connect:
        h._seed(AipEvalPackRegistry(connect_factory=connect))
        result=AipEvalRunner(connect_factory=connect).run(SCOPE,suite_id='suite-1',suite_revision=1,idempotency_key='legacy',actor='tester',
            resolve_artifact=h._resolver,execute_target=h._target,execute_judge=h._judge)
        assert result.gate_passed and result.subject_artifact_ref is None


def test_text_protocol_must_be_explicit_before_any_subject_read():
    runner=AipEvalRunner()
    runner._resolve_contract=lambda *args:SimpleNamespace(gate_policy={'subjectKind':'agent_text_output'})
    def forbidden(*args,**kwargs):raise AssertionError('no subject read before protocol authorization')
    runner._assert_media_subject=forbidden
    with pytest.raises(AipEvalAuthorityConflict,match='explicit text-envelope'):
        runner.run(SCOPE,suite_id='suite',suite_revision=1,idempotency_key='key',actor='tester',resolve_artifact=None,execute_target=None,execute_judge=None,
            eval_contract_ref=object(),subject_artifact_ref=object(),stage_attempt_ref=object(),gate_policy_ref=object(),evidence_cutoff_at=object())


def test_content_protocol_must_be_explicit_before_any_subject_read():
    runner=AipEvalRunner()
    runner._resolve_contract=lambda *args:SimpleNamespace(gate_policy={'subjectKind':'ecommerce_content'})
    runner._assert_media_subject=lambda *_a,**_k:pytest.fail('no content read before protocol authorization')
    with pytest.raises(AipEvalAuthorityConflict,match='explicit ecommerce-readable-content'):
        runner.run(SCOPE,suite_id='suite',suite_revision=1,idempotency_key='key',actor='tester',
            resolve_artifact=None,execute_target=None,execute_judge=None,
            eval_contract_ref=object(),subject_artifact_ref=object(),stage_attempt_ref=object(),
            gate_policy_ref=object(),evidence_cutoff_at=object())


def test_content_subject_envelope_is_exact_and_case_input_is_copied():
    subject=EvalSubjectArtifactRef(resourceId='content',contentHash='a'*64)
    payload={'body':'玫瑰面霜草稿','factSourceRefs':[{'resourceId':'facts'}]}
    criteria={'nested':{'value':1}}
    first=AipEvalRunner._content_subject_input(subject,payload,criteria)
    assert first['schemaVersion']=='aos.eval-ecommerce-content-input/v1'
    assert first['subjectArtifactRef']==subject.model_dump(mode='json',by_alias=True)
    assert first['content']==payload
    first['content']['body']='tampered'
    first['caseInput']['nested']['value']=99
    second=AipEvalRunner._content_subject_input(subject,payload,criteria)
    assert second['content']==payload and second['caseInput']==criteria


def test_target_input_mutation_does_not_change_next_case():
    subject=EvalSubjectArtifactRef(resourceId='text',contentHash=sha256(TEXT.encode()).hexdigest())
    criteria={'nested':{'value':1}}
    def resolver(ref):return ResolvedArtifact(reference=ref,value=TEXT)
    first=AipEvalRunner._text_subject_input(resolver,subject,criteria)
    first['caseInput']['nested']['value']=99
    first['subjectArtifactRef']['contentHash']='b'*64
    second=AipEvalRunner._text_subject_input(resolver,subject,criteria)
    assert second['caseInput']=={'nested':{'value':1}}
    assert second['subjectArtifactRef']['contentHash']==subject.content_hash
