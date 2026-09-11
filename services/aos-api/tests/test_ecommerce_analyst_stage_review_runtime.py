import pytest
from aos_api.aip_task_store import AipTaskStore
from aos_api.aip_contracts import PlanStep
from aos_api.aip_task_models import CreateTaskRequest,CreatePlanRevisionRequest,CreateTaskRunRequest
from aos_api.aip_eval_contracts import EvalStageAttemptRef
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_stage_review_runtime import require_stage_review_runtime
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database,SCOPE

STAGES=('portrait','diagnosis','solution-design')


def setup(connect):
    store=AipTaskStore(connect_factory=connect)
    task=store.create_task(SCOPE,'tester','review-runtime-task',CreateTaskRequest(type='analysis',title='Isolated review runtime'))
    plan=store.create_plan(SCOPE,'tester',task.id,'review-runtime-plan',CreatePlanRevisionRequest(expected_task_version=task.version,steps=[PlanStep(step_key=key,title=key) for key in STAGES]))
    task=store.get_task(SCOPE,task.id)
    store.approve_plan(SCOPE,'tester',task.id,plan.revision,task.version,plan.content_hash)
    task=store.get_task(SCOPE,task.id)
    run=store.create_run(SCOPE,'tester',task.id,'review-runtime-run',CreateTaskRunRequest(plan_revision_id=plan.id,expected_task_version=task.version))
    store.start_run(SCOPE,run.id,expected_run_version=run.version,expected_task_version=store.timeline(SCOPE,run.id).task.version,actor='tester',idempotency_key='review-runtime-start')
    return store,run,plan


def finish(store,run,plan,stage):
    lease=store.claim_step(SCOPE,run.id,stage,'worker',lease_seconds=60)
    kind,key={'portrait':('InsightRevision','insightRef'),'diagnosis':('DecisionSummaryRevision','decisionRef'),'solution-design':('GrowthPlanRevision','growthPlanRef')}[stage]
    subject=AnalystExactRef(resourceType=kind,resourceId=stage,revision=1,contentHash='a'*64)
    for phase in ('think','act','verify','observe'):
        body={key:subject.model_dump(mode='json',by_alias=True)} if phase=='observe' else {'passed':True}
        store.record_step_phase(SCOPE,lease.step_run_id,'worker',lease.fence,'tester',phase,body)
    store.complete_step(SCOPE,lease.step_run_id,'worker',lease.fence,'tester')
    return dict(task_run_id=run.id,plan_ref=AnalystExactRef(resourceType='PlanRevision',resourceId=plan.id,revision=plan.revision,contentHash=plan.content_hash),stage=stage,
        stage_attempt_ref=EvalStageAttemptRef(runId=run.id,stepKey=stage,stepRunId=lease.step_run_id,attempt=lease.attempt,inputHash=lease.input_hash),subject_ref=subject)


def test_all_three_actual_stage_checkpoints_and_exact_subjects():
    with disposable_database() as connect:
        store,run,plan=setup(connect)
        for stage in STAGES:
            args=finish(store,run,plan,stage)
            with connect(SCOPE) as conn:
                result=require_stage_review_runtime(HostTransaction(conn),SCOPE,**args)
                assert result['plan_revision_id']==plan.id
                for field,change in [('plan_ref',{'content_hash':'b'*64}),('subject_ref',{'content_hash':'b'*64}),('stage_attempt_ref',{'attempt':99})]:
                    bad={**args,field:args[field].model_copy(update=change)}
                    with pytest.raises(ValueError):require_stage_review_runtime(HostTransaction(conn),SCOPE,**bad)
                with pytest.raises(ValueError):require_stage_review_runtime(HostTransaction(conn),TenantScope('dev-org','dev-project'),**args)


def test_started_successor_prevents_old_stage_reapproval():
    with disposable_database() as connect:
        store,run,plan=setup(connect);args=finish(store,run,plan,'portrait')
        store.claim_step(SCOPE,run.id,'diagnosis','next-worker',lease_seconds=60)
        with connect(SCOPE) as conn:
            with pytest.raises(ValueError,match='successor already started'):require_stage_review_runtime(HostTransaction(conn),SCOPE,**args)


def test_missing_checkpoint_is_not_inferred_from_step_success():
    with disposable_database() as connect:
        store,run,plan=setup(connect);args=finish(store,run,plan,'portrait')
        with connect(SCOPE) as conn:
            class Missing:
                def execute(self,sql,params=None):
                    if 'SELECT * FROM aip_checkpoint' in sql:
                        from types import SimpleNamespace
                        return SimpleNamespace(fetchone=lambda:None)
                    return conn.execute(sql,params)
            with pytest.raises(ValueError,match='checkpoint missing'):require_stage_review_runtime(HostTransaction(Missing()),SCOPE,**args)


@pytest.mark.parametrize('step',['solution-design','solution_design'])
def test_solution_stage_preserves_exact_runtime_spelling(step):
    from test_ecommerce_analyst_stage_decision import decision,ref
    from test_aip_business_investigation_eval import request
    from aos_api.aip_business_investigation_eval import BusinessInvestigationStageEvalRequest
    item=decision(stage='solution-design',subject_ref=ref('GrowthPlanRevision','plan'),
        stage_attempt_ref=dict(resourceType='StepRunAttempt',runId='run',stepKey=step,stepRunId='step',attempt=1,inputHash='b'*64))
    assert item.stage_attempt_ref.step_key==step
    original=request().model_dump(mode='python')
    original.update(stage='solution_design',stage_attempt_ref=item.stage_attempt_ref)
    assert BusinessInvestigationStageEvalRequest(**original).stage_attempt_ref.step_key==step
    original['stage']='portrait'
    with pytest.raises(ValueError):BusinessInvestigationStageEvalRequest(**original)


def test_diagnosis_without_completed_portrait_is_not_reviewable():
    with disposable_database() as connect:
        store,run,plan=setup(connect)
        args=finish(store,run,plan,'diagnosis')
        with connect(SCOPE) as conn:
            with pytest.raises(ValueError,match='latest stage completion'):require_stage_review_runtime(HostTransaction(conn),SCOPE,**args)
