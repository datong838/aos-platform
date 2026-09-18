"""Original failed-run claims share one outer transaction under Completion lock."""
from contextlib import contextmanager
from uuid import uuid4
import pytest
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.pipeline_snapshot_group_completion import PipelineSnapshotGroupCompletion
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner

pytest_plugins=('test_snapshot_group_recovery_authority_pg',)


@pytest.fixture
def stopped_case(authority_case,monkeypatch):
    runtime,owner,command,state,receipt,authority,args=authority_case
    claims=PipelineSourceClaimOwner(controls=owner._controls,recovery=authority,recovery_bindings=args['bindings'])
    def build():
        completion=PipelineSnapshotGroupCompletion(claims=claims,store=runtime._completion._store,
            connect=runtime._completion._connect,eng=runtime._completion._retirement._links._objects._single._eng)
        def stop(**kw):
            with runtime._completion._connect() as other:
                locked=other.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS locked',
                    (completion._lock_key(command['scope'],command['group_id']),)).fetchone()['locked']
                if locked:other.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))',(completion._lock_key(command['scope'],command['group_id']),))
                assert locked is False
            raise RuntimeError('named stop before Store')
        monkeypatch.setattr(completion._retirement,'execute',stop)
        return completion
    with runtime._transaction(command['scope']) as conn:
        conn.execute("UPDATE public.meta_schedule_run SET status='failed',executor_stopped=true,finished_at=clock_timestamp()")
    call=args|dict(group_id=command['group_id'],policy_ref=receipt['body']['policyRef'])
    return runtime,command,state,build,call


def test_all_original_stopped_failed_runs_reopen_atomically(stopped_case):
    runtime,command,state,build,call=stopped_case
    with pytest.raises(RuntimeError,match='before Store'):build().complete(**call)
    with runtime._transaction(command['scope']) as conn:
        assert conn.execute("SELECT count(*) AS n FROM meta_schedule_run WHERE status='running' AND executor_stopped=false AND finished_at IS NULL").fetchone()['n']==12
        assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_recovery_claim').fetchone()['n']==12
        assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==12
        assert conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n']==0
    assert state['calls']==1


def test_recovery_attempt_commits_before_full_saved_recovery_authority(stopped_case,monkeypatch):
    runtime,command,state,build,call=stopped_case
    completion=build()
    completion._retirement.execute=type(completion._retirement).execute.__get__(completion._retirement)
    recovery=completion._claims._recovery

    def stop_after_committed_attempt(*args,**kwargs):
        with runtime._transaction(command['scope']) as conn:
            row=conn.execute("""SELECT state,revision FROM extension_runtime_execution_attempt
                WHERE operation_kind='recoverable_store' ORDER BY accepted_at DESC LIMIT 1""").fetchone()
        assert row=={'state':'running','revision':1}
        raise RuntimeError('named full recovery after committed attempt')

    monkeypatch.setattr(recovery,'run_current',stop_after_committed_attempt)
    with pytest.raises(RuntimeError,match='full recovery after committed attempt'):
        completion.complete(**call)
    with runtime._transaction(command['scope']) as conn:
        assert conn.execute("""SELECT state,revision FROM extension_runtime_execution_attempt
            WHERE operation_kind='recoverable_store'""").fetchone()=={'state':'failed','revision':2}
    assert state['calls']==1


def test_twelfth_recovery_failure_rolls_back_all_original_runs(stopped_case,monkeypatch):
    import aos_api.ec_ingress_claim as module
    runtime,command,state,build,call=stopped_case
    original=module.claim_failed_run;calls=[]
    def fail(*a,**kw):
        calls.append(a[2])
        if len(calls)==12:raise RuntimeError('named last recovery failure')
        return original(*a,**kw)
    monkeypatch.setattr(module,'claim_failed_run',fail)
    with pytest.raises(RuntimeError,match='last recovery'):build().complete(**call)
    with runtime._transaction(command['scope']) as conn:
        assert conn.execute("SELECT count(*) AS n FROM meta_schedule_run WHERE status='failed' AND executor_stopped AND finished_at IS NOT NULL").fetchone()['n']==12
        assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_recovery_claim').fetchone()['n']==0
    assert len(calls)==12 and state['calls']==1


def test_unknown_commit_ack_recovers_original_all_running_state(stopped_case,monkeypatch):
    runtime,command,state,build,call=stopped_case
    completion=build();original=completion._transaction
    @contextmanager
    def lost(scope):
        with original(scope) as conn:yield conn
        raise OSError('named whole recovery commit acknowledgement lost')
    monkeypatch.setattr(completion,'_transaction',lost)
    with pytest.raises(OSError,match='acknowledgement'):completion.complete(**call)
    with runtime._transaction(command['scope']) as conn:
        before=conn.execute('SELECT run_id,claim_id,payload_hash FROM ecommerce_ingress_recovery_claim ORDER BY run_id').fetchall()
        assert before==[]
    # The attempt commit was acknowledged by PostgreSQL but not by the caller.
    # A new executor must observe it as live and never enter Store work.
    with pytest.raises(RuntimeConflict,match='already active'):build().complete(**call)
    with runtime._transaction(command['scope']) as conn:
        assert conn.execute('SELECT run_id,claim_id,payload_hash FROM ecommerce_ingress_recovery_claim ORDER BY run_id').fetchall()==before
        assert conn.execute("SELECT count(*) AS n FROM meta_schedule_run WHERE status='failed' AND executor_stopped").fetchone()['n']==12
        assert conn.execute("SELECT count(*) AS n FROM extension_runtime_execution_attempt WHERE operation_kind='recoverable_store' AND state='running'").fetchone()['n']==1
    assert state['calls']==1


def test_same_approval_cannot_reopen_a_second_failed_attempt(stopped_case):
    runtime,command,state,build,call=stopped_case
    with pytest.raises(RuntimeError,match='before Store'):build().complete(**call)
    with runtime._transaction(command['scope']) as conn:
        conn.execute("UPDATE public.meta_schedule_run SET status='failed',executor_stopped=true,finished_at=clock_timestamp()")
    with pytest.raises(IngressJournalConflict,match='APPROVAL_ALREADY_CONSUMED'):build().complete(**call)
    with runtime._transaction(command['scope']) as conn:
        assert conn.execute("SELECT count(*) AS n FROM meta_schedule_run WHERE status='failed' AND executor_stopped").fetchone()['n']==12
        assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_recovery_claim').fetchone()['n']==12
    assert state['calls']==1


@pytest.mark.parametrize('fault',['unstopped','unfinished','mixed','ordinary'])
def test_unknown_or_non_recovery_instance_cannot_reopen(stopped_case,fault):
    runtime,command,state,build,call=stopped_case
    completion=build()
    with runtime._transaction(command['scope']) as conn:
        if fault=='unstopped':conn.execute('UPDATE meta_schedule_run SET executor_stopped=false')
        if fault=='unfinished':conn.execute('UPDATE meta_schedule_run SET finished_at=NULL')
        if fault=='mixed':conn.execute("UPDATE meta_schedule_run SET status='running',executor_stopped=false,finished_at=NULL WHERE id=(SELECT min(id) FROM meta_schedule_run)")
    if fault=='ordinary':
        completion=PipelineSnapshotGroupCompletion(claims=PipelineSourceClaimOwner(controls=completion._claims._controls),
            store=completion._store,connect=completion._connect,eng=runtime._completion._retirement._links._objects._single._eng)
    with pytest.raises(IngressJournalConflict,match='MIXED'):completion.complete(**call)
    with runtime._transaction(command['scope']) as conn:
        assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_recovery_claim').fetchone()['n']==0
        assert conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n']==0
    assert state['calls']==1


def test_wrong_group_lock_or_policy_cannot_reopen_original_runs(stopped_case):
    runtime,command,state,build,call=stopped_case
    with pytest.raises(PermissionError,match='fixed original'):
        build().complete(**(call|dict(group_id=str(uuid4()))))
    policy=dict(call['policy_ref']);policy['contentHash']='sha256:'+'0'*64
    with pytest.raises(ValueError,match='policy differs'):
        build().complete(**(call|dict(policy_ref=policy)))
    with runtime._transaction(command['scope']) as conn:
        assert conn.execute("SELECT count(*) AS n FROM meta_schedule_run WHERE status='failed' AND executor_stopped").fetchone()['n']==12
        assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_recovery_claim').fetchone()['n']==0
    assert state['calls']==1
