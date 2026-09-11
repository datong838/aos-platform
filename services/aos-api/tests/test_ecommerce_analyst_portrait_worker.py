from types import SimpleNamespace
from datetime import timedelta
import os
import pytest
from aos_api.aip_task_store import AipTaskTransitionBlocked,_canonical_hash
from aos_api.ecommerce_analyst_portrait_worker import portrait_stage_attempt_id,require_portrait_stage_lineage,PortraitTaorWorker
from test_ecommerce_analyst_growth_plan_worker import lineage as growth_lineage
from test_aip_taor_observation_recovery import SCOPE


def lineage():
    snapshot,run,_=growth_lineage()
    snapshot.plan.steps[0].assignee_refs=snapshot.plan.steps[-1].assignee_refs
    snapshot.plan.steps[-1].assignee_refs=[]
    snapshot.plan.content_hash=_canonical_hash({'steps':[x.model_dump(mode='json',by_alias=True) for x in snapshot.plan.steps],'dependencies':[],'risk':{}})
    snapshot.steps=[];run.request.skill.asset_id='ecommerce.skill.D01'
    return snapshot,run,SimpleNamespace(attempt_id=portrait_stage_attempt_id(SCOPE,snapshot),attempt_no=1)


def test_exact_first_stage_lineage():
    snapshot,run,command=lineage()
    require_portrait_stage_lineage(SCOPE,snapshot,run,command)


@pytest.mark.parametrize('fault',['tenant','task','run','plan','revision','hash','approval','order','already_done','assignee','instance','skill','attempt','attempt_no'])
def test_lineage_drift_rejected(fault):
    snapshot,run,command=lineage()
    if fault=='tenant':run.tenant.org_id='other'
    if fault=='task':run.task_id='other'
    if fault=='run':run.task_run_id='other'
    if fault=='plan':run.request.plan_ref.resource_id='other'
    if fault=='revision':run.request.plan_ref.revision='2'
    if fault=='hash':snapshot.plan.content_hash='d'*64
    if fault=='approval':snapshot.plan.approval_status='draft'
    if fault=='order':snapshot.plan.steps.reverse()
    if fault=='already_done':snapshot.steps=[dict(step_key='portrait',status='succeeded')]
    if fault=='assignee':run.instance_id='other'
    if fault=='instance':run.instance_version=2
    if fault=='skill':run.request.skill.asset_id='ecommerce.skill.D02'
    if fault=='attempt':command.attempt_id='new'
    if fault=='attempt_no':command.attempt_no=2
    with pytest.raises(AipTaskTransitionBlocked):require_portrait_stage_lineage(SCOPE,snapshot,run,command)


@pytest.mark.skipif(os.getenv('AOS_GROWTH_DRAFT_FULL_GRAPH_TEST')!='1',reason='explicit disposable database')
@pytest.mark.parametrize('outcome',['success','unknown','wrong_source'])
def test_real_scheduler_stops_at_portrait_boundary(monkeypatch,outcome):
    # Real Task/Plan/Run/checkpoint storage; AgentRun, input and generation ports
    # are isolated doubles. This is not full D01 provisioning or Provider proof.
    from aos_api.aip_contracts import PlanStep,ResourceRef
    from aos_api.aip_task_models import CreateTaskRequest,CreatePlanRevisionRequest,CreateTaskRunRequest
    from aos_api.aip_task_store import AipTaskStore
    from aos_api.ecommerce_analyst_authority_store import canonical_hash
    from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
    from aos_api.ecommerce_analyst_portrait_generation import insight_from_completed_generation
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database
    from test_ecommerce_analyst_portrait_service import harness
    from test_ecommerce_analyst_portrait_generation import fixture,completed
    import aos_api.ecommerce_analyst_portrait_worker as module
    _,_,command,_,_=harness(monkeypatch)
    inputs=fixture(monkeypatch);attempt,answer=completed(inputs)
    original=insight_from_completed_generation(attempt=attempt,answer=answer,actor='compiler',**inputs)
    with disposable_database() as connect:
        store=AipTaskStore(connect_factory=connect)
        task=store.create_task(SCOPE,'compiler','portrait-task',CreateTaskRequest(type='analysis',title='Synthetic portrait boundary'))
        steps=[PlanStep(step_key=key,title=key) for key in ('portrait','diagnosis','solution-design')]
        steps[0].assignee_refs=[ResourceRef(resource_type='AgentInstance',resource_id='colleague',revision='1',authority='aip-assignee-directory')]
        plan=store.create_plan(SCOPE,'compiler',task.id,'portrait-plan',CreatePlanRevisionRequest(expected_task_version=task.version,steps=steps))
        task=store.get_task(SCOPE,task.id)
        store.approve_plan(SCOPE,'compiler',task.id,plan.revision,task.version,plan.content_hash)
        task=store.get_task(SCOPE,task.id)
        run=store.create_run(SCOPE,'compiler',task.id,'portrait-run',CreateTaskRunRequest(plan_revision_id=plan.id,expected_task_version=task.version))
        snapshot=store.timeline(SCOPE,run.id)
        store.start_run(SCOPE,run.id,expected_run_version=run.version,expected_task_version=snapshot.task.version,actor='compiler',idempotency_key='portrait-start')
        snapshot=store.timeline(SCOPE,run.id)
        _,agent,_=lineage();agent.agent_run_id='agent-portrait';agent.task_id=task.id;agent.task_run_id=run.id
        agent.request.task_ref.resource_id=task.id;agent.request.plan_ref.resource_id=plan.id
        command.attempt_id=portrait_stage_attempt_id(SCOPE,snapshot)
        command.method_ref=original.method_ref;command.eval_ref=original.eval_ref;command.cutoff_at=original.cutoff_at
        identity=canonical_hash({'tenant':{'orgId':SCOPE.org_id,'projectId':SCOPE.project_id},'attemptId':command.attempt_id})
        saved=original.model_copy(update={'insight_id':'portrait-'+identity[:40]})
        saved=saved.model_copy(update={'content_hash':canonical_hash(saved.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))})
        ref=AnalystExactRef(resourceType='InsightRevision',resourceId=saved.insight_id,revision=1,contentHash=saved.content_hash)
        attempt=attempt.model_copy(update={'agent_run_id':agent.agent_run_id,'attempt_id':command.attempt_id})
        def generate(*args,**kwargs):
            if outcome=='unknown':raise ValueError('unknown Provider result')
            return ref
        worker=PortraitTaorWorker.__new__(PortraitTaorWorker)
        worker._tasks=store;worker._connect=connect;worker._runs=SimpleNamespace(get=lambda *args:agent)
        worker._generation=SimpleNamespace(generate=generate)
        worker._attempts=SimpleNamespace(get=lambda *args:attempt)
        worker._analyst=SimpleNamespace(get_insight_exact=lambda *args:saved if outcome!='wrong_source' else saved.model_copy(update={'method_ref':saved.method_ref.model_copy(update={'content_hash':'d'*64})}))
        monkeypatch.setattr(module,'read_portrait_inputs',lambda **kwargs:inputs)
        def call():return worker.run(SCOPE,run.id,agent.agent_run_id,command,actor='compiler',worker_id='portrait-worker',markings=['internal','secret'],clock=lambda:inputs['now'],max_source_age=timedelta(days=1),max_bytes=10000)
        if outcome=='success':assert call().run.status.value=='running'
        else:
            with pytest.raises(AipTaskTransitionBlocked):call()
        after=store.timeline(SCOPE,run.id)
        assert after.run.status.value=='running'
        assert all(step['step_key']!='diagnosis' for step in after.steps)
        assert len(after.checkpoints)==(1 if outcome=='success' else 0)
