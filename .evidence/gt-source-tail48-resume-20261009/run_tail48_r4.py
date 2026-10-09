import os,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import psycopg,pytest
from psycopg.conninfo import conninfo_to_dict
REPO=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;lab=json.loads((OUT/'lab.json').read_text());PASS=Path(lab['passfile']);assert PASS.stat().st_mode&0o077==0
state=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect',lab['name']],text=True))[0];assert state['Id']==lab['container_id'] and state['State']['Running']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()=='2c4d584377f59d44f6aa7a123ee69b39cfa46e4d'
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(key,None)
os.environ.update(AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5437/aos_meta',AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5437',AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',AOS_TEST_RETAIN_DATABASE='1',AOS_TEST_USE_SHARED_DATABASE='0',AOS_DOTENV_DISABLED='1',AOS_SOURCE_MODEL_EVIDENCE_LABEL='source-newjudge-source-tail48-r4',AOS_SOURCE_NEW_JUDGE_NATIVE='1',AOS_NEW_JUDGE_INTENT_NATIVE='1',AOS_SOURCE_NEWJUDGE_PROOF='newjudge-source-proof-1607.json',AOS_JUDGE_NATIVE_EVIDENCE_LABEL='source-tail48-r4',AOS_MUTATION_BATCH='B')
sys.path.insert(0,str(REPO/'services/aos-api'));sys.path.insert(0,str(REPO/'services/aos-api/tests/extension_runtime'));sys.path.insert(0,str(REPO/'.evidence/gt-atomic-model-admission-20261008'));sys.path.insert(0,str(OUT))
original=psycopg.connect

def owned_connect(*args,**kwargs):
 assert len(args)<=1
 params=conninfo_to_dict(args[0] if args else kwargs.get('conninfo',''))
 for key in ('user','host','port','dbname'):
  if key in kwargs:params[key]=kwargs[key]
 if params.get('user')=='aos_app':
  assert params.get('host')=='127.0.0.1' and str(params.get('port'))=='5437'
  assert params.get('dbname')=='aos_meta' or params.get('dbname','').startswith('aos_test_')
  kwargs['passfile']=str(PASS)
  assert not kwargs.get('options') and not params.get('options')
  kwargs['options']='-c max_parallel_workers_per_gather=0 -c max_parallel_maintenance_workers=0 -c enable_parallel_hash=off -c work_mem=1MB -c hash_mem_multiplier=1'
 conn=original(*args,**kwargs)
 if params.get('user')=='aos_app':
  with conn.cursor() as cur:
   cur.execute("SELECT current_database() AS database_name,session_user AS session_name,pg_backend_pid() AS backend_pid,current_setting('max_parallel_workers_per_gather') AS query_parallel,current_setting('max_parallel_maintenance_workers') AS maintenance_parallel,current_setting('enable_parallel_hash') AS parallel_hash,current_setting('work_mem') AS work_memory,current_setting('hash_mem_multiplier') AS hash_multiplier,current_setting('fsync') AS fsync,current_setting('full_page_writes') AS full_pages,current_setting('synchronous_commit') AS synchronous_commit")
   row=cur.fetchone();values=list(row.values()) if isinstance(row,dict) else list(row)
  assert values[3:]==['0','0','off','1MB','1','on','on','on']
  if not conn.autocommit:conn.rollback()
  with (OUT/'tail48-r4-connections.jsonl').open('a') as audit:audit.write(json.dumps(dict(database=values[0],session=values[1],pid=values[2],settings=values[3:],startup_readonly_probe=True,known_read_rollback=True))+'\n')
 return conn
psycopg.connect=owned_connect
with original(host='127.0.0.1',port=5437,user='aos_app',dbname='aos_meta',passfile=str(PASS)) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 assert c.execute("SELECT count(*) FROM pg_database WHERE datname LIKE 'aos_test_%'").fetchone()[0]>=2
with original(host='127.0.0.1',port=5437,user='aos_app',dbname='template1',passfile=str(PASS)) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute("SELECT extversion FROM pg_extension WHERE extname='aos_ed25519'").fetchone()==('1.0',)
import importlib.util
spec=importlib.util.spec_from_file_location('native_lab_memoryctl',REPO/'scripts/memory/memoryctl.py');mc=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mc;spec.loader.exec_module(mc)
assert mc.load_authority()['project_revision']=='AOS-001646'
task=json.loads((mc.DEFAULT_PATHS.receipts_path/'tasks'/'gt-source-tail48-resume-20261009.json').read_text())
leases=[x for x in mc.load_leases(mc.DEFAULT_PATHS)['leases'] if x['task_id']==task['task_id']]
assert len(leases)==1 and task['owner']==leases[0]['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
assert datetime.fromisoformat(task['lease_expires_at'])>datetime.now(timezone.utc)
with (OUT/'native-tail48-r4-attempt.json').open('x') as h:json.dump({'head':'2c4d584377f59d44f6aa7a123ee69b39cfa46e4d','authority':'AOS-001646','lab':lab['container_id'],'cluster':lab['cluster'],'helper_sha256':__import__('hashlib').sha256((OUT/'input-bindings-r3.json').read_bytes()).hexdigest(),'product_sha256':__import__('hashlib').sha256((REPO/'services/aos-api/aos_api/aip_physical_capacity_occupation.py').read_bytes()).hexdigest(),'source_consumer_sha256':__import__('hashlib').sha256((REPO/'services/aos-api/aos_api/aip_provider_capacity_occupation_source.py').read_bytes()).hexdigest(),'fresh_original_bootstrap':True,'no_shared_database':True},h)
class Recorder:
 def __init__(self):self.database=None;self.results=[]
 def pytest_collection_finish(self,session):
  self.collected=[x.nodeid for x in session.items];assert self.collected==json.loads((OUT/'selection.json').read_text());(OUT/'tail48-r4-collection.json').write_text(json.dumps(self.collected,indent=2))
 def pytest_runtest_setup(self,item):
  free=int(subprocess.check_output(['docker','--context','colima-aos-extension','exec',lab['name'],'df','-P','-B1','/var/lib/postgresql/data'],text=True).splitlines()[-1].split()[3]);assert free>2580000000, 'ISOLATED_LAB_DISK_RESERVE_REQUIRED'
 def pytest_runtest_call(self,item):
  from aos_api.db import get_dsn
  self.database=conninfo_to_dict(get_dsn())['dbname'];assert self.database.startswith('aos_test_') and self.database.endswith('_ti4_test');self.results.append({'nodeid':item.nodeid,'phase':'database_binding','database':self.database})
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.results.append({'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome})
(OUT/'process.json').write_text(json.dumps({'pid':os.getpid(),'started_at':datetime.now(timezone.utc).isoformat(),'head':'2c4d584377f59d44f6aa7a123ee69b39cfa46e4d','authority':'AOS-001646','state':'RUNNING','replay_allowed':False},indent=2))
r=Recorder();code=pytest.main([str(REPO/'services/aos-api'/x) for x in json.loads((OUT/'selection.json').read_text())]+['-q','-s','--maxfail=1'],plugins=[r]);(OUT/'native-tail48-r4-result.json').write_text(json.dumps({'observed_at':datetime.now(timezone.utc).isoformat(),'database':r.database,'pytest_exit':int(code),'results':r.results,'scope':'Exact original remaining48 nodes diagnostic; never full386nodeSource acceptance'},indent=2)+'\n');raise SystemExit(code)
