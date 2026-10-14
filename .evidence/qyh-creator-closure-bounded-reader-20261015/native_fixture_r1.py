"""Owned tmpfs PG, exact w6_009 four-table DDL; synthetic evidence only."""
from pathlib import Path
import ast,contextlib,datetime,hashlib,importlib.util,json,os,secrets,subprocess,sys,time
import psycopg
from psycopg import IsolationLevel,sql
from psycopg.rows import dict_row
E=Path(__file__).resolve().parent;R=E.parents[1]
os.environ.update(AOS_DATABASE_URL='postgresql://placeholder@127.0.0.1:1/unused',AOS_DOTENV_DISABLED='1')
sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.ecommerce_three_module_closure_readonly import CreatorClosureReadonlyReader,CreatorClosureReadonlyError
from aos_api.ecommerce_workshop_three_module_closure import EcommerceWorkshopThreeModuleClosureService,ThreeModuleClosureRevision,BindThreeModuleUsageRequest
spec=importlib.util.spec_from_file_location('closure_fixture_cases',R/'services/aos-api/tests/test_ecommerce_three_module_closure_readonly.py');cases=importlib.util.module_from_spec(spec);spec.loader.exec_module(cases)
OWNER='codex-01a13484-f019-7d82-94ce-812396db9124';NAME='qyh-creator-closure-bounded-native-20261015-r1';PORT=18616
IMAGE='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
SCOPE=cases.SCOPE;TABLES=cases.TABLES

def docker(*args):return subprocess.run(['docker','--context','colima-aos-extension',*args],capture_output=True,text=True)
def save(name,obj):
 with (E/name).open('x') as f:json.dump(obj,f,indent=2);f.flush();os.fsync(f.fileno())
lease=json.loads((R.parent/'docs/palantier/AOS项目开发上下文/memory/receipts/tasks'/(E.name+'.json')).read_text());assert lease['owner']==OWNER and lease['base_revision']=='AOS-002031' and datetime.datetime.fromisoformat(lease['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
assert not (E/'native-r1-intent.json').exists() and docker('inspect',NAME).returncode!=0
assert not subprocess.run(['lsof','-t',f'-iTCP:{PORT}','-sTCP:LISTEN'],capture_output=True,text=True).stdout.strip()
password=secrets.token_hex(24);save('native-r1-intent.json',dict(name=NAME,owner=OWNER,tmpfs=True,port=PORT,originalVolumeTouched=False))
created=docker('run','-d','--name',NAME,'--label','aos.owner='+OWNER,'--label','aos.task='+E.name,'--tmpfs','/var/lib/postgresql/data:rw,size=512m','-p',f'127.0.0.1:{PORT}:5432','-e','POSTGRES_PASSWORD='+password,IMAGE);assert created.returncode==0
cid=created.stdout.strip();save('native-r1-created.json',dict(containerId=cid,name=NAME,owner=OWNER))
args=dict(host='127.0.0.1',port=PORT,dbname='postgres',password=password,row_factory=dict_row,connect_timeout=1)
try:
 for _ in range(100):
  try:
   with psycopg.connect(user='postgres',**args) as c:c.execute('SELECT 1')
   break
  except psycopg.OperationalError:time.sleep(.1)
 else:raise RuntimeError('fixture startup unresolved')
 with psycopg.connect(user='postgres',**args) as c:
  c.execute('CREATE ROLE aos_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS')
  c.execute(sql.SQL('CREATE ROLE fixture_reader LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}').format(sql.Literal(password)))
  c.execute('GRANT aos_runtime TO fixture_reader')
  c.execute('CREATE TABLE meta_workspace(org_id text,project_id text,PRIMARY KEY(org_id,project_id))')
  c.execute('INSERT INTO meta_workspace VALUES(%s,%s),(%s,%s)',(*SCOPE.key,'foreign-fixture',SCOPE.project_id))
  source=(R/'services/aos-api/alembic/versions/w6_009_three_module_closure.py').read_text();tree=ast.parse(source)
  class Op:
   def execute(self,s):c.execute(s)
  names=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['_scope','upgrade']]
  env={'op':Op(),'_BINDING_TABLES':tuple(TABLES[k] for k in ['usage','effect','handoff'])}
  exec(compile(ast.Module(body=names,type_ignores=[]),'exact-owned-w6-ddl','exec'),env);env['upgrade']()
  cases.NOW=c.execute('SELECT transaction_timestamp() AS now').fetchone()['now']-datetime.timedelta(seconds=5)
 def seed_row(kind,row):
  table=TABLES[kind];identity='closure_id' if kind=='closure' else 'binding_id'
  columns=['org_id','project_id',identity,'revision','module','source_id' if kind=='closure' else 'closure_id','content_hash','authority_data','created_at']
  values=[row['org_id'],row['project_id'],row['resource_id'],1,row['module'],row['source_id'] if kind=='closure' else row['closure_id'],row['content_hash'],json.dumps(row['authority_data']),row['created_at']]
  with psycopg.connect(user='postgres',**args) as c:c.execute(sql.SQL('INSERT INTO {} ({}) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,columns))),values)
 own=cases.authority_rows()
 for kind,row in own.items():seed_row(kind,row)
 cases.SCOPE=type(SCOPE)('foreign-fixture',SCOPE.project_id);foreign=cases.authority_rows();cases.SCOPE=SCOPE
 for kind,row in foreign.items():seed_row(kind,row)
 injected=[False];observations=[]
 def concurrent_usage():
  fixture=cases.ProducerFixture();fixture.closure=ThreeModuleClosureRevision.model_validate(own['closure']['authority_data'])
  original=fixture.resolve_usage
  fixture.resolve_usage=lambda scope,identity:{**original(scope,identity),'quality':'measured','quantity':7.0,'settlement':'measured'}
  svc=EcommerceWorkshopThreeModuleClosureService(fixture);exact=svc._ref('ThreeModuleClosureRevision',fixture.closure.closure_id,fixture.closure.content_hash)
  with psycopg.connect(user='postgres',**args) as c:now=c.execute('SELECT transaction_timestamp() AS now').fetchone()['now']
  value=svc.bind_usage(SCOPE,BindThreeModuleUsageRequest(closureRef=exact,usageReceiptId='fixture-usage-new'),now=now)
  seed_row('usage',dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,resource_id=value.binding_id,module=None,closure_id=fixture.closure.closure_id,source_id=None,content_hash=value.content_hash,authority_data=value.model_dump(mode='json',by_alias=True),created_at=now))
 @contextlib.contextmanager
 def connection(scope):
  assert scope==SCOPE
  with psycopg.connect(user='fixture_reader',**args) as c:
   c.read_only=True;c.isolation_level=IsolationLevel.REPEATABLE_READ;c.execute('SET LOCAL ROLE aos_runtime');c.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
   observations.append(dict(c.execute("SELECT current_user AS role,current_setting('transaction_read_only') AS readonly,current_setting('transaction_isolation') AS isolation").fetchone()))
   class Probe:
    read_only=c.read_only;autocommit=c.autocommit;isolation_level=c.isolation_level
    def execute(self,statement,params=()):
     result=c.execute(statement,params)
     if 'transaction_timestamp() AS cutoff' in statement and not injected[0]:injected[0]=True;concurrent_usage()
     return result
   yield Probe()
 reader=CreatorClosureReadonlyReader(connect_factory=connection);first=reader.read(SCOPE);second=reader.read(SCOPE)
 assert first.latest_usage.quantity is None and second.latest_usage.quantity==7.0 and not first.allowed_commands and not second.allowed_commands
 with psycopg.connect(user='fixture_reader',**args) as c:
  c.read_only=True;c.isolation_level=IsolationLevel.REPEATABLE_READ;c.execute('SET LOCAL ROLE aos_runtime');c.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
  assert c.execute('SELECT count(*) AS n FROM ecommerce_three_module_closure_revision').fetchone()['n']==1
  try:c.execute('INSERT INTO ecommerce_three_module_closure_revision SELECT * FROM ecommerce_three_module_closure_revision')
  except psycopg.Error as error:state=error.sqlstate;c.rollback()
  else:raise AssertionError('native write not denied')
 assert state=='25006'
 original=own['closure']['authority_data'];oversize={**original,'compiledBy':'x'*70000}
 with psycopg.connect(user='postgres',**args) as c:c.execute('UPDATE ecommerce_three_module_closure_revision SET authority_data=%s::jsonb WHERE org_id=%s AND project_id=%s',(json.dumps(oversize),*SCOPE.key))
 try:reader.read(SCOPE)
 except CreatorClosureReadonlyError as error:oversize_code=error.code
 else:raise AssertionError('oversize source silently returned')
 assert oversize_code=='CREATOR_CLOSURE_READ_LIMIT_EXCEEDED'
 with psycopg.connect(user='postgres',**args) as c:c.execute('UPDATE ecommerce_three_module_closure_revision SET authority_data=%s::jsonb WHERE org_id=%s AND project_id=%s',(json.dumps({**original,'compiledBy':'fixture@example.invalid'}),*SCOPE.key))
 try:reader.read(SCOPE)
 except CreatorClosureReadonlyError as error:privacy_code=error.code
 else:raise AssertionError('private actor exposed')
 assert privacy_code=='CREATOR_CLOSURE_READ_PRIVACY_UNAVAILABLE'
 save('native-r1-result.json',dict(containerId=cid,fixtureOnlyNotOriginalSchema=True,tables=list(TABLES.values()),exactW6DdlSha=hashlib.sha256(source.encode()).hexdigest(),sourceSha=hashlib.sha256((R/'services/aos-api/aos_api/ecommerce_three_module_closure_readonly.py').read_bytes()).hexdigest(),observations=observations,snapshotFirstQuantity=None,snapshotNextQuantity=7.0,foreignRowsHiddenWithoutWhere=True,writeDeniedSqlstate=state,oversizeSqlCaseError=oversize_code,privacyError=privacy_code,commandsEmpty=True,originalVolumeTouched=False,realUserApproval=False))
 print(json.dumps({'snapshot':[None,7.0],'writeDenied':state,'oversize':oversize_code,'privacy':privacy_code,'originalVolumeTouched':False}))
finally:
 owned=json.loads(docker('inspect',NAME).stdout)[0];assert owned['Id']==cid and owned['Config']['Labels']['aos.owner']==OWNER
 assert docker('stop',NAME).returncode==0;after=json.loads(docker('inspect',NAME).stdout)[0];assert after['Id']==cid and not after['State']['Running']
 save('native-r1-stopped.json',dict(containerId=cid,stopped=True,originalVolumeTouched=False))
