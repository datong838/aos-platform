"""Real isolated Store recovery; source/assets are explicitly named fixtures."""
import pytest
from threading import Event
from time import monotonic
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.tenant_scope import TenantScope
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.pipeline_snapshot_group_completion import PipelineSnapshotGroupCompletion
from aos_api.pipeline_snapshot_group_recovery_runtime import PipelineSnapshotGroupRecoveryRuntime

pytest_plugins=('test_snapshot_group_recovery_owner_pg',)


def runtime_for(runtime,owner):
    return PipelineSnapshotGroupRecoveryRuntime(claims=PipelineSourceClaimOwner(controls=owner._controls),
        store=runtime._completion._store,connect=runtime._completion._connect,
        eng=runtime._completion._retirement._links._objects._single._eng)


def counts(runtime,scope):
    tables=('meta_schedule_run','pipeline_controlled_source_claim','ecom_object','ecom_ingest_receipt',
        'ecommerce_ingress_dataset_receipt','ecom_link')
    with runtime._transaction(scope) as conn:
        return {t:conn.execute('SELECT count(*) AS n FROM public.'+t).fetchone()['n'] for t in tables}


@pytest.mark.parametrize('stopped',[False,True],ids=['running','stopped-failed'])
def test_original_partial_store_commit_recovers_under_new_window_once(recovery_case,monkeypatch,stopped):
    runtime,owner,command,state=recovery_case
    store=runtime._completion._store
    original=store.apply_batch;armed=True
    def lost(command):
        nonlocal armed
        result=original(command)
        if armed:armed=False;raise OSError('named original Store acknowledgement lost')
        return result
    monkeypatch.setattr(store,'apply_batch',lost)
    first=PipelineSnapshotGroupCompletion(claims=PipelineSourceClaimOwner(controls=owner._controls),store=store,
        connect=runtime._completion._connect,eng=runtime._completion._retirement._links._objects._single._eng)
    with runtime._transaction(command['scope']) as conn:
        claim=runtime._claims.read(conn,scope=command['scope'],group_id=command['group_id'])
        definition=runtime._definitions.read(conn,scope=command['scope'],definition_id=command['expected_definition_ref']['resourceId'].removeprefix('snapshot-schedule-'))
    old_pairs=tuple((m['controlRef'],m['runId']) for m in claim['members'])
    with pytest.raises(OSError,match='acknowledgement'):
        first.complete(scope=command['scope'],group_id=command['group_id'],actor=command['actor'],bindings=old_pairs,policy_ref=definition['body']['policyRef'])
    partial=counts(runtime,command['scope'])
    assert partial['ecom_object']==partial['ecom_ingest_receipt']==1 and partial['meta_schedule_run']==12
    monkeypatch.setattr(store,'apply_batch',original)
    with runtime._transaction(command['scope']) as conn:
        if stopped:
            # Named stopped-executor fixture after an original partial Store effect.
            conn.execute("UPDATE public.meta_schedule_run SET status='failed',executor_stopped=true,finished_at=clock_timestamp()")
        receipt=owner.renew(conn,**command)
    call=dict(scope=command['scope'],actor=command['actor'],recovery_ref=receipt['ref'])
    result=runtime_for(runtime,owner).resume_saved(**call)
    assert result['status']=='succeeded' and result['input_replayed'] is True
    before=counts(runtime,command['scope'])
    assert before==dict(meta_schedule_run=12,pipeline_controlled_source_claim=12,ecom_object=12,ecom_ingest_receipt=13,
        ecommerce_ingress_dataset_receipt=12,ecom_link=1)
    with runtime._transaction(command['scope']) as conn:
        assert conn.execute("SELECT count(*) AS n FROM meta_schedule_run WHERE status='succeeded' AND executor_stopped").fetchone()['n']==12
        recovery_claims=conn.execute('SELECT run_id,claim_id,payload_hash FROM ecommerce_ingress_recovery_claim ORDER BY run_id').fetchall()
        assert len(recovery_claims)==(12 if stopped else 0)
    again=runtime_for(runtime,owner).resume_saved(**call)
    assert again['replayed'] is True and again['projection_hash']==result['projection_hash']
    assert again['preparation_hash']==result['preparation_hash'] and counts(runtime,command['scope'])==before
    with runtime._transaction(command['scope']) as conn:
        assert conn.execute('SELECT run_id,claim_id,payload_hash FROM ecommerce_ingress_recovery_claim ORDER BY run_id').fetchall()==recovery_claims
    assert state['calls']==1


@pytest.mark.parametrize('fault',['disabled','actor','stale-ref','failed-unknown','negative-tenant'])
def test_invalid_current_recovery_never_reaches_store(recovery_case,fault):
    runtime,owner,command,state=recovery_case
    with runtime._transaction(command['scope']) as conn:
        receipt=owner.renew(conn,**command)
        if fault=='disabled':
            runtime._definitions.transition(conn,scope=command['scope'],actor=command['actor'],
                definition_id=receipt['body']['currentDefinitionRef']['resourceId'].removeprefix('snapshot-schedule-'),
                expected_ref=receipt['body']['currentDefinitionRef'],intent='disable',idempotency_key='disable-before-resume')
        if fault=='failed-unknown':
            conn.execute("UPDATE public.meta_schedule_run SET status='failed',executor_stopped=false,finished_at=clock_timestamp()")
    before=counts(runtime,command['scope'])
    call=dict(scope=command['scope'],actor=command['actor'],recovery_ref=receipt['ref'])
    error,message=ValueError,'definition'
    if fault=='actor':call['actor']='another-actor';error,message=PermissionError,'executor'
    if fault=='stale-ref':call['recovery_ref']=dict(receipt['ref'],revision=99);message='receipt'
    if fault=='failed-unknown':error,message=IngressJournalConflict,'MIXED'
    if fault=='negative-tenant':call['scope']=TenantScope('dev-org','dev-project');error,message=LookupError,'receipt'
    with pytest.raises(error,match=message):runtime_for(runtime,owner).resume_saved(**call)
    assert counts(runtime,command['scope'])==before and before['ecom_ingest_receipt']==0
    assert state['calls']==1


def test_cancelled_or_expired_execution_does_not_start_store(recovery_case):
    runtime,owner,command,state=recovery_case
    with runtime._transaction(command['scope']) as conn:receipt=owner.renew(conn,**command)
    call=dict(scope=command['scope'],actor=command['actor'],recovery_ref=receipt['ref'])
    stopped=Event();stopped.set()
    with pytest.raises(IngressJournalConflict,match='CANCELLED'):
        runtime_for(runtime,owner).resume_saved(**call,cancel_event=stopped)
    with pytest.raises(IngressJournalConflict,match='DEADLINE'):
        runtime_for(runtime,owner).resume_saved(**call,deadline=monotonic()-1)
    assert counts(runtime,command['scope'])['ecom_ingest_receipt']==0 and state['calls']==1
