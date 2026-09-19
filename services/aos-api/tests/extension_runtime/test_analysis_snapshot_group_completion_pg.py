"""Original twelve-run completion: Store effects recover, metadata closes atomically."""
import hashlib
import json
from threading import Event

import pytest

from test_analysis_snapshot_native_projection_pg import (
    native_projection_case, private_database, stored, native_claims_case,
    native_input_case, host_case, control_governed, governed, service_case,
    pair, body,
)
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.pipeline_snapshot_group_completion import PipelineSnapshotGroupCompletion


@pytest.fixture
def completion_case(native_projection_case):
    objects, conn, args, state = native_projection_case
    policy = json.loads(state['policy_raw'])
    policy.update(
        schemaVersion='aos.snapshot-relationships/v2',
        retirement=dict(
            mode='present-rows-only', requireCompleteReferences=True,
            rejectNewerThanObservation=True, allowMissingRowDeletion=False,
        ),
    )
    state['policy_raw'] = json.dumps(policy).encode()
    args = args | {'policy_ref': args['policy_ref'].model_copy(update={
        'content_hash': 'sha256:' + hashlib.sha256(state['policy_raw']).hexdigest(),
    })}
    service = PipelineSnapshotGroupCompletion(
        claims=objects._claims,
        store=objects._store,
        connect=objects._single._ingress._connect,
        eng=objects._single._eng,
    )
    return service, conn, args, state


def _run_rows(conn):
    return conn.execute(
        "SELECT id,schedule_id,status,executor_id,executor_stopped,finished_at "
        "FROM meta_schedule_run ORDER BY id"
    ).fetchall()


def test_complete_twelve_runs_atomically_then_read_only_replays(completion_case, monkeypatch):
    service, conn, args, state = completion_case
    result = service.complete(**args)
    rows = _run_rows(conn)
    assert result['status'] == 'succeeded' and result['replayed'] is False
    assert len(result['runs']) == len(rows) == 12
    assert all(row['status'] == 'succeeded' and row['executor_id'] == 'ec-live-v1'
               and row['executor_stopped'] is True and row['finished_at'] is not None for row in rows)
    assert conn.execute("SELECT count(*) AS n FROM meta_schedule WHERE last_run IS NOT NULL").fetchone()['n'] == 12
    before = {table: conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()['n']
              for table in ('ecom_object','ecom_ingest_receipt','projection_outbox',
                            'pipeline_snapshot_group_retirement')}
    schedule_before = conn.execute(
        'SELECT id,last_run,updated_at FROM meta_schedule ORDER BY id'
    ).fetchall()
    monkeypatch.setattr(service._retirement, 'execute',
                        lambda **_: (_ for _ in ()).throw(AssertionError('completed replay executed Store')))
    again = service.complete(**args)
    assert again['status'] == 'succeeded' and again['replayed'] is True
    assert before == {table: conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()['n']
                      for table in before}
    assert conn.execute('SELECT id,last_run,updated_at FROM meta_schedule ORDER BY id').fetchall() == schedule_before
    assert state['calls'] == 1


def test_metadata_failure_rolls_back_all_terminal_rows_and_recovers(completion_case, monkeypatch):
    service, conn, args, state = completion_case
    import aos_api.pipeline_snapshot_group_completion as module
    original = module._persist_schedule_result
    calls = 0
    def fail_sixth(*a, **kw):
        nonlocal calls
        calls += 1
        value = original(*a, **kw)
        if calls == 6:
            raise RuntimeError('sixth terminal write failed')
        return value
    monkeypatch.setattr(module, '_persist_schedule_result', fail_sixth)
    with pytest.raises(RuntimeError, match='sixth terminal write failed'):
        service.complete(**args)
    assert {row['status'] for row in _run_rows(conn)} == {'running'}
    assert conn.execute("SELECT count(*) AS n FROM meta_schedule WHERE last_run IS NOT NULL").fetchone()['n'] == 0
    # Twelve object batches plus the actual Shop -> Weapp relationship batch
    # are independently durable and become the recovery source of truth.
    assert conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n'] == 13
    assert conn.execute('SELECT count(*) AS n FROM ecom_link WHERE deleted_at IS NULL').fetchone()['n'] == 1
    monkeypatch.setattr(module, '_persist_schedule_result', original)
    recovered = service.complete(**args)
    assert recovered['status'] == 'succeeded' and recovered['replayed'] is False
    assert {row['status'] for row in _run_rows(conn)} == {'succeeded'}
    assert state['calls'] == 1


def test_mixed_terminal_state_never_executes_group(completion_case, monkeypatch):
    service, conn, args, state = completion_case
    run_id = args['bindings'][0][1]
    conn.execute(
        "UPDATE meta_schedule_run SET status='succeeded',executor_id='ec-live-v1',"
        "executor_stopped=true,finished_at=clock_timestamp() WHERE id=%s",
        (run_id,),
    )
    called = False
    def execute(**_):
        nonlocal called
        called = True
    monkeypatch.setattr(service._retirement, 'execute', execute)
    with pytest.raises(IngressJournalConflict, match='GROUP_RUN_STATE_MIXED'):
        service.complete(**args)
    assert called is False
    assert conn.execute('SELECT count(*) AS n FROM ecom_object').fetchone()['n'] == 0
    assert state['calls'] == 1


def test_group_advisory_lock_is_fail_closed(completion_case):
    service, _, args, _ = completion_case
    with service._connect() as blocker:
        assert blocker.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS locked",
            (service._lock_key(args['scope'], args['group_id']),),
        ).fetchone()['locked'] is True
        try:
            with pytest.raises(IngressJournalConflict, match='GROUP_COMPLETION_BUSY'):
                service.complete(**args)
        finally:
            blocker.execute(
                "SELECT pg_advisory_unlock(hashtextextended(%s,0))",
                (service._lock_key(args['scope'], args['group_id']),),
            )


def test_lost_attempt_heartbeat_cancels_before_group_store(completion_case, monkeypatch):
    service, conn, args, state = completion_case
    heartbeat_lost = Event()
    heartbeat_lost.set()

    class LostAttempt:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def cancellation(self, caller_event):
            assert caller_event is None
            return heartbeat_lost

    monkeypatch.setattr(service._attempts, 'claim', lambda *_args, **_kwargs: LostAttempt())
    with pytest.raises(IngressJournalConflict, match='INGRESS_CANCELLED'):
        service.complete(**args)

    assert conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n'] == 0
    assert state['calls'] == 1
