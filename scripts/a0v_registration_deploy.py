"""Fixed local registration migration, verified on a retained restored clone first."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import a0v_controlled_source_claim_deploy as base
ROOT=base.ROOT
STATE=ROOT.parent/'.aos-recovery-20260913/state/registration-deployment'
CLONE='aos_registration_20260913_test'
SOURCE='a0v_025'
TARGET='a0v_030'
FILES=('a0v_026_dispatch_registration_receipt.py','a0v_027_dispatch_first_registration.py',
       'a0v_028_dispatch_read_lock.py','a0v_029_dispatch_withdrawal_receipt.py','a0v_030_dispatch_pristine_withdrawal.py')
TABLES=base.TABLES+('bundle_installation_revision','extension_operation_dispatch_binding',
    'automation_schedule_binding','ecommerce_growth_runtime_command_receipt')
base.CLONE=CLONE
base.TABLES=TABLES
base.FILES=FILES


def require_lease():
    records=json.loads((ROOT.parent/'docs/palantier/AOS项目开发上下文/memory/leases.json').read_text())['leases']
    lease=next(r for r in records if r['task_id']=='A0V-REGISTRATION-LOCAL-DEPLOYMENT-20260913')
    if (lease['owner']!='m1' or lease['status']!='ACTIVE'
            or datetime.fromisoformat(lease['lease_expires_at'])<=datetime.now(timezone.utc)
            or subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='m1'):
        raise ValueError('owned deployment lease required')


def upgrade(database):
    from sqlalchemy import URL
    from alembic.config import Config
    from alembic import command
    from alembic.script import ScriptDirectory
    args=base.parameters(database)
    with base.connect(database,autocommit=True) as lock:
        acquired=lock.execute("SELECT pg_try_advisory_lock(hashtext('aos.registration.migration'),hashtext(current_database())) AS acquired").fetchone()['acquired']
        if not acquired:raise ValueError('migration lock busy')
        try:
            if base.version(lock)!=[SOURCE]:raise ValueError('exact source baseline required')
            cfg=Config(str(ROOT/'services/aos-api/alembic.ini'))
            cfg.set_main_option('script_location',str(ROOT/'services/aos-api/alembic'))
            directory=ScriptDirectory.from_config(cfg)
            if (directory.get_heads()!=[TARGET] or [r.revision for r in directory.iterate_revisions(TARGET,SOURCE)]
                    !=['a0v_030','a0v_029','a0v_028','a0v_027','a0v_026']):
                raise ValueError('migration chain differs')
            url=URL.create('postgresql+psycopg',username=args['user'],password=args['password'],host=args['host'],port=int(args['port']),database=database,
                query={'options':'-c lock_timeout=5s -c statement_timeout=30s'})
            cfg.set_main_option('sqlalchemy.url',url.render_as_string(hide_password=False).replace('%','%%'))
            previous=os.environ.pop('AOS_DATABASE_URL',None)
            try:command.upgrade(cfg,TARGET)
            finally:
                if previous is not None:os.environ['AOS_DATABASE_URL']=previous
            if base.version(lock)!=[TARGET]:raise ValueError('migration commit not observed')
        finally:
            lock.execute("SELECT pg_advisory_unlock(hashtext('aos.registration.migration'),hashtext(current_database()))")


def verify(conn):
    from psycopg import sql
    tables={}
    for name in ('extension_dispatch_registration_receipt','extension_dispatch_withdrawal_receipt'):
        row=dict(conn.execute('''SELECT relrowsecurity,relforcerowsecurity,
            has_table_privilege('aos_runtime',oid,'SELECT') AS runtime_read,
            has_table_privilege('aos_runtime',oid,'INSERT,UPDATE,DELETE,TRUNCATE') AS runtime_write,
            has_table_privilege('aos_extension_maintainer',oid,'INSERT,UPDATE,DELETE,TRUNCATE') AS maintainer_write
            FROM pg_class WHERE oid=to_regclass(%s)''',('public.'+name,)).fetchone())
        count=conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(name))).fetchone()['n']
        if row!=dict(relrowsecurity=True,relforcerowsecurity=True,runtime_read=True,runtime_write=False,maintainer_write=False) or count!=0:
            raise ValueError('receipt schema or ACL differs')
        tables[name]=dict(row,count=count)
    dispatch=conn.execute("SELECT has_table_privilege('aos_runtime','extension_operation_dispatch_binding','INSERT,UPDATE,DELETE,TRUNCATE') AS runtime_write,has_table_privilege('aos_extension_maintainer','extension_operation_dispatch_binding','INSERT,UPDATE,DELETE,TRUNCATE') AS maintainer_write").fetchone()
    if any(dispatch.values()):raise ValueError('direct dispatch write remains')
    for function,role in [('extension_dispatch_register_a0v_027(jsonb,text)','aos_extension_maintainer'),
            ('extension_dispatch_withdraw_a0v_030(jsonb,text)','aos_extension_maintainer'),
            ('extension_dispatch_lock_group_a0v_028(uuid)','aos_runtime')]:
        row=conn.execute('''SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed,
            EXISTS(SELECT 1 FROM pg_proc p,aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
              WHERE p.oid=to_regprocedure(%s) AND a.grantee=0 AND a.privilege_type='EXECUTE') AS public_execute''',(role,function,function)).fetchone()
        if row['allowed'] is not True or row['public_execute'] is not False:raise ValueError('restricted function ACL differs')
        other='aos_runtime' if role=='aos_extension_maintainer' else 'aos_extension_maintainer'
        if conn.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(other,function)).fetchone()['allowed']:
            raise ValueError('unexpected control function grant')
    return tables


def prepare():
    from psycopg import sql
    require_lease();STATE.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(STATE,0o700)
    backup=STATE/'aos_meta_head-before-a0v_030.dump'
    if backup.exists() or (STATE/'prepare.json').exists():raise ValueError('retained preparation already exists')
    with base.connect(base.MAIN) as conn:
        if base.version(conn)!=[SOURCE]:raise ValueError('unexpected main baseline')
        before=base.fingerprint(conn);user=conn.info.user
        if conn.execute('SELECT 1 FROM pg_database WHERE datname=%s',(CLONE,)).fetchone():raise ValueError('clone exists')
    with backup.open('xb') as out:
        os.chmod(backup,0o600)
        result=subprocess.run(['docker','--context',base.CONTEXT,'exec',base.CONTAINER,'pg_dump','-U',user,'-d',base.MAIN,'-Fc'],stdout=out,stderr=subprocess.PIPE,timeout=120)
    if result.returncode or not backup.stat().st_size:raise RuntimeError('backup failed')
    with base.connect(base.MAIN,autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(CLONE)))
        conn.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(CLONE)))
    with backup.open('rb') as source:
        result=subprocess.run(['docker','--context',base.CONTEXT,'exec','-i',base.CONTAINER,'pg_restore','-U',user,'-d',CLONE,'--exit-on-error'],stdin=source,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if result.returncode:raise RuntimeError('restore failed; clone retained')
    with base.connect(CLONE) as conn:
        if base.version(conn)!=[SOURCE] or base.fingerprint(conn)!=before:raise ValueError('restored baseline differs')
    upgrade(CLONE)
    with base.connect(CLONE) as conn:
        after=base.fingerprint(conn);tables=verify(conn)
        if after!=before:raise ValueError('clone data changed')
    proof=dict(outcome='REGISTRATION_CLONE_VERIFIED',source=SOURCE,target=TARGET,main=base.MAIN,clone=CLONE,
        migrations=base.migration_hashes(),backup=dict(path=str(backup),sha256=base.digest(backup),bytes=backup.stat().st_size),
        before=before,after=after,tables=tables,at=datetime.now(timezone.utc).isoformat())
    base.protected_write(STATE/'prepare.json',proof)
    return proof


def validate_proof(proof):
    backup=STATE/'aos_meta_head-before-a0v_030.dump'
    if (proof.get('outcome')!='REGISTRATION_CLONE_VERIFIED' or proof.get('source')!=SOURCE or proof.get('target')!=TARGET
            or proof.get('main')!=base.MAIN or proof.get('clone')!=CLONE or proof.get('migrations')!=base.migration_hashes()
            or proof.get('backup',{}).get('path')!=str(backup) or proof['backup'].get('sha256')!=base.digest(backup)
            or proof.get('before')!=proof.get('after') or not proof.get('before')):
        raise ValueError('preparation proof differs')


def apply():
    require_lease()
    if (STATE/'apply-intent.json').exists():raise ValueError('existing apply intent requires readback')
    proof=json.loads((STATE/'prepare.json').read_text());validate_proof(proof)
    identity_clone()
    with base.connect(CLONE) as conn:
        if base.version(conn)!=[TARGET] or base.fingerprint(conn)!=proof['before']:raise ValueError('clone drifted')
        verify(conn)
    with base.connect(base.MAIN) as conn:
        if base.version(conn)!=[SOURCE] or base.fingerprint(conn)!=proof['before']:raise ValueError('main drifted')
    base.protected_write(STATE/'apply-intent.json',dict(target=TARGET,migrations=proof['migrations'],at=datetime.now(timezone.utc).isoformat()))
    upgrade(base.MAIN)
    with base.connect(base.MAIN) as conn:
        if base.fingerprint(conn)!=proof['before']:raise ValueError('main data changed')
        tables=verify(conn)
    result=dict(outcome='REGISTRATION_LOCAL_SCHEMA_DEPLOYED',revision=TARGET,tables=tables,businessWrites=0,at=datetime.now(timezone.utc).isoformat())
    base.protected_write(STATE/'apply.json',result)
    return result


ROLE='aos_ecommerce_registration_control'
INSTALLATION='97aeb2e7-59ba-40f6-89a3-fb0293bc0497'


def identity_clone():
    import secrets
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    require_lease()
    proof=json.loads((STATE/'prepare.json').read_text());validate_proof(proof)
    path=STATE/'registration-clone-identity.json'
    if not path.exists():
        with base.connect(base.MAIN) as conn:
            if conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(ROLE,)).fetchone():
                raise ValueError('existing login without retained identity requires inspection')
        args=base.parameters(CLONE);password=secrets.token_urlsafe(48)
        args.update(user=ROLE,password=password)
        payload=dict(schemaVersion='aos.ecommerce.registration-identity/v1',role=ROLE,dsn=make_conninfo(**args))
        with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as out:
            json.dump(payload,out);out.flush();os.fsync(out.fileno())
        with base.connect(base.MAIN) as conn:
            conn.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEROLE NOCREATEDB NOREPLICATION').format(sql.Identifier(ROLE),sql.Literal(password)))
            conn.execute(sql.SQL('GRANT aos_runtime,aos_extension_maintainer TO {}').format(sql.Identifier(ROLE)))
            conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(CLONE),sql.Identifier(ROLE)))
    return verify_identity_target(path,CLONE,'identity-clone.json')


def verify_identity_target(path,database,proof_name):
    previous=os.environ.get('AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE')
    os.environ['AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE']=str(path)
    try:
        from aos_api.ecommerce_growth_registration_connection import registration_connection
        from aos_api.asset_registry.control_wiring import build_runtime_control_plane
        from aos_api.tenant_scope import TenantScope
        with registration_connection() as conn:
            if conn.info.dbname!=database:raise ValueError('clone identity target differs')
        owner=build_runtime_control_plane(registration_connect=registration_connection).first_dispatch_registration_service
        status=owner.registration_status(scope=TenantScope('org-org','dev-project'),installation_id=INSTALLATION,actor='a0v-ecommerce-growth-1.4-runtime-owner')
        if status['state']!='unregistered' or status['allowedActions']:raise ValueError('clone status differs')
        from aos_api.asset_registry.errors import DutySeparationRequiredError
        for scope,actor in [(TenantScope('dev-org','dev-project'),'a0v-ecommerce-growth-1.4-runtime-owner'),
                            (TenantScope('org-org','dev-project'),'user:dev')]:
            try:owner.registration_status(scope=scope,installation_id=INSTALLATION,actor=actor)
            except (LookupError,PermissionError,DutySeparationRequiredError):pass
            else:raise ValueError('negative scope or role was not refused')
        result=dict(outcome='REGISTRATION_IDENTITY_READ_VERIFIED',database=database,role=ROLE,currentStatus=status['state'],defaultActorDenied=True,negativeTenantDenied=True,businessWrites=0,at=datetime.now(timezone.utc).isoformat())
        if not (STATE/proof_name).exists():base.protected_write(STATE/proof_name,result)
        return result
    finally:
        if previous is None:os.environ.pop('AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE',None)
        else:os.environ['AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE']=previous


def identity_main():
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    require_lease();identity_clone()
    applied=json.loads((STATE/'apply.json').read_text())
    if applied.get('outcome')!='REGISTRATION_LOCAL_SCHEMA_DEPLOYED' or applied.get('revision')!=TARGET:
        raise ValueError('verified main deployment required')
    with base.connect(base.MAIN) as conn:
        if base.version(conn)!=[TARGET]:raise ValueError('main version differs')
        verify(conn)
    value=json.loads((STATE/'registration-clone-identity.json').read_text())
    args=conninfo_to_dict(value['dsn'])
    if args.get('dbname')!=CLONE or args.get('user')!=ROLE:raise ValueError('source identity differs')
    args['dbname']=base.MAIN;value['dsn']=make_conninfo(**args)
    path=STATE/'registration-main-identity.json'
    if path.exists():
        if json.loads(path.read_text())!=value:raise ValueError('retained main identity differs')
    else:
        with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as out:
            json.dump(value,out);out.flush();os.fsync(out.fileno())
    return verify_identity_target(path,base.MAIN,'identity-main.json')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply','identity-clone','identity-main']);args=parser.parse_args()
    try:
        result={'prepare':prepare,'apply':apply,'identity-clone':identity_clone,'identity-main':identity_main}[args.action]()
        print(json.dumps({k:v for k,v in result.items() if k in ('outcome','revision','at','businessWrites')}))
    except Exception as error:
        print(json.dumps(dict(outcome='STOPPED_FOR_INSPECTION',errorType=type(error).__name__,sqlstate=getattr(error,'sqlstate',None))))
        raise SystemExit(1)
