"""Real two-connection races; named source assets do not imply live acceptance."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event
from time import monotonic

import psycopg
from psycopg.rows import dict_row
import pytest

pytest_plugins = ('test_pipeline_snapshot_schedule_service_pg',)


def observe_wait(database, ready, pid, blocker):
    assert ready.wait(5), 'contender failed to enter its real connection'
    deadline = monotonic() + 5
    with psycopg.connect(database, autocommit=True) as observer:
        while monotonic() < deadline:
            blockers = observer.execute('SELECT pg_blocking_pids(%s)', (pid[0],)).fetchone()[0]
            if blocker in blockers:
                return
            Event().wait(.01)
    pytest.fail('no database lock wait observed; serial execution is not race evidence')


@pytest.fixture
def race(service, definition_case, monkeypatch):
    import aos_api.pipeline_schedule_claim as single
    api, command, database, _ = service
    _, owner, args = definition_case
    ready, pid = Event(), []
    @contextmanager
    def connection(scope):
        assert scope == args['scope']
        with api._connection() as db:
            db.execute("SET LOCAL statement_timeout='10s'")
            pid.append(db.info.backend_pid)
            ready.set()
            yield db
    monkeypatch.setattr(single, '_connection', connection)
    return api, command, database, owner, args, single, ready, pid


def test_group_commit_wins_and_waiting_singleton_cannot_create_run(race):
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    api, _, database, owner, args, single, ready, pid = race
    binding = args['bindings'][0]
    def claim():
        with single.schedule_claim_connection(args['scope'], schedule_id=binding.schedule_id, binding=binding):
            pytest.fail('assigned member reached singleton executor')
    with ThreadPoolExecutor(max_workers=1) as pool:
        with api._connection() as db:
            owner.configure(db, **args)
            future = pool.submit(claim)
            observe_wait(database, ready, pid, db.info.backend_pid)
        with pytest.raises(RuntimeConflict, match='group'):
            future.result(timeout=12)
    with psycopg.connect(database, row_factory=dict_row) as db:
        assert db.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_current_member').fetchone()['n'] == 12
        assert db.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n'] == 0


@pytest.mark.parametrize('status,stopped', [('running', True), ('failed', False)])
def test_singleton_commit_wins_and_waiting_configuration_rolls_back(race, status, stopped):
    api, command, database, _, args, single, _, _ = race
    binding = min(args['bindings'], key=lambda b:b.schedule_id)
    ready, pid = Event(), []
    original = api._connection
    @contextmanager
    def contender_connection():
        with original() as db:
            db.execute("SET LOCAL statement_timeout='10s'")
            pid.append(db.info.backend_pid)
            ready.set()
            yield db
    with ThreadPoolExecutor(max_workers=1) as pool:
        with single.schedule_claim_connection(args['scope'], schedule_id=binding.schedule_id, binding=binding) as db:
            db.execute('''INSERT INTO meta_schedule_run
                (id,org_id,project_id,schedule_id,scheduled_for,trigger,status,executor_stopped)
                VALUES('race-original-run',%s,%s,%s,date_trunc('minute',clock_timestamp()),'manual',%s,%s)''',
                (*args['scope'].key, binding.schedule_id, status, stopped))
            # Only the connection factory changes; permission, controls and locks remain original.
            api._connection = contender_connection
            future = pool.submit(api.configure, **command)
            observe_wait(database, ready, pid, db.info.backend_pid)
        with pytest.raises(ValueError, match='active or unknown'):
            future.result(timeout=12)
    with psycopg.connect(database, row_factory=dict_row) as db:
        for table in ('pipeline_snapshot_schedule_definition_revision',
                      'pipeline_snapshot_schedule_definition_head',
                      'pipeline_snapshot_schedule_definition_member',
                      'pipeline_snapshot_schedule_current_member'):
            assert db.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] == 0
        assert db.execute('SELECT count(*) AS n FROM meta_schedule WHERE enabled').fetchone()['n'] == 12
        run = db.execute("SELECT status,executor_stopped FROM meta_schedule_run WHERE id='race-original-run'").fetchone()
        assert run == dict(status=status, executor_stopped=stopped)
        assert db.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n'] == 0
