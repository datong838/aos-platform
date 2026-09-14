"""Locate original PG group membership; never source or installation authority."""
from datetime import datetime, timezone, timedelta
import pytest
from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from aos_api.pipeline_snapshot_group_locator import PipelineSnapshotGroupLocator
from aos_api.tenant_scope import TenantScope


def locate(executor, conn, args, run_id, cutoff):
    with conn.transaction():
        return PipelineSnapshotGroupLocator(claims=executor._claims).read(conn,
            scope=args['scope'], run_id=run_id, expected_cutoff=cutoff)


def test_original_members_find_same_group_and_exact_bindings(prepared_case):
    executor, conn, args, state = prepared_case
    prepared = executor.prepare(**args)
    cutoff = conn.execute('SELECT read_completed_at FROM pipeline_snapshot_group_input').fetchone()['read_completed_at']
    routes = [locate(executor, conn, args, run, cutoff) for _, run in args['bindings']]
    assert routes[0] == routes[1]
    assert routes[0].group_id == args['group_id'] and routes[0].actor == args['actor']
    assert routes[0].bindings == tuple(sorted(args['bindings'], key=lambda pair:pair[0].resource_id))
    assert routes[0].manifest_hash == prepared.manifest_hash
    assert routes[0].read_completed_at == cutoff and state['calls'] == 1


def test_missing_committed_group_never_reads_source(prepared_case):
    executor, conn, args, state = prepared_case
    assert locate(executor, conn, args, args['bindings'][0][1], datetime.now(timezone.utc)) is None
    assert state['calls'] == 0


def test_unknown_run_never_substitutes_recent_group(prepared_case):
    executor, conn, args, state = prepared_case
    executor.prepare(**args)
    assert locate(executor, conn, args, 'missing-run', datetime.now(timezone.utc)) is None
    assert state['calls'] == 1


def test_cutoff_must_match_original_observation(prepared_case):
    executor, conn, args, state = prepared_case
    executor.prepare(**args)
    cutoff = conn.execute('SELECT read_completed_at FROM pipeline_snapshot_group_input').fetchone()['read_completed_at']
    with pytest.raises(ValueError, match='cutoff'):
        locate(executor, conn, args, args['bindings'][0][1], cutoff + timedelta(microseconds=1))
    assert state['calls'] == 1


def test_runtime_tenant_scope_required(prepared_case):
    executor, conn, args, state = prepared_case
    with pytest.raises(PermissionError):
        locate(executor, conn, args | {'scope':TenantScope('dev-org','dev-project')},
            args['bindings'][0][1], datetime.now(timezone.utc))
    assert state['calls'] == 0


@pytest.mark.parametrize('run_id,cutoff', [(' ',datetime.now(timezone.utc)), ('run',datetime(2026,9,14))])
def test_invalid_route_input_rejected(prepared_case, run_id, cutoff):
    executor, conn, args, state = prepared_case
    with pytest.raises(ValueError): locate(executor, conn, args, run_id, cutoff)
    assert state['calls'] == 0


def test_original_unique_run_constraint_rejects_duplicate_member(prepared_case):
    import psycopg
    executor, conn, args, state = prepared_case
    executor.prepare(**args)
    with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
        conn.execute('''INSERT INTO pipeline_snapshot_group_member(org_id,project_id,group_id,ordinal,run_id)
            VALUES(%s,%s,%s,3,%s)''', (*args['scope'].key,args['group_id'],args['bindings'][0][1]))
    assert state['calls'] == 1


@pytest.mark.parametrize('table', ['pipeline_snapshot_group_claim','pipeline_snapshot_group_input'])
def test_corrupted_original_hash_rejected_in_isolated_database(prepared_case, table):
    from psycopg import sql
    from psycopg.types.json import Jsonb
    executor, conn, args, state = prepared_case
    executor.prepare(**args)
    cutoff = conn.execute('SELECT read_completed_at FROM pipeline_snapshot_group_input').fetchone()['read_completed_at']
    # Explicit test-only corruption bypass, never executed on the main database.
    with conn.transaction():
        conn.execute('RESET ROLE')
        conn.execute(sql.SQL('ALTER TABLE {} DISABLE TRIGGER USER').format(sql.Identifier(table)))
        if table.endswith('claim'):
            conn.execute(sql.SQL("UPDATE {} SET binding=jsonb_set(binding,'{{actor}}',%s)").format(sql.Identifier(table)),
                (Jsonb('corrupted-test-actor'),))
        else:
            conn.execute(sql.SQL('UPDATE {} SET manifest_hash=%s').format(sql.Identifier(table)),
                ('sha256:'+'0'*64,))
        conn.execute(sql.SQL('ALTER TABLE {} ENABLE TRIGGER USER').format(sql.Identifier(table)))
        conn.execute('SET ROLE aos_runtime')
    with pytest.raises(ValueError, match='binding differs'):
        locate(executor, conn, args, args['bindings'][0][1], cutoff)
    assert state['calls'] == 1
