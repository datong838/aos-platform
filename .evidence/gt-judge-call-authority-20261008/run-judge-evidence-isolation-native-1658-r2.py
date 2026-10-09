"""One fresh owned database; original fixtures, exact copies, no old replay."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

B=Path(__file__).resolve().parent
R=B.parents[1]
target=B/'judge-evidence-isolation-native-1658-r2'
M=R/'.evidence/gt-atomic-model-admission-20261008'
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
container=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['name']],text=True))[0]
assert container['Id']==lab['container_id'] and container['State']['Running']
assert lab['cluster']=='7694680278363095064' and lab['port']==5441
passfile=Path(lab['passfile']);assert passfile.stat().st_mode & 0o077 == 0
free=int(subprocess.check_output(['docker','--context',lab['context'],'exec',lab['name'],'df','-P','-B1','/var/lib/postgresql/data'],text=True).splitlines()[-1].split()[3]);assert free>2500000000
volume=json.loads(subprocess.check_output(['docker','--context',lab['context'],'volume','inspect',lab['volume']],text=True))[0];assert volume['Driver']=='local' and not volume['Options']
files=[M/'legal-model-prefix-application-r4.json',M/'legal-eval-application-result-r4.json', *B.glob('*-whole-plan-proof.json'), *B.glob('*-full-proof.json')]
before={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
target.mkdir()
for filename in ('legal_model_prefix_for_application_r4.py','legal_eval_application_fixture_r4.py','build_whole_native_plan_1602.py'):
    with (target/filename).open('xb') as f:f.write((M/filename).read_bytes())
bindings={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
    R/'services/aos-api/tests/aip/test_model_eval_judge_authority_pg.py',R/'services/aos-api/aos_api/aip_model_eval_execution_owner.py',*(target/x for x in ('legal_model_prefix_for_application_r4.py','legal_eval_application_fixture_r4.py','build_whole_native_plan_1602.py'))]}
with (B/'judge-evidence-isolation-native-1658-r2-attempt.json').open('x') as f:
    json.dump({'authority':'AOS-001658','head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
        'container':container['Id'],'started_at':container['State']['StartedAt'],'file_hashes':bindings,'free_bytes':free,'volume':lab['volume'],
        'old_evidence_hashes':before,'scope':'one fresh retained original independently approved Judge whole-plan application; old evidence preserved; no Provider/formal execution'},f,indent=2)
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):
    os.environ.pop(key,None)
os.environ.update(AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5441/aos_meta',AOS_DOTENV_DISABLED='1',
    AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5441',
    AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',AOS_TEST_RETAIN_DATABASE='1',
    AOS_TEST_USE_SHARED_DATABASE='0',AOS_JUDGE_FIXTURE_EVIDENCE_ROOT=str(target),
    AOS_JUDGE_NATIVE_EVIDENCE_LABEL='judge-evidence-isolation-native-1658-r2')
sys.path.insert(0,str(R/'services/aos-api'))
sys.path.insert(0,str(R/'services/aos-api/tests/extension_runtime'))
sys.path.insert(0,str(R/'services/aos-api/tests'))
import psycopg
from psycopg.conninfo import conninfo_to_dict
original_connect=psycopg.connect
def owned_connect(*args,**kwargs):
    assert len(args)<=1
    params=conninfo_to_dict(args[0] if args else kwargs.get('conninfo',''))
    for key in ('host','port','user','dbname'):
        if key in kwargs:params[key]=kwargs[key]
    if params.get('user')=='aos_app':
        assert params.get('host')=='127.0.0.1' and str(params.get('port'))=='5441'
        assert params.get('dbname')=='aos_meta' or params.get('dbname','').startswith('aos_test_')
        kwargs['passfile']=str(passfile)
    return original_connect(*args,**kwargs)
psycopg.connect=owned_connect
import pytest
class Recorder:
    def __init__(self):self.database=None;self.results=[]
    def pytest_runtest_call(self,item):
        from aos_api.db import get_dsn
        self.database=conninfo_to_dict(get_dsn())['dbname']
        assert self.database.startswith('aos_test_')
    def pytest_runtest_logreport(self,report):
        if report.when=='call' or report.failed:
            self.results.append({'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome})
recorder=Recorder()
code=pytest.main([str(R/'services/aos-api/tests/aip/test_model_eval_judge_authority_pg.py')+'::test_exact_signed_rule_new_original_suite','-q','-s','-p','no:cacheprovider'],plugins=[recorder])
after={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
out={'observed_at':datetime.now(timezone.utc).isoformat(),'pytest_exit':int(code),'database':recorder.database,
    'results':recorder.results,'old_evidence_hashes_before':before,'old_evidence_hashes_after':after,
    'old_evidence_unchanged':before==after,'execution_allowed':False,'full_model_admission':False}
with (B/'judge-evidence-isolation-native-1658-r2-result.json').open('x') as f:json.dump(out,f,indent=2)
assert before==after
raise SystemExit(code)
