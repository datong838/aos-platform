"""Scoped migration/acceptance helpers for configured-unactivated retirement."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/aos-api'))
from a0v_formal_text_model_renewal import database_connect
CLONE='aos_config_retirement_20260912'
MAIN='aos_meta_head'
INSTALLATION='e42e042b-1fe7-4cfa-bb83-469ff256081d'


def parameters(database):
    if database not in (CLONE,MAIN):raise ValueError('EXACT_RETIREMENT_DATABASE_REQUIRED')
    with database_connect(MAIN)() as c:
        values=c.info.get_parameters();values['password']=c.info.password
    values['dbname']=database
    return values


@contextmanager
def connect(database):
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(**parameters(database),row_factory=dict_row) as conn:
        if conn.info.dbname!=database:raise ValueError('RETIREMENT_DATABASE_DRIFT')
        yield conn


def upgrade(database):
    from sqlalchemy import URL
    from alembic.config import Config
    from alembic import command
    with connect(database) as c:
        versions=[r['version_num'] for r in c.execute('SELECT version_num FROM alembic_version').fetchall()]
    if versions==['a0v_020']:return {'replayed':True,'revision':'a0v_020'}
    if versions!=['a0v_019']:raise ValueError('EXACT_MIGRATION_BASELINE_REQUIRED')
    args=parameters(database)
    url=URL.create('postgresql+psycopg',username=args['user'],password=args['password'],host=args['host'],port=int(args['port']),database=database)
    previous=os.environ.pop('AOS_DATABASE_URL',None)
    try:
        cfg=Config(str(ROOT/'services/aos-api/alembic.ini'))
        cfg.set_main_option('script_location',str(ROOT/'services/aos-api/alembic'))
        cfg.set_main_option('sqlalchemy.url',url.render_as_string(hide_password=False).replace('%','%%'))
        command.upgrade(cfg,'a0v_020')
    finally:
        if previous is not None:os.environ['AOS_DATABASE_URL']=previous
    return {'replayed':False,'revision':'a0v_020'}


def fingerprint(database, *, canary=False):
    from psycopg import sql
    result={}
    with connect(database) as conn:
        rows=conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name").fetchall()
        for row in rows:
            name=row['table_name']
            if canary:
                columns=conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name IN ('org_id','project_id')",(name,)).fetchall()
                if len(columns)!=2:continue
            query=sql.SQL("SELECT count(*) AS count,md5(string_agg(md5(row_to_json(t)::text),'' ORDER BY md5(row_to_json(t)::text))) AS digest FROM {} t").format(sql.Identifier('public',name))
            if canary:query+=sql.SQL(" WHERE org_id='dev-org' AND project_id='dev-project'")
            result[name]=dict(conn.execute(query).fetchone())
    return result


def retire_clone():
    import psycopg
    from psycopg.rows import dict_row
    from a0v_ecommerce_1_7_first_install import load,RECOVERY,TRUST_STATE
    path=RECOVERY/'state/installation-control-identity.json'
    if path.stat().st_mode & 0o777 != 0o600:raise ValueError('PRIVATE_APP_IDENTITY_REQUIRED')
    identity=json.loads(path.read_text())
    if identity['role']!='aos_a0v_installation_20260912':raise ValueError('EXACT_APP_IDENTITY_REQUIRED')
    @contextmanager
    def app_connect():
        values=parameters(CLONE);values.update(user=identity['role'],password=identity['password'])
        with psycopg.connect(**values,row_factory=dict_row) as conn:
            conn.execute('SET ROLE aos_app');conn.commit();yield conn
    legacy=load('a0v_ecommerce_invalid_baseline_uninstall')
    store,service=legacy._build(app_connect,TRUST_STATE/'signing/trust-roots.json')
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
    command=dict(installation_id=INSTALLATION,request=UninstallInstallationRequest(reason='Retire exact disabled generation after confirmed resource cleanup'),org_id='org-org',project_id='dev-project',actor='a0v-ecommerce-growth-1.4-runtime-owner',roles=['admin'],markings=[],idempotency_key='a0v-ecommerce-1.7-configured-disabled-retire-v1',if_match='"5"')
    canary_before=fingerprint(CLONE,canary=True)
    first=service.uninstall(**command)
    replay_before=fingerprint(CLONE)
    second=service.uninstall(**command)
    replay_after=fingerprint(CLONE)
    canary_after=fingerprint(CLONE,canary=True)
    if replay_before!=replay_after or canary_before!=canary_after:raise ValueError('RETIREMENT_REPLAY_OR_CANARY_DRIFT')
    record=store.get_installation(org_id='org-org',project_id='dev-project',installation_id=INSTALLATION)
    if record.state!='uninstalled' or record.active_revision is not None:raise ValueError('RETIREMENT_COMMIT_NOT_OBSERVED')
    return dict(database=CLONE,installationId=INSTALLATION,state=record.state,revision=record.current_revision,firstReplayed=first.replayed,secondReplayed=second.replayed,unchangedReplayTables=len(replay_before),unchangedCanaryTables=len(canary_before),receipt=first.response_json)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--database-name',required=True);parser.add_argument('--upgrade',action='store_true');parser.add_argument('--retire-clone',action='store_true');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.upgrade==args.retire_clone:raise ValueError('ONE_EXPLICIT_ACTION_REQUIRED')
    if args.retire_clone and args.database_name!=CLONE:raise ValueError('CLONE_ONLY_ACCEPTANCE_REQUIRED')
    result={'database':args.database_name,**upgrade(args.database_name)} if args.upgrade else retire_clone()
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
