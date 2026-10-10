"""Fresh retained Model native review; exact isolated lab, never preview DB."""
import importlib.util,json,os,re,subprocess,sys,hashlib
from pathlib import Path
from datetime import datetime,timezone
E=Path(__file__).resolve().parent;R=E.parents[1]
label=sys.argv[1];assert re.fullmatch(r'reboot-native-r[1-9][0-9]*(?:-n[0-9]{2})?',label)
node=sys.argv[2] if len(sys.argv)==3 else None
if node is not None:
 assert node in json.loads((E/'reboot-native-r1/terminal.json').read_text())['collected']
J=E/label;J.mkdir(mode=0o700)
def save(name,value):
 with os.fdopen(os.open(J/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as out:json.dump(value,out,indent=2);out.flush();os.fsync(out.fileno())
s=importlib.util.spec_from_file_location('model_reboot_memory',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
a=m.load_authority();t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks/gt-model-typed-proof-20261008.json').read_text());assert a['project_revision']=='AOS-001701' and t['status']=='ACTIVE' and t['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
assert [x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']==t['task_id']]==[t]
expanded=label.startswith(('reboot-native-r4-','reboot-native-r5-','reboot-native-r6-')); lab=json.loads((E/'reboot-lab.json' if expanded else R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text()); expected_port=5442 if expanded else 5441;p=Path(lab['passfile']);assert p.is_file() and p.stat().st_mode&0o077==0
x=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['name']]))[0]
assert x['Id']==lab['container_id'] and x['State']['Running'] and x['Image']==lab['image'] and x['HostConfig']['ShmSize']==(1073741824 if expanded else 268435456)
assert [z['Name'] for z in x['Mounts'] if z['Type']=='volume']==[lab['volume']] and lab['port']==expected_port
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(key,None)
os.environ.update(AOS_DATABASE_URL=f'postgresql://aos_app@127.0.0.1:{expected_port}/aos_meta',AOS_TEST_RETAIN_DATABASE='1',AOS_TEST_USE_SHARED_DATABASE='0',AOS_DOTENV_DISABLED='1',AOS_TWA_STORE='memory')
sys.path.insert(0,str(R/'services/aos-api'));sys.path.insert(0,str(R/'services/aos-api/tests'));sys.path.insert(0,str(R/'services/aos-api/tests/extension_runtime'));sys.path.insert(0,str(R/'.evidence/gt-atomic-model-admission-20261008'))
import psycopg
from psycopg.conninfo import conninfo_to_dict
original=psycopg.connect
def owned_connect(*args,**kwargs):
 assert len(args)<=1
 params=conninfo_to_dict(args[0] if args else kwargs.get('conninfo',''))
 for key in ('user','host','port','dbname'):
  if key in kwargs:params[key]=kwargs[key]
 assert params.get('host')=='127.0.0.1' and str(params.get('port'))==str(expected_port), 'test lab connection only'
 assert params.get('dbname')=='aos_meta' or re.fullmatch(r'aos_test_[0-9a-f]{12}_ti4_test',params.get('dbname','')), 'original fresh test database only'
 if params.get('user')=='aos_app':kwargs['passfile']=str(p)
 return original(*args,**kwargs)
psycopg.connect=owned_connect
with psycopg.connect(os.environ['AOS_DATABASE_URL']) as c:
 c.read_only=True
 assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 assert c.execute('SELECT count(*) FROM pg_stat_activity WHERE pid<>pg_backend_pid() AND backend_type=\'client backend\'').fetchone()[0]==0
 c.rollback()
files=['services/aos-api/aos_api/aip_model_eval_execution_authority.py','services/aos-api/aos_api/aip_model_eval_execution_reader.py','services/aos-api/alembic/versions/a0v_158_model_eval_execution_authority.py','services/aos-api/alembic/versions/a0v_159_model_judge_budget.py','services/aos-api/tests/aip/test_model_eval_execution_authority_pg.py','services/aos-api/tests/aip/test_model_eval_execution_contracts.py']
save('attempt.json',{'state':'RUNNING','head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'authority':a['project_revision'],'lab_container':x['Id'],'lab_cluster':lab['cluster'],'source_hashes':{f:hashlib.sha256((R/f).read_bytes()).hexdigest() for f in files},'preview_connection_allowed':False,'replay_allowed':False,'fresh_database_retained':True})
import pytest
class Recorder:
 def __init__(self):self.database=None;self.results=[];self.collected=[]
 def pytest_collection_modifyitems(self,items):
  # Original zero-storage assertions precede durable certificates; no node omitted.
  priority={'test_model_private_storage_native_boundary':0,'test_model_issuer_history_has_independent_closed_owner_and_native_boundaries':1}
  items.sort(key=lambda i:priority.get(i.originalname,2));self.collected=[i.nodeid for i in items]
 def pytest_runtest_call(self,item):
  from aos_api.db import get_dsn
  self.database=conninfo_to_dict(get_dsn())['dbname'];assert self.database.startswith('aos_test_')
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.results.append({'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome})
r=Recorder();target=str(R/'services/aos-api')+'/'+node if node is not None else str(R/'services/aos-api/tests/aip/test_model_eval_execution_authority_pg.py')
code=pytest.main([target,'-q','--maxfail=1'],plugins=[r])
save('terminal.json',{'exit':int(code),'database':r.database,'collected':r.collected,'results':r.results,'clock_mocked':False,'synthetic_root':True,'execution_allowed':False});print(json.dumps({'exit':int(code),'database':r.database,'results':len(r.results),'collected':len(r.collected)}));raise SystemExit(code)
