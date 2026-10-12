"""Original Alembic migration SQL on a clone of the latest fully restored source."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
LAB = 'qyh-current159-exact-restore-20261012'
DB = 'qyh_current160_fresh_rehearsal_20261012'
TEMPLATE = 'qyh_current159_full_restore_r2_20261012'
DOCKER = ['docker', '--context', 'colima-aos-extension']


def save(name, value):
    with (OUT / name).open('x') as stream:
        json.dump(value, stream, indent=2)


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fingerprint(database, helpers):
    native = load('fingerprint_' + database, ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/backup_restore.py')
    native.current_sql = lambda query: helpers.sql(LAB, database, query)
    return native.source_fingerprint()


def main():
    assert not (OUT / 'migration-intent.json').exists(), 'Reconcile previous migration; never replay'
    helpers = load('restore_helpers', ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/restore-r2.py')
    baseline = json.loads((ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/current-baseline.json').read_text())
    assert fingerprint(TEMPLATE, helpers) == baseline
    source = load('true_source', ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/backup_restore.py')
    assert source.source_fingerprint() == baseline
    seq = helpers.sequences(LAB, TEMPLATE)
    private = OUT / 'private'
    private.mkdir(mode=0o700)
    api = ROOT / '.evidence/qyh-head160-restoration-rehearsal-20261012/private/source/services/aos-api'
    migration = api / 'alembic/versions/a0v_160_skill_eval_dispatch_intent.py'
    current = ROOT / 'services/aos-api/alembic/versions/a0v_160_skill_eval_dispatch_intent.py'
    assert migration.read_bytes() == current.read_bytes()
    command = "from alembic.config import Config;from alembic import command;from alembic.script import ScriptDirectory;import io;c=Config('alembic.ini',output_buffer=io.StringIO());c.set_main_option('script_location','alembic');c.set_main_option('sqlalchemy.url','postgresql://localhost/unused');assert ScriptDirectory.from_config(c).get_heads()==['a0v_160'];command.upgrade(c,'a0v_159:a0v_160',sql=True);print(c.output_buffer.getvalue(),end='')"
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'TMPDIR', 'LANG')}
    env.update({'AOS_DOTENV_DISABLED': '1', 'PYTHONPATH': str(api)})
    generated = subprocess.run([str(ROOT / 'services/aos-api/.venv/bin/python'), '-c', command],
                               cwd=api, env=env, capture_output=True)
    assert generated.returncode == 0, 'Original SQL generation failed, no DB change'
    assert generated.stdout.strip().startswith(b'BEGIN;') and generated.stdout.strip().endswith(b'COMMIT;')
    sql_file = private / 'original-159-to160.sql'
    fd = os.open(sql_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(generated.stdout)
    assert helpers.sql(LAB, 'postgres', "SELECT count(*) FROM pg_database WHERE datname='" + DB + "';").strip() == '0'
    save('migration-intent.json', {'database': DB, 'template': TEMPLATE,
        'originalMigrationSHA256': hashlib.sha256(migration.read_bytes()).hexdigest(),
        'originalGeneratedSQLSHA256': hashlib.sha256(generated.stdout).hexdigest(),
        'actualSourceMigrated': False, 'offlineGenerationNativeTransactionalExecution': True})
    subprocess.run(DOCKER + ['exec', LAB, 'createdb', '-U', 'aos_app', '-T', TEMPLATE, '-O', 'aos_app', DB],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert fingerprint(DB, helpers) == baseline
    fd = os.open(private / 'migration.log', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as log, sql_file.open('rb') as input_stream:
        result = subprocess.run(DOCKER + ['exec', '-i', LAB, 'psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1',
            '-U', 'aos_app', '-d', DB], stdin=input_stream, stdout=log, stderr=log)
    save('migration-terminal.json', {'exitCode': result.returncode, 'database': DB})
    assert result.returncode == 0, 'Original migration failed; reconcile owned DB, no replay'
    after = fingerprint(DB, helpers)
    assert {key for key in baseline if baseline[key] != after.get(key)} == {'public.alembic_version'}
    added = set(after) - set(baseline)
    assert added == {'public.aip_skill_eval_intent', 'public.aip_skill_eval_dispatch', 'public.aip_skill_eval_dispatch_observation'}
    assert all(after[key]['rows'] == 0 for key in added)
    assert helpers.sequences(LAB, DB) == seq
    gate = json.loads(helpers.sql(LAB, DB, """SELECT json_build_object(
      'version',(SELECT version_num FROM alembic_version),
      'rls',(SELECT json_agg(json_build_object('table',relname,'enabled',relrowsecurity,'forced',relforcerowsecurity) ORDER BY relname) FROM pg_class WHERE relname IN ('aip_skill_eval_intent','aip_skill_eval_dispatch','aip_skill_eval_dispatch_observation')),
      'writerUnsafe',(SELECT rolcanlogin OR rolinherit OR rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication FROM pg_roles WHERE rolname='aos_aip_eval_writer'),
      'writerRunUpdate',has_table_privilege('aos_aip_eval_writer','aip_eval_run','UPDATE'),
      'runtimeCanSelect',has_table_privilege('aos_runtime','aip_skill_eval_intent','SELECT'),
      'runtimeCanInsert',has_table_privilege('aos_runtime','aip_skill_eval_intent','INSERT'),
      'writerCanUpdateVersion',has_column_privilege('aos_aip_eval_writer','aip_skill_eval_intent','version','UPDATE'),
      'writerCanUpdateIdentity',has_column_privilege('aos_aip_eval_writer','aip_skill_eval_intent','request_hash','UPDATE'));"""))
    assert gate['version'] == 'a0v_160' and len(gate['rls']) == 3
    assert all(row['enabled'] and row['forced'] for row in gate['rls'])
    assert gate['writerUnsafe'] is False and gate['writerRunUpdate'] is False
    assert gate['runtimeCanSelect'] and not gate['runtimeCanInsert']
    assert gate['writerCanUpdateVersion'] and not gate['writerCanUpdateIdentity']
    assert fingerprint(TEMPLATE, helpers) == baseline and source.source_fingerprint() == baseline
    save('result.json', {'originalAlembicGeneratedSQLExecuted': True, 'originalTables': 647,
        'all646OldBusinessTableFingerprintsUnchanged': True, 'original12SequencesUnchanged': True,
        'addedEmptyTables': sorted(added), 'nativeACLAndRoleReadback': gate,
        'fresh159TemplateAndActualSourceUnchanged': True, 'actualSourceMigrated': False,
        'signedPackageAndRuntimeCompatibilityComplete': False, 'eightWorkshopsAccepted': False})
    print(json.dumps({'fresh160RehearsalPassed': True, 'oldBusinessTablesUnchanged': 646,
                      'actualSourceMigrated': False}), flush=True)


if __name__ == '__main__':
    main()
