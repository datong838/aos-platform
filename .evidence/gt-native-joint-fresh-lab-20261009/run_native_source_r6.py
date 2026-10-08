import os,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import psycopg,pytest
from psycopg.conninfo import conninfo_to_dict
REPO=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;lab=json.loads((OUT/'lab.json').read_text());PASS=Path(lab['passfile']);assert PASS.stat().st_mode&0o077==0
state=json.loads(subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect',lab['name']],text=True))[0];assert state['Id']==lab['container_id'] and state['State']['Running']
assert state['HostConfig']['Memory']==805306368
space=subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','exec',lab['name'],'df','-Pk','/var/lib/postgresql/data'],text=True).splitlines()[-1].split();assert int(space[3])>16*1024
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()=='986bf81ea5bac9169f066266677d9a5cb0a30112'
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(key,None)
os.environ.update(AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5435/aos_test_f70639ea0633_ti4_test',AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5435',AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',AOS_TEST_RETAIN_DATABASE='1',AOS_TEST_USE_SHARED_DATABASE='0',AOS_DOTENV_DISABLED='1',AOS_SOURCE_MODEL_EVIDENCE_LABEL='source-joint-fresh-lab-r6')
sys.path.insert(0,str(REPO/'services/aos-api'));sys.path.insert(0,str(REPO/'services/aos-api/tests/extension_runtime'));sys.path.insert(0,str(REPO/'.evidence/gt-atomic-model-admission-20261008'))
original=psycopg.connect

def owned_connect(*args,**kwargs):
 assert len(args)<=1
 params=conninfo_to_dict(args[0] if args else kwargs.get('conninfo',''))
 for key in ('user','host','port','dbname'):
  if key in kwargs:params[key]=kwargs[key]
 if params.get('user')=='aos_app':
  assert params.get('host')=='127.0.0.1' and str(params.get('port'))=='5435'
  assert params.get('dbname')=='aos_meta' or params.get('dbname','').startswith('aos_test_')
  kwargs['passfile']=str(PASS)
 return original(*args,**kwargs)
psycopg.connect=owned_connect
with original(host='127.0.0.1',port=5435,user='aos_app',dbname='aos_meta',passfile=str(PASS)) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 assert c.execute("SELECT datname FROM pg_database WHERE datname LIKE 'aos_test_%' ORDER BY datname").fetchall()==[('aos_test_014da5b585b6_ti4_test',),('aos_test_4abf2ec5e78c_ti4_test',),('aos_test_f70639ea0633_ti4_test',)]
with original(host='127.0.0.1',port=5435,user='aos_app',dbname='aos_test_f70639ea0633_ti4_test',passfile=str(PASS)) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT version_num FROM alembic_version').fetchone()==('a0v_159',)
 for table in ('registry_epoch','source_publication'):assert c.execute('SELECT count(*) FROM aos_capacity_publication_private.'+table).fetchone()[0]==0
 assert c.execute("SELECT count(*) FROM meta_object_type WHERE id IN ('ModelEvalRequest','ProviderCapacityRequest','ProviderCapacitySourceReview')").fetchone()[0]==3
with original(host='127.0.0.1',port=5435,user='aos_app',dbname='template1',passfile=str(PASS)) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute("SELECT extversion FROM pg_extension WHERE extname='aos_ed25519'").fetchone()==('1.0',)
import importlib.util
spec=importlib.util.spec_from_file_location('native_lab_memoryctl',REPO/'scripts/memory/memoryctl.py');mc=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mc;spec.loader.exec_module(mc)
assert mc.load_authority()['project_revision']=='AOS-001596'
task=json.loads((mc.DEFAULT_PATHS.receipts_path/'tasks'/'gt-native-joint-fresh-lab-20261009.json').read_text())
leases=[x for x in mc.load_leases(mc.DEFAULT_PATHS)['leases'] if x['task_id']==task['task_id']]
assert len(leases)==1 and task['owner']==leases[0]['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
assert datetime.fromisoformat(task['lease_expires_at'])>datetime.now(timezone.utc)
with (OUT/'native-r6-attempt.json').open('x') as h:json.dump({'head':'986bf81ea5bac9169f066266677d9a5cb0a30112','authority':'AOS-001596','lab':lab['container_id'],'cluster':lab['cluster'],'fresh_original_bootstrap_completed_r4':True,'exact_retained_isolated_bootstrap_adapter':True,'no_original_source_replay':True},h)
class Recorder:
 def __init__(self):self.database=None;self.results=[]
 def pytest_runtest_call(self,item):
  from aos_api.db import get_dsn
  self.database=conninfo_to_dict(get_dsn())['dbname'];assert self.database.startswith('aos_test_') and self.database.endswith('_ti4_test')
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.results.append({'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome})
class RetainedIsolatedBootstrap:
 @pytest.hookimpl(tryfirst=True)
 def pytest_fixture_setup(self,fixturedef,request):
  if fixturedef.argname!='_isolated_postgres_database':return None
  assert fixturedef.scope=='session' and os.environ['AOS_TEST_USE_SHARED_DATABASE']=='0'
  with original(host='127.0.0.1',port=5435,user='aos_app',dbname='aos_test_f70639ea0633_ti4_test',passfile=str(PASS)) as c:
   c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster'];assert c.execute('SELECT version_num FROM alembic_version').fetchone()==('a0v_159',)
   assert c.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state<>'idle'").fetchone()[0]==0
  fixturedef.cached_result=(True,fixturedef.cache_key(request),None);return True
r=Recorder();code=pytest.main([str(REPO/'services/aos-api/tests/aip/test_physical_capacity_occupation_pg.py')+'::test_source_model_preparation_original_native_caller','-q','-s'],plugins=[r,RetainedIsolatedBootstrap()]);(OUT/'native-r6-result.json').write_text(json.dumps({'observed_at':datetime.now(timezone.utc).isoformat(),'database':r.database,'pytest_exit':int(code),'results':r.results,'scope':'unmodified original isolated Source/Model physical caller fullhead159, not newJudge joint or business firstchain'},indent=2)+'\n');raise SystemExit(code)
