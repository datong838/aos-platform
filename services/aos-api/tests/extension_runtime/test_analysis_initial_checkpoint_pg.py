"""Canonical first-input checkpoint tests; no business stage or model execution."""
from uuid import uuid4
import pytest
from aos_api.db import connect
from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked, AipTaskIdempotencyConflict
from aos_api.aip_task_models import CreateTaskRequest,CreatePlanRevisionRequest,CreateTaskRunRequest,PlanStep
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def initial_run():
    scope=TenantScope('org-org','dev-project')
    with connect() as bootstrap:
        bootstrap.execute("INSERT INTO twa_org(id,name) VALUES('org-org','fixture') ON CONFLICT DO NOTHING")
        bootstrap.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','fixture') ON CONFLICT DO NOTHING")
        bootstrap.commit()
    with connect(scope) as conn:
        tasks=AipTaskStore(TransactionBoundConnectFactory(HostTransaction(conn),scope))
        key='fixture-initial-'+uuid4().hex
        task=tasks.create_task(scope,'fixture',key,CreateTaskRequest(title='initial checkpoint fixture'))
        plan=tasks.create_plan(scope,'fixture',task.id,key+'-plan',CreatePlanRevisionRequest(
            expectedTaskVersion=task.version,steps=[PlanStep(stepKey='portrait',title='portrait not started')]))
        tasks.approve_plan(scope,'fixture',task.id,plan.revision,task.version+1,plan.content_hash)
        run=tasks.create_run(scope,'fixture',task.id,key+'-run',CreateTaskRunRequest(
            planRevisionId=plan.id,expectedTaskVersion=task.version+2))
        started=tasks.start_run(scope,run.id,expected_run_version=run.version,expected_task_version=task.version+2,
            actor='fixture',idempotency_key=key+'-start')
        yield conn,tasks,scope,started,key
        conn.rollback()


def pause(data,**extra):
    _,tasks,scope,started,key=data
    return tasks.pause_run(scope,started.run.id,expected_run_version=started.run.version,
        expected_task_version=started.task.version,actor='fixture',idempotency_key=key+'-pause',
        reason='initial data readiness',checkpoint_before_first_step=True,**extra)


def test_initial_checkpoint_resumes_without_completing_portrait(initial_run):
    conn,tasks,scope,started,key=initial_run
    paused=pause(initial_run)
    assert paused.run.status.value=='paused'
    assert pause(initial_run).run.last_checkpoint_id==paused.run.last_checkpoint_id
    timeline=tasks.timeline(scope,started.run.id)
    assert timeline.steps==[] and timeline.artifacts==[]
    assert len(timeline.checkpoints)==1
    checkpoint=timeline.checkpoints[0]
    assert checkpoint['state_snapshot_ref']['status']=='not-started'
    assert checkpoint['state_snapshot_ref']['kind']=='initial-input'
    assert checkpoint['step_key']=='portrait' and checkpoint['attempt']==1
    resumed=tasks.resume_run(scope,started.run.id,expected_run_version=paused.run.version,
        expected_task_version=paused.task.version,actor='fixture',idempotency_key=key+'-resume')
    assert resumed.run.status.value=='running'
    assert tasks.timeline(scope,started.run.id).steps==[]


def test_initial_checkpoint_and_pause_roll_back_together(initial_run):
    conn,tasks,scope,started,_=initial_run
    with pytest.raises(RuntimeError,match='outer rollback'),conn.transaction():
        assert pause(initial_run).run.last_checkpoint_id
        raise RuntimeError('outer rollback')
    assert tasks.get_run(scope,started.run.id)==started.run
    assert tasks.timeline(scope,started.run.id).checkpoints==[]


def test_initial_and_plain_pause_cannot_share_idempotency_key(initial_run):
    _,tasks,scope,started,key=initial_run
    pause(initial_run)
    with pytest.raises(AipTaskIdempotencyConflict):
        tasks.pause_run(scope,started.run.id,expected_run_version=started.run.version,
            expected_task_version=started.task.version,actor='fixture',idempotency_key=key+'-pause',reason='initial data readiness')


def test_claimed_step_cannot_be_relabelled_as_unexecuted(initial_run):
    _,tasks,scope,started,_=initial_run
    tasks.claim_step(scope,started.run.id,'portrait','fixture-worker',lease_seconds=30)
    with pytest.raises(AipTaskTransitionBlocked,match='unexecuted run'):pause(initial_run)
    assert tasks.get_run(scope,started.run.id).status.value=='running'
    assert tasks.timeline(scope,started.run.id).checkpoints==[]


def test_initial_input_drift_blocks_resume(initial_run):
    from aos_api.aip_task_store import AipTaskVersionConflict
    conn,tasks,scope,started,key=initial_run
    paused=pause(initial_run)
    conn.execute("UPDATE aip_plan_revision SET steps=jsonb_set(steps,'{0,title}',to_jsonb('changed input'::text)) WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s",
        (*scope.key,started.run.plan_revision_id))
    with pytest.raises(AipTaskVersionConflict,match='snapshot drifted'):
        tasks.resume_run(scope,started.run.id,expected_run_version=paused.run.version,
            expected_task_version=paused.task.version,actor='fixture',idempotency_key=key+'-resume')
    assert tasks.get_run(scope,started.run.id).status.value=='paused'
    row=conn.execute('SELECT decision,reason_codes FROM aip_run_resume_decision_revision WHERE org_id=%s AND project_id=%s AND run_id=%s',
        (*scope.key,started.run.id)).fetchone()
    assert row['decision']=='invalidated' and 'CHECKPOINT_INPUT_HASH_DRIFTED' in row['reason_codes']


def test_plain_pause_keeps_existing_no_checkpoint_behavior(initial_run):
    _,tasks,scope,started,key=initial_run
    paused=tasks.pause_run(scope,started.run.id,expected_run_version=started.run.version,
        expected_task_version=started.task.version,actor='fixture',idempotency_key=key+'-plain-pause')
    assert paused.run.last_checkpoint_id is None
    assert tasks.timeline(scope,started.run.id).checkpoints==[]
