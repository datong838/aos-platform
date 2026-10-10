from pathlib import Path
import os,sys,json,hashlib,subprocess,importlib.util
B=Path(__file__).resolve().parent;R=B.parents[2]
J=R/'.evidence/gt-judge-call-authority-20261008';M=R/'.evidence/gt-atomic-model-admission-20261008'
label='origin-positive-1720-r4';target=J/label
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
c=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['name']],text=True))[0]
assert c['Id']==lab['container_id'] and c['Image']==lab['image'] and c['State']['Running']
assert lab['cluster']=='7694680278363095064' and lab['port']==5441
free=int(subprocess.check_output(['docker','--context',lab['context'],'exec',lab['name'],'df','-P','-B1','/var/lib/postgresql/data'],text=True).splitlines()[-1].split()[3]);assert free>2500000000
old=[M/'legal-model-prefix-application-r4.json',M/'legal-eval-application-result-r4.json',R/'services/aos-api/aos_api/aip_model_eval_execution_reader.py',R/'services/aos-api/aos_api/aip_model_eval_execution_authority.py']
before={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in old}
target.mkdir()
for n in ('legal_model_prefix_for_application_r4.py','legal_eval_application_fixture_r4.py','build_whole_native_plan_1602.py'):
 (target/n).open('xb').write((M/n).read_bytes())
for n in ('legal_model_prefix_for_application_r4.py','legal_eval_application_fixture_r4.py','build_whole_native_plan_1602.py'):
 (B/n).open('xb').write((M/n).read_bytes())
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
os.environ.update(AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5441/aos_meta',AOS_DOTENV_DISABLED='1',AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5441',AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',AOS_TEST_RETAIN_DATABASE='1',AOS_TEST_USE_SHARED_DATABASE='0',AOS_JUDGE_FIXTURE_EVIDENCE_ROOT=str(target),AOS_JUDGE_NATIVE_EVIDENCE_LABEL=label,AOS_PARENT_LIFECYCLE_EVIDENCE=str(B))
sys.path[:0]=[str(R/'services/aos-api'),str(R/'services/aos-api/tests/extension_runtime'),str(R/'services/aos-api/tests')]
import psycopg
from psycopg.conninfo import conninfo_to_dict
connect=psycopg.connect
def owned_connect(*args,**kwargs):
 assert len(args)<=1
 params=conninfo_to_dict(args[0] if args else kwargs.get('conninfo',''))
 for k in ('host','port','user','dbname'):
  if k in kwargs:params[k]=kwargs[k]
 if params.get('user')=='aos_app':
  assert params.get('host')=='127.0.0.1' and str(params.get('port'))=='5441'
  assert params.get('dbname')=='aos_meta' or params.get('dbname','').startswith('aos_test_')
  kwargs['passfile']=lab['passfile']
 return connect(*args,**kwargs)
psycopg.connect=owned_connect
import pytest
s=importlib.util.spec_from_file_location('expected',J/'registered_judge_expected_fixture_1659.py');fixture=importlib.util.module_from_spec(s);s.loader.exec_module(fixture);patch=pytest.MonkeyPatch();fixture.install(patch)
os.environ.update(AOS_SOURCE_MODEL_EVIDENCE_LABEL=label,AOS_SOURCE_NEW_JUDGE_NATIVE='1',AOS_NEW_JUDGE_INTENT_NATIVE='1')
sys.path.insert(0,str(B))
import source_newjudge_native_trial_1606 as trial
from aos_api.aip_model_eval_execution_owner import ModelEvalExecutionOwner
original_judge=ModelEvalExecutionOwner.prepare_judge_application
def record_judge(self,*args,**kwargs):
 trial.POLICY=kwargs
 return original_judge(self,*args,**kwargs)
patch.setattr(ModelEvalExecutionOwner,'prepare_judge_application',record_judge)
import tests.aip.test_physical_capacity_occupation_pg as test_module
PlainPath=Path
class EvidencePath(type(Path())):
 def __truediv__(self,other):
  result=super().__truediv__(other)
  if str(result)==str(M):return B
  return result
patch.setattr(test_module,'Path',EvidencePath)
class Recorder:
 def __init__(self):self.databases=[];self.results=[]
 def pytest_collection_modifyitems(self,items):
  for item in items:
   if str(item.path).endswith('test_physical_capacity_occupation_pg.py'):
    patch.setattr(item.module,'Path',EvidencePath)
 def pytest_runtest_call(self,item):
  from aos_api.db import get_dsn
  self.databases.append(conninfo_to_dict(get_dsn())['dbname'])
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.results.append({'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome})
rec=Recorder()
files=['services/aos-api/aos_api/aip_physical_capacity_occupation.py','services/aos-api/tests/aip/test_physical_capacity_occupation_pg.py','services/aos-api/aos_api/aip_model_eval_execution_contracts.py','services/aos-api/aos_api/aip_model_eval_execution_owner.py','services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py','services/aos-api/aos_api/aip_physical_capacity_occupation_contracts.py']
bindings={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in files}
(B/'attempt-r4.json').open('x').write(json.dumps({'cluster':lab['cluster'],'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'file_hashes':bindings,'old_hashes':before,'free_bytes':free,'execution_allowed':False},indent=2))
code=pytest.main([str(R/'services/aos-api/tests/aip/test_physical_capacity_occupation_pg.py')+'::test_source_model_preparation_original_native_caller','-q','-s','-p','no:cacheprovider'],plugins=[rec])
after={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in old};assert before==after
(B/'result-r4.json').open('x').write(json.dumps({'pytest_exit':int(code),'databases':rec.databases,'reports':rec.results,'old_files_unchanged':before==after,'file_hashes':bindings,'execution_allowed':False,'full_task_delivered':False},indent=2))
raise SystemExit(code)
