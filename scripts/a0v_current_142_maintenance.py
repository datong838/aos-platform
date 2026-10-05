"""Current-142 maintenance executor under construction.

Only mandatory guards and private journal are implemented. No production mutation
entry point is exposed until the complete sequencer has isolated acceptance.
"""
import json
import os
from pathlib import Path


class MaintenanceBlocked(RuntimeError):
    pass


def require(value, reason):
    if not value:
        raise MaintenanceBlocked(reason)


def require_source(item):
    require(item['Name'] == '/aos-a0v-recovery-pg' and item['State']['Running'], 'SOURCE_IDENTITY_DRIFT')
    require(item['Config']['Cmd'] == ['postgres'] and item['Config']['Entrypoint'] == ['docker-entrypoint.sh'], 'SOURCE_COMMAND_DRIFT')
    require(item['HostConfig']['RestartPolicy']['Name'] == 'no'
            and item['HostConfig']['NetworkMode'] == 'bridge', 'SOURCE_RESTART_OR_NETWORK_DRIFT')
    require(item['NetworkSettings']['Ports'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18435'}]}, 'SOURCE_PORT_DRIFT')
    mounts = item['Mounts']
    require(len(mounts) == 2, 'SOURCE_MOUNT_DRIFT')
    data = [m for m in mounts if m['Destination'] == '/var/lib/postgresql/data']
    backup = [m for m in mounts if m['Destination'] == '/backup']
    require(len(data) == 1 and data[0]['Type'] == 'volume'
            and data[0].get('Name') == 'aos-a0v-recovery-pg-data' and data[0]['RW'], 'SOURCE_VOLUME_DRIFT')
    require(len(backup) == 1 and backup[0]['Type'] == 'bind' and not backup[0]['RW']
            and backup[0]['Source'] == '/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/backups', 'SOURCE_BACKUP_MOUNT_DRIFT')


def record_attempt(directory: Path, step: str, evidence: dict):
    require(step in {'stop_clients', 'fence_tcp', 'snapshot_dump', 'independent_restore',
                     'migrate_steps', 'verify', 'restore_tcp', 'restart_clients', 'acceptance'}, 'UNKNOWN_STEP')
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), 'JOURNAL_DIRECTORY_INVALID')
    path = directory / (step + '-attempt.json')
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise MaintenanceBlocked('EXISTING_ATTEMPT_RECONCILE_ONLY') from None
    with os.fdopen(fd, 'w') as handle:
        json.dump(evidence, handle, ensure_ascii=False, indent=2)
        handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
    # Persist the directory entry as well as file contents before any mutation.
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def require_window(*, listen_addresses, tcp_exit, other_clients, prepared):
    require(listen_addresses == '' and type(tcp_exit) is int and tcp_exit > 0, 'TCP_EXECUTION_NOT_FENCED')
    require(other_clients == 0 and prepared == 0, 'EXISTING_EXECUTION_NOT_DRAINED')
