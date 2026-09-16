"""Original twelve-source input timestamps, without event-clock alignment.

The real source claim/input Owners and full database schema are exercised;
remote source and installed assets retain the explicit native fixture boundary.
"""
from datetime import timedelta

import pytest

pytest_plugins = ('test_analysis_snapshot_native_ingress_pg',)

from aos_api.pipeline_snapshot_group_locator import PipelineSnapshotGroupLocator
from aos_api.tenant_scope import TenantScope


def test_discovery_preserves_original_time_and_exact_read_contract(native_input_case):
    source, conn, args, state = native_input_case
    source.prepare(**args)
    locator = PipelineSnapshotGroupLocator(claims=source._claims)
    kwargs = dict(scope=args['scope'], run_id=args['bindings'][0][1])
    saved = conn.execute('SELECT read_completed_at FROM pipeline_snapshot_group_input').fetchone()
    before = conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_input').fetchone()['n']
    with source._transaction(args['scope']) as db:
        route = locator.discover(db, **kwargs)
        assert route.group_id == args['group_id']
        assert route.actor == args['actor']
        assert len(route.bindings) == 12
        assert route.read_completed_at == saved['read_completed_at']
        assert locator.read(db, **kwargs, expected_cutoff=route.read_completed_at) == route
        with pytest.raises(ValueError, match='cutoff differs'):
            locator.read(db, **kwargs, expected_cutoff=route.read_completed_at + timedelta(microseconds=1))
        with pytest.raises(ValueError, match='aware original cutoff'):
            locator.read(db, **kwargs, expected_cutoff=None)
        assert locator.discover(db, **kwargs) == route
        assert locator.discover(db, scope=args['scope'], run_id='no-original-group') is None
        with pytest.raises(PermissionError, match='tenant'):
            locator.discover(db, scope=TenantScope('dev-org', 'dev-project'), run_id=kwargs['run_id'])
    with source._transaction(TenantScope('dev-org', 'dev-project')) as db:
        assert locator.discover(db, scope=TenantScope('dev-org', 'dev-project'), run_id=kwargs['run_id']) is None
    assert state['calls'] == 1
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_input').fetchone()['n'] == before


def test_discovery_keeps_runtime_role_boundary(native_input_case):
    source, conn, args, state = native_input_case
    source.prepare(**args)
    locator = PipelineSnapshotGroupLocator(claims=source._claims)
    kwargs = dict(scope=args['scope'], run_id=args['bindings'][0][1])
    with conn.transaction():
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",args['scope'].key)
        with pytest.raises(PermissionError, match='runtime route tenant'):
            locator.discover(conn, **kwargs)
    with source._transaction(args['scope']) as db:
        route = locator.discover(db, **kwargs)
        assert route.manifest_hash.startswith('sha256:')
        assert route.read_started_at <= route.read_completed_at
    assert state['calls'] == 1
