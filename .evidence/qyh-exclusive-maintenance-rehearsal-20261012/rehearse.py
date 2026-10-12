"""Native maintenance fence exercise in one new, isolated database only."""
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
DOCKER = ['docker', '--context', 'colima-aos-extension']
LAB = 'qyh-current159-exact-restore-20261012'
DB = 'qyh_exclusive_window_20261012'
TEMPLATE = 'qyh_current159_full_restore_r2_20261012'
CID = '3fb59cb46c8daeb402caee95bf9f2d9aefbb3aa42d87988811afe29418790687'


def record(name, value):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)


def execute(query, database='postgres'):
    return subprocess.check_output(DOCKER + ['exec', '-i', LAB, 'psql', '-X',
        '-qAt', '-v', 'ON_ERROR_STOP=1', '-U', 'aos_app', '-d', database],
        input=query, text=True, timeout=30).strip()


def window_admissible():
    counts = json.loads(execute("SELECT json_build_object('clients',"
        f"(SELECT count(*) FROM pg_stat_activity WHERE datname='{DB}'),"
        "'prepared',(SELECT count(*) FROM pg_prepared_xacts));"))
    return counts['clients'] == 0 and counts['prepared'] == 0, counts


def read_hba(path):
    return subprocess.check_output(DOCKER + ['exec', LAB, 'cat', path], timeout=10)


def replace_hba(path, content):
    # Preserve file ownership/mode; bytes never pass through command arguments.
    subprocess.run(DOCKER + ['exec', '-i', LAB, 'sh', '-c', 'cat > "$1"',
        'qyh-hba-write', path], input=content, check=True, timeout=10)
    assert read_hba(path) == content
    assert execute('SELECT pg_reload_conf();') == 't'
    assert execute('SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL;') == '0'


def main():
    assert not (OUT / 'intent.json').exists(), 'Existing intent: reconcile; never replay'
    meta = json.loads(subprocess.check_output(DOCKER + ['inspect', '--format',
        '{"id":{{json .Id}},"network":{{json .HostConfig.NetworkMode}},'
        '"ports":{{json .NetworkSettings.Ports}},"mounts":{{json .Mounts}}}', LAB], text=True))
    assert meta['id'] == CID and meta['network'] == 'none'
    assert not any(meta['ports'].values())
    assert [m['Name'] for m in meta['mounts']] == ['aos-qyh-current159-exact-restore-20261012']
    assert execute('SELECT version_num FROM alembic_version;', TEMPLATE) == 'a0v_159'
    assert execute(f"SELECT count(*) FROM pg_database WHERE datname='{DB}';") == '0'
    assert execute("SELECT rolsuper FROM pg_roles WHERE rolname='aos_app';") == 't'
    spec = importlib.util.spec_from_file_location('backup_readonly',
        ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/backup_restore.py')
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    source_before = native.source_fingerprint()
    native.current_sql = lambda q: execute('BEGIN READ ONLY; ' + q + ' COMMIT;', TEMPLATE)
    template_before = native.source_fingerprint()
    hba = execute('SHOW hba_file;')
    original = read_hba(hba)
    record('intent.json', {'containerId': CID, 'newDatabase': DB,
        'templateDatabase': TEMPLATE, 'originalHbaSHA256': hashlib.sha256(original).hexdigest(),
        'realSourceWrites': False, 'restartAllowed': False})
    execute(f'CREATE DATABASE "{DB}" TEMPLATE "{TEMPLATE}";')
    holder = subprocess.Popen(DOCKER + ['exec', '-i', LAB, 'psql', '-X', '-qAt',
        '-v', 'ON_ERROR_STOP=1', '-U', 'aos_app', '-d', DB],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        holder.stdin.write('SELECT pg_backend_pid();\n')
        holder.stdin.flush()
        backend_pid = int(holder.stdout.readline().strip())
        allowed, occupied = window_admissible()
        assert not allowed and occupied['clients'] >= 1
    finally:
        holder.stdin.write('\\q\n')
        holder.stdin.flush()
        holder.communicate(timeout=10)
    assert holder.returncode == 0
    allowed, empty = window_admissible()
    assert allowed
    prefix = (f'local {DB} aos_app trust\nlocal {DB} all reject\n'
              f'host {DB} all 0.0.0.0/0 reject\nhost {DB} all ::/0 reject\n').encode()
    denials = []
    try:
        replace_hba(hba, prefix + original)
        for role, transport in [('aos_app', 'tcp'), ('aos_runtime', 'local')]:
            command = DOCKER + ['exec', LAB, 'psql', '-X', '-qAt', '-U', role, '-d', DB]
            if transport == 'tcp':
                command += ['-h', '127.0.0.1']
            result = subprocess.run(command + ['-c', 'SELECT 1'], capture_output=True,
                text=True, timeout=10)
            assert result.returncode != 0 and 'pg_hba.conf rejects connection' in result.stderr
            denials.append({'role': role, 'transport': transport, 'exitCode': result.returncode,
                'nativeHbaRejected': True})
        assert execute('SELECT 1;', DB) == '1'
        assert execute('SELECT version_num FROM alembic_version;', TEMPLATE) == 'a0v_159'
        assert window_admissible()[0]
    finally:
        replace_hba(hba, original)
        record('hba-restoration.json', {'originalSHA256': hashlib.sha256(original).hexdigest(),
            'restoredSHA256': hashlib.sha256(read_hba(hba)).hexdigest(), 'restoredExact': True})
    assert execute('SELECT 1;', DB) == '1'
    assert native.source_fingerprint() == template_before
    # Reset the diagnostic reader to the original real-source read-only helper.
    spec.loader.exec_module(native)
    assert native.source_fingerprint() == source_before
    record('result.json', {'containerId': CID, 'newDatabase': DB,
        'occupiedWindowRefused': occupied, 'testBackendClosed': backend_pid,
        'emptyWindowCounts': empty, 'nativeDenials': denials,
        'localMaintenanceSucceeded': True, 'otherDatabaseStillReadable': True,
        'hbaRestoredExactly': True, 'templateAndRealSource647Unchanged': True,
        'preparedPositiveCaseExercised': False, 'realSourceWindowEstablished': False,
        'realSourceMigration': False, 'restartPerformed': False,
        'formalAuthenticationEstablished': False})
    print('ISOLATED_MAINTENANCE_HBA_NATIVE_REHEARSAL_PASSED')


if __name__ == '__main__':
    main()
