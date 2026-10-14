"""Owned isolated native PG projection proof; no original volume or user data."""
from pathlib import Path
import contextlib, datetime, hashlib, json, os, secrets, subprocess, sys, time
import psycopg
from psycopg import IsolationLevel, sql
from psycopg.rows import dict_row

E=Path(__file__).resolve().parent;R=E.parents[1]
os.environ.update(AOS_DATABASE_URL='postgresql://placeholder@127.0.0.1:1/unused',AOS_DOTENV_DISABLED='1')
sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.ecommerce_creator_internal_workflow_readonly import CreatorInternalWorkflowReadonlyReader,CreatorWorkflowReadonlyError
from aos_api.ecommerce_creator_internal_workflow import EcommerceCreatorInternalWorkflow
from aos_api.aip_production_contract_store import canonical_hash
from aos_api.tenant_scope import TenantScope

NAME='qyh-creator-workflow-bounded-native-20261014-r1';OWNER='codex-01a13484-f019-7d82-94ce-812396db9124';PORT=18573
IMAGE='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
SCOPE=TenantScope('org-org','dev-project')
TABLES=['aip_task','aip_task_brief_head','aip_task_brief_revision']
def docker(*args):return subprocess.run(['docker','--context','colima-aos-extension',*args],text=True,capture_output=True)
def save(name,value):
 with (E/name).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
assert not (E/'native-r1-intent.json').exists(),'known operation must reconcile, never replay'
lease=json.loads((R.parent/'docs/palantier/AOS项目开发上下文/memory/receipts/tasks'/f'{E.name}.json').read_text())
assert lease['owner']==OWNER and datetime.datetime.fromisoformat(lease['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
assert docker('inspect',NAME).returncode!=0
assert not subprocess.run(['lsof','-t',f'-iTCP:{PORT}','-sTCP:LISTEN'],capture_output=True,text=True).stdout.strip()
password=secrets.token_hex(24)
save('native-r1-intent.json',dict(name=NAME,port=PORT,tmpfs=True,owner=OWNER,originalVolumeTouched=False))
created=docker('run','-d','--name',NAME,'--label','aos.owner='+OWNER,'--label','aos.task='+E.name,'--tmpfs','/var/lib/postgresql/data:rw,size=512m','-p',f'127.0.0.1:{PORT}:5432','-e','POSTGRES_PASSWORD='+password,IMAGE)
assert created.returncode==0,'creation terminal failed, inspect exact known name before new action'
cid=created.stdout.strip();save('native-r1-created.json',dict(name=NAME,containerId=cid,owner=OWNER))
args=dict(host='127.0.0.1',port=PORT,dbname='postgres',password=password,row_factory=dict_row,connect_timeout=1)
try:
 # Host TCP readiness avoids pg_isready succeeding against temporary init server.
 for attempt in range(100):
  try:
   with psycopg.connect(user='postgres',**args) as c:c.execute('SELECT 1')
   break
  except psycopg.OperationalError:time.sleep(.1)
 else:raise RuntimeError('fixture host startup unresolved')
 with psycopg.connect(user='postgres',**args) as c:
  c.execute('CREATE ROLE aos_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS')
  c.execute(sql.SQL('CREATE ROLE fixture_reader LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}').format(sql.Literal(password)))
  c.execute('GRANT aos_runtime TO fixture_reader')
  c.execute('CREATE TABLE aip_task(org_id text,project_id text,task_id text,task_type text,PRIMARY KEY(org_id,project_id,task_id))')
  c.execute('CREATE TABLE aip_task_brief_head(org_id text,project_id text,brief_id text,task_id text,current_revision bigint,version bigint,updated_at timestamptz DEFAULT now(),PRIMARY KEY(org_id,project_id,brief_id))')
  c.execute('CREATE TABLE aip_task_brief_revision(org_id text,project_id text,brief_id text,task_id text,revision bigint,brief_type text,schema_ref jsonb,spec jsonb,content_hash text,lifecycle text,created_by text,created_at timestamptz DEFAULT now(),PRIMARY KEY(org_id,project_id,brief_id,revision))')
  for table in TABLES:
   c.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(sql.Identifier(table)))
   c.execute(sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(sql.Identifier(table)))
   c.execute(sql.SQL("CREATE POLICY tenant_scope ON {} TO aos_runtime USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier(table)))
   c.execute(sql.SQL('GRANT SELECT ON {} TO aos_runtime').format(sql.Identifier(table)))
 schema=EcommerceCreatorInternalWorkflow._schema_ref().model_dump(mode='json',by_alias=True)
 def spec(purpose='outreach_batch'):
  return dict(purpose=purpose,title='隔离内部准备',summary='隔离来源与合作条件',status='draft',externalEffectsAllowed=False,details={'channel':'站内邀约'})
 def seed(brief,purpose='outreach_batch',org=SCOPE.org_id,kind='creator_internal_workflow',data=None):
  body=data or spec(purpose);digest=canonical_hash(dict(briefType=kind,schemaRef=schema,spec=body));task='task-'+brief
  with psycopg.connect(user='postgres',**args) as c:
   c.execute('INSERT INTO aip_task VALUES(%s,%s,%s,%s)',(org,SCOPE.project_id,task,'ecommerce.workshop.creator_internal_task'))
   c.execute('INSERT INTO aip_task_brief_head(org_id,project_id,brief_id,task_id,current_revision,version) VALUES(%s,%s,%s,%s,1,1)',(org,SCOPE.project_id,brief,task))
   c.execute('INSERT INTO aip_task_brief_revision(org_id,project_id,brief_id,task_id,revision,brief_type,schema_ref,spec,content_hash,lifecycle,created_by) VALUES(%s,%s,%s,%s,1,%s,%s::jsonb,%s::jsonb,%s,%s,%s)',(org,SCOPE.project_id,brief,task,kind,json.dumps(schema),json.dumps(body),digest,'draft','isolated-fixture'))
 seed('initial');seed('foreign',org='dev-org');seed('other-kind',kind='unrelated_brief')
 observations=[];inject=[True]
 @contextlib.contextmanager
 def connect(scope):
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
     if 'transaction_timestamp() AS cutoff' in statement and inject[0]:
      inject[0]=False;seed('concurrent','candidate_import')
     return result
   yield Probe()
 reader=CreatorInternalWorkflowReadonlyReader(connect_factory=connect)
 first=reader.list(SCOPE);second=reader.list(SCOPE)
 assert first.count==1 and second.count==2
 with psycopg.connect(user='fixture_reader',**args) as c:
  c.read_only=True;c.isolation_level=IsolationLevel.REPEATABLE_READ;c.execute('SET LOCAL ROLE aos_runtime');c.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
  assert c.execute('SELECT count(*) AS n FROM aip_task_brief_head').fetchone()['n']==3
  try:c.execute('UPDATE aip_task_brief_head SET version=version+1')
  except psycopg.Error as error:write_state=error.sqlstate;c.rollback()
  else:raise AssertionError('native write was not denied')
 assert write_state in {'25006','42501'}
 # Known sensitive source is never returned or silently omitted.
 seed('sensitive',data={**spec('delivery_check'),'details':{'channel':'fixture@example.test'}})
 try:reader.list(SCOPE)
 except CreatorWorkflowReadonlyError as error:privacy=error.code
 else:raise AssertionError('sensitive saved content was exposed')
 assert privacy=='CREATOR_WORKFLOW_READ_PRIVACY_UNAVAILABLE'
 with psycopg.connect(user='postgres',**args) as c:
  c.execute("DELETE FROM aip_task_brief_revision WHERE brief_id='sensitive'");c.execute("DELETE FROM aip_task_brief_head WHERE brief_id='sensitive'");c.execute("DELETE FROM aip_task WHERE task_id='task-sensitive'")
 seed('oversize',data={**spec('delivery_check'),'details':{'channel':'x'*70000}})
 try:reader.list(SCOPE)
 except CreatorWorkflowReadonlyError as error:oversize=error.code
 else:raise AssertionError('oversize returned success')
 assert oversize=='CREATOR_WORKFLOW_READ_LIMIT_EXCEEDED'
 with psycopg.connect(user='postgres',**args) as c:
  c.execute("DELETE FROM aip_task_brief_revision WHERE brief_id='oversize'");c.execute("DELETE FROM aip_task_brief_head WHERE brief_id='oversize'");c.execute("DELETE FROM aip_task WHERE task_id='task-oversize'")
 # Enough current creator heads to prove server LIMIT+1 fails before dedup.
 body=spec();digest=canonical_hash(dict(briefType='creator_internal_workflow',schemaRef=schema,spec=body))
 with psycopg.connect(user='postgres',**args) as c:
  c.execute("INSERT INTO aip_task_brief_head(org_id,project_id,brief_id,task_id,current_revision,version) SELECT %s,%s,'bulk-'||g,'task-initial',1,1 FROM generate_series(1,1000) g",SCOPE.key)
  c.execute("INSERT INTO aip_task_brief_revision(org_id,project_id,brief_id,task_id,revision,brief_type,schema_ref,spec,content_hash,lifecycle,created_by) SELECT org_id,project_id,brief_id,task_id,1,'creator_internal_workflow',%s::jsonb,%s::jsonb,%s,'draft','fixture' FROM aip_task_brief_head WHERE brief_id LIKE 'bulk-%%'",(json.dumps(schema),json.dumps(body),digest))
 try:reader.list(SCOPE)
 except CreatorWorkflowReadonlyError as error:rowlimit=error.code
 else:raise AssertionError('rowlimit silently truncated')
 assert rowlimit=='CREATOR_WORKFLOW_READ_LIMIT_EXCEEDED'
 save('native-r1-result.json',dict(containerId=cid,name=NAME,owner=OWNER,sourceSha256=hashlib.sha256((R/'services/aos-api/aos_api/ecommerce_creator_internal_workflow_readonly.py').read_bytes()).hexdigest(),tables=TABLES,fixtureOnlyNotFullOriginalSchema=True,observations=observations,firstSnapshotCount=first.count,nextSnapshotCount=second.count,otherTypeExcluded=True,foreignRowsHiddenWithoutWhere=True,writeDeniedSqlstate=write_state,privacyError=privacy,oversizeCaseError=oversize,rowLimitError=rowlimit,originalVolumeTouched=False,originalUserOrBudgetApproval=False))
 print(json.dumps({'snapshotCounts':[first.count,second.count],'writeDenied':write_state,'privacy':privacy,'oversize':oversize,'rowlimit':rowlimit,'originalVolumeTouched':False}))
finally:
 owned=json.loads(docker('inspect',NAME).stdout)[0]
 assert owned['Id']==cid and owned['Config']['Labels']['aos.owner']==OWNER
 stopped=docker('stop',NAME);assert stopped.returncode==0
 after=json.loads(docker('inspect',NAME).stdout)[0];assert after['Id']==cid and not after['State']['Running']
 save('native-r1-stopped.json',dict(containerId=cid,stopped=True,originalVolumeTouched=False))
