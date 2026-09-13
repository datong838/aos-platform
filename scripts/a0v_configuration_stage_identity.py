"""Provision a private configuration transport identity; no business membership or approval."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import subprocess

import a0v_configuration_stage_deploy as deployment

ROOT=deployment.ROOT
STATE=deployment.STATE
ROLE='aos_configuration_stage_transport_20260914'
TASK='A0V-CONFIGURATION-STAGE-API-IDENTITY-20260914'
SUBJECT='a0v-ecommerce-growth-1.4-runtime-owner'
SCHEMA='aos.runtime-configuration-api-identity/v1'


def require_lease():
    leases=json.loads((ROOT.parent/'docs/palantier/AOS项目开发上下文/memory/leases.json').read_text())['leases']
    found=[x for x in leases if x['task_id']==TASK]
    if (len(found)!=1 or found[0]['owner']!='m1' or found[0]['status']!='ACTIVE'
        or datetime.fromisoformat(found[0]['lease_expires_at'])<=datetime.now(timezone.utc)
        or subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='m1'):
        raise ValueError('identity deployment lease required')


def _assert_database(database):
    with deployment.storage.connect(database) as conn:
        if deployment.storage.version(conn)!=[deployment.TARGET]:raise ValueError('038 schema required')
        deployment.verify(conn)
        return deployment.storage.fingerprint(conn)


def _read_private(path):
    from aos_api.extension_runtime.restricted_api_identity import read_identity
    return read_identity(str(path),schema_version=SCHEMA,logical_role='aos_configuration_stage_api',label='Configuration staging')


def verify(path,database):
    import psycopg
    from aos_api.extension_runtime.configuration_stage_connection import CREDENTIAL_FILE, configuration_stage_connection
    from aos_api.tenant_scope import TenantScope
    before=_assert_database(database)
    previous=os.environ.get(CREDENTIAL_FILE);os.environ[CREDENTIAL_FILE]=str(path)
    denied=[]
    def must_deny(operation,label):
        try:operation()
        except psycopg.errors.InsufficientPrivilege:denied.append(label)
        else:raise ValueError('required identity denial missing')
    positive=TenantScope('org-org','dev-project')
    try:
        with configuration_stage_connection(scope=positive,subject=SUBJECT) as conn:
            if conn.info.dbname!=database:raise ValueError('identity database differs')
            row=conn.execute('SELECT session_user AS login,current_user AS role').fetchone()
            if row!=dict(login=ROLE,role='aos_configuration_stage_api'):raise ValueError('transport role differs')
            conn.execute('SELECT public.extension_configuration_stage_principal_a0v_037(%s,%s::uuid)',
                         (SUBJECT,'97aeb2e7-59ba-40f6-89a3-fb0293bc0497'))
            value=conn.execute('SELECT public.extension_configuration_stage_query_a0v_037(%s,%s::uuid) AS result',
                (SUBJECT,'00000000-0000-0000-0000-000000000000')).fetchone()
            if value['result'] is not None:raise ValueError('absent request metadata differs')
            value=conn.execute('SELECT public.extension_configuration_stage_lookup_a0v_038(%s,%s) AS result',
                (SUBJECT,'identity-read-only-absent-key')).fetchone()
            if value['result'] is not None:raise ValueError('absent key metadata differs')
        def probe(scope,query,args=()):
            with configuration_stage_connection(scope=scope,subject=SUBJECT) as conn:conn.execute(query,args)
        must_deny(lambda:probe(positive,'SELECT public.extension_configuration_stage_principal_a0v_037(%s,NULL)',('user:dev',)),'subject-mismatch')
        must_deny(lambda:probe(TenantScope('dev-org','dev-project'),'SELECT public.extension_configuration_stage_principal_a0v_037(%s,NULL)',(SUBJECT,)),'negative-tenant')
        must_deny(lambda:probe(positive,'SELECT * FROM public.extension_runtime_configuration_stage_request LIMIT 1'),'direct-queue')
        must_deny(lambda:probe(positive,'SELECT * FROM public.extension_runtime_configuration LIMIT 1'),'direct-configuration')
        must_deny(lambda:probe(positive,'SELECT public.extension_ui_read_host_principal_a0v_033(%s,ARRAY[]::text[])',(SUBJECT,)),'host-function')
    finally:
        if previous is None:os.environ.pop(CREDENTIAL_FILE,None)
        else:os.environ[CREDENTIAL_FILE]=previous
    if _assert_database(database)!=before:raise ValueError('business data changed during verification')
    result=dict(outcome='CONFIGURATION_STAGE_TRANSPORT_IDENTITY_VERIFIED',database=database,role=ROLE,
        identityFileHash=deployment.storage.digest(path),
        reachableRole='aos_configuration_stage_api',positiveSubjectVerified=True,installationVisibilityVerified=True,
        absentRequestReturnedNull=True,absentKeyReturnedNull=True,
        denials=denied,queueCount=0,businessWrites=0,at=datetime.now(timezone.utc).isoformat())
    proof=STATE/('configuration-identity-main-proof.json' if database==deployment.storage.MAIN else 'configuration-identity-clone-proof.json')
    if not proof.exists():deployment.protected_write(proof,result)
    return result


def clone():
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    require_lease();_assert_database(deployment.CLONE)
    path=STATE/'configuration-stage-clone-identity.json'
    if not path.exists():
        with deployment.storage.connect(deployment.storage.MAIN) as conn:
            if conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(ROLE,)).fetchone():
                raise ValueError('existing transport role without retained identity requires inspection')
        args=deployment.storage.parameters(deployment.CLONE)
        password=secrets.token_urlsafe(48)
        args.update(user=ROLE,password=password)
        deployment.protected_write(path,dict(schemaVersion=SCHEMA,role=ROLE,dsn=make_conninfo(**args)))
        with deployment.storage.connect(deployment.storage.MAIN) as conn:
            conn.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEROLE NOCREATEDB NOREPLICATION').format(sql.Identifier(ROLE),sql.Literal(password)))
            conn.execute(sql.SQL('GRANT aos_configuration_stage_api TO {}').format(sql.Identifier(ROLE)))
            conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(deployment.CLONE),sql.Identifier(ROLE)))
    return verify(path,deployment.CLONE)


def main_identity():
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    require_lease()
    clone_path=STATE/'configuration-stage-clone-identity.json'
    verify(clone_path,deployment.CLONE)
    proof=json.loads((STATE/'apply.json').read_text())
    if proof.get('outcome')!='CONFIGURATION_STAGE_LOCAL_SCHEMA_DEPLOYED' or proof.get('revision')!=deployment.TARGET:
        raise ValueError('verified main deployment required')
    _assert_database(deployment.storage.MAIN)
    identity=_read_private(clone_path);args=conninfo_to_dict(identity['dsn'])
    if identity['role']!=ROLE or args.get('user')!=ROLE or args.get('dbname')!=deployment.CLONE:
        raise ValueError('retained clone identity differs')
    args['dbname']=deployment.storage.MAIN
    identity=dict(identity,dsn=make_conninfo(**args))
    path=STATE/'configuration-stage-main-identity.json'
    if path.exists():
        if _read_private(path)!=identity:raise ValueError('retained main identity differs')
    else:
        deployment.protected_write(path,identity)
        with deployment.storage.connect(deployment.storage.MAIN) as conn:
            conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(deployment.storage.MAIN),sql.Identifier(ROLE)))
    return verify(path,deployment.storage.MAIN)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('clone','main'));args=parser.parse_args()
    try:result=clone() if args.mode=='clone' else main_identity()
    except Exception as exc:
        print(json.dumps(dict(outcome='CONFIGURATION_STAGE_IDENTITY_NEEDS_INSPECTION',phase=args.mode,errorType=type(exc).__name__)))
        raise SystemExit(2) from None
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
