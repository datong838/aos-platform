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
target=B/'model-owner-fixture-isolation-native-1651'
container=json.loads(subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect','aos-capacity-publication-scram-20261006'],text=True))[0]
assert container['Id']=='4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2' and container['State']['Running']
env=dict(x.split('=',1) for x in container['Config']['Env'])
assert env.get('POSTGRES_USER')=='aos_app' and env.get('POSTGRES_PASSWORD')
existing_password=env['POSTGRES_PASSWORD']
del env
files=[B/'legal-model-prefix-application-r4.json',B/'legal-eval-application-result-r4.json']
before={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
target.mkdir()
for filename in ('legal_model_prefix_for_application_r4.py','legal_eval_application_fixture_r4.py'):
    with (target/filename).open('xb') as f:f.write((B/filename).read_bytes())
bindings={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
    R/'services/aos-api/tests/aip/test_model_eval_execution_owner_pg.py',*(target/x for x in ('legal_model_prefix_for_application_r4.py','legal_eval_application_fixture_r4.py'))]}
with (B/'model-owner-fixture-isolation-native-1651-attempt.json').open('x') as f:
    json.dump({'authority':'AOS-001651','head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
        'container':container['Id'],'started_at':container['State']['StartedAt'],'file_hashes':bindings,
        'old_evidence_hashes':before,'scope':'one fresh isolated original Model application, no Provider or formal execution'},f,indent=2)
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):
    os.environ.pop(key,None)
os.environ.update(AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5434/aos_meta',AOS_DOTENV_DISABLED='1',
    AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5434',
    AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',AOS_TEST_RETAIN_DATABASE='1',
    AOS_TEST_USE_SHARED_DATABASE='0',AOS_MODEL_OWNER_FIXTURE_EVIDENCE_ROOT=str(target),
    AOS_MODEL_OWNER_EVIDENCE_LABEL='model-owner-fixture-isolation-native-1651-owner')
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
        assert params.get('host')=='127.0.0.1' and str(params.get('port'))=='5434'
        assert params.get('dbname')=='aos_meta' or params.get('dbname','').startswith('aos_test_')
        kwargs['password']=existing_password
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
code=pytest.main([str(R/'services/aos-api/tests/aip/test_model_eval_execution_owner_pg.py')+'::test_model_owner_from_original_published_approved_application','-q','-s','-p','no:cacheprovider'],plugins=[recorder])
after={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
out={'observed_at':datetime.now(timezone.utc).isoformat(),'pytest_exit':int(code),'database':recorder.database,
    'results':recorder.results,'old_evidence_hashes_before':before,'old_evidence_hashes_after':after,
    'old_evidence_unchanged':before==after,'execution_allowed':False,'full_model_admission':False}
with (B/'model-owner-fixture-isolation-native-1651-result.json').open('x') as f:json.dump(out,f,indent=2)
assert before==after
raise SystemExit(code)
