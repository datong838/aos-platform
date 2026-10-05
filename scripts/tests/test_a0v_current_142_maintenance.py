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
