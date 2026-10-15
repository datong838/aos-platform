"""Original W6-007 DDL in owned disposable tmpfs; no original DB access."""
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
F=E/'private/candidate-source-r1'
os.environ.update(AOS_DATABASE_URL='postgresql://placeholder@127.0.0.1:1/unused',AOS_DOTENV_DISABLED='1')
sys.path.insert(0,str(F/'services/aos-api'));sys.path.insert(0,str(R/'scripts/memory'))
import memoryctl as m
from aos_api.tenant_scope import TenantScope
from aos_api import ecommerce_customer_lifecycle_readonly as rd
spec=importlib.util.spec_from_file_location('customer_native_fixture',F/'services/aos-api/tests/test_ecommerce_customer_lifecycle_readonly.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
OWNER='codex-01a13484-f019-7d82-94ce-812396db9124'
NAME='qyh-customer-lifecycle-native-20261015-r1';PORT=18621
IMAGE='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
SCOPE=TenantScope('dev-org','fixture-project')
def docker(*args):return subprocess.run(['docker','--context','colima-aos-extension',*args],capture_output=True,text=True)
def save(name,value):
 m.scan_secrets(value)
 with (E/name).open('x') as stream:
  json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno())
lease=next(x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']==E.name)
assert lease['owner']==OWNER and lease['base_revision']=='AOS-002036'
assert datetime.datetime.fromisoformat(lease['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
assert m.load_authority(m.DEFAULT_PATHS)['project_revision']=='AOS-002036'
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
 else:raise RuntimeError('Fixture startup unresolved; reconcile, no replay')
 with psycopg.connect(user='postgres',**args) as conn:
  conn.execute('CREATE ROLE aos_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS')
  conn.execute(sql.SQL('CREATE ROLE fixture_reader LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}').format(sql.Literal(password)))
  conn.execute('GRANT aos_runtime TO fixture_reader')
  conn.execute('CREATE TABLE meta_workspace(org_id text,project_id text,PRIMARY KEY(org_id,project_id))')
  conn.execute('INSERT INTO meta_workspace VALUES(%s,%s),(%s,%s)',(*SCOPE.key,'foreign-fixture',SCOPE.project_id))
  source=(F/'services/aos-api/alembic/versions/w6_007_customer_lifecycle.py').read_text();tree=ast.parse(source)
  nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='upgrade' or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TABLES' for t in n.targets)]
  class Op:
   def execute(self,statement):conn.execute(statement)
  env={'op':Op()};exec(compile(ast.Module(body=nodes,type_ignores=[]),'exact-w6_007-ddl','exec'),env);env['upgrade']()
 fixture,data=f.producer_fixture()
 identities={table:identity for table,identity,*_ in rd.POLICIES};identities[rd.BATCH_TABLE]='batch_id'
 def insert(table,row,foreign=False):
  with psycopg.connect(user='postgres',**args) as conn:
   payload=json.loads(json.dumps(row['authority_data']))
   org='foreign-fixture' if foreign else row['org_id'];payload['tenant']['orgId']=org
   conn.execute(f'INSERT INTO {table}(org_id,project_id,{identities[table]},revision,content_hash,authority_data,created_at) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s)',
    (org,row['project_id'],row['identity'],row['revision'],row['content_hash'],json.dumps(payload),row['created_at']))
 for table,rows in data.items():
  for row in rows:insert(table,row);insert(table,row,True)
 policy_table=rd.POLICIES[0][0];original=data[policy_table][0]
 request=rd._request(rd.domain.CreateCustomerConsentPolicyRequest,rd.domain.CustomerConsentPolicyRevision.model_validate(original['authority_data']))
 payload=request.model_dump(mode='json',by_alias=True);payload['revision']=2
 revision2=rd.domain.EcommerceWorkshopCustomerLifecycleService._tenant(SCOPE)
 raw=rd.domain.CustomerConsentPolicyRevision(tenant=revision2,**payload,contentHash=rd.domain.canonical_hash(payload),createdBy='synthetic-revision-two',createdAt=fixture.NOW)
 second_policy=f.row(raw,'policy_id')
 injected=[False];facts=[]
 @contextlib.contextmanager
 def connection(scope):
  assert scope==SCOPE
  with psycopg.connect(user='fixture_reader',**args) as conn:
   conn.read_only=True;conn.isolation_level=IsolationLevel.REPEATABLE_READ
   conn.execute('SET LOCAL ROLE aos_runtime')
   conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
   facts.append(dict(conn.execute("SELECT current_user AS role,current_setting('transaction_read_only') AS readonly,current_setting('transaction_isolation') AS isolation").fetchone()))
   class Probe:
    read_only=conn.read_only;autocommit=conn.autocommit;isolation_level=conn.isolation_level
    def execute(self,statement,params=()):
     result=conn.execute(statement,params)
     if 'transaction_timestamp() AS cutoff' in statement and not injected[0]:
      injected[0]=True;insert(policy_table,second_policy)
     return result
   yield Probe()
 reader=rd.CustomerLifecycleReadonlyReader(connect_factory=connection)
 first,second=reader.read(SCOPE),reader.read(SCOPE)
 assert first.consent_policy_count==1 and second.consent_policy_count==2
 assert second.latest_batch.consent_policy_ref.revision==1 and second.latest_batch.lifecycle=='frozen'
 assert second.latest_batch.ledger.unknown==1 and not second.allowed_commands
 with connection(SCOPE) as conn:
  visible=conn.execute(f'SELECT count(*) AS n FROM {policy_table}').fetchone()['n'];assert visible==2
  try:conn.execute(f'INSERT INTO {policy_table} SELECT * FROM {policy_table}')
  except psycopg.Error as error:state=error.sqlstate
  else:raise AssertionError('Write not denied')
 assert state=='25006'
 batch=data[rd.BATCH_TABLE][-1];saved=batch['authority_data']
 def change(table,identity,revision,payload,created_at=None):
  with psycopg.connect(user='postgres',**args) as conn:
   conn.execute(f'UPDATE {table} SET authority_data=%s::jsonb'+(',created_at=%s' if created_at else '')+f' WHERE org_id=%s AND project_id=%s AND {identities[table]}=%s AND revision=%s',
    (json.dumps(payload),*((created_at,) if created_at else ()),*SCOPE.key,identity,revision))
 def denied(suffix):
  try:reader.read(SCOPE)
  except rd.CustomerLifecycleReadonlyError as error:assert error.code=='CUSTOMER_LIFECYCLE_READ_'+suffix
  else:raise AssertionError('Invalid saved fact accepted')
 change(rd.BATCH_TABLE,batch['identity'],2,{**saved,'createdBy':'x'*(rd.MAX_ROW_BYTES+1)})
 denied('LIMIT_EXCEEDED')
 with connection(SCOPE) as conn:
  row=reader._row(conn,SCOPE,rd.BATCH_TABLE,'batch_id');assert row['authority_data'] is None and row['size']>rd.MAX_ROW_BYTES
 change(rd.BATCH_TABLE,batch['identity'],2,{**saved,'createdBy':'fixture@example.invalid'});denied('SENSITIVE_CONTENT')
 change(rd.BATCH_TABLE,batch['identity'],2,saved)
 bad=json.loads(json.dumps(original['authority_data']));bad['tenant']['orgId']='foreign-fixture'
 change(policy_table,original['identity'],1,bad);denied('AUTHORITY_DRIFT')
 bad=json.loads(json.dumps(original['authority_data']));bad['createdAt']='invalidZ'
 change(policy_table,original['identity'],1,bad);denied('AUTHORITY_UNAVAILABLE')
 change(policy_table,original['identity'],1,original['authority_data'])
 with psycopg.connect(user='postgres',**args) as conn:future=conn.execute("SELECT transaction_timestamp()+interval '1 day' AS at").fetchone()['at']
 future_raw=json.loads(json.dumps(second_policy['authority_data']));future_raw['createdAt']=future.isoformat()
 change(policy_table,second_policy['identity'],2,future_raw,future);denied('AUTHORITY_DRIFT')
 change(policy_table,second_policy['identity'],2,second_policy['authority_data'],second_policy['created_at'])
 assert reader.read(SCOPE).consent_policy_count==2
 save('native-r1-result.json',dict(containerId=cid,originalVolumeTouched=False,fixtureOnlyNotOriginalSchema=True,
  exactW6DdlSha=hashlib.sha256(source.encode()).hexdigest(),sourceSha=hashlib.sha256((F/'services/aos-api/aos_api/ecommerce_customer_lifecycle_readonly.py').read_bytes()).hexdigest(),
  originalProducerSyntheticResolver=True,actualConsentAuthority=False,productionAuthority=False,snapshotCounts=[1,2],
  savedRevisionCountNotDistinct=True,oldExactPolicyRefPreserved=True,unknownPreserved=True,commandsEmpty=True,
  foreignRowsHiddenWithoutWhere=True,visiblePolicyRows=visible,writeDeniedSqlstate=state,sqlCaseNull=True,
  privacyRejected=True,aggregateTenantDriftRejected=True,malformedTimestampRejected=True,futureCountNotFiltered=True,
  connectionFacts=facts,wholeGoalComplete=False))
 print(json.dumps(dict(snapshotCounts=[1,2],oldExactRefPreserved=True,writeDenied=state,sqlCaseNull=True,originalVolumeTouched=False)))
finally:
 owned=json.loads(docker('inspect',NAME).stdout)[0]
 assert owned['Id']==cid and owned['Config']['Labels']['aos.owner']==OWNER and owned['Config']['Labels']['aos.task']==E.name
 assert docker('stop',NAME).returncode==0
 after=json.loads(docker('inspect',NAME).stdout)[0];assert after['Id']==cid and not after['State']['Running']
 save('native-r1-stopped.json',dict(containerId=cid,stopped=True,originalVolumeTouched=False))
