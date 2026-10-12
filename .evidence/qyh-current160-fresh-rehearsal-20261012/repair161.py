"""Execute committed original 161 SQL on the retained latest-source rehearsal."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
DB = 'qyh_current160_fresh_rehearsal_20261012'
LAB = 'qyh-current159-exact-restore-20261012'
DOCKER = ['docker', '--context', 'colima-aos-extension']


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def save(name, value):
    with (OUT / name).open('x') as stream:
        json.dump(value, stream, indent=2)


def old_catalog(helpers, database):
    return json.loads(helpers.sql(LAB, database, """SELECT json_build_object(
      'relations',(SELECT json_agg(row_to_json(x) ORDER BY x.schema,x.name) FROM
        (SELECT n.nspname AS schema,c.relname AS name,c.relowner,c.relacl::text,c.relrowsecurity,c.relforcerowsecurity,
          (SELECT json_agg(json_build_array(a.attname,a.atttypid,a.attnotnull,a.attacl::text) ORDER BY a.attnum) FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped) AS columns,
          (SELECT json_agg(to_jsonb(p) ORDER BY p.policyname) FROM pg_policies p WHERE p.schemaname=n.nspname AND p.tablename=c.relname) AS policies,
          (SELECT json_agg(pg_get_triggerdef(t.oid) ORDER BY t.tgname) FROM pg_trigger t WHERE t.tgrelid=c.oid) AS triggers
         FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r'
         AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%'
         AND c.relname NOT IN ('aip_skill_eval_intent','aip_skill_eval_dispatch','aip_skill_eval_dispatch_observation')) x),
      'defaults',(SELECT json_agg(to_jsonb(d) ORDER BY oid) FROM pg_default_acl d));"""))


def main():
    assert not (OUT / 'repair161-intent.json').exists(), 'Reconcile previous161, never replay'
    helpers = load('restore', ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/restore-r2.py')
    base = json.loads((ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/current-baseline.json').read_text())
    native = load('native', ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/backup_restore.py')
    assert native.source_fingerprint() == base
    fingerprint = load('fingerprint', ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/backup_restore.py')
    fingerprint.current_sql = lambda query: helpers.sql(LAB, DB, query)
    before = fingerprint.source_fingerprint()
    old = old_catalog(helpers, DB)
    seq = helpers.sequences(LAB, DB)
    roles = helpers.roles(LAB)
    assert helpers.sql(LAB, DB, 'SELECT version_num FROM alembic_version;').strip() == 'a0v_160'
    private = OUT / 'private'
    source = private / 'source161'
    source.mkdir(mode=0o700)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    archive = subprocess.check_output(['git', 'archive', '--format=tar', head, 'services/aos-api'], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar:
            relative = PurePosixPath(member.name)
            assert not relative.is_absolute() and '..' not in relative.parts and '.env' not in relative.parts
            assert member.isfile() or member.isdir()
            if member.isfile():
                path = source / member.name
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with path.open('xb') as stream:
                    stream.write(tar.extractfile(member).read())
                path.chmod(0o600)
    api = source / 'services/aos-api'
    env = {k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','LANG')}
    env.update({'AOS_DOTENV_DISABLED':'1','PYTHONPATH':str(api)})
    code = "from alembic.config import Config;from alembic import command;from alembic.script import ScriptDirectory;import io;c=Config('alembic.ini',output_buffer=io.StringIO());c.set_main_option('script_location','alembic');c.set_main_option('sqlalchemy.url','postgresql://localhost/unused');assert ScriptDirectory.from_config(c).get_heads()==['a0v_161'];command.upgrade(c,'a0v_160:a0v_161',sql=True);print(c.output_buffer.getvalue(),end='')"
    generated = subprocess.run([str(ROOT / 'services/aos-api/.venv/bin/python'),'-c',code],cwd=api,env=env,capture_output=True)
    assert generated.returncode == 0
    statement = generated.stdout
    assert statement.strip().startswith(b'BEGIN;') and statement.strip().endswith(b'COMMIT;')
    path = private / 'original160-to161.sql'
    with path.open('xb') as stream:
        stream.write(statement)
    path.chmod(0o600)
    save('repair161-intent.json', {'head':head,'ownedDatabase':DB,'sqlSHA256':hashlib.sha256(statement).hexdigest(),'actualSourceMigration':False})
    log = private / 'repair161.log'
    fd = os.open(log,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as output, path.open('rb') as input_stream:
        result = subprocess.run(DOCKER+['exec','-i',LAB,'psql','-X','-q','-v','ON_ERROR_STOP=1','-U','aos_app','-d',DB],stdin=input_stream,stdout=output,stderr=output)
    save('repair161-terminal.json',{'exitCode':result.returncode})
    assert result.returncode == 0, 'Owned repair failed; reconcile without replay'
    after = fingerprint.source_fingerprint()
    assert {key for key in before if before[key]!=after.get(key)} == {'public.alembic_version'}
    assert helpers.sql(LAB,DB,'SELECT version_num FROM alembic_version;').strip() == 'a0v_161'
    assert old_catalog(helpers, DB) == old and len(old['relations']) == 647
    assert helpers.sequences(LAB,DB) == seq and helpers.roles(LAB) == roles
    gates=json.loads(helpers.sql(LAB,DB,"SELECT json_agg(json_build_object('table',relname,'acl',relacl::text,'runtimeRead',has_table_privilege('aos_runtime',oid,'SELECT'),'runtimeWrite',has_table_privilege('aos_runtime',oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'),'writerInsert',has_table_privilege('aos_aip_eval_writer',oid,'INSERT'),'writerUpdate',has_table_privilege('aos_aip_eval_writer',oid,'UPDATE'),'forcedRLS',relforcerowsecurity)) FROM pg_class WHERE relname IN ('aip_skill_eval_intent','aip_skill_eval_dispatch','aip_skill_eval_dispatch_observation');"))
    assert len(gates)==3 and all(g['runtimeRead'] and not g['runtimeWrite'] and g['writerInsert'] and not g['writerUpdate'] and g['forcedRLS'] for g in gates)
    assert native.source_fingerprint() == base
    fingerprint.current_sql=lambda query:helpers.sql(LAB,'qyh_current159_full_restore_r2_20261012',query)
    assert fingerprint.source_fingerprint()==base
    save('repair161-result.json',{'head':head,'ownedVersion':'a0v_161','allOldBusinessDataAndNewEmptyTablesUnchanged':True,
        'all647OldTableACLColumnsPoliciesTriggersAndDefaultsUnchanged':True,'all12SequencesAnd39RolesUnchanged':True,
        'journalNativePermissionReadback':gates,'realSourceAndFresh159TemplateUnchanged':True,'actualSourceMigrated':False,
        'signedBundleRuntimeCompatibilityAccepted':False,'formalIdentityAndEightWorkshopsAccepted':False})
    print(json.dumps({'owned161RepairPassed':True,'old647ACLAndDataPreserved':True,'actualSourceMigrated':False}),flush=True)


if __name__=='__main__':
    main()
