"""Fresh full backup of the exact retained Qiyuehui data volume before loading."""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

R = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('qyh_restore_backup', R.parent / 'qyh-org-name-maintenance-20261011/prepare.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
M.DB = 'aos_meta_head'
SOURCE = 'aos-qyh-history159-prepared-20261011'
VOLUME = 'aos-qyh-history159-prepared-data-20261011'
CLUSTER = '7695302940039200809'
PRIVATE = R / 'private'


def record(name, data):
    (R / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def native_identity(container=SOURCE):
    sql = """BEGIN READ ONLY; SELECT json_build_object(
      'cluster',(SELECT system_identifier::text FROM pg_control_system()),
      'database',current_database(),'schema',(SELECT version_num FROM alembic_version),
      'activeOtherConnections',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND state='active' AND pid<>pg_backend_pid()),
      'loginExists',(SELECT count(*) FROM pg_roles WHERE rolname='qyh_restored_api_login'),
      'name',(SELECT name FROM meta_org WHERE id='org-org'),
      'nameUpdatedAt',(SELECT updated_at::text FROM meta_org WHERE id='org-org'),
      'disabledBindings',(SELECT bool_and(NOT enabled AND operation_fence) FROM extension_runtime_binding WHERE org_id='org-org' AND project_id='dev-project'));
      COMMIT;"""
    return json.loads(M.psql(container, M.DB, sql))


if __name__ == '__main__':
    assert not (R / 'volume-backup-intent.json').exists(), 'Existing intent: reconcile only'
    item = json.loads(M.run(['docker', '--context', M.CTX, 'inspect', '--format',
        '{"Id":{{json .Id}},"Image":{{json .Image}},"Mounts":{{json .Mounts}},"Network":{{json .HostConfig.NetworkMode}}}', SOURCE]))
    assert item['Id'] == '9e8e903010304d33a801065e96c38693c9cbdc7687b7fd35a76e2fe8dbb7ae82'
    assert item['Image'] == M.IMAGE and item['Network'] == 'none' and len(item['Mounts']) == 1
    assert item['Mounts'][0]['Name'] == VOLUME and item['Mounts'][0]['Destination'] == '/var/lib/postgresql/data'
    identity = native_identity()
    assert identity['cluster'] == CLUSTER and identity['database'] == M.DB and identity['schema'] == 'a0v_159'
    assert identity['activeOtherConnections'] == 0 and identity['loginExists'] == 0 and identity['disabledBindings'] is True
    before = M.fingerprint(SOURCE)
    baseline = json.loads((R.parent / 'qyh-durable-restoration-preparation-20261011/restored159.json').read_text())
    assert before == baseline and len(before) == 647
    record('volume-before.json', {'docker': item, 'database': identity})
    record('volume-fingerprint-before.json', before)
    record('volume-backup-intent.json', {'source': SOURCE, 'volume': VOLUME, 'cluster': CLUSTER, 'database': M.DB, 'mode': 'full-backup-before-transport-maintenance'})
    PRIVATE.mkdir(mode=0o700)
    for name, args in [('history159.dump', ['pg_dump', '-U', 'aos_app', '-d', M.DB, '-Fc']),
                       ('globals.sql', ['pg_dumpall', '-U', 'aos_app', '--globals-only', '--no-role-passwords']),
                       ('original-pg_hba.conf', ['cat', '/var/lib/postgresql/data/pg_hba.conf']),
                       ('original-postgresql.conf', ['cat', '/var/lib/postgresql/data/postgresql.conf'])]:
        path = PRIVATE / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            result = subprocess.run(['docker', '--context', M.CTX, 'exec', SOURCE] + args,
                                    stdout=stream, stderr=subprocess.PIPE, timeout=180)
            assert result.returncode == 0, 'Backup/config preservation failed; no transport mutation'
    manifest = {}
    for path in sorted(PRIVATE.iterdir()):
        copy = PRIVATE / (path.name + '.second-copy')
        shutil.copyfile(path, copy)
        os.chmod(copy, 0o600)
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        assert hashlib.sha256(copy.read_bytes()).hexdigest() == expected
        manifest[path.name] = {'sha256': expected, 'bytes': path.stat().st_size, 'secondCopyExact': True}
    assert M.fingerprint(SOURCE) == before and native_identity() == identity
    record('volume-backup-terminal.json', {'outcome': 'EXACT647_VOLUME_FRESH_FULL_BACKUP_GREEN', 'tables': 647, 'files': manifest, 'independentSecondSnapshot': False, 'originalRestorationBaselineExact': True})
    print('EXACT647_VOLUME_FRESH_FULL_BACKUP_GREEN')
