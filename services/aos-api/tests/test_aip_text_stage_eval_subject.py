from contextlib import contextmanager
from types import SimpleNamespace
import pytest
from aos_api.aip_eval_runner import AipEvalRunner
from aos_api.aip_eval_authority_store import AipEvalAuthorityConflict
from aos_api.aip_eval_contracts import EvalSubjectArtifactRef,EvalStageAttemptRef,EvalContractRevisionRef
from aos_api.aip_task_store import AipTaskStore
from aos_api.aip_contracts import PlanStep
from aos_api.aip_task_models import CreateTaskRequest,CreatePlanRevisionRequest,CreateTaskRunRequest
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database,SCOPE


def setup(connect):
    store=AipTaskStore(connect_factory=connect)
    task=store.create_task(SCOPE,'tester','text-eval-task',CreateTaskRequest(type='analysis',title='Isolated text subject'))
    plan=store.create_plan(SCOPE,'tester',task.id,'text-eval-plan',CreatePlanRevisionRequest(expected_task_version=task.version,steps=[PlanStep(step_key='portrait',title='Portrait')]))
    task=store.get_task(SCOPE,task.id)
    store.approve_plan(SCOPE,'tester',task.id,plan.revision,task.version,plan.content_hash)
    task=store.get_task(SCOPE,task.id)
    run=store.create_run(SCOPE,'tester',task.id,'text-eval-run',CreateTaskRunRequest(plan_revision_id=plan.id,expected_task_version=task.version))
    store.start_run(SCOPE,run.id,expected_run_version=run.version,expected_task_version=store.timeline(SCOPE,run.id).task.version,actor='tester',idempotency_key='text-eval-start')
    lease=store.claim_step(SCOPE,run.id,'portrait','worker',lease_seconds=60)
    artifact=store.record_artifact(SCOPE,run.id,'tester','agent_text_output',{'contentHash':'a'*64,'marking':['internal']})
    return EvalSubjectArtifactRef(resourceId=artifact,contentHash='a'*64),EvalStageAttemptRef(runId=run.id,stepKey='portrait',stepRunId=lease.step_run_id,attempt=lease.attempt,inputHash=lease.input_hash)


def test_actual_task_artifact_and_latest_step_are_required():
    with disposable_database() as connect:
        artifact,attempt=setup(connect)
        runner=AipEvalRunner(connect_factory=connect)
        runner._assert_media_subject(SCOPE,artifact,attempt,subject_kind='agent_text_output')
        with pytest.raises(AipEvalAuthorityConflict):runner._assert_media_subject(SCOPE,artifact,attempt)
        for ref,step in [(artifact.model_copy(update={'content_hash':'b'*64}),attempt),
            (artifact,attempt.model_copy(update={'run_id':'other'})),
            (artifact,attempt.model_copy(update={'attempt':2})),
            (artifact,attempt.model_copy(update={'input_hash':'b'*64}))]:
            with pytest.raises(AipEvalAuthorityConflict):runner._assert_media_subject(SCOPE,ref,step,subject_kind='agent_text_output')
        @contextmanager
        def same_database(scope):
            with connect(SCOPE) as conn:yield conn
        other=AipEvalRunner(connect_factory=same_database)
        with pytest.raises(AipEvalAuthorityConflict):other._assert_media_subject(TenantScope('dev-org','dev-project'),artifact,attempt,subject_kind='agent_text_output')


@pytest.mark.parametrize('kind',['unknown','',None,True,[]])
def test_unknown_subject_kind_is_not_accepted(kind):
    runner=AipEvalRunner()
    with pytest.raises(AipEvalAuthorityConflict):runner._assert_media_subject(SCOPE,None,None,subject_kind=kind)


@pytest.mark.parametrize('declared',['agent_text_output','media_variant',None])
def test_run_resolves_contract_before_subject_check(declared):
    runner=AipEvalRunner()
    events=[]
    policy={} if declared is None else {'subjectKind':declared}
    runner._resolve_contract=lambda *args: (events.append('contract') or SimpleNamespace(gate_policy=policy))
    def subject(*args,**kwargs):
        events.append(kwargs['subject_kind'])
        raise AipEvalAuthorityConflict('stop after verified dispatch')
    runner._assert_media_subject=subject
    with pytest.raises(AipEvalAuthorityConflict,match='verified dispatch'):
        runner.run(SCOPE,suite_id='suite',suite_revision=1,idempotency_key='key',actor='tester',resolve_artifact=None,execute_target=None,execute_judge=None,
            eval_contract_ref=EvalContractRevisionRef(resourceId='contract',revision=1,contentHash='a'*64),
            subject_artifact_ref=object(),stage_attempt_ref=object(),gate_policy_ref=object(),evidence_cutoff_at=object())
    assert events==['contract',declared or 'media_variant']


@pytest.mark.parametrize('role',['variant','master','draft',None])
def test_default_media_family_boundary_is_unchanged(role):
    artifact=EvalSubjectArtifactRef(resourceId='artifact',contentHash='a'*64)
    attempt=EvalStageAttemptRef(runId='run',stepKey='render',stepRunId='step',attempt=1,inputHash='b'*64)
    rows=[dict(artifact_id='artifact',content_hash='a'*64,run_id='run',family_role=role,artifact_type='image'),
        dict(step_run_id='step',run_id='run',step_key='render',attempt=1,input_hash='b'*64),
        dict(step_run_id='step',attempt=1)]
    @contextmanager
    def connect(scope):
        assert scope==SCOPE
        def execute(*args):return SimpleNamespace(fetchone=lambda:rows.pop(0))
        yield SimpleNamespace(execute=execute)
    runner=AipEvalRunner(connect_factory=connect)
    if role=='variant':runner._assert_media_subject(SCOPE,artifact,attempt)
    else:
        with pytest.raises(AipEvalAuthorityConflict):runner._assert_media_subject(SCOPE,artifact,attempt)
