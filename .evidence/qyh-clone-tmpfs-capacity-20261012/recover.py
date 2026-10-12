"""Recover a confirmed terminal test-only cluster with a larger tmpfs limit."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PREVIOUS = ROOT / '.evidence/aos-colima-data-expansion-20261012'
ORIGINAL = 'qyh-source-boundary-clone-20261011'
FAILED = ORIGINAL + '-recovered-20261012'
NEW = 'qyh-source-boundary-clone-capacity-20261012'
DOCKER = ['docker', '--context', 'colima-aos-extension']


def main():
    assert not (OUT / 'recovery-create-intent.json').exists(), 'Reconcile existing recovery before retry'
    failed = json.loads(subprocess.check_output(DOCKER + ['inspect', FAILED]))[0]
    assert not failed['State']['Running'] and failed['State']['Pid'] == 0
    original = json.loads((PREVIOUS / 'private' / (ORIGINAL + '-full-inspect.json')).read_text())[0]
    backup = json.loads((PREVIOUS / (ORIGINAL + '-backup.json')).read_text())
    archive = PREVIOUS / 'private' / (ORIGINAL + '.tar')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == backup['sha256']
    spec = importlib.util.spec_from_file_location('loader', PREVIOUS / 'load_physical.py')
    lib = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lib)
    lib.OUT = OUT
    config = dict(original['Config'])
    host = dict(original['HostConfig'])
    config['Image'] = original['Image']
    config['Entrypoint'] = ['sh', '-c', '''set -eu
test ! -e "$PGDATA/PG_VERSION"
i=0
while [ ! -f /bootstrap/ready ]; do i=$((i+1)); [ "$i" -lt 1800 ] || exit 70; sleep 1; done
pg_verifybackup "$PGDATA"
chown -R postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"
exec docker-entrypoint.sh "$@"
''', 'physical-capacity-recovery']
    config['AttachStdin'] = config['AttachStdout'] = config['AttachStderr'] = False
    config['OpenStdin'] = False
    host['Tmpfs'] = {'/var/lib/postgresql/data': 'rw,nosuid,size=1g', '/bootstrap': 'rw,nosuid,size=16m'}
    assert host['PortBindings'] == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18431'}]}
    private = OUT / 'private'
    private.mkdir(mode=0o700)
    log = private / 'recovery.log'
    fd = os.open(log, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    created = lib.action('recovery', 'create', lambda: lib.api('POST', '/containers/create?name=' + NEW, {**config, 'HostConfig': host}))
    cid = created['Id']
    lib.save('recovery-container.json', {'name': NEW, 'containerId': cid, 'failedContainerRetained': failed['Id'], 'archiveSHA256': backup['sha256']})
    lib.action('recovery', 'start', lambda: lib.api('POST', '/containers/' + cid + '/start'))
    with archive.open('rb') as stream:
        lib.action('recovery', 'upload', lambda: lib.exec_private(NEW, log, ['tar', '-xf', '-', '-C', '/var/lib/postgresql/data'], stream))
    lib.action('recovery', 'ready', lambda: lib.exec_private(NEW, log, ['touch', '/bootstrap/ready']))
    meta = None
    for _ in range(60):
        assert lib.api('GET', '/containers/' + cid + '/json')['State']['Running']
        result = subprocess.run(DOCKER + ['exec', NEW, 'psql', '-X', '-qAt', '-U', 'aos_app', '-d', 'postgres', '-c',
            "BEGIN READ ONLY; SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'databases',(SELECT json_agg(datname ORDER BY datname) FROM pg_database WHERE NOT datistemplate)); COMMIT;"], capture_output=True, text=True)
        if result.returncode == 0:
            meta = json.loads(result.stdout.strip())
            break
        time.sleep(1)
    assert meta and meta['cluster'] == backup['cluster'] and meta['databases'] == backup['databases']
    current = lib.api('GET', '/containers/' + cid + '/json')
    assert current['Config']['Env'] == original['Config']['Env'] and current['Image'] == original['Image']
    assert current['HostConfig']['PortBindings'] == host['PortBindings']
    lib.save('result.json', {'currentName': NEW, 'currentId': cid, 'failedContainerRetained': failed['Id'],
        'cluster': meta['cluster'], 'originalDatabaseSetExact': True, 'tmpfsLimitGiB': 1,
        'imageEnvironmentPortPreserved': True, 'nativeManifestWalAndRecoveryPassed': True,
        'failedTestFixtureChangesNotRecovered': True, 'realSourceVolumeUntouched': True})
    print(json.dumps({'experimentalClusterRecovered': True, 'tmpfsLimitGiB': 1, 'originalClusterPreserved': True}), flush=True)


if __name__ == '__main__':
    main()
