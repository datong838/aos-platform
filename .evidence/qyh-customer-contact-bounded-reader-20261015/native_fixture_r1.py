"""Original W6-007/008 SQL in owned tmpfs only, never original business DB."""
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
E=Path(__file__).resolve().parent;R=E.parents[1];F=E/'private/candidate-source-r1'
os.environ.update(AOS_DATABASE_URL='postgresql://placeholder@127.0.0.1:1/unused',AOS_DOTENV_DISABLED='1')
sys.path.insert(0,str(F/'services/aos-api'));sys.path.insert(0,str(R/'scripts/memory'))
import memoryctl as m
from aos_api import ecommerce_customer_contact_readonly as rd
from aos_api import ecommerce_workshop_customer_contact as d
from aos_api.tenant_scope import TenantScope
spec=importlib.util.spec_from_file_location('native_contact_facts',F/'services/aos-api/tests/test_ecommerce_customer_contact_readonly.py')
fx=importlib.util.module_from_spec(spec);spec.loader.exec_module(fx)
OWNER='codex-01a13484-f019-7d82-94ce-812396db9124';NAME='qyh-customer-contact-native-20261015-r1';PORT=18623
IMAGE='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
def docker(*args):return subprocess.run(['docker','--context','colima-aos-extension',*args],capture_output=True,text=True)
def save(name,value):
 m.scan_secrets(value)
 with (E/name).open('x') as stream:json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno())
lease=next(x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']==E.name)
assert lease['owner']==OWNER and lease['base_revision']=='AOS-002037' and datetime.datetime.fromisoformat(lease['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
assert m.load_authority(m.DEFAULT_PATHS)['project_revision']=='AOS-002037'
assert not (E/'native-r1-intent.json').exists() and docker('inspect',NAME).returncode!=0
assert not subprocess.run(['lsof','-t',f'-iTCP:{PORT}','-sTCP:LISTEN'],capture_output=True,text=True).stdout.strip()
password=secrets.token_hex(24)
save('native-r1-intent.json',dict(name=NAME,port=PORT,tmpfs=True,owner=OWNER,originalVolumeTouched=False))
created=docker('run','-d','--name',NAME,'--label','aos.owner='+OWNER,'--label','aos.task='+E.name,'--tmpfs','/var/lib/postgresql/data:rw,size=512m','-p',f'127.0.0.1:{PORT}:5432','-e','POSTGRES_PASSWORD='+password,IMAGE)
assert created.returncode==0;cid=created.stdout.strip();save('native-r1-created.json',dict(containerId=cid,name=NAME,owner=OWNER))
args=dict(host='127.0.0.1',port=PORT,dbname='postgres',password=password,row_factory=dict_row,connect_timeout=1)
try:
 for _ in range(100):
  try:
   with psycopg.connect(user='postgres',**args) as conn:conn.execute('SELECT 1')
   break
  except psycopg.OperationalError:time.sleep(.1)
 else:raise RuntimeError('Fixture startup unresolved; reconcile without replay')
 scope,fixture_cutoff,data,start=fx.producer_fixture()
 foreign=TenantScope('foreign-fixture','fixture-project');empty=TenantScope('empty-fixture','fixture-project')
 ddl_hashes={}
 with psycopg.connect(user='postgres',**args) as conn:
  conn.execute('CREATE ROLE aos_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS')
  conn.execute(sql.SQL('CREATE ROLE fixture_reader LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}').format(sql.Literal(password)))
  conn.execute('GRANT aos_runtime TO fixture_reader')
  conn.execute('CREATE TABLE meta_workspace(org_id text,project_id text,PRIMARY KEY(org_id,project_id))')
  conn.execute('INSERT INTO meta_workspace VALUES(%s,%s),(%s,%s),(%s,%s)',(*scope.key,*foreign.key,*empty.key))
  for name in ['w6_007_customer_lifecycle.py','w6_008_customer_contact.py']:
   source=(F/'services/aos-api/alembic/versions'/name).read_text();tree=ast.parse(source)
   nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='upgrade' or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TABLES' for t in n.targets)]
   class Op:
    def execute(self,statement):conn.execute(statement)
   env={'op':Op()};exec(compile(ast.Module(body=nodes,type_ignores=[]),name,'exec'),env);env['upgrade']()
   ddl_hashes[name]=hashlib.sha256(source.encode()).hexdigest()
 def foreign_payload(value):
  if isinstance(value,dict):return {k:({'orgId':foreign.org_id,'projectId':foreign.project_id} if k=='tenant' else foreign_payload(v)) for k,v in value.items()}
  if isinstance(value,list):return [foreign_payload(v) for v in value]
  return value
 def insert(table,row,*,other=False):
  identity,_model,_date,extras=rd._SPECS[table]
  values=[foreign.org_id if other else row['org_id'],row['project_id'],row['identity'],row['revision']]
  values.extend(row[key] for key in extras)
  raw=foreign_payload(row['authority_data']) if other else row['authority_data']
  values.extend([row['content_hash'],json.dumps(raw),row['created_at']])
  columns=['org_id','project_id',identity,'revision',*extras,'content_hash','authority_data','created_at']
  placeholders=['%s']*(len(columns)-2)+['%s::jsonb','%s']
  with psycopg.connect(user='postgres',**args) as conn:
   conn.execute(f'INSERT INTO {table}('+','.join(columns)+') VALUES('+','.join(placeholders)+')',values)
 for table,rows in data.items():
  for row in rows:insert(table,row);insert(table,row,other=True)
 frequency_raw=data[rd._FREQUENCY][0]['authority_data']
 request=d.CreateCustomerFrequencyPolicyRequest.model_validate({field.alias:frequency_raw[field.alias] for field in d.CreateCustomerFrequencyPolicyRequest.model_fields.values()})
 class PolicyStore:
  def append_frequency_policy(self,tenant,item):return item
 policy2=d.EcommerceWorkshopCustomerContactService(PolicyStore(),None).create_frequency_policy(scope,request.model_copy(update={'revision':2}),'synthetic-second-revision',now=fixture_cutoff)
 policy2_row=fx.row(policy2,'policy_id')
 injected=[False];trace=[];facts=[]
 @contextlib.contextmanager
 def connection(tenant):
  assert tenant.key in [scope.key,empty.key]
  with psycopg.connect(user='fixture_reader',**args) as conn:
   conn.read_only=True;conn.isolation_level=IsolationLevel.REPEATABLE_READ
   conn.execute('SET LOCAL ROLE aos_runtime')
   conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",tenant.key)
   facts.append(dict(conn.execute("SELECT current_user AS role,current_setting('transaction_read_only') AS readonly,current_setting('transaction_isolation') AS isolation").fetchone()))
   class Probe:
    read_only=conn.read_only;autocommit=conn.autocommit;isolation_level=conn.isolation_level
    def execute(self,statement,params=()):
     table=next((t for t in data if 'FROM '+t+' ' in statement),None)
     trace.append(dict(table=table,payload='AS authority_data' in statement))
     result=conn.execute(statement,params)
     if 'transaction_timestamp() AS cutoff' in statement and tenant==scope and not injected[0]:
      injected[0]=True;insert(rd._FREQUENCY,policy2_row)
     return result
   yield Probe()
 reader=rd.CustomerContactReadonlyReader(connect_factory=connection)
 empty_view=reader.read(empty)
 assert empty_view.latest_start is None and empty_view.frequency_policy_count==empty_view.withdrawal_count==0 and not empty_view.allowed_commands
 first,second=reader.read(scope),reader.read(scope)
 assert first.frequency_policy_count==1 and second.frequency_policy_count==2
 assert second.withdrawal_count==1 and second.latest_start.batch_ref==start.batch_ref
 assert second.latest_start.exact_refs['frequencyPolicy'].revision==1
 assert second.ledger.unknown==second.ledger.skipped_withdrawn==1 and second.latest_start.items[0].reservation.status=='held'
 assert not second.allowed_commands and second.latest_start.content_hash==start.content_hash
 assert 'reason' not in second.model_dump(mode='json',by_alias=True)['latestStart']
 with connection(scope) as conn:
  visible=conn.execute('SELECT count(*) AS n FROM ecommerce_customer_frequency_policy_revision ').fetchone()['n'];assert visible==2
  try:conn.execute('INSERT INTO ecommerce_customer_frequency_policy_revision SELECT * FROM ecommerce_customer_frequency_policy_revision')
  except psycopg.Error as error:state=error.sqlstate
  else:raise AssertionError('Readonly write was not denied')
 assert state=='25006'
 original_start=data[rd._START][0]['authority_data']
 def change(table,identity,revision,payload,at=None):
  column=rd._SPECS[table][0]
  with psycopg.connect(user='postgres',**args) as conn:
   conn.execute(f'UPDATE {table} SET authority_data=%s::jsonb'+(',created_at=%s' if at else '')+f' WHERE org_id=%s AND project_id=%s AND {column}=%s AND revision=%s',
    (json.dumps(payload),*((at,) if at else ()),*scope.key,identity,revision))
 def denied(suffix):
  try:reader.read(scope)
  except rd.CustomerContactReadonlyError as error:assert error.code=='CUSTOMER_CONTACT_READ_'+suffix
  else:raise AssertionError('Invalid saved fact accepted')
 legacy={k:v for k,v in original_start.items() if k!='reason'}
 change(rd._START,start.decision_id,1,legacy);denied('SIGNING_MATERIAL_UNAVAILABLE')
 change(rd._START,start.decision_id,1,{**original_start,'reason':'fixture@example.invalid'});denied('SENSITIVE_CONTENT')
 change(rd._START,start.decision_id,1,{**original_start,'reason':'x'*(rd.MAX_ROW_BYTES+1)});denied('LIMIT_EXCEEDED')
 with connection(scope) as conn:
  value=reader._rows(conn,scope,rd._START,payload=True);assert value['authority_data'] is None and value['size']>rd.MAX_ROW_BYTES
 change(rd._START,start.decision_id,1,original_start)
 bad=json.loads(json.dumps(policy2_row['authority_data']));bad['tenant']['orgId']='foreign-fixture'
 change(rd._FREQUENCY,policy2.policy_id,2,bad);denied('AUTHORITY_DRIFT')
 bad=json.loads(json.dumps(policy2_row['authority_data']));bad['createdAt']='invalidZ'
 change(rd._FREQUENCY,policy2.policy_id,2,bad);denied('AUTHORITY_UNAVAILABLE')
 change(rd._FREQUENCY,policy2.policy_id,2,policy2_row['authority_data'])
 with psycopg.connect(user='postgres',**args) as conn:future=conn.execute("SELECT transaction_timestamp()+interval '1 day' AS at").fetchone()['at']
 bad=json.loads(json.dumps(policy2_row['authority_data']));bad['createdAt']=future.isoformat()
 change(rd._FREQUENCY,policy2.policy_id,2,bad,future);denied('AUTHORITY_DRIFT')
 change(rd._FREQUENCY,policy2.policy_id,2,policy2_row['authority_data'],policy2.created_at)
 observation=data[rd._OBSERVATION][0]
 for index in range(9):
  large={**observation,'identity':'budget-fixture-'+str(index),'authority_data':{**observation['authority_data'],'padding':'x'*(rd.MAX_ROW_BYTES-4096)}}
  insert(rd._OBSERVATION,large)
 trace.clear();denied('LIMIT_EXCEEDED')
 observation_queries=[x for x in trace if x['table']==rd._OBSERVATION]
 assert observation_queries==[dict(table=rd._OBSERVATION,payload=False)]
 with psycopg.connect(user='postgres',**args) as conn:
  sizes=conn.execute('SELECT max(octet_length(authority_data::text)) AS maximum,sum(octet_length(authority_data::text)) AS total FROM ecommerce_customer_dispatch_observation WHERE org_id=%s AND project_id=%s',scope.key).fetchone()
  assert sizes['maximum']<=rd.MAX_ROW_BYTES and sizes['total']>rd.MAX_TOTAL_BYTES
  conn.execute("DELETE FROM ecommerce_customer_dispatch_observation WHERE org_id=%s AND project_id=%s AND observation_id LIKE 'budget-fixture-%%'",scope.key)
 assert reader.read(scope).ledger.unknown==1
 save('native-r1-result.json',dict(containerId=cid,originalVolumeTouched=False,fixtureOnlyNotOriginalSchema=True,originalProducersSyntheticResolvers=True,actualConsentReceiptOrContactAuthority=False,
  exactDdlHashes=ddl_hashes,sourceSha=hashlib.sha256((F/'services/aos-api/aos_api/ecommerce_customer_contact_readonly.py').read_bytes()).hexdigest(),
  genuineEmptySqlSumNull=True,snapshotSavedRevisionCounts=[1,2],oldExactFrequencyRefPreserved=True,unknownAndSkipPreserved=True,reservationHeld=True,privateReasonNotPublic=True,
  originalStartHashPreservedInProjection=True,foreignRowsHiddenWithoutWhere=True,visibleOwnPolicyRows=visible,writeDeniedSqlstate=state,
  missingReasonRejected=True,sensitiveReasonRejected=True,sqlCaseNull=True,aggregateTenantDriftRejected=True,malformedDateRejected=True,futureAggregateNotHidden=True,
  totalBudgetProvenBeforeBulkPayload=True,bulkBudgetQueryTrace=observation_queries,connectionFacts=facts,wholeGoalComplete=False))
 print(json.dumps(dict(snapshotCounts=[1,2],unknownHeld=True,skipPreserved=True,metadataBeforeBulk=True,writeDenied=state,originalVolumeTouched=False)))
finally:
 owned=json.loads(docker('inspect',NAME).stdout)[0];assert owned['Id']==cid and owned['Config']['Labels']['aos.owner']==OWNER and owned['Config']['Labels']['aos.task']==E.name
 assert docker('stop',NAME).returncode==0
 stopped=json.loads(docker('inspect',NAME).stdout)[0];assert stopped['Id']==cid and not stopped['State']['Running']
 save('native-r1-stopped.json',dict(containerId=cid,stopped=True,originalVolumeTouched=False))
