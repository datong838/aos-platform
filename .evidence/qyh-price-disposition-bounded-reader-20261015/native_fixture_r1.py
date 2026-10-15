"""Owned tmpfs W6-006 experiment; synthetic records, never the original volume."""
from pathlib import Path
import ast
import contextlib
import datetime
import hashlib
import importlib.util
import json
import os
import secrets
import subprocess
import sys
import time

import psycopg
from psycopg import IsolationLevel, sql
from psycopg.rows import dict_row

E=Path(__file__).resolve().parent; R=E.parents[1]
os.environ.update(AOS_DATABASE_URL='postgresql://placeholder@127.0.0.1:1/unused', AOS_DOTENV_DISABLED='1')
sys.path.insert(0,str(R/'services/aos-api')); sys.path.insert(0,str(R/'scripts/memory'))
import memoryctl as m
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_price_disposition_readonly import EcommercePriceDispositionReadonlyReader, PriceDispositionReadonlyError, MAX_ROW_BYTES
from aos_api.ecommerce_workshop_price_disposition import CreatePriceCaseRequest
spec=importlib.util.spec_from_file_location('original_disposition_rows',R/'services/aos-api/tests/aip/test_ecommerce_price_disposition_readonly.py')
fixture=importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
OWNER='codex-01a13484-f019-7d82-94ce-812396db9124'
NAME='qyh-disposition-bounded-native-20261015-r1'; PORT=18619
IMAGE='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
SCOPE=TenantScope('dev-org','fixture-project')

def docker(*args):
    return subprocess.run(['docker','--context','colima-aos-extension',*args],capture_output=True,text=True)

def save(name,value):
    m.scan_secrets(value)
    with (E/name).open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())

leases=m.load_leases(m.DEFAULT_PATHS)['leases']
lease=next(row for row in leases if row['task_id']==E.name)
assert lease['owner']==OWNER and lease['base_revision']=='AOS-002034'
assert datetime.datetime.fromisoformat(lease['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
assert m.load_authority(m.DEFAULT_PATHS)['project_revision']=='AOS-002034'
assert not (E/'native-r1-intent.json').exists() and docker('inspect',NAME).returncode!=0
assert not subprocess.run(['lsof','-t',f'-iTCP:{PORT}','-sTCP:LISTEN'],capture_output=True,text=True).stdout.strip()
password=secrets.token_hex(24)
save('native-r1-intent.json',dict(name=NAME,port=PORT,owner=OWNER,tmpfs=True,originalVolumeTouched=False))
created=docker('run','-d','--name',NAME,'--label','aos.owner='+OWNER,'--label','aos.task='+E.name,
    '--tmpfs','/var/lib/postgresql/data:rw,size=512m','-p',f'127.0.0.1:{PORT}:5432','-e','POSTGRES_PASSWORD='+password,IMAGE)
assert created.returncode==0
cid=created.stdout.strip();save('native-r1-created.json',dict(containerId=cid,name=NAME,owner=OWNER))
args=dict(host='127.0.0.1',port=PORT,dbname='postgres',password=password,row_factory=dict_row,connect_timeout=1)
try:
    for _ in range(100):
        try:
            with psycopg.connect(user='postgres',**args) as conn:conn.execute('SELECT 1')
            break
        except psycopg.OperationalError:time.sleep(.1)
    else:raise RuntimeError('fixture startup unresolved')
    with psycopg.connect(user='postgres',**args) as conn:
        conn.execute('CREATE ROLE aos_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS')
        conn.execute(sql.SQL('CREATE ROLE fixture_reader LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}').format(sql.Literal(password)))
        conn.execute('GRANT aos_runtime TO fixture_reader')
        conn.execute('CREATE TABLE meta_workspace(org_id text,project_id text,PRIMARY KEY(org_id,project_id))')
        conn.execute('INSERT INTO meta_workspace VALUES(%s,%s),(%s,%s)',(*SCOPE.key,'foreign-fixture',SCOPE.project_id))
        source=(R/'services/aos-api/alembic/versions/w6_006_price_disposition.py').read_text()
        tree=ast.parse(source)
        nodes=[n for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name=='upgrade') or
               (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TABLES' for t in n.targets))]
        class Op:
            def execute(self,statement):conn.execute(statement)
        env={'op':Op()};exec(compile(ast.Module(body=nodes,type_ignores=[]),'exact-owned-w6_006-ddl','exec'),env);env['upgrade']()
        at=conn.execute('SELECT transaction_timestamp() AS now').fetchone()['now']-datetime.timedelta(seconds=5)
    f,tables=fixture.saved_rows(scope=SCOPE,at=at)
    _,foreign=fixture.saved_rows(scope=TenantScope('foreign-fixture',SCOPE.project_id),at=at)
    identities=dict(env['TABLES'])
    def insert_row(conn,table,row):
        identity=identities[table]
        conn.execute(f'INSERT INTO {table}(org_id,project_id,{identity},revision,content_hash,authority_data,created_at) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s)',
            (row['org_id'],row['project_id'],row['identity'],row['revision'],row['content_hash'],json.dumps(row['authority_data']),row['created_at']))
    with psycopg.connect(user='postgres',**args) as conn:
        for collection in (tables,foreign):
            for table,rows in collection.items():
                for row in rows:insert_row(conn,table,row)
    injected=[False];observations=[];payload_calls=[]
    def concurrent_case():
        store,service,original_case,_sku=f.authority_fixture()
        payload={name:getattr(original_case,name) for name in CreatePriceCaseRequest.model_fields}
        payload['case_id']='case-after-cutoff'
        with psycopg.connect(user='postgres',**args) as conn:
            now=conn.execute('SELECT transaction_timestamp() AS now').fetchone()['now']
            case=service.create_case(SCOPE,CreatePriceCaseRequest.model_validate(payload),'synthetic-concurrent',now=now)
            insert_row(conn,'ecommerce_price_case_revision',dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,
                identity=case.case_id,revision=case.revision,content_hash=case.content_hash,
                authority_data=case.model_dump(mode='json',by_alias=True),created_at=case.created_at))
    @contextlib.contextmanager
    def connection(scope):
        assert scope==SCOPE
        with psycopg.connect(user='fixture_reader',**args) as conn:
            conn.read_only=True;conn.isolation_level=IsolationLevel.REPEATABLE_READ
            conn.execute('SET LOCAL ROLE aos_runtime')
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
            observations.append(dict(conn.execute("SELECT current_user AS role,current_setting('transaction_read_only') AS readonly,current_setting('transaction_isolation') AS isolation").fetchone()))
            class Probe:
                read_only=conn.read_only;autocommit=conn.autocommit;isolation_level=conn.isolation_level
                def execute(self,statement,params=()):
                    result=conn.execute(statement,params)
                    if 'THEN authority_data' in statement:payload_calls.append(statement)
                    if 'transaction_timestamp() AS cutoff' in statement and not injected[0]:
                        injected[0]=True;concurrent_case()
                    return result
            yield Probe()
    reader=EcommercePriceDispositionReadonlyReader(connect_factory=connection)
    first,second=reader.read(SCOPE),reader.read(SCOPE)
    assert (first.case_count,second.case_count)==(1,2)
    assert sum(first.disposition_counts.values())==sum(second.disposition_counts.values())==8
    assert first.latest_observation.disposition_ref.resource_id!=first.latest_disposition.disposition_id
    assert not first.allowed_commands and not second.allowed_commands
    with connection(SCOPE) as conn:
        counts={table:conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] for table in identities}
        assert counts['ecommerce_price_case_revision']==2 and counts['ecommerce_price_disposition_revision']==8
        try:conn.execute('INSERT INTO ecommerce_price_case_revision SELECT * FROM ecommerce_price_case_revision')
        except psycopg.Error as error:state=error.sqlstate
        else:raise AssertionError('native write not denied')
    assert state=='25006'
    original=tables['ecommerce_price_case_revision'][0]['authority_data']
    def change(payload):
        with psycopg.connect(user='postgres',**args) as conn:
            conn.execute('UPDATE ecommerce_price_case_revision SET authority_data=%s::jsonb WHERE org_id=%s AND project_id=%s AND case_id=%s',
                (json.dumps(payload),*SCOPE.key,'case-1'))
    change({**original,'createdBy':'x'*(MAX_ROW_BYTES+1)})
    before=len(payload_calls)
    try:reader.read(SCOPE)
    except PriceDispositionReadonlyError as error:oversize=error.code
    else:raise AssertionError('oversize transferred')
    assert oversize=='PRICE_DISPOSITION_READ_LIMIT_EXCEEDED' and len(payload_calls)==before
    with connection(SCOPE) as conn:
        rows=reader._query(conn,SCOPE,'ecommerce_price_case_revision','case_id',payload=True)
        assert next(row for row in rows if row['identity']=='case-1')['authority_data'] is None
    change({**original,'createdBy':'fixture@example.invalid'})
    try:reader.read(SCOPE)
    except PriceDispositionReadonlyError as error:privacy=error.code
    else:raise AssertionError('private actor exposed')
    assert privacy=='PRICE_DISPOSITION_READ_SENSITIVE_CONTENT'
    save('native-r1-result.json',dict(containerId=cid,fixtureOnlyNotOriginalSchema=True,
        exactW6DdlSha=hashlib.sha256(source.encode()).hexdigest(),
        sourceSha=hashlib.sha256((R/'services/aos-api/aos_api/ecommerce_price_disposition_readonly.py').read_bytes()).hexdigest(),
        originalProducerWithSyntheticMemoryResolvers=True,productionGateAuthorization=False,originalVolumeTouched=False,
        snapshotCaseCounts=[first.case_count,second.case_count],savedRevisionCount=8,
        earlierFrozenObservationAccepted=True,observations=observations,foreignRowsHiddenWithoutWhere=True,
        readonlyRoleCounts=counts,writeDeniedSqlstate=state,oversizeBeforePayload=True,sqlCaseReturnedNull=True,
        oversizeError=oversize,privacyError=privacy,commandsEmpty=True,wholeGoalComplete=False))
    print(json.dumps(dict(snapshot=[first.case_count,second.case_count],savedRevisions=8,writeDenied=state,
        oversizeBeforePayload=True,sqlCaseNull=True,privacy=privacy,originalVolumeTouched=False)))
finally:
    owned=json.loads(docker('inspect',NAME).stdout)[0]
    assert owned['Id']==cid and owned['Config']['Labels']['aos.owner']==OWNER
    assert docker('stop',NAME).returncode==0
    after=json.loads(docker('inspect',NAME).stdout)[0]
    assert after['Id']==cid and not after['State']['Running']
    save('native-r1-stopped.json',dict(containerId=cid,stopped=True,originalVolumeTouched=False))
