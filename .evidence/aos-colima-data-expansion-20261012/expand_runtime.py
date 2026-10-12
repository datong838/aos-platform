"""One-shot supported capacity maintenance after physical loader probes pass."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
DOCKER = ['docker', '--context', 'colima-aos-extension']


def save(name, value):
    with (OUT / name).open('x') as stream:
        json.dump(value, stream, indent=2)


def inspect(name):
    return json.loads(subprocess.check_output(DOCKER + ['inspect', name]))[0]


def same_mounts(left, right):
    return sorted(left, key=lambda m: m['Destination']) == sorted(right, key=lambda m: m['Destination'])


def command(stage, args):
    save(stage + '-intent.json', {'operation': stage, 'unknownUntilTerminal': True})
    log = OUT / 'private' / (stage + '.log')
    fd = os.open(log, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        result = subprocess.run(args, stdout=stream, stderr=stream)
    save(stage + '-terminal.json', {'exitCode': result.returncode, 'operation': stage})
    assert result.returncode == 0, 'Maintenance action failed; reconcile exact state before retry'


def main():
    assert not (OUT / 'maintenance-stop-window-intent.json').exists(), 'Reconcile prior window before retry'
    before = json.loads((OUT / 'before-containers.json').read_text())
    running = set(subprocess.check_output(DOCKER + ['ps', '--format', '{{.Names}}'], text=True).splitlines())
    assert running == set(before), 'Unregistered active container; do not stop VM'
    for name, r in before.items():
        current = inspect(name)
        assert current['Id'] == r['Id'] and current['State']['Running']
        assert current['Image'] == r['Image'] and same_mounts(current['Mounts'], r['Mounts'])
        if r['Tmpfs']:
            candidates = [OUT / (name + '-load-probe-verified.json'), OUT / (name + '-load-probe-r2-verified.json')]
            verified = json.loads(next(p for p in candidates if p.exists()).read_text())
            assert verified['normalStopVerified'] and verified['exactClusterAndDatabases']
            assert not inspect(verified['name'])['State']['Running']
        env = dict(s.split('=', 1) for s in current['Config']['Env'])
        user = env.get('POSTGRES_USER')
        if not user:
            assert name == 'qyh-restored-pg-20261011'
            user = 'aos_app'  # Original physical recovery container has no initdb environment.
        active = subprocess.check_output(DOCKER + ['exec', name, 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1',
            '-U', user, '-d', 'postgres', '-c',
            "BEGIN READ ONLY; SELECT (SELECT count(*) FROM pg_stat_activity WHERE pid<>pg_backend_pid() AND backend_type='client backend' AND state='active')+(SELECT count(*) FROM pg_prepared_xacts); COMMIT;"], text=True).strip()
        assert active == '0', 'Active database client or prepared transaction; defer stop'
    spec = importlib.util.spec_from_file_location('fresh', ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/backup_restore.py')
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    baseline = json.loads((ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/current-baseline.json').read_text())
    assert fresh.source_fingerprint() == baseline
    backup_root = ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012'
    terminal = json.loads((backup_root / 'backup-terminal.json').read_text())
    for relative in ['private/current.dump', 'private/copy/current.dump']:
        assert hashlib.sha256((backup_root / relative).read_bytes()).hexdigest() == terminal['backupSHA256']
    assert shutil.disk_usage(OUT).free > 45 * 1024**3
    context = subprocess.check_output(['docker', 'context', 'show'], text=True).strip()
    config_path = Path('/Users/ddt/.colima/aos-extension/colima.yaml')
    config_backup = OUT / 'private' / 'colima-before.yaml'
    fd = os.open(config_backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(config_path.read_bytes())
    save('maintenance-stop-window-intent.json', {'existingRunningContainers': sorted(running),
        'source647TableFingerprintsUnchanged': True, 'twoCurrentBackupCopiesSHAEqual': True,
        'allDatabaseActiveClientAndPreparedCountsZero': True, 'physicalLoaderProbes': 7,
        'defaultDockerContextBefore': context, 'volumeDeletionAllowed': False, 'actualSchemaMigration': False})
    for index, name in enumerate(before):
        command('stop-original-' + str(index), DOCKER + ['stop', '--time', '30', name])
        assert not inspect(name)['State']['Running']
    command('stop-colima', ['colima', 'stop', '--profile', 'aos-extension'])
    command('expand-start-colima', ['colima', 'start', '--profile', 'aos-extension', '--disk', '60',
                                   '--cpus', '2', '--memory', '3', '--root-disk', '20', '--activate=false'])
    assert subprocess.check_output(['docker', 'context', 'show'], text=True).strip() == context
    size = int(subprocess.check_output(['colima', 'ssh', '--profile', 'aos-extension', '--',
                                       'lsblk', '-b', '-n', '-o', 'SIZE', '/dev/vdb'], text=True).splitlines()[0].strip())
    assert size >= 60 * 1024**3
    for index, (name, r) in enumerate(before.items()):
        current = inspect(name)
        assert current['Id'] == r['Id'] and current['Image'] == r['Image']
        assert same_mounts(current['Mounts'], r['Mounts'])
        if not r['Tmpfs']:
            command('start-original-volume-' + str(index), DOCKER + ['start', name])
            assert inspect(name)['State']['Running']
        else:
            assert not current['State']['Running']
    save('disk-expanded-readback.json', {'dataDiskGiB': size // 1024**3,
        'originalVolumeContainersRestored': True, 'originalVolumesAndContainerIdsPreserved': True,
        'defaultDockerContextUnchanged': True, 'tmpfsRecoveryPending': True, 'actualSchemaMigration': False})
    print(json.dumps({'dataDiskGiB': size // 1024**3, 'volumeContainersRestarted': True, 'tmpfsRecoveryPending': True}), flush=True)


if __name__ == '__main__':
    main()
