"""Renew all twelve original controls atomically without another source call."""
from datetime import timedelta
from contextlib import contextmanager
from copy import deepcopy
from uuid import uuid4
import pytest
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.pipeline_snapshot_group_completion import PipelineSnapshotGroupCompletion
from aos_api.pipeline_snapshot_group_recovery_owner import PipelineSnapshotGroupRecoveryOwner
from aos_api.pipeline_snapshot_group_recovery_receipt import read_recovery_receipt

pytest_plugins=('test_snapshot_schedule_runtime_pg',)


@pytest.fixture
def recovery_case(runtime_case,monkeypatch):
    runtime,args,state,*_=runtime_case
    def stop(**kw):raise RuntimeError('named stop after input')
    monkeypatch.setattr(runtime._completion,'complete',stop)
    with pytest.raises(RuntimeError,match='after input'):runtime.execute(**args)
    owner=PipelineSnapshotGroupRecoveryOwner(definitions=runtime._definitions,claims=runtime._claims)
    with runtime._transaction(args['scope']) as conn:
        row=conn.execute('SELECT manifest_hash FROM pipeline_snapshot_group_input WHERE group_id=%s',(args['group_id'],)).fetchone()
        start=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        end=conn.execute("SELECT max((payload->'draft'->>'expiresAt')::timestamptz) AS last FROM pipeline_runtime_control_revision").fetchone()['last']+timedelta(hours=1)
    command=dict(scope=args['scope'],group_id=args['group_id'],actor=args['actor'],
        expected_definition_ref=args['definition_ref'],expected_recovery_ref=None,
        input_manifest_hash=row['manifest_hash'],not_before=start,expires_at=end,idempotency_key='formal-renewal')
    return runtime,owner,command,state


def test_atomic_renewal_replays_original_receipt_without_new_source(recovery_case):
    runtime,owner,command,state=recovery_case
    with runtime._transaction(command['scope']) as conn:
        receipt=owner.renew(conn,**command)
    with runtime._transaction(command['scope']) as conn:
        assert owner.renew(conn,**command)==receipt
        assert read_recovery_receipt(conn,scope=command['scope'],group_id=command['group_id'])==receipt
        assert conn.execute('SELECT count(*) AS n FROM pipeline_runtime_control_revision').fetchone()['n']==24
        assert conn.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n']==12
        assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_recovery_receipt').fetchone()['n']==1
        assert receipt['body']['originalDefinitionRef']==command['expected_definition_ref']
        assert receipt['body']['mode']=='saved-input-only'
        with pytest.raises(ValueError,match='idempotency'):
            owner.renew(conn,**(command|dict(expires_at=command['expires_at']+timedelta(minutes=1))))
        current=runtime._definitions.read(conn,scope=command['scope'],definition_id=receipt['body']['currentDefinitionRef']['resourceId'].removeprefix('snapshot-schedule-'))
        bindings=runtime._definitions._saved_bindings(conn,command['scope'],current['body'])
        with pytest.raises(ValueError,match='recovery-only'),conn.transaction():
            runtime._claims.claim(conn,scope=command['scope'],group_id=str(uuid4()),actor=command['actor'],
                scheduled_for=conn.execute("SELECT date_trunc('minute',clock_timestamp()) AS t").fetchone()['t'],
                trigger='manual',bindings=bindings,definition_ref=current['ref'])
    assert state['calls']==1


def _counts(conn):
    tables=('pipeline_source_selection_revision','pipeline_runtime_control_revision','pipeline_schedule_control_binding',
        'pipeline_snapshot_schedule_definition_revision','pipeline_snapshot_group_recovery_receipt','meta_schedule_run')
    return {table:conn.execute('SELECT count(*) AS n FROM public.'+table).fetchone()['n'] for table in tables}


def test_twelfth_control_failure_rolls_back_every_renewal(recovery_case,monkeypatch):
    runtime,owner,command,state=recovery_case
    original=owner._controls.append;calls=[]
    def fail_last(*a,**kw):
        calls.append(kw['draft'].pipeline_id)
        if len(calls)==12:raise RuntimeError('named twelfth control failure')
        return original(*a,**kw)
    with runtime._transaction(command['scope']) as conn:before=_counts(conn)
    monkeypatch.setattr(owner._controls,'append',fail_last)
    with runtime._transaction(command['scope']) as conn:
        with pytest.raises(RuntimeError,match='twelfth'):owner.renew(conn,**command)
        assert _counts(conn)==before
    assert len(calls)==12 and state['calls']==1


def test_stale_window_cas_and_manager_fail_before_appends(recovery_case):
    runtime,owner,command,state=recovery_case
    wrong=deepcopy(command['expected_definition_ref']);wrong['revision']+=1
    with runtime._transaction(command['scope']) as conn:
        before=_counts(conn)
        cases=[(dict(expected_definition_ref=wrong),ValueError,'predecessor'),
            (dict(expires_at=command['not_before']-timedelta(seconds=1)),ValueError,'window'),
            (dict(actor='not-current-member'),RuntimeConflict,'membership')]
        for update,error,message in cases:
            with pytest.raises(error,match=message):owner.renew(conn,**(command|update))
            assert _counts(conn)==before
    assert state['calls']==1


def test_original_completion_lock_blocks_renewal_without_waiting(recovery_case):
    runtime,owner,command,state=recovery_case
    key=PipelineSnapshotGroupCompletion._lock_key(command['scope'],command['group_id'])
    with runtime._completion._connect() as other:
        other.execute('SELECT pg_advisory_lock(hashtextextended(%s,0))',(key,))
        try:
            with runtime._transaction(command['scope']) as conn:
                before=_counts(conn)
                with pytest.raises(IngressJournalConflict,match='BUSY'):owner.renew(conn,**command)
                assert _counts(conn)==before
        finally:other.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))',(key,))
    assert state['calls']==1


def test_missing_original_input_never_approves_recovery(runtime_case,monkeypatch):
    runtime,args,state,*_=runtime_case
    original=runtime._ingress._transaction
    @contextmanager
    def unknown(scope):
        with original(scope) as conn:yield conn
        raise RuntimeError('named unknown before input')
    monkeypatch.setattr(runtime._ingress,'_transaction',unknown)
    with pytest.raises(RuntimeError,match='before input'):runtime.execute(**args)
    owner=PipelineSnapshotGroupRecoveryOwner(definitions=runtime._definitions,claims=runtime._claims)
    with runtime._transaction(args['scope']) as conn:
        now=conn.execute('SELECT clock_timestamp() AS t').fetchone()['t'];before=_counts(conn)
        with pytest.raises(IngressJournalConflict,match='INPUT_REQUIRED'):
            owner.renew(conn,scope=args['scope'],group_id=args['group_id'],actor=args['actor'],
                expected_definition_ref=args['definition_ref'],expected_recovery_ref=None,input_manifest_hash='sha256:'+'0'*64,
                not_before=now,expires_at=now+timedelta(hours=2),idempotency_key='no-input')
        assert _counts(conn)==before
    assert state['calls']==0


def test_second_renewal_requires_latest_receipt_and_advancing_window(recovery_case):
    runtime,owner,command,state=recovery_case
    with runtime._transaction(command['scope']) as conn:first=owner.renew(conn,**command)
    second=command|dict(expected_definition_ref=first['body']['currentDefinitionRef'],expected_recovery_ref=first['ref'],
        expires_at=command['expires_at']+timedelta(hours=1),idempotency_key='second-formal-renewal')
    with runtime._transaction(command['scope']) as conn:
        before=_counts(conn)
        with pytest.raises(ValueError,match='predecessor'):
            owner.renew(conn,**(second|dict(expected_recovery_ref=None)))
        with pytest.raises(ValueError,match='advance'):
            owner.renew(conn,**(second|dict(expires_at=command['expires_at'])))
        assert _counts(conn)==before
        result=owner.renew(conn,**second)
        assert result['ref']['revision']==2 and result['body']['priorRef']==first['ref']
        assert result['body']['originalDefinitionRef']==command['expected_definition_ref']
        assert conn.execute('SELECT count(*) AS n FROM pipeline_runtime_control_revision').fetchone()['n']==36
        assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==12
    assert state['calls']==1


def test_mixed_or_unknown_run_state_cannot_be_renewed(recovery_case):
    runtime,owner,command,state=recovery_case
    with runtime._transaction(command['scope']) as conn:
        before=_counts(conn)
        for condition in ("executor_stopped=true", "status='failed',executor_stopped=false,finished_at=clock_timestamp()"):
            with pytest.raises(ValueError,match='mixed'),conn.transaction():
                conn.execute('UPDATE public.meta_schedule_run SET '+condition+' WHERE id=(SELECT min(id) FROM public.meta_schedule_run)')
                owner.renew(conn,**command)
            assert _counts(conn)==before
    assert state['calls']==1


def test_all_failed_stopped_runs_can_receive_approval_but_remain_failed(recovery_case):
    runtime,owner,command,state=recovery_case
    with runtime._transaction(command['scope']) as conn:
        conn.execute("UPDATE public.meta_schedule_run SET status='failed',executor_stopped=true,finished_at=clock_timestamp()")
        result=owner.renew(conn,**command)
        assert result['body']['mode']=='saved-input-only'
        assert conn.execute("SELECT count(*) AS n FROM public.meta_schedule_run WHERE status='failed' AND executor_stopped").fetchone()['n']==12
    assert state['calls']==1


def test_other_active_run_prevents_renewal(recovery_case):
    runtime,owner,command,state=recovery_case
    with runtime._transaction(command['scope']) as conn:
        conn.execute("""INSERT INTO public.meta_schedule_run
            (id,org_id,project_id,schedule_id,scheduled_for,trigger,status,started_at)
            SELECT 'named-other-active',org_id,project_id,schedule_id,scheduled_for+interval '1 minute','manual','running',clock_timestamp()
            FROM public.meta_schedule_run ORDER BY id LIMIT 1""")
        before=_counts(conn)
        with pytest.raises(ValueError,match='another active'):owner.renew(conn,**command)
        assert _counts(conn)==before
    assert state['calls']==1


def test_current_mapping_rechecks_original_object_types_before_receipt(recovery_case,monkeypatch):
    runtime,owner,command,state=recovery_case
    original=owner._facts.read
    def changed(*a,**kw):
        facts=deepcopy(original(*a,**kw))
        facts.parents[0]['outputRows'][0]['ot']='WrongType'
        return facts
    monkeypatch.setattr(owner._facts,'read',changed)
    with runtime._transaction(command['scope']) as conn:
        before=_counts(conn)
        with pytest.raises(ValueError,match='object type'):owner.renew(conn,**command)
        assert _counts(conn)==before
    assert state['calls']==1
