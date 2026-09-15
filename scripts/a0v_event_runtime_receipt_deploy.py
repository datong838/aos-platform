"""Exact additive event-dispatch migration after a retained, verified local restore."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('event_runtime_receipt_deploy_storage', Path(__file__).with_name('a0v_controlled_source_claim_deploy.py'))
storage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(storage)
STATE = ROOT.parent / '.aos-recovery-20260916/state/event-runtime-receipt-deployment'
CLONE = 'aos_event_runtime_receipt_20260916_test'
SOURCE, TARGET = 'a0v_057', 'a0v_058'
TASK = 'SC4-5L6M-EVENT-RUNTIME-RECEIPT-DEPLOY-20260916'
FILES = ('a0v_058_event_runtime_receipt.py',)
CHAIN = ['a0v_058']
storage.CLONE, storage.FILES = CLONE, FILES


def fingerprint(conn):
    from psycopg import sql
    tables = conn.execute("""SELECT tablename FROM pg_tables WHERE schemaname='public'
        AND tablename <> 'alembic_version'
        ORDER BY tablename""").fetchall()
    result = {}
    for row in tables:
        name = row['tablename']
        result[name] = dict(conn.execute(sql.SQL(
            "SELECT count(*) AS count,md5(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text))) AS digest FROM {} t"
        ).format(sql.Identifier('public', name))).fetchone())
    return result


storage.fingerprint = fingerprint


def require_lease():
    leases=json.loads((ROOT.parent/'docs/palantier/AOS项目开发上下文/memory/leases.json').read_text())['leases']
    found=[x for x in leases if x['task_id']==TASK]
    if (len(found)!=1 or found[0]['owner']!='m1' or found[0]['status']!='ACTIVE'
        or datetime.fromisoformat(found[0]['lease_expires_at'])<=datetime.now(timezone.utc)
        or subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='m1'):
        raise ValueError('current single-writer lease required')


def executor_hashes():
    return {p.name:storage.digest(p) for p in (Path(__file__),Path(storage.__file__),ROOT/'services/aos-api/alembic/env.py')}


def protected_write(path, value):
    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2)
        handle.write('\n');handle.flush();os.fsync(handle.fileno())
    directory=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(directory)
    finally:os.close(directory)


def upgrade(database):
    from sqlalchemy import URL, create_engine
    from psycopg.rows import dict_row, tuple_row
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic import command
    args=storage.parameters(database)
    with storage.connect(database,autocommit=True) as lock:
        if not lock.execute("SELECT pg_try_advisory_lock(hashtext('aos.event-runtime-receipt.migration'),hashtext(current_database())) AS ok").fetchone()['ok']:
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
            engine=create_engine(url, isolation_level='REPEATABLE READ')
            try:
                with engine.connect() as connection:
                    with connection.begin():
                        raw=connection.connection.driver_connection
                        raw.row_factory=dict_row
                        if storage.version(raw)!=[SOURCE]:raise ValueError('transaction source version differs')
                        before=fingerprint(raw)
                        cfg.attributes['connection']=connection
                        raw.row_factory=tuple_row
                        try:command.upgrade(cfg,TARGET)
                        finally:raw.row_factory=dict_row
                        after=fingerprint(raw)
                        if after!=before:raise ValueError('migration changed existing data')
                        if storage.version(raw)!=[TARGET]:raise ValueError('transaction target version differs')
                        schema=verify(raw)
                        transaction_proof=dict(source=SOURCE,target=TARGET,before=before,after=after,
                            schema=schema,migrations=storage.migration_hashes(),executors=executor_hashes(),
                            at=datetime.now(timezone.utc).isoformat())
                        if database==storage.MAIN:
                            protected_write(STATE/'transaction-verified.json',transaction_proof)
                if storage.version(lock)!=[TARGET]:raise ValueError('migration commit not observed')
                return transaction_proof
            finally:engine.dispose()
        finally:
            lock.execute("SELECT pg_advisory_unlock(hashtext('aos.event-runtime-receipt.migration'),hashtext(current_database()))")


def verify(conn):
    function='public.ecommerce_growth_runtime_receipt_put_ar2_005(text,text,text,bigint,uuid,uuid,bigint,uuid,bigint,bigint,jsonb,jsonb,text,timestamp with time zone)'
    row=conn.execute("""SELECT p.prosecdef,
        has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime,
        EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
          WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public_allowed,
        position('ecommerce_growth_event_control' in pg_get_functiondef(p.oid))>0 AS event_allowed
        FROM pg_proc p WHERE p.oid=to_regprocedure(%s)""",(function,)).fetchone()
    if row is None or dict(row)!=dict(prosecdef=True,runtime=True,public_allowed=False,event_allowed=True):
        raise ValueError('runtime Receipt function privileges or operation differ')
    row=conn.execute("""SELECT
        has_table_privilege('aos_runtime','public.ecommerce_growth_runtime_command_receipt','INSERT') AS insert_allowed,
        has_table_privilege('aos_runtime','public.ecommerce_growth_runtime_command_receipt','UPDATE') AS update_allowed,
        has_table_privilege('aos_runtime','public.ecommerce_growth_runtime_command_receipt','DELETE') AS delete_allowed""").fetchone()
    if any(row.values()):raise ValueError('runtime Receipt table grants widened')
    check=conn.execute("""SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint
        WHERE conrelid='public.ecommerce_growth_runtime_command_receipt'::regclass
        AND conname='ecommerce_growth_runtime_command_receipt_operation_id_check'""").fetchone()
    if check is None or 'ecommerce_growth_event_control' not in check['definition']:
        raise ValueError('runtime Receipt operation constraint differs')
    return dict(runtimeExecute=True,publicExecute=False,directWrite=False,eventAllowed=True)


def snapshot_backup(backup):
    """Keep the exported read snapshot alive until pg_dump has consumed it."""
    with storage.connect(storage.MAIN) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        if storage.version(conn)!=[SOURCE]:raise ValueError('main version differs')
        if conn.execute('SELECT 1 FROM pg_database WHERE datname=%s',(CLONE,)).fetchone():
            raise ValueError('clone already exists')
        snapshot=conn.execute('SELECT pg_export_snapshot() AS snapshot').fetchone()['snapshot']
        before=storage.fingerprint(conn);user=conn.info.user
        with backup.open('xb') as handle:
            os.chmod(backup,0o600)
            process=subprocess.run(['docker','--context',storage.CONTEXT,'exec',storage.CONTAINER,
                'pg_dump','-U',user,'-d',storage.MAIN,'-Fc','--snapshot',snapshot],
                stdout=handle,stderr=subprocess.PIPE,timeout=120)
            handle.flush();os.fsync(handle.fileno())
        if process.returncode or not backup.stat().st_size:raise RuntimeError('backup failed; retained for inspection')
    return before,user,snapshot


def prepare():
    from psycopg import sql
    require_lease();STATE.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(STATE,0o700)
    backup=STATE/'aos_meta_head-before-a0v_058.dump'
    if backup.exists() or (STATE/'prepare.json').exists():raise ValueError('retained preparation requires inspection')
    before,user,snapshot = snapshot_backup(backup)
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
    proof=dict(outcome='EVENT_RUNTIME_RECEIPT_RESTORE_VERIFIED',source=SOURCE,target=TARGET,main=storage.MAIN,clone=CLONE,
        migrations=storage.migration_hashes(),executors=executor_hashes(),
        backup=dict(path=str(backup),sha256=storage.digest(backup),bytes=backup.stat().st_size),
        before=before,after=after,snapshot=snapshot,schema=schema,businessWrites=0,at=datetime.now(timezone.utc).isoformat())
    protected_write(STATE/'prepare.json',proof)
    return proof


def validate_proof(proof):
    backup=STATE/'aos_meta_head-before-a0v_058.dump'
    if (proof.get('outcome')!='EVENT_RUNTIME_RECEIPT_RESTORE_VERIFIED' or proof.get('source')!=SOURCE or proof.get('target')!=TARGET
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
        if storage.version(conn)!=[SOURCE]:raise ValueError('main source version drifted')
    protected_write(STATE/'apply-intent.json',dict(migrations=proof['migrations'],executors=proof['executors'],target=TARGET,at=datetime.now(timezone.utc).isoformat()))
    upgrade(storage.MAIN)
    return readback()


def readback():
    require_lease()
    proof=json.loads((STATE/'prepare.json').read_text());validate_proof(proof)
    intent=json.loads((STATE/'apply-intent.json').read_text())
    if intent.get('target')!=TARGET or intent.get('migrations')!=proof['migrations'] or intent.get('executors')!=proof['executors']:
        raise ValueError('apply intent differs')
    transaction=json.loads((STATE/'transaction-verified.json').read_text())
    if (transaction.get('source')!=SOURCE or transaction.get('target')!=TARGET
        or transaction.get('migrations')!=proof['migrations'] or transaction.get('executors')!=proof['executors']
        or not transaction.get('before') or transaction.get('before')!=transaction.get('after')):
        raise ValueError('migration transaction proof differs')
    with storage.connect(storage.MAIN) as conn:
        if storage.version(conn)!=[TARGET]:raise ValueError('main deployment not verified')
        schema=verify(conn)
    result=dict(outcome='EVENT_RUNTIME_RECEIPT_LOCAL_SCHEMA_DEPLOYED',revision=TARGET,schema=schema,businessWrites=0,
        changedSinceBackup=sorted(k for k in set(proof['before'])|set(transaction['before']) if proof['before'].get(k)!=transaction['before'].get(k)),at=datetime.now(timezone.utc).isoformat())
    if not (STATE/'apply.json').exists():protected_write(STATE/'apply.json',result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('prepare','apply','readback'));args=parser.parse_args()
    try:result=globals()[args.mode]()
    except Exception as exc:
        print(json.dumps(dict(outcome='EVENT_RUNTIME_RECEIPT_DEPLOYMENT_NEEDS_INSPECTION',phase=args.mode,errorType=type(exc).__name__)))
        raise SystemExit(2) from None
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))


if __name__=='__main__':main()
