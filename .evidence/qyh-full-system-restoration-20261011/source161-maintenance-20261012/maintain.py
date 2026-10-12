"""Exact preserved-volume maintenance; no automatic replay or service start."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
SOURCE = 'qyh-restored-pg-20261011'
LAB = 'qyh-current159-exact-restore-20261012'
DB = 'aos_meta_head'
CLONE_DB = 'qyh_source161_window_restore_20261012'
DOCKER = ['docker', '--context', 'colima-aos-extension']
ADDED = {'public.aip_skill_eval_intent', 'public.aip_skill_eval_dispatch',
         'public.aip_skill_eval_dispatch_observation'}


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def record(name, value):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def sql(container, database, query):
    return subprocess.check_output(DOCKER + ['exec', '-i', container,
        'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-U', 'aos_app', '-d', database],
        input=query, text=True, timeout=60).strip()


def census():
    return json.loads(sql(SOURCE, 'postgres', "SELECT json_build_object("
        "'clients',(SELECT count(*) FROM pg_stat_activity WHERE datname='aos_meta_head'),"
        "'prepared',(SELECT count(*) FROM pg_prepared_xacts),"
        "'enabled',(SELECT count(*) FROM pg_stat_activity WHERE datname='aos_meta_head' AND state='active'));"))


def window():
    result = census()
    assert result['clients'] == 0 and result['prepared'] == 0, 'Window occupied: do not terminate unknown backends'
    return result


def file_bytes(container, path):
    return subprocess.check_output(DOCKER + ['exec', container, 'cat', path], timeout=10)


def hba_replace(path, expected, replacement):
    assert file_bytes(SOURCE, path) == expected, 'Concurrent HBA change: reconcile'
    subprocess.run(DOCKER + ['exec', '-i', SOURCE, 'sh', '-c', 'cat > "$1"',
        'qyh-maintenance-hba', path], input=replacement, check=True, timeout=10)
    assert file_bytes(SOURCE, path) == replacement
    assert sql(SOURCE, 'postgres', 'SELECT pg_reload_conf();') == 't'
    assert sql(SOURCE, 'postgres', 'SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL;') == '0'


def fingerprints(container, database):
    native = load('readonly_fingerprint', ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/backup_restore.py')
    native.current_sql = lambda query: sql(container, database, 'BEGIN READ ONLY; ' + query + ' COMMIT;')
    return native.source_fingerprint()


def schema(container, database, path):
    result = subprocess.run(DOCKER + ['exec', container, 'pg_dump', '--schema-only',
        '-U', 'aos_app', '-d', database], capture_output=True, timeout=60)
    assert result.returncode == 0, 'Schema dump failed; inspect private diagnostic'
    path.write_bytes(result.stdout)
    path.chmod(0o600)
    return b'\n'.join(line for line in result.stdout.splitlines()
        if not line.startswith((b'\\restrict ', b'\\unrestrict ')))


def catalog(container, database, helpers):
    adapter = type('ReadonlyAdapter', (), {'sql': staticmethod(
        lambda ignored, db, query: helpers.sql(container, db, query))})
    repair = load('original_catalog', ROOT / '.evidence/qyh-current160-fresh-rehearsal-20261012/repair161.py')
    return repair.old_catalog(adapter, database)


def migration(container, database, old, new, statement, private):
    window()
    assert sql(container, database, 'SELECT version_num FROM alembic_version;') == old
    name = ('source' if container == SOURCE else 'clone') + '-' + old + '-' + new
    record(name + '-intent.json', {'container': container, 'database': database,
        'from': old, 'to': new, 'sqlSHA256': hashlib.sha256(statement).hexdigest()})
    with (private / (name + '.log')).open('xb') as log:
        result = subprocess.run(DOCKER + ['exec', '-i', container, 'psql', '-X', '-q',
            '-v', 'ON_ERROR_STOP=1', '-U', 'aos_app', '-d', database],
            input=statement, stdout=log, stderr=log, timeout=120)
    record(name + '-terminal.json', {'exitCode': result.returncode})
    assert result.returncode == 0, 'Migration failed: reconcile terminal/version, never replay'
    assert sql(container, database, 'SELECT version_num FROM alembic_version;') == new


def verify161(container, database, baseline, old_catalog, sequences, roles, helpers):
    current = fingerprints(container, database)
    assert {key for key in baseline if baseline[key] != current.get(key)} == {'public.alembic_version'}
    assert set(current) - set(baseline) == ADDED and all(current[k]['rows'] == 0 for k in ADDED)
    assert catalog(container, database, helpers) == old_catalog
    assert helpers.sequences(container, database) == sequences
    assert helpers.roles(container) == roles
    acl = json.loads(sql(container, database, "SELECT json_agg(json_build_object("
        "'table',relname,'forcedRLS',relforcerowsecurity,'enabledRLS',relrowsecurity,"
        "'runtimeRead',has_table_privilege('aos_runtime',oid,'SELECT'),"
        "'runtimeWrite',has_table_privilege('aos_runtime',oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'),"
        "'writerInsert',has_table_privilege('aos_aip_eval_writer',oid,'INSERT'),"
        "'writerUpdate',has_table_privilege('aos_aip_eval_writer',oid,'UPDATE')) ORDER BY relname) "
        "FROM pg_class WHERE relname IN ('aip_skill_eval_intent','aip_skill_eval_dispatch','aip_skill_eval_dispatch_observation');"))
    assert len(acl) == 3 and all(x['forcedRLS'] and x['enabledRLS'] and x['runtimeRead']
        and not x['runtimeWrite'] and x['writerInsert'] and not x['writerUpdate'] for x in acl)
    assert sql(container, database, "SELECT has_table_privilege('aos_aip_eval_writer','aip_eval_run','UPDATE');") == 'f'
    return acl


def main():
    os.umask(0o077)
    assert not (OUT / 'intent.json').exists(), 'Existing intent: reconcile only'
    helpers = load('restore_helpers', ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/restore-r2.py')
    m = load('memoryctl', ROOT / 'scripts/memory/memoryctl.py')
    sys.modules['memoryctl'] = m
    lease = next(x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id'] == 'qyh-full-system-restoration-20261011')
    assert lease['owner'] == 'codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and lease['status'] == 'ACTIVE'
    assert datetime.fromisoformat(lease['lease_expires_at']) > datetime.now(timezone.utc)
    assert all(p['status'] == 'CURRENT' for p in m.memory_status()['projections'] if p['consistency'] == 'strong')
    for container, cid, volume in [(SOURCE, '84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c', 'aos-qyh-history159-prepared-data-20261011'),
        (LAB, '3fb59cb46c8daeb402caee95bf9f2d9aefbb3aa42d87988811afe29418790687', 'aos-qyh-current159-exact-restore-20261012')]:
        meta = json.loads(subprocess.check_output(DOCKER + ['inspect', '--format',
            '{"id":{{json .Id}},"mounts":{{json .Mounts}},"network":{{json .HostConfig.NetworkMode}}}', container], text=True))
        assert meta['id'] == cid and [x['Name'] for x in meta['mounts']] == [volume]
        if container == LAB:
            assert meta['network'] == 'none'
    assert sql(SOURCE, DB, 'SELECT system_identifier::text FROM pg_control_system();') == '7695302940039200809'
    assert sql(SOURCE, DB, 'SELECT version_num FROM alembic_version;') == 'a0v_159'
    assert sql(LAB, 'postgres', 'SELECT system_identifier::text FROM pg_control_system();') == '7695620413173166120'
    assert sql(SOURCE, DB, 'SELECT count(*) FROM extension_runtime_binding WHERE enabled OR NOT operation_fence;') == '0'
    assert sql(SOURCE, DB, "SELECT count(*) FROM meta_schedule WHERE org_id='org-org' AND project_id='dev-project' AND enabled;") == '0'
    assert sql(LAB, 'postgres', "SELECT count(*) FROM pg_database WHERE datname='" + CLONE_DB + "';") == '0'
    window()
    source = Path(json.loads((OUT.parent / 'latest-producer-source-20261012.json').read_text())['source'])
    for filename in ['a0v_160_skill_eval_dispatch_intent.py', 'a0v_161_skill_dispatch_acl.py']:
        # Current committed migrations must match the frozen startup candidate.
        relative = Path('services/aos-api/alembic/versions') / filename
        if not (source / relative).exists():
            raise ValueError('Exact migration filename must be reconciled before any maintenance')
        assert (source / relative).read_bytes() == (ROOT / relative).read_bytes()
    private = OUT / 'private'
    private.mkdir(mode=0o700)
    statements = []
    env = {k:v for k,v in os.environ.items() if k in ('PATH', 'HOME', 'TMPDIR', 'LANG')}
    env.update({'AOS_DOTENV_DISABLED':'1','PYTHONPATH':str(source / 'services/aos-api')})
    for old, new in [('a0v_159', 'a0v_160'), ('a0v_160', 'a0v_161')]:
        code = "from alembic.config import Config;from alembic import command;from alembic.script import ScriptDirectory;import io;c=Config('alembic.ini',output_buffer=io.StringIO());c.set_main_option('script_location','alembic');c.set_main_option('sqlalchemy.url','postgresql://localhost/unused');assert ScriptDirectory.from_config(c).get_heads()==['a0v_161'];command.upgrade(c,'"+old+":"+new+"',sql=True);print(c.output_buffer.getvalue(),end='')"
        generated = subprocess.run([str(ROOT / 'services/aos-api/.venv/bin/python'), '-c', code],
            cwd=source / 'services/aos-api', env=env, capture_output=True, timeout=30)
        assert generated.returncode == 0
        statement = generated.stdout
        assert statement.strip().startswith(b'BEGIN;') and statement.strip().endswith(b'COMMIT;')
        (private / (old + '-' + new + '.sql')).write_bytes(statement)
        statements.append((old, new, statement))
    baseline = fingerprints(SOURCE, DB)
    assert len(baseline) == 647
    before_schema = schema(SOURCE, DB, private / 'source-before.sql')
    old = catalog(SOURCE, DB, helpers)
    seq = helpers.sequences(SOURCE, DB)
    roles = helpers.roles(SOURCE)
    assert helpers.roles(LAB) == roles
    hba = sql(SOURCE, 'postgres', 'SHOW hba_file;')
    assert hba == '/etc/qyh_pg_hba.conf'
    original = file_bytes(SOURCE, hba)
    (private / 'original-hba').write_bytes(original)
    prefix = b'local aos_meta_head aos_app trust\nlocal aos_meta_head all reject\nhost aos_meta_head all 0.0.0.0/0 reject\nhost aos_meta_head all ::/0 reject\n'
    fenced = prefix + original
    record('intent.json', {'sourceDatabase': DB, 'sourceCluster':'7695302940039200809',
        'restoreDatabase':CLONE_DB,'originalHbaSHA256':hashlib.sha256(original).hexdigest(),
        'sourceMigrationCondition':'fresh independent full restore and exact sequential rehearsal under held fence',
        'serviceRestart':False,'formalExecution':False})
    try:
        hba_replace(hba, original, fenced)
        deny = subprocess.run(DOCKER + ['exec', SOURCE, 'psql', '-X', '-qAt', '-h',
            '127.0.0.1', '-U', 'aos_app', '-d', DB, '-c', 'SELECT 1;'], capture_output=True, timeout=10)
        assert deny.returncode != 0 and b'pg_hba.conf rejects connection' in deny.stderr
        record('window-established.json', {'observedAt':datetime.now(timezone.utc).isoformat(),
            'census':window(),'nativeTcpDenied':True,'controlledLocalMaintenanceOnly':True})
        dump = private / 'current.dump'
        with dump.open('xb') as stream:
            result = subprocess.run(DOCKER + ['exec', SOURCE, 'pg_dump', '-Fc', '-U',
                'aos_app', '-d', DB], stdout=stream, stderr=subprocess.PIPE, timeout=120)
        assert result.returncode == 0
        second = private / 'second-current.dump'
        shutil.copyfile(dump, second)
        digest = hashlib.sha256(dump.read_bytes()).hexdigest()
        assert hashlib.sha256(second.read_bytes()).hexdigest() == digest
        record('backup.json', {'firstSHA256':digest,'secondSHA256':digest,'bytes':dump.stat().st_size})
        globals_dump = subprocess.run(DOCKER + ['exec', SOURCE, 'pg_dumpall', '--globals-only',
            '--no-role-passwords', '-U', 'aos_app'], capture_output=True, timeout=60)
        assert globals_dump.returncode == 0
        (private / 'globals.sql').write_bytes(globals_dump.stdout)
        (private / 'second-globals.sql').write_bytes(globals_dump.stdout)
        record('global-backup.json', {'noRolePasswords':True,
            'firstSHA256':hashlib.sha256(globals_dump.stdout).hexdigest(),
            'secondSHA256':hashlib.sha256((private / 'second-globals.sql').read_bytes()).hexdigest()})
        window()
        record('restore-intent.json', {'database':CLONE_DB,'backupSHA256':digest,'singleTransaction':True})
        sql(LAB, 'postgres', 'CREATE DATABASE "' + CLONE_DB + '";')
        with dump.open('rb') as stream, (private / 'restore.log').open('xb') as log:
            result = subprocess.run(DOCKER + ['exec', '-i', '-e', 'PGOPTIONS=-c session_replication_role=replica',
                LAB, 'pg_restore', '--exit-on-error', '--single-transaction', '-U', 'aos_app', '-d', CLONE_DB],
                stdin=stream, stdout=log, stderr=log, timeout=120)
        record('restore-terminal.json', {'exitCode':result.returncode})
        assert result.returncode == 0
        assert fingerprints(LAB, CLONE_DB) == baseline
        assert schema(LAB, CLONE_DB, private / 'clone-before.sql') == before_schema
        assert helpers.sequences(LAB, CLONE_DB) == seq and helpers.roles(LAB) == roles
        clone_catalog = catalog(LAB, CLONE_DB, helpers)
        for old_revision, new_revision, statement in statements:
            migration(LAB, CLONE_DB, old_revision, new_revision, statement, private)
        clone_acl = verify161(LAB, CLONE_DB, baseline, clone_catalog, seq, roles, helpers)
        record('clone-rehearsal.json', {'full647RestoreExact':True,'sequential160161':True,'acl':clone_acl})
        assert fingerprints(SOURCE, DB) == baseline and file_bytes(SOURCE, hba) == fenced
        for old_revision, new_revision, statement in statements:
            migration(SOURCE, DB, old_revision, new_revision, statement, private)
        source_acl = verify161(SOURCE, DB, baseline, old, seq, roles, helpers)
        window()
        record('source-result.json', {'version':'a0v_161','tableCount':650,'old646BusinessTablesUnchanged':True,
            'old647CatalogAndDefaultsUnchanged':True,'sequencesAndRolesUnchanged':True,'acl':source_acl,
            'actualSourceMigrated':True,'serviceRestarted':False,'eightWorkshopsAccepted':False})
    finally:
        observed = file_bytes(SOURCE, hba)
        assert observed in (original, fenced), 'Unknown HBA edit: do not overwrite'
        if observed == fenced:
            hba_replace(hba, fenced, original)
        record('hba-restored.json', {'originalSHA256':hashlib.sha256(original).hexdigest(),
            'restoredSHA256':hashlib.sha256(file_bytes(SOURCE, hba)).hexdigest(), 'exact':True})
    print('SOURCE_MIGRATION_VERIFIED_NO_SERVICE_OR_BUSINESS_ACTIVATION')


if __name__ == '__main__':
    main()
