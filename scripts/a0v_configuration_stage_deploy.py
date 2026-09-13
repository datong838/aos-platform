"""Exact additive configuration-stage migration after a retained, verified local restore."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('configuration_stage_deploy_storage', Path(__file__).with_name('a0v_controlled_source_claim_deploy.py'))
storage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(storage)
STATE = ROOT.parent / '.aos-recovery-20260913/state/configuration-stage-deployment'
CLONE = 'aos_configuration_stage_20260914_test'
SOURCE, TARGET = 'a0v_035', 'a0v_038'
TASK = 'A0V-CONFIGURATION-STAGE-LOCAL-DEPLOYMENT-20260914'
FILES = ('a0v_036_runtime_configuration_stage.py', 'a0v_037_configuration_stage_api.py',
         'a0v_038_configuration_stage_lookup.py')
CHAIN = ['a0v_038','a0v_037','a0v_036']
COLUMNS = ('state','revision','completed_at','result_json','failure_code')
FUNCTIONS = {
    'extension_configuration_stage_principal_a0v_037(text,uuid)': 'aos_configuration_stage_api',
    'extension_configuration_stage_enqueue_a0v_037(text,text,jsonb)': 'aos_configuration_stage_api',
    'extension_configuration_stage_query_a0v_037(text,uuid)': 'aos_configuration_stage_api',
    'extension_configuration_stage_lookup_a0v_038(text,text)': 'aos_configuration_stage_api',
}
storage.CLONE, storage.FILES = CLONE, FILES
storage.TABLES += ('bundle_installation_revision','extension_operation_dispatch_binding',
    'extension_dispatch_registration_receipt','extension_dispatch_withdrawal_receipt',
    'ecommerce_investigation_case_head','ecommerce_investigation_case_revision',
    'ecommerce_investigation_run','ecommerce_investigation_run_state_head')


def require_lease():
    leases=json.loads((ROOT.parent/'docs/palantier/AOS项目开发上下文/memory/leases.json').read_text())['leases']
    found=[x for x in leases if x['task_id']==TASK]
    if (len(found)!=1 or found[0]['owner']!='m1' or found[0]['status']!='ACTIVE'
        or datetime.fromisoformat(found[0]['lease_expires_at'])<=datetime.now(timezone.utc)
        or subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='m1'):
        raise ValueError('current single-writer lease required')


def executor_hashes():
    return {p.name:storage.digest(p) for p in (Path(__file__),Path(storage.__file__))}


def protected_write(path, value):
    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2)
        handle.write('\n');handle.flush();os.fsync(handle.fileno())
    directory=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(directory)
    finally:os.close(directory)


def upgrade(database):
    from sqlalchemy import URL
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic import command
    args=storage.parameters(database)
    with storage.connect(database,autocommit=True) as lock:
        if not lock.execute("SELECT pg_try_advisory_lock(hashtext('aos.configuration-stage.migration'),hashtext(current_database())) AS ok").fetchone()['ok']:
            raise ValueError('migration lock busy')
        try:
            if storage.version(lock)!=[SOURCE]:raise ValueError('exact source version required')
            cfg=Config(str(ROOT/'services/aos-api/alembic.ini'))
            cfg.set_main_option('script_location',str(ROOT/'services/aos-api/alembic'))
            directory=ScriptDirectory.from_config(cfg)
            if directory.get_heads()!=[TARGET] or [r.revision for r in directory.iterate_revisions(TARGET,SOURCE)]!=CHAIN:
                raise ValueError('exact migration chain required')
            url=URL.create('postgresql+psycopg',username=args['user'],password=args['password'],host=args['host'],port=int(args['port']),database=database,
                           query={'options':'-c lock_timeout=5s -c statement_timeout=30s'})
            cfg.set_main_option('sqlalchemy.url',url.render_as_string(hide_password=False).replace('%','%%'))
            previous=os.environ.pop('AOS_DATABASE_URL',None)
            try:command.upgrade(cfg,TARGET)
            finally:
                if previous is not None:os.environ['AOS_DATABASE_URL']=previous
            if storage.version(lock)!=[TARGET]:raise ValueError('migration commit not observed')
        finally:
            lock.execute("SELECT pg_advisory_unlock(hashtext('aos.configuration-stage.migration'),hashtext(current_database()))")


def verify(conn):
    table='public.extension_runtime_configuration_stage_request'
    row=conn.execute("""SELECT relrowsecurity,relforcerowsecurity,
        has_table_privilege('aos_runtime',oid,'SELECT') AS readable,
        has_any_column_privilege('aos_runtime',oid,'INSERT') AS insertable,
        has_table_privilege('aos_runtime',oid,'DELETE,TRUNCATE') AS deletable,
        has_any_column_privilege('aos_configuration_stage_api',oid,'SELECT,INSERT,UPDATE,REFERENCES') AS api_columns,
        has_table_privilege('aos_configuration_stage_api',oid,'DELETE,TRUNCATE,TRIGGER') AS api_table
        FROM pg_class WHERE oid=to_regclass(%s)""",(table,)).fetchone()
    if row is None or dict(row)!=dict(relrowsecurity=True,relforcerowsecurity=True,readable=True,
            insertable=False,deletable=False,api_columns=False,api_table=False):
        raise ValueError('configuration queue privileges differ')
    columns=conn.execute("""SELECT attname FROM pg_attribute WHERE attrelid=to_regclass(%s)
        AND attnum>0 AND NOT attisdropped AND has_column_privilege('aos_runtime',attrelid,attname,'UPDATE')""",(table,)).fetchall()
    if {r['attname'] for r in columns}!=set(COLUMNS):raise ValueError('runtime completion columns differ')
    count=conn.execute('SELECT count(*) AS n FROM public.extension_runtime_configuration_stage_request').fetchone()['n']
    if count!=0:raise ValueError('deployment queue not empty')
    triggers=conn.execute("""SELECT t.tgname,t.tgenabled,p.proname,p.prosecdef FROM pg_trigger t
        JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgrelid=to_regclass(%s) AND NOT t.tgisinternal""",(table,)).fetchall()
    if {tuple(r.values()) for r in triggers}!={
        ('configuration_stage_guard','O','extension_runtime_configuration_stage_guard',False),
        ('configuration_stage_no_truncate','O','extension_reject_history_mutation',False)}:
        raise ValueError('configuration queue guards differ')
    for function,role in FUNCTIONS.items():
        row=conn.execute("""SELECT p.prosecdef,
            has_function_privilege(%s,p.oid,'EXECUTE') AS allowed,
            has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_allowed,
            EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
                WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public_allowed
            FROM pg_proc p WHERE p.oid=to_regprocedure(%s)""",(role,'public.'+function)).fetchone()
        if row is None or dict(row)!=dict(prosecdef=True,allowed=True,runtime_allowed=False,public_allowed=False):
            raise ValueError('configuration functions privileges differ')
    return dict(queueCount=count,forceRls=True,runtimeUpdateColumns=list(COLUMNS),apiDirectTableAccess=False,
                restrictedFunctionCount=len(FUNCTIONS))


def prepare():
    from psycopg import sql
    require_lease();STATE.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(STATE,0o700)
    backup=STATE/'aos_meta_head-before-a0v_038.dump'
    if backup.exists() or (STATE/'prepare.json').exists():raise ValueError('retained preparation requires inspection')
    with storage.connect(storage.MAIN) as conn:
        if storage.version(conn)!=[SOURCE]:raise ValueError('main version differs')
        before=storage.fingerprint(conn);user=conn.info.user
        if conn.execute('SELECT 1 FROM pg_database WHERE datname=%s',(CLONE,)).fetchone():raise ValueError('clone already exists')
    with backup.open('xb') as handle:
        os.chmod(backup,0o600)
        process=subprocess.run(['docker','--context',storage.CONTEXT,'exec',storage.CONTAINER,'pg_dump','-U',user,'-d',storage.MAIN,'-Fc'],stdout=handle,stderr=subprocess.PIPE,timeout=120)
        handle.flush();os.fsync(handle.fileno())
    if process.returncode or not backup.stat().st_size:raise RuntimeError('backup failed')
    with storage.connect(storage.MAIN,autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(CLONE)))
        conn.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(CLONE)))
    with backup.open('rb') as handle:
        process=subprocess.run(['docker','--context',storage.CONTEXT,'exec','-i',storage.CONTAINER,'pg_restore','-U',user,'-d',CLONE,'--exit-on-error'],stdin=handle,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if process.returncode:raise RuntimeError('restore failed; clone retained')
    with storage.connect(CLONE) as conn:
        if storage.version(conn)!=[SOURCE] or storage.fingerprint(conn)!=before:raise ValueError('restored baseline differs')
    upgrade(CLONE)
    with storage.connect(CLONE) as conn:
        after=storage.fingerprint(conn);schema=verify(conn)
        if after!=before:raise ValueError('restored business data changed')
    proof=dict(outcome='CONFIGURATION_STAGE_RESTORE_VERIFIED',source=SOURCE,target=TARGET,main=storage.MAIN,clone=CLONE,
        migrations=storage.migration_hashes(),executors=executor_hashes(),
        backup=dict(path=str(backup),sha256=storage.digest(backup),bytes=backup.stat().st_size),
        before=before,after=after,schema=schema,businessWrites=0,at=datetime.now(timezone.utc).isoformat())
    protected_write(STATE/'prepare.json',proof)
    return proof


def validate_proof(proof):
    backup=STATE/'aos_meta_head-before-a0v_038.dump'
    if (proof.get('outcome')!='CONFIGURATION_STAGE_RESTORE_VERIFIED' or proof.get('source')!=SOURCE or proof.get('target')!=TARGET
        or proof.get('main')!=storage.MAIN or proof.get('clone')!=CLONE
        or proof.get('migrations')!=storage.migration_hashes() or proof.get('executors')!=executor_hashes()
        or backup.is_symlink() or not backup.is_file() or backup.stat().st_mode & 0o777 != 0o600
        or proof.get('backup',{}).get('path')!=str(backup) or proof['backup'].get('sha256')!=storage.digest(backup)
        or proof['backup'].get('bytes')!=backup.stat().st_size or not proof.get('before') or proof.get('before')!=proof.get('after')):
        raise ValueError('retained preparation proof differs')


def apply():
    require_lease()
    if (STATE/'apply-intent.json').exists():raise ValueError('existing intent requires readback, not retry')
    proof=json.loads((STATE/'prepare.json').read_text());validate_proof(proof)
    with storage.connect(CLONE) as conn:
        if storage.version(conn)!=[TARGET] or storage.fingerprint(conn)!=proof['before']:raise ValueError('clone drifted')
        verify(conn)
    with storage.connect(storage.MAIN) as conn:
        if storage.version(conn)!=[SOURCE] or storage.fingerprint(conn)!=proof['before']:raise ValueError('main drifted')
    protected_write(STATE/'apply-intent.json',dict(migrations=proof['migrations'],executors=proof['executors'],target=TARGET,at=datetime.now(timezone.utc).isoformat()))
    upgrade(storage.MAIN)
    return readback()


def readback():
    require_lease()
    proof=json.loads((STATE/'prepare.json').read_text());validate_proof(proof)
    intent=json.loads((STATE/'apply-intent.json').read_text())
    if intent.get('target')!=TARGET or intent.get('migrations')!=proof['migrations'] or intent.get('executors')!=proof['executors']:
        raise ValueError('apply intent differs')
    with storage.connect(storage.MAIN) as conn:
        if storage.version(conn)!=[TARGET] or storage.fingerprint(conn)!=proof['before']:raise ValueError('main deployment not verified')
        schema=verify(conn)
    result=dict(outcome='CONFIGURATION_STAGE_LOCAL_SCHEMA_DEPLOYED',revision=TARGET,schema=schema,businessWrites=0,at=datetime.now(timezone.utc).isoformat())
    if not (STATE/'apply.json').exists():protected_write(STATE/'apply.json',result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('prepare','apply','readback'));args=parser.parse_args()
    try:result=globals()[args.mode]()
    except Exception as exc:
        print(json.dumps(dict(outcome='CONFIGURATION_STAGE_DEPLOYMENT_NEEDS_INSPECTION',phase=args.mode,errorType=type(exc).__name__)))
        raise SystemExit(2) from None
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))


if __name__=='__main__':main()
