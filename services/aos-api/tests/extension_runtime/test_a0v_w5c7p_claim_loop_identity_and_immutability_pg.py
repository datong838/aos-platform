"""Claim loop identity and historical row guards; no current-grant shortcut."""

from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from aos_api import pipeline_snapshot_claim_context as context
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.tenant_scope import TenantScope


def _loop(monkeypatch):
    conn = object()
    scope = TenantScope('org-org', 'dev-project')
    ref = PipelineExactRef(resource_type='PipelineRuntimeControlRevision',
        resource_id='pipeline-control-00000000-0000-0000-0000-000000000001',
        revision=1, content_hash='sha256:' + 'a' * 64)
    transaction = [(10, '20')]
    monkeypatch.setattr(context, '_transaction_key', lambda value: transaction[0])
    loop = context._ClaimLoop(conn, transaction[0], context.get_ident(), scope,
        'actor', 'group', (('run', ref),), object())
    return loop, conn, scope, ref, transaction


def test_claim_loop_rejects_connection_scope_actor_and_transaction_drift(monkeypatch):
    loop, conn, scope, _, transaction = _loop(monkeypatch)
    loop.check(conn, scope, 'actor')
    for wrong in ((object(), scope, 'actor'),
                  (conn, TenantScope('dev-org', 'dev-project'), 'actor'),
                  (conn, scope, 'other')):
        with pytest.raises(PermissionError):
            loop.check(*wrong)
    transaction[0] = (10, '21')
    with pytest.raises(PermissionError, match='transaction changed'):
        loop.check(conn, scope, 'actor')
    transaction[0] = (10, '20')
    loop.active = False
    with pytest.raises(PermissionError, match='expired'):
        loop.check(conn, scope, 'actor')


def test_claim_loop_rejects_other_thread_and_member(monkeypatch):
    loop, conn, scope, ref, _ = _loop(monkeypatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(PermissionError, match='identity differs'):
            pool.submit(loop.check, conn, scope, 'actor').result(timeout=2)
    token = context._active_loop.set(loop)
    try:
        context._check_source_claim_loop(conn, scope=scope, actor='actor',
            run_id='run', control_ref=ref)
        with pytest.raises(PermissionError, match='member differs'):
            context._check_source_claim_loop(conn, scope=scope, actor='actor',
                run_id='other-run', control_ref=ref)
    finally:
        context._active_loop.reset(token)


def test_original_claim_rows_reject_runtime_and_admin_mutation(prepared_case):
    executor, conn, args, state = prepared_case
    executor.prepare(**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n'] == 2
    run_id = args['bindings'][0][1]
    for operation in ('UPDATE pipeline_controlled_source_claim SET actor=actor WHERE run_id=%s',
                      'DELETE FROM pipeline_controlled_source_claim WHERE run_id=%s'):
        with pytest.raises(psycopg.Error), conn.transaction():
            conn.execute(operation, (run_id,))
    with conn.transaction():
        conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n'] == 0
    conn.execute('RESET ROLE')
    for operation in ('UPDATE pipeline_controlled_source_claim SET actor=actor WHERE run_id=%s',
                      'DELETE FROM pipeline_controlled_source_claim WHERE run_id=%s'):
        with pytest.raises(psycopg.Error), conn.transaction():
            conn.execute(operation, (run_id,))
    conn.execute('SET ROLE aos_runtime')
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n'] == 2
    assert state['calls'] == 1
