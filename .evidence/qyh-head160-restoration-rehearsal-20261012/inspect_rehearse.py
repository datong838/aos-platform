"""Current restoration readback and exact committed-code migration on owned clone."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import urllib.request
import urllib.error

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent
DB='qyh_head160_rehearsal_20261012'
CONTEXT='colima-aos-extension'


def put(name,value):
    with (OUT/name).open('x') as stream:
        json.dump(value,stream,indent=2,ensure_ascii=False)


def container(name):
    pattern='{"Id":{{json .Id}},"Image":{{json .Image}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}},"Running":{{json .State.Running}}}'
    return json.loads(subprocess.check_output(['docker','--context',CONTEXT,'inspect','--format',pattern,name],text=True))


def fingerprint(database):
    with psycopg.connect(host='127.0.0.1',port=18431,dbname=database,user='aos_app',row_factory=dict_row) as conn:
        conn.read_only=True
        assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']=='7695416748450308141'
        conn.execute("SET LOCAL statement_timeout='60s'")
        tables=conn.execute("""SELECT n.nspname AS schema,c.relname AS name FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r'
            AND n.nspname NOT IN ('pg_catalog','information_schema')
            AND n.nspname NOT LIKE 'pg_toast%' ORDER BY n.nspname,c.relname""").fetchall()
        result={}
        for table in tables:
            query=sql.SQL("""SELECT count(*) AS rows,
                encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),'UTF8')),'hex') AS hash
                FROM (SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') AS h FROM {}.{} t) q""").format(sql.Identifier(table['schema']),sql.Identifier(table['name']))
            result[table['schema']+'.'+table['name']]=conn.execute(query).fetchone()
        return result


def http(path):
    request=urllib.request.Request('http://127.0.0.1:18080'+path,
        headers={'Authorization':'Bearer dev','X-Org-Id':'org-org','X-Project-Id':'dev-project'})
    try:
        with urllib.request.urlopen(request,timeout=15) as response:
            return response.status,json.load(response)
    except urllib.error.HTTPError as error:
        return error.code,None


if __name__=='__main__':
    assert not (OUT/'intent.json').exists(), 'Existing attempt: read-only reconcile first'
    live=container('qyh-restored-pg-20261011')
    assert live['Running'] and len(live['Mounts'])==1 and live['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011'
    assert live['Ports']['5432/tcp']==[{'HostIp':'127.0.0.1','HostPort':'18446'}]
    query="""BEGIN READ ONLY; SELECT json_build_object('schema',(SELECT version_num FROM alembic_version),
      'cluster',(SELECT system_identifier::text FROM pg_control_system()),
      'orgName',(SELECT name FROM meta_org WHERE id='org-org'),
      'installations',(SELECT count(*) FROM bundle_installation WHERE org_id='org-org' AND project_id='dev-project'),
      'enabledBindings',(SELECT count(*) FROM extension_runtime_binding WHERE org_id='org-org' AND project_id='dev-project' AND enabled)); COMMIT;"""
    current=json.loads(subprocess.check_output(['docker','--context',CONTEXT,'exec','-i','qyh-restored-pg-20261011',
        'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','aos_app','-d','aos_meta_head'],input=query,text=True))
    assert current['cluster']=='7695302940039200809' and current['orgName']=='栖月汇商贸有限公司'
    status,oidc=http('/v1/auth/oidc'); me_status,me=http('/v1/me')
    principal_status,_=http('/v1/auth/principal'); modules_status,modules=http('/v1/ecommerce-workshop/modules')
    put('current.json',{'database':current,'volume':live['Mounts'][0]['Name'],
        'oidcStatus':status,'externalJwksPresent':bool(oidc.get('jwksUrls',[])) if isinstance(oidc,dict) else None,
        'meStatus':me_status,'tokenKind':me.get('tokenKind') if isinstance(me,dict) else None,
        'principalStatus':principal_status,'modulesStatus':modules_status,
        'httpTenant':{k:me.get(k) for k in ('orgId','projectId','orgName')} if isinstance(me,dict) else None,
        'actualDatabaseWrites':0})
    clone=container('qyh-source-boundary-clone-20261011')
    assert clone['Id']=='381ac0fd489c72a5cad26a962dd59ba749d027bb61ab779703d1eb4bdb197b93' and not clone['Mounts'] and clone['Running']
    assert clone['Image']=='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    private=OUT/'private';private.mkdir(mode=0o700)
    source=private/'source';source.mkdir(mode=0o700)
    archive=subprocess.check_output(['git','archive','--format=tar',head,'services/aos-api'],cwd=ROOT)
    manifest={}
    with tarfile.open(fileobj=io.BytesIO(archive),mode='r:') as tar:
        for member in tar:
            relative=PurePosixPath(member.name)
            assert not relative.is_absolute() and '..' not in relative.parts and '.env' not in relative.parts
            assert member.isfile() or member.isdir()
            if member.isfile():
                data=tar.extractfile(member).read();path=source/member.name
                path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                with path.open('xb') as stream:stream.write(data)
                path.chmod(0o600);manifest[member.name]=hashlib.sha256(data).hexdigest()
    api=source/'services/aos-api'
    env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR','LANG')}
    env.update({'AOS_DOTENV_DISABLED':'1','PYTHONPATH':str(api)})
    python=str(ROOT/'services/aos-api/.venv/bin/python')
    check="from alembic.config import Config;from alembic.script import ScriptDirectory;import aos_api;from pathlib import Path;c=Config('alembic.ini');c.set_main_option('script_location','alembic');assert Path(aos_api.__file__).resolve().is_relative_to(Path.cwd());assert ScriptDirectory.from_config(c).get_heads()==['a0v_160'];print('EXACT_HEAD160_IMPORT_PASS')"
    preflight=subprocess.run([python,'-c',check],cwd=api,env=env,capture_output=True,text=True)
    (OUT/'source-import.log').write_text(preflight.stdout+preflight.stderr)
    assert preflight.returncode==0, 'Committed migration import failed; no database created'
    before=fingerprint('aos_meta_head')
    put('baseline.json',before)
    with psycopg.connect(host='127.0.0.1',port=18431,dbname='postgres',user='aos_app',autocommit=True) as admin:
        assert admin.execute('SELECT 1 FROM pg_database WHERE datname=%s',(DB,)).fetchone() is None
        put('intent.json',{'head':head,'ownedCloneDatabase':DB,'sourceTemplate':'aos_meta_head','formalDatabaseTouched':False})
        admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE aos_meta_head').format(sql.Identifier(DB)))
    assert fingerprint(DB)==before
    dsn=f'postgresql://aos_app@127.0.0.1:18431/{DB}'
    env['AOS_DATABASE_URL']=dsn
    command="from alembic.config import Config;from alembic import command;c=Config('alembic.ini');c.set_main_option('script_location','alembic');c.set_main_option('sqlalchemy.url',__import__('os').environ['AOS_DATABASE_URL']);command.upgrade(c,'a0v_160')"
    attempt=subprocess.run([python,'-c',command],cwd=api,env=env,capture_output=True,text=True)
    (OUT/'migration.log').write_text(attempt.stdout+attempt.stderr)
    assert attempt.returncode==0, 'Migration result needs reconciliation; do not resend'
    after=fingerprint(DB); template_after=fingerprint('aos_meta_head');assert template_after==before
    changed={k for k in before if after.get(k)!=before[k]};assert changed=={'public.alembic_version'}
    added=set(after)-set(before)
    assert added=={'public.aip_skill_eval_intent','public.aip_skill_eval_dispatch','public.aip_skill_eval_dispatch_observation'}
    assert all(after[k]['rows']==0 for k in added)
    with psycopg.connect(dsn,row_factory=dict_row) as conn:
        conn.read_only=True
        version=conn.execute('SELECT version_num FROM alembic_version').fetchone()['version_num'];assert version=='a0v_160'
        permission=conn.execute("SELECT has_table_privilege('aos_aip_eval_writer','aip_eval_run','UPDATE') AS allowed").fetchone()['allowed'];assert permission is False
    put('result.json',{'head':head,'candidateManifestHash':hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),
        'oldTables':len(before),'oldTableDataUnchangedExceptVersion':True,'addedTables':sorted(added),'allNewTablesEmpty':True,
        'sourceTemplateUnchanged':True,'rehearsedDatabase':DB,'rehearsedVersion':version,'writerCanUpdateRun':permission,
        'actualDatabaseVersion':current['schema'],'actualDatabaseMigrated':False,'formalLoginProven':False,'eightWorkshopsRestored':False})
    print(json.dumps({'rehearsedVersion':version,'oldTables':len(before),'oldDataUnchanged':True,'sourceTemplateUnchanged':True,'actualDatabaseMigrated':False}))
