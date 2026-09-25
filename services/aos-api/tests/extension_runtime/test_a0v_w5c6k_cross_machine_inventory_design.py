"""No-effect inventory: managed assignment is not all-machine Host liveness."""

import inspect
from pathlib import Path

from aos_api.extension_runtime.runtime_directory import PostgresRuntimeTenantDirectory
from a0v_w5c6j_host_topology_discovery import classify


MIGRATION = (Path(__file__).resolve().parents[2] / 'alembic' / 'versions'
             / 'ar1_003_runtime_host_directory.py')


def _table(sql, name):
    return sql.split(f'CREATE TABLE {name} (', 1)[1].split(');', 1)[0]


def test_managed_directory_has_identity_history_but_no_instance_freshness():
    sql = MIGRATION.read_text()
    identity = _table(sql, 'extension_runtime_host_identity')
    assignment = _table(sql, 'extension_runtime_host_assignment')
    for body in (identity, assignment):
        assert 'revision bigint' in body
        assert 'updated_at timestamptz' in body
        assert 'heartbeat' not in body
        assert 'expires_at' not in body
        assert 'instance_epoch' not in body
    assert 'CREATE TABLE extension_runtime_host_identity_revision' in sql
    assert 'CREATE TABLE extension_runtime_host_assignment_revision' in sql


def test_runtime_directory_returns_scopes_not_live_process_inventory():
    sql = MIGRATION.read_text()
    directory = inspect.getsource(PostgresRuntimeTenantDirectory.read_descriptors)
    assert 'RETURNS TABLE(org_id text, project_id text, assignment_revision bigint)' in sql
    assert 'extension_runtime_read_host_assignments()' in directory
    assert 'RuntimeTenantDescriptor' in directory
    assert 'heartbeat' not in directory
    assert 'process_id' not in directory


def test_zero_known_signals_still_fails_cross_machine_authority():
    result = classify({
        'knownLauncherPids': [],
        'managedDirectory': {'outcome': 'MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY'},
        'databaseSessions': {'knownLoginSessions': 0, 'remoteClientSessions': 0,
                             'unknownClientSessions': 0},
    })
    assert result['topologyComplete'] is False
    assert result['closureAuthorized'] is False
    assert result['reason'] == 'UNMANAGED_OR_OTHER_MACHINE_HOSTS_NOT_EXCLUDED'
