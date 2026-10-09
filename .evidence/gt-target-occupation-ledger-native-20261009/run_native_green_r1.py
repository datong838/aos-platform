import os,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import psycopg,pytest
from psycopg.conninfo import conninfo_to_dict
REPO=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;lab=json.loads((OUT/'lab.json').read_text());PASS=Path(lab['passfile']);assert PASS.stat().st_mode&0o077==0
state=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect',lab['name']],text=True))[0];assert state['Id']==lab['container_id'] and state['State']['Running']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()=='5c8cf9d383c0fdf288fd96ae8b725b2a9625f5bb'
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(key,None)
os.environ.update(AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5436/aos_meta',AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5436',AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',AOS_TEST_RETAIN_DATABASE='1',AOS_TEST_USE_SHARED_DATABASE='0',AOS_DOTENV_DISABLED='1',AOS_SOURCE_MODEL_EVIDENCE_LABEL='source-newjudge-ledger-green-r1',AOS_SOURCE_NEW_JUDGE_NATIVE='1',AOS_NEW_JUDGE_INTENT_NATIVE='1',AOS_SOURCE_NEWJUDGE_PROOF='newjudge-source-proof-1607.json',AOS_JUDGE_NATIVE_EVIDENCE_LABEL='ledger-green-r1')
sys.path.insert(0,str(REPO/'services/aos-api'));sys.path.insert(0,str(REPO/'services/aos-api/tests/extension_runtime'));sys.path.insert(0,str(REPO/'.evidence/gt-atomic-model-admission-20261008'));sys.path.insert(0,str(OUT))
original=psycopg.connect

def owned_connect(*args,**kwargs):
 assert len(args)<=1
 params=conninfo_to_dict(args[0] if args else kwargs.get('conninfo',''))
 for key in ('user','host','port','dbname'):
  if key in kwargs:params[key]=kwargs[key]
 if params.get('user')=='aos_app':
  assert params.get('host')=='127.0.0.1' and str(params.get('port'))=='5436'
  assert params.get('dbname')=='aos_meta' or params.get('dbname','').startswith('aos_test_')
  kwargs['passfile']=str(PASS)
 return original(*args,**kwargs)
psycopg.connect=owned_connect
with original(host='127.0.0.1',port=5436,user='aos_app',dbname='aos_meta',passfile=str(PASS)) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 assert c.execute("SELECT datname FROM pg_database WHERE datname LIKE 'aos_test_%' ORDER BY datname").fetchall()==[('aos_test_14f68098c98d_ti4_test',), ('aos_test_18d23eeed874_ti4_test',), ('aos_test_3b1c904ab404_ti4_test',), ('aos_test_448279bddf13_ti4_test',), ('aos_test_48cb82e0fea9_ti4_test',), ('aos_test_4a449d82b60d_ti4_test',), ('aos_test_4d88bf4f8260_ti4_test',), ('aos_test_62a134e19612_ti4_test',), ('aos_test_66e465631080_ti4_test',), ('aos_test_74ed8a83ca18_ti4_test',), ('aos_test_7818fc629997_ti4_test',), ('aos_test_7f77c609b447_ti4_test',), ('aos_test_858917ed5f33_ti4_test',), ('aos_test_88cc4629bf66_ti4_test',), ('aos_test_8c277b14bd4f_ti4_test',), ('aos_test_9af4d49e082f_ti4_test',), ('aos_test_bc8172e66192_ti4_test',), ('aos_test_c2a1c2de2db6_ti4_test',), ('aos_test_d41e27f56293_ti4_test',), ('aos_test_d8047e76fe2d_ti4_test',), ('aos_test_e834db53fa0d_ti4_test',), ('aos_test_f3c5df7f369b_ti4_test',), ('aos_test_f82d9dd124bc_ti4_test',)]
with original(host='127.0.0.1',port=5436,user='aos_app',dbname='template1',passfile=str(PASS)) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute("SELECT extversion FROM pg_extension WHERE extname='aos_ed25519'").fetchone()==('1.0',)
import importlib.util
spec=importlib.util.spec_from_file_location('native_lab_memoryctl',REPO/'scripts/memory/memoryctl.py');mc=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mc;spec.loader.exec_module(mc)
assert mc.load_authority()['project_revision']=='AOS-001614'
task=json.loads((mc.DEFAULT_PATHS.receipts_path/'tasks'/'gt-target-occupation-ledger-native-20261009.json').read_text())
leases=[x for x in mc.load_leases(mc.DEFAULT_PATHS)['leases'] if x['task_id']==task['task_id']]
assert len(leases)==1 and task['owner']==leases[0]['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
assert datetime.fromisoformat(task['lease_expires_at'])>datetime.now(timezone.utc)
with (OUT/'native-green-r1-attempt.json').open('x') as h:json.dump({'head':'5c8cf9d383c0fdf288fd96ae8b725b2a9625f5bb','authority':'AOS-001614','lab':lab['container_id'],'cluster':lab['cluster'],'helper_sha256':__import__('hashlib').sha256((OUT/'source_newjudge_native_trial_1606.py').read_bytes()).hexdigest(),'fresh_original_bootstrap':True,'no_shared_database':True},h)
class Recorder:
 def __init__(self):self.database=None;self.results=[]
 def pytest_runtest_call(self,item):
  from aos_api.db import get_dsn
  self.database=conninfo_to_dict(get_dsn())['dbname'];assert self.database.startswith('aos_test_') and self.database.endswith('_ti4_test')
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.results.append({'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome})
r=Recorder();code=pytest.main([str(REPO/'services/aos-api/tests/aip/test_physical_capacity_occupation_pg.py')+'::test_source_model_preparation_original_native_caller','-q','-s'],plugins=[r]);(OUT/'native-green-r1-result.json').write_text(json.dumps({'observed_at':datetime.now(timezone.utc).isoformat(),'database':r.database,'pytest_exit':int(code),'results':r.results,'scope':'initial occupation root and first immutable event from original trusted Target call; zero actual inflight; no admission'},indent=2)+'\n');raise SystemExit(code)
