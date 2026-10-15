"""Original W6-009 DDL in an owned disposable tmpfs, never original business DB."""
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
E=Path(__file__).resolve().parent;R=E.parents[1]
os.environ.update(AOS_DATABASE_URL='postgresql://placeholder@127.0.0.1:1/unused',AOS_DOTENV_DISABLED='1')
F=E/'private/candidate-source-r3';sys.path.insert(0,str(F/'services/aos-api'));sys.path.insert(0,str(R/'scripts/memory'))
import memoryctl as m
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_customer_closure_readonly import CustomerClosureReadonlyReader,CustomerClosureReadonlyError,MAX_ITEM_BYTES
from aos_api.ecommerce_three_module_closure_readonly import CreatorClosureReadonlyReader
from aos_api.ecommerce_workshop_three_module_closure import ThreeModule
spec=importlib.util.spec_from_file_location('closure_native_fixture',F/'services/aos-api/tests/test_ecommerce_three_module_closure_readonly.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
spec2=importlib.util.spec_from_file_location('customer_closure_native_fixture',F/'services/aos-api/tests/test_ecommerce_customer_closure_readonly.py')
c=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(c)
OWNER='codex-01a13484-f019-7d82-94ce-812396db9124'
NAME='qyh-customer-closure-native-20261015-r1';PORT=18625
IMAGE='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
SCOPE=TenantScope('dev-org','fixture-project')
def docker(*args):return subprocess.run(['docker','--context','colima-aos-extension',*args],capture_output=True,text=True)
def save(name,value):
    m.scan_secrets(value)
    with (E/name).open('x') as stream:
        json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno())
lease=next(r for r in m.load_leases(m.DEFAULT_PATHS)['leases'] if r['task_id']==E.name)
assert lease['owner']==OWNER and lease['base_revision']=='AOS-002038'
assert datetime.datetime.fromisoformat(lease['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
assert m.load_authority(m.DEFAULT_PATHS)['project_revision']=='AOS-002038'
assert not (E/'native-r1-intent.json').exists() and docker('inspect',NAME).returncode!=0
assert not subprocess.run(['lsof','-t',f'-iTCP:{PORT}','-sTCP:LISTEN'],capture_output=True,text=True).stdout.strip()
password=secrets.token_hex(24)
save('native-r1-intent.json',dict(name=NAME,port=PORT,tmpfs=True,owner=OWNER,originalVolumeTouched=False))
created=docker('run','-d','--name',NAME,'--label','aos.owner='+OWNER,'--label','aos.task='+E.name,
    '--tmpfs','/var/lib/postgresql/data:rw,size=512m','-p',f'127.0.0.1:{PORT}:5432','-e','POSTGRES_PASSWORD='+password,IMAGE)
assert created.returncode==0;cid=created.stdout.strip()
save('native-r1-created.json',dict(containerId=cid,name=NAME,owner=OWNER))
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
        source=(F/'services/aos-api/alembic/versions/w6_009_three_module_closure.py').read_text();tree=ast.parse(source)
        nodes=[n for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name in {'_scope','upgrade'}) or
               (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_BINDING_TABLES' for t in n.targets))]
        class Op:
            def execute(self,statement):conn.execute(statement)
        env={'op':Op()};exec(compile(ast.Module(body=nodes,type_ignores=[]),'exact-owned-w6_009-ddl','exec'),env);env['upgrade']()
    own=c.customer_rows(scope=SCOPE)
    creator=f.authority_rows('creator',scope=SCOPE)
    foreign=c.customer_rows(scope=TenantScope('foreign-fixture',SCOPE.project_id))
    def insert_rows(rows):
        with psycopg.connect(user='postgres',**args) as conn:
            for kind,row in rows.items():
                table=f.TABLES[kind];identity='closure_id' if kind=='closure' else 'binding_id'
                extra_column='source_id' if kind=='closure' else 'closure_id'
                extra_value=row['source_id'] if kind=='closure' else row['closure_id']
                conn.execute(f'INSERT INTO {table}(org_id,project_id,{identity},revision,module,{extra_column},content_hash,authority_data,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)',
                    (row['org_id'],row['project_id'],row['resource_id'],1,row['module'],extra_value,row['content_hash'],json.dumps(row['authority_data']),row['created_at']))
    injected=[False];connection_facts=[]
    def concurrent_closure():
        with psycopg.connect(user='postgres',**args) as conn:
            now=conn.execute('SELECT transaction_timestamp() AS now').fetchone()['now']
        store=f.ProducerFixture();service=f.EcommerceWorkshopThreeModuleClosureService(store)
        item=service.compile(SCOPE,f.CompileThreeModuleClosureRequest(module='customer',sourceRef=f.ref('CustomerBatchStartDecisionRevision','customer-after-cutoff')),'synthetic-concurrent',now=now)
        insert_rows({'closure':dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,
            resource_id=item.closure_id,closure_id=item.closure_id,module='customer',source_id=item.source_ref.resource_id,
            content_hash=item.content_hash,authority_data=item.model_dump(mode='json',by_alias=True),created_at=now)})
    @contextlib.contextmanager
    def connection(scope):
        assert scope==SCOPE
        with psycopg.connect(user='fixture_reader',**args) as conn:
            conn.read_only=True;conn.isolation_level=IsolationLevel.REPEATABLE_READ
            conn.execute('SET LOCAL ROLE aos_runtime')
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
            connection_facts.append(dict(conn.execute("SELECT current_user AS role,current_setting('transaction_read_only') AS readonly,current_setting('transaction_isolation') AS isolation").fetchone()))
            class Probe:
                read_only=conn.read_only;autocommit=conn.autocommit;isolation_level=conn.isolation_level
                def execute(self,statement,params=()):
                    result=conn.execute(statement,params)
                    if 'transaction_timestamp() AS cutoff' in statement and not injected[0]:
                        injected[0]=True;concurrent_closure()
                    return result
            yield Probe()
    reader=CustomerClosureReadonlyReader(connect_factory=connection)
    injected[0]=True
    empty=reader.read(SCOPE)
    assert empty.latest_closure is empty.latest_usage is empty.latest_effect is empty.latest_handoff is None
    assert len(empty.blockers)==4 and not empty.allowed_commands
    injected[0]=False
    for rows in (own,creator,foreign):insert_rows(rows)
    first,second=reader.read(SCOPE),reader.read(SCOPE)
    assert first.latest_closure.source_ref.resource_id=='customer-fixture'
    assert second.latest_closure.source_ref.resource_id=='customer-after-cutoff'
    assert first.latest_usage.quantity is None and first.latest_effect.maturity_status=='immature'
    assert first.latest_handoff.business_decision=='request_more' and not first.allowed_commands
    assert second.latest_usage is second.latest_effect is second.latest_handoff is None
    creator_view=CreatorClosureReadonlyReader(connect_factory=connection).read(SCOPE)
    assert creator_view.module is ThreeModule.CREATOR and creator_view.latest_closure.source_ref.resource_type=='CreatorBatchStartDecisionRevision'
    with connection(SCOPE) as conn:
        counts={row['module']:row['n'] for row in conn.execute('SELECT module,count(*) AS n FROM ecommerce_three_module_closure_revision GROUP BY module').fetchall()}
        assert counts=={'creator':1,'customer':2}
        try:conn.execute('INSERT INTO ecommerce_three_module_closure_revision SELECT * FROM ecommerce_three_module_closure_revision')
        except psycopg.Error as error:state=error.sqlstate
        else:raise AssertionError('native write not denied')
    assert state=='25006'
    latest=second.latest_closure
    original=latest.model_dump(mode='json',by_alias=True)
    def change(payload):
        with psycopg.connect(user='postgres',**args) as conn:
            conn.execute('UPDATE ecommerce_three_module_closure_revision SET authority_data=%s::jsonb WHERE org_id=%s AND project_id=%s AND closure_id=%s',
                (json.dumps(payload),*SCOPE.key,latest.closure_id))
    change({**original,'compiledBy':'x'*(MAX_ITEM_BYTES+1)})
    try:reader.read(SCOPE)
    except CustomerClosureReadonlyError as error:oversize=error.code
    else:raise AssertionError('oversize not denied')
    assert oversize=='CUSTOMER_CLOSURE_READ_LIMIT_EXCEEDED'
    with connection(SCOPE) as conn:
        row=reader._row(conn,SCOPE,'closure',None)
        assert row['authority_data'] is None and row['payload_bytes']>MAX_ITEM_BYTES
    change({**original,'compiledBy':'fixture@example.invalid'})
    try:reader.read(SCOPE)
    except CustomerClosureReadonlyError as error:privacy=error.code
    else:raise AssertionError('private actor exposed')
    assert privacy=='CUSTOMER_CLOSURE_READ_PRIVACY_UNAVAILABLE'
    save('native-r1-result.json',dict(containerId=cid,originalVolumeTouched=False,fixtureOnlyNotOriginalSchema=True,
        exactW6DdlSha=hashlib.sha256(source.encode()).hexdigest(),sourceSha=hashlib.sha256((F/'services/aos-api/aos_api/ecommerce_customer_closure_readonly.py').read_bytes()).hexdigest(),
        originalCompilerWithSyntheticResolvers=True,productionAuthority=False,customerSavedSnapshotNotCurrentSourceAuthority=True,
        snapshotSourceIds=[first.latest_closure.source_ref.resource_id,second.latest_closure.source_ref.resource_id],
        trueEmptyFourBlockers=True,fiveAxesPreserved=True,creatorStillCreator=True,foreignRowsHiddenWithoutWhere=True,visibleClosureCounts=counts,
        writeDeniedSqlstate=state,sqlCaseNull=True,oversizeError=oversize,privacyError=privacy,connectionFacts=connection_facts,wholeGoalComplete=False))
    print(json.dumps(dict(snapshot=['customer-fixture','customer-after-cutoff'],creatorPreserved=True,writeDenied=state,sqlCaseNull=True,originalVolumeTouched=False)))
finally:
    owned=json.loads(docker('inspect',NAME).stdout)[0]
    assert owned['Id']==cid and owned['Config']['Labels']['aos.owner']==OWNER
    assert docker('stop',NAME).returncode==0
    after=json.loads(docker('inspect',NAME).stdout)[0];assert after['Id']==cid and not after['State']['Running']
    save('native-r1-stopped.json',dict(containerId=cid,stopped=True,originalVolumeTouched=False))
