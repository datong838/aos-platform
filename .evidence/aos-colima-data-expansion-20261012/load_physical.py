"""Supported Docker API restoration into new tmpfs; retain all original containers."""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.parse import quote

OUT = Path(__file__).resolve().parent
DOCKER = ['docker', '--context', 'colima-aos-extension']
SOCKET = '/Users/ddt/.colima/aos-extension/docker.sock'


class UnixHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(SOCKET)


def api(method, path, payload=None):
    conn = UnixHTTP('localhost', timeout=30)
    body = None if payload is None else json.dumps(payload).encode()
    try:
        conn.request(method, path, body=body, headers={'Content-Type': 'application/json'})
        response = conn.getresponse()
        data = response.read()
        assert response.status < 300, 'Docker API action failed; reconcile before retry'
        return json.loads(data) if data else None
    finally:
        conn.close()


def save(name, value):
    with (OUT / name).open('x') as stream:
        json.dump(value, stream, indent=2)


def action(prefix, stage, callback):
    save(prefix + '-' + stage + '-intent.json', {'stage': stage, 'unknownUntilTerminal': True})
    value = callback()
    save(prefix + '-' + stage + '-terminal.json', {'stage': stage, 'returnedSuccessfully': True})
    return value


def exec_private(name, log, args, input_file=None):
    with log.open('ab') as stream:
        result = subprocess.run(DOCKER + ['exec'] + (['-i'] if input_file else []) + [name] + args,
                                stdin=input_file, stdout=stream, stderr=stream)
    assert result.returncode == 0, 'Container transfer failed; inspect retained private log'


def load(probe):
    before = json.loads((OUT / 'before-containers.json').read_text())
    for index, (original_name, frozen) in enumerate(before.items()):
        if not frozen['Tmpfs']:
            continue
        prefix = original_name + ('-load-probe-r2' if probe else '-load-recovered')
        if (OUT / (prefix + '-verified.json')).exists() or (probe and (OUT / (original_name + '-load-probe-verified.json')).exists()):
            continue
        assert not list(OUT.glob(prefix + '-*-intent.json')), 'Reconcile earlier attempt before retry'
        original = json.loads((OUT / 'private' / (original_name + '-full-inspect.json')).read_text())[0]
        assert original['Id'] == frozen['Id']
        validation = json.loads((OUT / (original_name + '-restore-validation.json')).read_text())
        assert validation['nativeManifestAndWalVerified'] and validation['exactOriginalClusterAndDatabases']
        backup = json.loads((OUT / (original_name + '-backup.json')).read_text())
        archive = Path(backup.get('archivePath', OUT / 'private' / (original_name + '.tar')))
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == backup['sha256']
        assert original['Config']['Entrypoint'] == ['docker-entrypoint.sh']
        assert original['Config']['Cmd'] == ['postgres']
        assert original['HostConfig']['Binds'] is None
        assert not original['Config'].get('User')
        env = dict(s.split('=', 1) for s in original['Config']['Env'])
        assert env.get('PGDATA', '/var/lib/postgresql/data') == '/var/lib/postgresql/data'
        role = env['POSTGRES_USER']
        assert all(c.isalnum() or c == '_' for c in role)
        prior = OUT / (original_name + '-backup-r2-intent.json')
        hba = json.loads(prior.read_text()).get('originalHbaPath') if prior.exists() else None
        name = ('aos-physical-loader-probe-r2-20261012-' + str(index)) if probe else original_name + '-recovered-20261012'
        config = dict(original['Config'])
        host = dict(original['HostConfig'])
        config['Image'] = frozen['Image']
        config['Entrypoint'] = ['sh', '-c', '''set -eu
test ! -e "$PGDATA/PG_VERSION"
i=0
while [ ! -f /bootstrap/ready ]; do
  i=$((i+1)); [ "$i" -lt 1800 ] || exit 70; sleep 1
done
pg_verifybackup "$PGDATA"
if [ -f /bootstrap/original-pg_hba.conf ]; then cp /bootstrap/original-pg_hba.conf "$PGDATA/pg_hba.conf"; fi
chown -R postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"
exec docker-entrypoint.sh "$@"
''', 'physical-restore']
        config['AttachStdin'] = config['AttachStdout'] = config['AttachStderr'] = False
        config['OpenStdin'] = False
        host['Tmpfs'] = {**host['Tmpfs'], '/bootstrap': 'rw,nosuid,size=16m'}
        if probe:
            host['NetworkMode'] = 'none'
            host['PortBindings'] = {}
        payload = {**config, 'HostConfig': host}
        log = OUT / 'private' / (prefix + '.log')
        fd = os.open(log, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        created = action(prefix, 'create', lambda: api('POST', '/containers/create?name=' + quote(name), payload))
        cid = created['Id']
        save(prefix + '-container.json', {'originalContainerId': frozen['Id'], 'newContainerId': cid,
                                         'name': name, 'image': frozen['Image'], 'probeOnly': probe})
        action(prefix, 'start', lambda: api('POST', '/containers/' + cid + '/start'))
        with archive.open('rb') as stream:
            action(prefix, 'upload', lambda: exec_private(name, log, ['tar', '-xf', '-', '-C', '/var/lib/postgresql/data'], stream))
        if hba:
            with Path(hba).open('rb') as stream:
                action(prefix, 'original-hba', lambda: exec_private(name, log,
                       ['sh', '-c', 'cat > /bootstrap/original-pg_hba.conf'], stream))
            uploaded = subprocess.check_output(DOCKER + ['exec', name, 'cat', '/bootstrap/original-pg_hba.conf'])
            assert hashlib.sha256(uploaded).hexdigest() == hashlib.sha256(Path(hba).read_bytes()).hexdigest()
        action(prefix, 'ready', lambda: exec_private(name, log, ['touch', '/bootstrap/ready']))
        metadata = None
        for _ in range(60):
            observed = api('GET', '/containers/' + cid + '/json')
            assert observed['State']['Running'], 'Restore process stopped; reconcile before retry'
            result = subprocess.run(DOCKER + ['exec', name, 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1',
                                    '-U', role, '-d', 'postgres', '-c',
                                    "BEGIN READ ONLY; SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'databases',(SELECT json_agg(datname ORDER BY datname) FROM pg_database WHERE NOT datistemplate)); COMMIT;"],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                metadata = json.loads(result.stdout.strip())
                break
            time.sleep(1)
        assert metadata, 'Readback timed out; do not infer terminal or rerun'
        assert metadata['cluster'] == backup['cluster'] and metadata['databases'] == backup['databases']
        observed = api('GET', '/containers/' + cid + '/json')
        assert observed['Image'] == frozen['Image']
        assert observed['Config']['Env'] == original['Config']['Env']
        assert observed['HostConfig']['NetworkMode'] == host['NetworkMode']
        assert observed['HostConfig']['PortBindings'] == host['PortBindings']
        if hba:
            raw = subprocess.check_output(DOCKER + ['exec', name, 'cat', '/var/lib/postgresql/data/pg_hba.conf'])
            assert hashlib.sha256(raw).hexdigest() == hashlib.sha256(Path(hba).read_bytes()).hexdigest()
        if probe:
            action(prefix, 'stop', lambda: api('POST', '/containers/' + cid + '/stop?t=30'))
            assert not api('GET', '/containers/' + cid + '/json')['State']['Running']
        save(prefix + '-verified.json', {'originalContainerId': frozen['Id'], 'newContainerId': cid,
                                        'name': name, 'probeOnly': probe, 'exactClusterAndDatabases': True,
                                        'originalEnvironmentAndAuthenticationPreserved': True,
                                        'originalImageVerified': True, 'normalStopVerified': probe,
                                        'hostPublishedPorts': host['PortBindings'], 'network': host['NetworkMode']})
        print(json.dumps({'container': original_name, 'loaderVerified': True, 'probeOnly': probe}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--recover', action='store_true')
    args = parser.parse_args()
    assert args.probe != args.recover
    if args.recover:
        gate = json.loads((OUT / 'disk-expanded-readback.json').read_text())
        assert gate['dataDiskGiB'] >= 60 and gate['originalVolumeContainersRestored']
    load(args.probe)
