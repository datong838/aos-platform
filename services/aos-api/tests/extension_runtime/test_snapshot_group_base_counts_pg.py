"""Actual canonical projection proof, counted as base objects rather than events."""
import pytest
from test_snapshot_group_projection_owner_pg import (
    database,pytestmark,ledger,owner_case,claim_case,executor_case,group_claim_case,
    journal_case,object_case,projection_case,mutate_store,
)
from test_controlled_snapshot_group_ingress_pg import prepared_case as base_prepared_case
from test_snapshot_group_assessment_owner_pg import assessment_case as base_assessment_case
from aos_api.pipeline_snapshot_group_projection_owner import PipelineSnapshotGroupProjectionOwner
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ecom_consistency_store import EcomConsistencyError


@pytest.fixture
def prepared_case(group_claim_case,monkeypatch,request):
    case=base_prepared_case.__wrapped__(group_claim_case,monkeypatch)
    case[3]['empty']=getattr(request,'param',False)
    return case


@pytest.fixture
def assessment_case(prepared_case):
    from dataclasses import replace
    import json,hashlib
    executor,conn,args,state,owner,ref=base_assessment_case.__wrapped__(prepared_case)
    selections=executor._claims._controls._selections;original=selections._guarded
    controls=executor._claims._controls
    with conn.transaction():
        prior=controls.run_current_snapshot(conn,scope=args['scope'],ref=args['bindings'][1][0],actor=args['actor'],execute=lambda draft,plan:draft)
    def assets(db,item,actor,callback,*,snapshot=False):
        def adapt(plan):
            if item.pipeline_id=='P02-group':
                plan=replace(plan,read_spec=replace(plan.read_spec,object_type='Payment'),
                             defaults=plan.defaults+(('orderId',1),('outTradeNo','fixture'),('payStatus',1),('pay_duration_min',0)))
            return callback(plan if snapshot else plan.read_spec)
        return original(db,item,actor,adapt,snapshot=True)
    selections._guarded=assets
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
    from test_pipeline_source_selection_owner_pg import approve
    from test_pipeline_runtime_control_owner_pg import append
    changed=prior.model_copy(update={'mapping_ref':prior.mapping_ref.model_copy(update={'content_hash':'sha256:'+'f'*64})})
    selection=PipelineSourceSelectionDraft.model_validate(changed.model_dump(exclude={'schema_version','source_selection_ref'}))
    selected=approve(conn,selections,selection,'base-counts-payment-selection',prior.source_selection_ref)
    control=append(conn,controls,changed.model_copy(update={'source_selection_ref':selected}),
                   'base-counts-payment-control',args['bindings'][1][0])
    args=args|{'bindings':(args['bindings'][0],(control,args['bindings'][1][1]))}
    # Named normalized Payment fixture includes a derived value; the ORIGINAL
    # derived command/Store/projector create real events and Receipts.
    state['policy_raw']=state['policy_raw'].replace(b'Weapp',b'Payment')
    ref=ref.model_copy(update={'content_hash':'sha256:'+hashlib.sha256(state['policy_raw']).hexdigest()})
    return executor,conn,args,state,owner,ref


@pytest.fixture
def completed_group(object_case):
    executor,conn,args,state=object_case
    executor.execute(**args)
    conn.execute('RESET ROLE')
    conn.execute('ALTER TABLE meta_schedule_run ADD COLUMN IF NOT EXISTS executor_id text, ADD COLUMN IF NOT EXISTS executor_stopped boolean, ADD COLUMN IF NOT EXISTS finished_at timestamptz')
    conn.execute("UPDATE meta_schedule_run SET status='succeeded',executor_id='ec-live-v1',executor_stopped=true,finished_at=clock_timestamp()")
    conn.execute('SET ROLE aos_runtime')
    return executor,conn,args,state,None


def test_base_counts_do_not_count_derived_events_as_objects(projection_case):
    _,conn,call,state,owner=projection_case
    with conn.transaction():before=owner.run_current(conn,**call,execute=lambda x:x)
    with conn.transaction():counts=owner.run_current_base_counts(conn,**call,execute=lambda x:x)
    assert counts.payload['projectionHash']==before.content_hash
    assert all(m['sourceTotal']==m['projectedBaseTotal']==1 for m in counts.payload['members'])
    assert any(len(m['events'])>1 for m in before.payload['members'])
    with conn.transaction():after=owner.run_current(conn,**call,execute=lambda x:x)
    assert before==after and state['calls']==1


@pytest.mark.parametrize('prepared_case',[True],indirect=True)
def test_empty_original_observation_counts_zero(projection_case):
    _,conn,call,_,owner=projection_case
    with conn.transaction():result=owner.run_current_base_counts(conn,**call,execute=lambda x:x)
    assert all(m['sourceTotal']==m['projectedBaseTotal']==m['sourceDeleted']==0 for m in result.payload['members'])


@pytest.mark.parametrize('fault',['output','deferred','base'])
def test_current_guard_protects_count_consumption(projection_case,fault):
    executor,conn,call,_,owner=projection_case
    def consume(current):
        if fault=='output':current.payload['members'][0]['projectedBaseTotal']=999
        if fault=='deferred':return (x for x in [current])
        if fault=='base':mutate_store(executor,call['scope'],"UPDATE ecom_object SET payload_hash=repeat('0',64)")
    with pytest.raises((ValueError,TypeError,IngressJournalConflict,EcomConsistencyError)),conn.transaction():
        owner.run_current_base_counts(conn,**call,execute=consume)
