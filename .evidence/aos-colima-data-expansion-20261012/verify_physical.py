"""Verify retained physical archives using the exact original PostgreSQL image."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

OUT = Path(__file__).resolve().parent
DOCKER = ['docker', '--context', 'colima-aos-extension']


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)


def verify():
    before = json.loads((OUT / 'before-containers.json').read_text())
    for index, (name, original) in enumerate(before.items()):
        if not original['Tmpfs']:
            continue
        result_path = OUT / (name + '-restore-validation.json')
        if result_path.exists():
            continue
        intent = OUT / (name + '-restore-validation-r2-intent.json')
        assert not intent.exists(), 'Reconcile existing validation before retry'
        backup = json.loads((OUT / (name + '-backup.json')).read_text())
        archive = Path(backup.get('archivePath', OUT / 'private' / (name + '.tar')))
        assert archive.parent == OUT / 'private'
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == backup['sha256']
        with tarfile.open(archive) as tar:
            for member in tar:
                parts = Path(member.name).parts
                assert not member.name.startswith('/') and '..' not in parts
                assert member.isfile() or member.isdir(), 'Unexpected archive member type'
        previous = OUT / (name + '-backup-r2-intent.json')
        if previous.exists():
            metadata = json.loads(previous.read_text())
        else:
            metadata = json.loads((OUT / (name + '-intent.json')).read_text())
        user = metadata.get('existingMaintenanceRole')
        if not user:
            user = subprocess.check_output(DOCKER + ['exec', name, 'printenv', 'POSTGRES_USER'], text=True).strip()
        assert user and all(c.isalnum() or c == '_' for c in user)
        hba_path = metadata.get('originalHbaPath')
        hba_name = Path(hba_path).name if hba_path else ''
        if hba_path:
            assert Path(hba_path).parent == OUT / 'private'
            assert hashlib.sha256(Path(hba_path).read_bytes()).hexdigest() == metadata['originalHbaSHA256']
        container = 'aos-tmpfs-backup-verify-r2-20261012-' + str(index)
        save(intent, {'container': container, 'originalContainerId': original['Id'],
                      'archiveSHA256': backup['sha256'], 'image': original['Image'],
                      'network': 'none', 'publishedPorts': [], 'runtimeStopIssued': False})
        shell = '''set -eu
tar -xf - -C /verify
pg_verifybackup --ignore=.maintenance-original-hba.conf /verify
if [ -f /verify/.maintenance-original-hba.conf ]; then mv /verify/.maintenance-original-hba.conf /verify/pg_hba.conf; fi
chown -R postgres:postgres /verify
chmod 700 /verify
su postgres -c 'pg_ctl -D /verify -l /tmp/verify.log -o "-c listen_addresses= -c unix_socket_directories=/tmp -c hba_file=/verify/pg_hba.conf -c default_transaction_read_only=on" -w start'
psql -X -qAt -v ON_ERROR_STOP=1 -h /tmp -U "$3" -d postgres -c "BEGIN READ ONLY; SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'databases',(SELECT json_agg(datname ORDER BY datname) FROM pg_database WHERE NOT datistemplate)); COMMIT;"
su postgres -c 'pg_ctl -D /verify -m fast -w stop'
'''
        command = DOCKER + ['run', '-i', '--name', container, '--network', 'none', '--read-only',
                            '--tmpfs', '/verify:rw,nosuid,size=768m', '--tmpfs', '/tmp:rw,nosuid,size=32m',
                            '--entrypoint', 'sh', original['Image'], '-c', shell, 'verify', archive.name, hba_name, user]
        log = OUT / 'private' / (name + '-restore-validation-r2.log')
        fd = os.open(log, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stream, stderr=stream)
            try:
                with tarfile.open(archive) as source, tarfile.open(fileobj=proc.stdin, mode='w|') as target:
                    for member in source:
                        target.addfile(member, source.extractfile(member) if member.isfile() else None)
                    if hba_path:
                        data = Path(hba_path).read_bytes()
                        member = tarfile.TarInfo('.maintenance-original-hba.conf')
                        member.size = len(data)
                        member.mode = 0o600
                        target.addfile(member, io.BytesIO(data))
            finally:
                proc.stdin.close()
                code = proc.wait()
        if code:
            print(json.dumps({'container': name, 'validationFailed': True, 'exitCode': code}), flush=True)
            raise RuntimeError('Native validation failed; reconcile private log, do not stop runtime')
        rows = [json.loads(line) for line in log.read_text().splitlines() if line.startswith('{')]
        assert len(rows) == 1
        assert rows[0]['cluster'] == backup['cluster']
        assert rows[0]['databases'] == backup['databases']
        save(result_path, {'container': name, 'validationContainer': container,
                          'archiveSHA256': backup['sha256'], 'nativeManifestAndWalVerified': True,
                          'physicalRecoveryStartedAndStopped': True, 'exactOriginalClusterAndDatabases': True,
                          'cluster': rows[0]['cluster'], 'runtimeStopIssued': False})
        print(json.dumps({'container': name, 'nativePhysicalRestoreVerified': True}), flush=True)


if __name__ == '__main__':
    verify()
