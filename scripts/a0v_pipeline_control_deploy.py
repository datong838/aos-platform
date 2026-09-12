"""Exact local additive migration, with retained backup and isolated restore first."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/aos-api'))
os.environ['AOS_DOTENV_DISABLED']='1'
MAIN='aos_meta_head'
CLONE='aos_pipeline_control_20260912_ti4_test'
CONTEXT='colima-aos-extension'
CONTAINER='aos-a0v-recovery-pg'
STATE=ROOT.parent/'.aos-recovery-20260912/state/pipeline-control-deployment'
FILES=('a0v_022_pipeline_source_selection.py','a0v_023_pipeline_runtime_control.py')
TABLES=('meta_source','data_source_configuration_revision','phase5_pipeline_graph','meta_pipeline',
        'meta_schedule','meta_schedule_run','meta_dataset','bundle_installation','extension_runtime_configuration')
NEW_TABLES=('pipeline_source_selection_revision','pipeline_runtime_control_revision')


def digest(path):
    hasher=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):hasher.update(chunk)
    return 'sha256:'+hasher.hexdigest()


def migration_hashes():
    return {name:digest(ROOT/'services/aos-api/alembic/versions'/name) for name in FILES}


def require_leases():
    path=ROOT.parent/'docs/palantier/AOS项目开发上下文/memory/leases.json'
    leases={item['task_id']:item for item in json.loads(path.read_text())['leases']}
    for task in ('A0V-PIPELINE-CONTROL-LOCAL-MIGRATION-20260912','A0V-PIPELINE-CONTROL-RESTORE-DRILL-20260912'):
        lease=leases[task]
        if lease['owner']!='m1' or lease['status']!='ACTIVE' or datetime.fromisoformat(lease['lease_expires_at'])<=datetime.now(timezone.utc):
            raise ValueError('exact migration lease unavailable')
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    if branch!='m1':raise ValueError('migration requires owned m1 checkout')


def parameters(database):
    if database not in (MAIN,CLONE):raise ValueError('unexpected database')
    from a0v_formal_text_model_renewal import database_connect
    with database_connect(MAIN)() as conn:
        values=conn.info.get_parameters();values['password']=conn.info.password
    values['dbname']=database
    return values


@contextmanager
def connect(database,*,autocommit=False):
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(**parameters(database),row_factory=dict_row,autocommit=autocommit) as conn:
        if conn.info.dbname!=database:raise ValueError('database target drifted')
        yield conn


def version(conn):
    return [row['version_num'] for row in conn.execute('SELECT version_num FROM alembic_version').fetchall()]


def fingerprint(conn):
    from psycopg import sql
    result={}
    for table in TABLES:
        result[table]=dict(conn.execute(sql.SQL("SELECT count(*) AS count,md5(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text))) AS digest FROM {} t").format(sql.Identifier('public',table))).fetchone())
    return result


def verify_tables(conn):
    from psycopg import sql
    result={}
    for table in NEW_TABLES:
        row=conn.execute('''SELECT c.relrowsecurity,c.relforcerowsecurity,
            has_table_privilege('aos_runtime',c.oid,'SELECT') AS can_select,
            has_table_privilege('aos_runtime',c.oid,'INSERT') AS can_insert,
            has_table_privilege('aos_runtime',c.oid,'UPDATE') AS can_update,
            has_table_privilege('aos_runtime',c.oid,'DELETE') AS can_delete,
            has_table_privilege('aos_runtime',c.oid,'TRUNCATE') AS can_truncate,
            has_table_privilege('aos_runtime',c.oid,'TRIGGER') AS can_trigger,
            has_table_privilege('aos_runtime',c.oid,'REFERENCES') AS can_reference
            FROM pg_class c WHERE c.oid=to_regclass(%s)''',('public.'+table,)).fetchone()
        count=conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier('public',table))).fetchone()['n']
        if (row is None or not row['relrowsecurity'] or not row['relforcerowsecurity']
                or not row['can_select'] or not row['can_insert'] or any(row[key] for key in ('can_update','can_delete','can_truncate','can_trigger','can_reference')) or count!=0):
            raise ValueError('new history contract differs')
        triggers=conn.execute('''SELECT tgname FROM pg_trigger WHERE tgrelid=to_regclass(%s) AND NOT tgisinternal ORDER BY tgname''',('public.'+table,)).fetchall()
        if [item['tgname'] for item in triggers]!=['immutable_history','immutable_truncate']:
            raise ValueError('history immutability triggers missing')
        result[table]=dict(row,count=count,triggers=[item['tgname'] for item in triggers])
    return result


def upgrade(database):
    from sqlalchemy import URL
    from alembic.config import Config
    from alembic import command
    from alembic.script import ScriptDirectory
    args=parameters(database)
    with connect(database,autocommit=True) as lock:
        acquired=lock.execute("SELECT pg_try_advisory_lock(hashtext('aos.pipeline-control.migration'),hashtext(current_database())) AS acquired").fetchone()['acquired']
        if not acquired:raise ValueError('migration lock busy')
        try:
            if version(lock)!=['a0v_021']:raise ValueError('exact a0v_021 baseline required')
            cfg=Config(str(ROOT/'services/aos-api/alembic.ini'))
            cfg.set_main_option('script_location',str(ROOT/'services/aos-api/alembic'))
            directory=ScriptDirectory.from_config(cfg)
            if directory.get_heads()!=['a0v_023'] or [step.revision for step in directory.iterate_revisions('a0v_023','a0v_021')]!=['a0v_023','a0v_022']:
                raise ValueError('migration range differs')
            url=URL.create('postgresql+psycopg',username=args['user'],password=args['password'],host=args['host'],port=int(args['port']),database=database,
                query={'options':'-c lock_timeout=5s -c statement_timeout=30s'})
            cfg.set_main_option('sqlalchemy.url',url.render_as_string(hide_password=False).replace('%','%%'))
            # This isolated command deliberately cannot inherit another target URL.
            os.environ.pop('AOS_DATABASE_URL',None)
            command.upgrade(cfg,'a0v_023')
            if version(lock)!=['a0v_023']:raise ValueError('migration commit not observed')
        finally:
            lock.execute("SELECT pg_advisory_unlock(hashtext('aos.pipeline-control.migration'),hashtext(current_database()))")


def protected_write(path,value):
    with path.open('x',encoding='utf-8') as handle:
        os.chmod(path,0o600)
        json.dump(value,handle,ensure_ascii=False,indent=2)
        handle.write('\n')


def prepare():
    from psycopg import sql
    require_leases()
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(STATE,0o700)
    backup=STATE/'aos_meta_head-before-a0v_022-023.dump'
    proof=STATE/'prepare.json'
    if backup.exists() or proof.exists():raise ValueError('existing preparation must be inspected, never overwritten')
    with connect(MAIN) as conn:
        if version(conn)!=['a0v_021']:raise ValueError('unexpected source baseline')
        before=fingerprint(conn)
        if conn.execute('SELECT 1 FROM pg_database WHERE datname=%s',(CLONE,)).fetchone() is not None:
            raise ValueError('clone already exists; never overwrite')
        user=conn.info.user
    with backup.open('xb') as handle:
        os.chmod(backup,0o600)
        process=subprocess.run(['docker','--context',CONTEXT,'exec',CONTAINER,'pg_dump','-U',user,'-d',MAIN,'-Fc'],stdout=handle,stderr=subprocess.PIPE,timeout=120)
    if process.returncode!=0 or backup.stat().st_size==0:raise RuntimeError('protected backup failed')
    with connect(MAIN,autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(CLONE)))
        conn.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(CLONE)))
    with backup.open('rb') as handle:
        process=subprocess.run(['docker','--context',CONTEXT,'exec','-i',CONTAINER,'pg_restore','-U',user,'-d',CLONE,'--exit-on-error'],stdin=handle,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if process.returncode!=0:raise RuntimeError('isolated restore failed; retained clone requires inspection')
    with connect(CLONE) as conn:
        if version(conn)!=['a0v_021'] or fingerprint(conn)!=before:raise ValueError('restored baseline differs')
    upgrade(CLONE)
    with connect(CLONE) as conn:
        after=fingerprint(conn);tables=verify_tables(conn)
        if after!=before:raise ValueError('clone business baseline changed')
    result=dict(outcome='ISOLATED_RESTORE_AND_MIGRATION_VERIFIED',at=datetime.now(timezone.utc).isoformat(),
        main=MAIN,clone=CLONE,backup=dict(path=str(backup),bytes=backup.stat().st_size,sha256=digest(backup)),
        migrations=migration_hashes(),before=before,after=after,tables=tables,sourceRowsRead=0,businessWrites=0)
    protected_write(proof,result)
    return result



def resume_prepare():
    import importlib.util
    from types import SimpleNamespace
    from psycopg import sql
    require_leases()
    backup=STATE/'aos_meta_head-before-a0v_022-023.dump'
    proof=STATE/'prepare.json'
    if proof.exists() or backup.is_symlink() or not backup.is_file() or backup.stat().st_mode & 0o777 != 0o600:
        raise ValueError('retained preparation requires inspection')
    with connect(MAIN) as conn:
        if version(conn)!=['a0v_021']:raise ValueError('main baseline changed')
        before=fingerprint(conn)
    with connect(CLONE) as conn:
        if version(conn)!=['a0v_023'] or fingerprint(conn)!=before:
            raise ValueError('retained clone differs from main business baseline')
        for table in NEW_TABLES:
            if conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier('public',table))).fetchone()['n']!=0:
                raise ValueError('retained control tables are not empty')
        for name in FILES:
            spec=importlib.util.spec_from_file_location('exact_control_permission_repair',ROOT/'services/aos-api/alembic/versions'/name)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            module.op=SimpleNamespace(execute=conn.execute)
            module.restrict_history_permissions()
        after=fingerprint(conn);tables=verify_tables(conn)
        if after!=before:raise ValueError('clone business baseline changed')
    result=dict(outcome='ISOLATED_RESTORE_AND_MIGRATION_VERIFIED',at=datetime.now(timezone.utc).isoformat(),
        main=MAIN,clone=CLONE,backup=dict(path=str(backup),bytes=backup.stat().st_size,sha256=digest(backup)),
        migrations=migration_hashes(),before=before,after=after,tables=tables,sourceRowsRead=0,businessWrites=0,
        repair='Retained restored clone: restricted inherited default privileges on two empty new tables only')
    protected_write(proof,result)
    return result


def apply():
    require_leases()
    result=json.loads((STATE/'prepare.json').read_text())
    if (result['outcome']!='ISOLATED_RESTORE_AND_MIGRATION_VERIFIED' or result['main']!=MAIN or result['clone']!=CLONE
            or result['migrations']!=migration_hashes() or result['backup']['sha256']!=digest(Path(result['backup']['path']))):
        raise ValueError('preparation evidence differs')
    with connect(CLONE) as conn:
        if version(conn)!=['a0v_023'] or fingerprint(conn)!=result['before']:raise ValueError('verified clone drifted')
        verify_tables(conn)
    with connect(MAIN) as conn:
        before=fingerprint(conn)
        if version(conn)!=['a0v_021']:raise ValueError('exact source migration baseline required')
    upgrade(MAIN)
    with connect(MAIN) as conn:
        after=fingerprint(conn);tables=verify_tables(conn)
        if after!=before:raise ValueError('business baseline changed during deployment')
    result=dict(outcome='LOCAL_PIPELINE_CONTROL_SCHEMA_DEPLOYED',at=datetime.now(timezone.utc).isoformat(),
        database=MAIN,revision='a0v_023',migrations=migration_hashes(),before=before,after=after,tables=tables,
        approvalsWritten=0,sourceRowsRead=0,businessWrites=0)
    protected_write(STATE/'apply.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','resume-prepare','apply']);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        result={'prepare':prepare,'resume-prepare':resume_prepare,'apply':apply}[args.action]()
    except Exception as error:
        from a0v_ecommerce_runtime_host import _safe_error_chain
        result=dict(outcome='STOPPED_FOR_INSPECTION',errorChain=_safe_error_chain(error))
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({key:value for key,value in result.items() if key not in {'before','after','tables'}},ensure_ascii=False))
