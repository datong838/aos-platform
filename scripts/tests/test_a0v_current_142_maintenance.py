"""Mandatory maintenance boundaries; never proves formal current migration."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('maintenance142', Path(__file__).parents[1] / 'a0v_current_142_maintenance.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def source():
    return {'Name': '/aos-a0v-recovery-pg', 'State': {'Running': True},
            'Config': {'Cmd': ['postgres'], 'Entrypoint': ['docker-entrypoint.sh']},
            'HostConfig': {'RestartPolicy': {'Name': 'no'}, 'NetworkMode': 'bridge'},
            'NetworkSettings': {'Ports': {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18435'}]}},
            'Mounts': [{'Type': 'volume', 'Name': 'aos-a0v-recovery-pg-data', 'Destination': '/var/lib/postgresql/data', 'RW': True},
                       {'Type': 'bind', 'Source': '/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/backups', 'Destination': '/backup', 'RW': False}]}


def test_source_allows_original_read_only_backup_mount():
    m.require_source(source())


@pytest.mark.parametrize('drift', ['volume', 'port', 'wildcard', 'restart', 'command', 'backup_writable'])
def test_source_rejects_drift_before_any_service_stop(drift):
    s = source()
    if drift == 'volume': s['Mounts'][0]['Name'] = 'other-volume'
    if drift == 'port': s['NetworkSettings']['Ports']['5432/tcp'][0]['HostPort'] = '18436'
    if drift == 'wildcard': s['NetworkSettings']['Ports']['5432/tcp'][0]['HostIp'] = '0.0.0.0'
    if drift == 'restart': s['HostConfig']['RestartPolicy']['Name'] = 'always'
    if drift == 'command': s['Config']['Cmd'] += ['-c', 'listen_addresses=*']
    if drift == 'backup_writable': s['Mounts'][1]['RW'] = True
    with pytest.raises(m.MaintenanceBlocked): m.require_source(s)


def test_unknown_step_cannot_be_reissued(tmp_path):
    m.record_attempt(tmp_path, 'fence_tcp', {'expected': 'source'})
    with pytest.raises(m.MaintenanceBlocked):
        m.record_attempt(tmp_path, 'fence_tcp', {'expected': 'source'})


def test_zero_connections_is_not_enough_without_tcp_denial():
    with pytest.raises(m.MaintenanceBlocked):
        m.require_window(listen_addresses='*', tcp_exit=0, other_clients=0, prepared=0)


@pytest.mark.parametrize('clients,prepared', [(1, 0), (0, 1)])
def test_window_rejects_existing_execution(clients, prepared):
    with pytest.raises(m.MaintenanceBlocked):
        m.require_window(listen_addresses='', tcp_exit=2, other_clients=clients, prepared=prepared)


@pytest.mark.parametrize('exit_code', [None, -9, True])
def test_window_rejects_missing_or_terminated_tcp_observation(exit_code):
    with pytest.raises(m.MaintenanceBlocked):
        m.require_window(listen_addresses='', tcp_exit=exit_code, other_clients=0, prepared=0)


def test_sequencer_never_advances_or_reissues_failed_migration(tmp_path):
    journal = m.MaintenanceJournal(tmp_path)
    calls = []
    for step in m.STEPS[:4]:
        journal.perform(step, lambda: {'observed': True})
    def failed():
        calls.append('migration')
        raise RuntimeError('actual migration failed')
    with pytest.raises(RuntimeError): journal.perform('migrate_steps', failed)
    with pytest.raises(m.MaintenanceBlocked): journal.perform('restore_tcp', lambda: calls.append('unsafe restore'))
    with pytest.raises(m.MaintenanceBlocked): journal.perform('migrate_steps', failed)
    assert calls == ['migration']


def test_sequencer_rejects_skipping_independent_restore(tmp_path):
    journal = m.MaintenanceJournal(tmp_path)
    for step in m.STEPS[:3]: journal.perform(step, lambda: {'observed': True})
    with pytest.raises(m.MaintenanceBlocked): journal.perform('migrate_steps', lambda: {'version': 'a0v_142'})


def process():
    return {'pid': 10001, 'ppid': 9001, 'uid': 501, 'started': '2026-10-05T00:49:12',
            'argv_sha256': 'a'*64, 'cwd': '/Users/ddt/work/projects/ai_agent/aos-platform',
            'children': [], 'listener_ports': [8080]}


@pytest.mark.parametrize('field,value', [('pid', 10002), ('ppid', 1), ('uid', 0),
    ('started', 'new-process'), ('argv_sha256', 'b'*64), ('cwd', '/tmp'),
    ('children', [101]), ('listener_ports', [8080, 18181])])
def test_process_identity_drift_refuses_candidate(field, value):
    observed = {**process(), field: value}
    with pytest.raises(m.MaintenanceBlocked):
        m.require_process(process(), observed, executor_pid=20001)


def test_process_guard_cannot_target_executor():
    with pytest.raises(m.MaintenanceBlocked):
        m.require_process(process(), process(), executor_pid=10001)


def test_verified_original_leaf_is_read_only_candidate():
    m.require_process(process(), process(), executor_pid=20001)


def maintenance_task():
    return {'task_id': 'current142-formal-resource', 'owner': m.OWNER,
            'base_revision': 'AOS-001329', 'status': 'ACTIVE',
            'lease_expires_at': '2026-10-05T16:00:00+08:00', 'scope': list(m.MAINTENANCE_SCOPES)}


@pytest.mark.parametrize('drift', ['expired', 'wrong_owner', 'missing_database', 'no_live_lease', 'delivered', 'authority_changed'])
def test_formal_task_refuses_stale_or_code_only_permission(drift):
    from datetime import datetime, timezone
    task = maintenance_task(); live = [task.copy()]; delivered = False; revision = 'AOS-001329'
    if drift == 'expired': task['lease_expires_at'] = '2026-10-05T09:00:00+08:00'; live = [task.copy()]
    if drift == 'wrong_owner': task['owner'] = 'old-thread'; live = [task.copy()]
    if drift == 'missing_database': task['scope'] = ['aos-platform/scripts/a0v_current_142_maintenance.py']; live = [task.copy()]
    if drift == 'no_live_lease': live = []
    if drift == 'delivered': delivered = True
    if drift == 'authority_changed': revision = 'AOS-001330'
    with pytest.raises(m.MaintenanceBlocked):
        m.require_maintenance_task(task, live, revision=revision, delivered=delivered,
                                   now=datetime(2026, 10, 5, 2, 5, tzinfo=timezone.utc))


def test_formal_task_accepts_exact_live_resource_lease():
    from datetime import datetime, timezone
    task = maintenance_task()
    m.require_maintenance_task(task, [task.copy()], revision='AOS-001329', delivered=False,
                               now=datetime(2026, 10, 5, 2, 5, tzinfo=timezone.utc))


def test_listen_restore_resets_added_override_when_original_has_none():
    rows = [{'sourcefile': '/var/lib/postgresql/data/postgresql.conf', 'setting': '*', 'applied': True, 'error': None}]
    assert m.listen_restore_statement(rows, effective='*') == 'ALTER SYSTEM RESET listen_addresses'


def test_listen_restore_keeps_original_auto_override():
    rows = [{'sourcefile': '/var/lib/postgresql/data/postgresql.auto.conf', 'setting': '*', 'applied': True, 'error': None}]
    assert m.listen_restore_statement(rows, effective='*') == "ALTER SYSTEM SET listen_addresses = '*'"


def test_listen_restore_rejects_unexpected_effective_configuration():
    with pytest.raises(m.MaintenanceBlocked): m.listen_restore_statement([], effective='localhost')


def test_sequencer_does_not_accept_truncated_done_evidence(tmp_path):
    (tmp_path / 'stop_clients-done.json').write_text('{')
    with pytest.raises(m.MaintenanceBlocked):
        m.MaintenanceJournal(tmp_path).perform('fence_tcp', lambda: {'unsafe': True})


def test_sequencer_does_not_accept_symlink_done_evidence(tmp_path):
    external = tmp_path / 'unrelated.json'; external.write_text('{"observed": true}')
    (tmp_path / 'stop_clients-done.json').symlink_to(external)
    with pytest.raises(m.MaintenanceBlocked):
        m.MaintenanceJournal(tmp_path).perform('fence_tcp', lambda: {'unsafe': True})
