"""Real approval routing to the original Runtime; execution is a named seam."""
import pytest
from test_snapshot_schedule_worker_pg import worker_for

pytest_plugins=('test_snapshot_group_recovery_authority_pg',)


def test_formal_recovery_uses_original_receipt_executor_under_same_lock(authority_case,monkeypatch):
    runtime,owner,command,state,receipt,authority,args=authority_case
    worker=worker_for(runtime,command['scope']);other=worker_for(runtime,command['scope'])
    definition=receipt['body']['currentDefinitionRef']['resourceId'].removeprefix('snapshot-schedule-')
    calls=[]
    def finish(**call):
        calls.append(call)
        assert other.run_definition(definition)['status']=='busy'
        # Named completion routing only; C5 holds actual Store evidence.
        with runtime._transaction(command['scope']) as conn:
            conn.execute("UPDATE meta_schedule_run SET status='succeeded',executor_id='ec-live-v1',executor_stopped=true,finished_at=clock_timestamp()")
        return dict(status='succeeded',mode='saved-input-only')
    monkeypatch.setattr(worker._recovery,'resume_saved',finish)
    assert worker.run_definition(definition)['status']=='succeeded'
    assert calls[0]['recovery_ref']==receipt['ref'] and calls[0]['actor']==receipt['body']['executor']
    assert calls[0]['scope']==command['scope']
    assert worker.run_definition(definition)['status'] in ('slot_completed','recovery_only')
    assert len(calls)==1 and state['calls']==1


def test_disabled_recovery_never_enters_runtime(authority_case,monkeypatch):
    runtime,owner,command,state,receipt,authority,args=authority_case
    worker=worker_for(runtime,command['scope'])
    definition=receipt['body']['currentDefinitionRef']['resourceId'].removeprefix('snapshot-schedule-')
    with runtime._transaction(command['scope']) as conn:
        runtime._definitions.transition(conn,scope=command['scope'],definition_id=definition,
            actor=command['actor'],intent='disable',expected_ref=receipt['body']['currentDefinitionRef'],idempotency_key='recovery-worker-stop')
    monkeypatch.setattr(worker._recovery,'resume_saved',lambda **_:pytest.fail('disabled recovery executed'))
    assert worker.run_definition(definition)['status']=='disabled' and state['calls']==1


def test_automatic_recovery_rechecks_persisted_permission_before_store(authority_case,monkeypatch):
    import psycopg
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    runtime,owner,command,state,receipt,authority,args=authority_case
    worker=worker_for(runtime,command['scope'])
    definition=receipt['body']['currentDefinitionRef']['resourceId'].removeprefix('snapshot-schedule-')
    with runtime._connect() as conn:dsn=conn.info.dsn
    # Named isolated administration, not a production identity mutation.
    with psycopg.connect(dsn) as admin:
        admin.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
            (*command['scope'].key,command['actor']))
    monkeypatch.setattr(worker._recovery._store,'apply_batch',lambda *_:pytest.fail('revoked Store access'))
    with pytest.raises(RuntimeConflict,match='membership'):worker.run_definition(definition)
    assert state['calls']==1
