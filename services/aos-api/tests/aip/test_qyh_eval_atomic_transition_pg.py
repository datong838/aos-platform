"""Native transaction composition of original Run CAS, not Skill execution."""
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier

import pytest
import psycopg
from psycopg.conninfo import conninfo_to_dict

from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityConflict, AipEvalAuthorityNotFound,
    AipEvalAuthorityTransitionBlocked,
)
from aos_api.aip_eval_contracts import EvalRunStatus
from aos_api.tenant_scope import TenantScope
from test_aip_eval_authority_store import authority_store, _event, _run

SCOPE = TenantScope('org-org', 'dev-project')
CANARY = TenantScope('dev-org', 'dev-project')


@pytest.fixture
def prepared(authority_store):
    parts = conninfo_to_dict(os.environ['AOS_DATABASE_URL'])
    assert (parts['host'], parts['port']) == ('127.0.0.1', '18431')
    assert parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')
    store, connect = authority_store
    with connect(SCOPE) as conn:
        assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == '7695416748450308141'
        conn.execute('INSERT INTO twa_workspace VALUES (%s,%s),(%s,%s)', (*SCOPE.key, *CANARY.key))
        conn.commit()
    store.create_eval_run(SCOPE, _run(SCOPE), _event(SCOPE, event_id='initial', sequence=1,
                          from_status=None, to_status=EvalRunStatus.QUEUED))
    return store, connect


def running(scope=SCOPE, *, event_id='running', sequence=2):
    return _event(scope, event_id=event_id, sequence=sequence,
                  from_status=EvalRunStatus.QUEUED, to_status=EvalRunStatus.RUNNING)


def snapshot(connect):
    with connect(SCOPE) as conn:
        return conn.execute('SELECT status,version FROM aip_eval_run WHERE org_id=%s AND project_id=%s', SCOPE.key).fetchone(), conn.execute('SELECT count(*) AS n FROM aip_eval_run_event').fetchone()['n']


def test_late_failure_rolls_back_run_and_event(prepared):
    store, connect = prepared
    before = snapshot(connect)
    with pytest.raises(RuntimeError, match='late proof failure'):
        with connect(SCOPE) as conn:
            result = store._transition_eval_run_with_connection(conn, SCOPE, running(), expected_version=1)
            assert result.status is EvalRunStatus.RUNNING and result.version == 2
            assert snapshot(connect) == before, 'helper committed before caller completed'
            raise RuntimeError('late proof failure')
    assert snapshot(connect) == before


def test_caller_commit_persists_run_and_event_together(prepared):
    store, connect = prepared
    with connect(SCOPE) as conn:
        store._transition_eval_run_with_connection(conn, SCOPE, running(), expected_version=1)
        assert snapshot(connect) == ({'status': 'queued', 'version': 1}, 1)
        conn.commit()
    assert snapshot(connect) == ({'status': 'running', 'version': 2}, 2)


def test_server_rejects_late_write_and_rolls_back_transition(prepared):
    store, connect = prepared
    before = snapshot(connect)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with connect(SCOPE) as conn:
            store._transition_eval_run_with_connection(conn, SCOPE, running(), expected_version=1)
            conn.execute('INSERT INTO aip_eval_run_event SELECT * FROM aip_eval_run_event WHERE event_id=%s', ('initial',))
    assert snapshot(connect) == before


def test_autocommit_connection_cannot_split_event_and_run(prepared):
    store, connect = prepared
    before = snapshot(connect)
    with connect(SCOPE) as conn:
        conn.commit()
        conn.autocommit = True
        with pytest.raises(AipEvalAuthorityConflict, match='caller-owned transaction'):
            store._transition_eval_run_with_connection(conn, SCOPE, running(), expected_version=1)
    assert snapshot(connect) == before


@pytest.mark.parametrize('case', ['version', 'tenant', 'transition', 'sequence'])
def test_original_rejection_gates_preserve_rows(prepared, case):
    store, connect = prepared
    event, scope, version = running(), SCOPE, 1
    expected = AipEvalAuthorityConflict
    if case == 'version':
        version = 2
    elif case == 'tenant':
        scope, event = CANARY, running(CANARY)
        expected = AipEvalAuthorityNotFound
    elif case == 'transition':
        event = event.model_copy(update={'to_status': EvalRunStatus.SUCCEEDED})
        expected = AipEvalAuthorityTransitionBlocked
    else:
        event = running(sequence=3)
    before = snapshot(connect)
    with pytest.raises(expected):
        with connect(scope) as conn:
            store._transition_eval_run_with_connection(conn, scope, event, expected_version=version)
    assert snapshot(connect) == before


def test_two_connections_same_version_have_one_winner(prepared):
    store, connect = prepared
    barrier = Barrier(2)
    def attempt(index):
        with connect(SCOPE) as conn:
            conn.execute("SET LOCAL lock_timeout='5s'")
            barrier.wait(timeout=5)
            try:
                store._transition_eval_run_with_connection(conn, SCOPE,
                    running(event_id=f'running-{index}'), expected_version=1)
            except AipEvalAuthorityConflict:
                conn.rollback()
                return 'conflict'
            conn.commit()
            return 'committed'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, [1, 2])) == ['committed', 'conflict']
    assert snapshot(connect) == ({'status': 'running', 'version': 2}, 2)
