"""Private signing material through original W6-008 Store/DDL in owned tmpfs."""
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
from aos_api import ecommerce_workshop_customer_contact as d
from aos_api.ecommerce_workshop_customer_contact_store import EcommerceWorkshopCustomerContactStore
from aos_api.tenant_scope import TenantScope
spec=importlib.util.spec_from_file_location('signing_native_fixture',F/'services/aos-api/tests/test_customer_start_signing_material.py')
fx=importlib.util.module_from_spec(spec);spec.loader.exec_module(fx)
OWNER='codex-01a13484-f019-7d82-94ce-812396db9124';NAME='qyh-customer-start-material-native-20261015-r1';PORT=18622
IMAGE='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
def docker(*args):return subprocess.run(['docker','--context','colima-aos-extension',*args],capture_output=True,text=True)
def save(name,value):
 m.scan_secrets(value)
 with (E/name).open('x') as s:json.dump(value,s,indent=2);s.flush();os.fsync(s.fileno())
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
 else:raise RuntimeError('Fixture startup unresolved; no replay')
 f,service,synthetic,batch,request,start=fx.fixture();scope=f.SCOPE
 foreign=TenantScope('foreign-fixture','fixture-project')
 with psycopg.connect(user='postgres',**args) as conn:
  conn.execute('CREATE ROLE aos_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS')
  conn.execute(sql.SQL('CREATE ROLE fixture_writer LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}').format(sql.Literal(password)))
  conn.execute('GRANT aos_runtime TO fixture_writer')
  conn.execute('CREATE TABLE meta_workspace(org_id text,project_id text,PRIMARY KEY(org_id,project_id))')
  conn.execute('INSERT INTO meta_workspace VALUES(%s,%s),(%s,%s)',(*scope.key,*foreign.key))
  source=(F/'services/aos-api/alembic/versions/w6_008_customer_contact.py').read_text();tree=ast.parse(source)
  nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='upgrade' or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TABLES' for t in n.targets)]
  class Op:
   def execute(self,statement):conn.execute(statement)
  env={'op':Op()};exec(compile(ast.Module(body=nodes,type_ignores=[]),'original-w6_008-ddl','exec'),env);env['upgrade']()
 facts=[]
 @contextlib.contextmanager
 def connect(tenant,readonly=False):
  with psycopg.connect(user='fixture_writer',**args) as conn:
   if readonly:conn.read_only=True;conn.isolation_level=IsolationLevel.REPEATABLE_READ
   conn.execute('SET LOCAL ROLE aos_runtime')
   conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",tenant.key)
   facts.append(dict(conn.execute("SELECT current_user AS role,current_setting('transaction_read_only') AS readonly").fetchone()))
   yield conn
 store=EcommerceWorkshopCustomerContactStore(connect_factory=connect)
 restored=store.append_start(scope,batch.batch_id,start)
 assert restored.reason==request.reason and d.customer_start_signing_hash(restored)==start.content_hash
 public=restored.model_dump(mode='json',by_alias=True)
 assert public==start.model_dump(mode='json',by_alias=True) and 'reason' not in public and request.reason not in repr(restored)
 with connect(scope,True) as conn:
  raw=conn.execute('SELECT authority_data FROM ecommerce_customer_batch_start_decision_revision WHERE decision_id=%s',(start.decision_id,)).fetchone()['authority_data']
  assert raw['reason']==request.reason
 before=json.dumps(raw,sort_keys=True)
 duplicate=store.append_start(scope,batch.batch_id,start);assert duplicate==restored
 with connect(scope,True) as conn:
  after=conn.execute('SELECT authority_data FROM ecommerce_customer_batch_start_decision_revision WHERE decision_id=%s',(start.decision_id,)).fetchone()['authority_data']
 assert json.dumps(after,sort_keys=True)==before
 legacy=d.CustomerBatchStartDecisionRevision.model_validate(public).model_copy(update={'decision_id':'legacy-fixture-start'})
 legacy_restored=store.append_start(scope,'legacy-fixture-batch',legacy)
 assert legacy_restored.reason is None
 try:d.customer_start_signing_hash(legacy_restored)
 except d.CustomerContactBlocked as error:assert str(error)=='CUSTOMER_START_SIGNING_MATERIAL_UNAVAILABLE'
 else:raise AssertionError('Legacy missing signing material was guessed')
 f.SCOPE=foreign;other_service,_,other_batch=f.service_fixture()
 other=other_service.start_batch(foreign,other_batch.batch_id,f.start_request(other_batch),'synthetic-foreign',now=f.NOW)
 store.append_start(foreign,other_batch.batch_id,other)
 with connect(scope,True) as conn:
  visible=conn.execute('SELECT count(*) AS n FROM ecommerce_customer_batch_start_decision_revision').fetchone()['n'];assert visible==2
  legacy_raw=conn.execute('SELECT authority_data FROM ecommerce_customer_batch_start_decision_revision WHERE decision_id=%s',(legacy.decision_id,)).fetchone()['authority_data'];assert 'reason' not in legacy_raw
  try:conn.execute('INSERT INTO ecommerce_customer_batch_start_decision_revision SELECT * FROM ecommerce_customer_batch_start_decision_revision')
  except psycopg.Error as error:state=error.sqlstate
  else:raise AssertionError('Readonly write was not denied')
 assert state=='25006'
 assert start.contact_resolution_count==start.provider_call_count==start.send_count==start.external_effect_count==0
 save('native-r1-result.json',dict(containerId=cid,originalVolumeTouched=False,fixtureOnlyNotOriginalSchema=True,originalProducerSyntheticResolvers=True,actualConsentOrReceiptAuthority=False,
  exactDdlSha=hashlib.sha256(source.encode()).hexdigest(),sourceHashes={p:hashlib.sha256((F/p).read_bytes()).hexdigest() for p in ['services/aos-api/aos_api/ecommerce_workshop_customer_contact.py','services/aos-api/aos_api/ecommerce_workshop_customer_contact_store.py']},
  rawAuthorityContainsPrivateReason=True,publicWireUnchanged=True,reprOmitsReason=True,originalTypedHashReconstructed=True,sameHashIdempotent=True,legacyWithoutReasonNotRewritten=True,legacySigningMaterialUnavailable=True,foreignRowsHiddenWithoutWhere=True,visibleOwnRows=visible,writeDeniedSqlstate=state,originalFourEffectsZero=True,connectionFacts=facts,wholeGoalComplete=False))
 print(json.dumps(dict(privateSigningRoundtrip=True,publicWireUnchanged=True,legacyUnchanged=True,RLS=True,writeDenied=state,originalVolumeTouched=False)))
finally:
 owned=json.loads(docker('inspect',NAME).stdout)[0];assert owned['Id']==cid and owned['Config']['Labels']['aos.owner']==OWNER and owned['Config']['Labels']['aos.task']==E.name
 assert docker('stop',NAME).returncode==0
 stopped=json.loads(docker('inspect',NAME).stdout)[0];assert stopped['Id']==cid and not stopped['State']['Running']
 save('native-r1-stopped.json',dict(containerId=cid,stopped=True,originalVolumeTouched=False))
