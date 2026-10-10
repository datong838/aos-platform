"""Original execution primitives only; synthetic callbacks, no Provider."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

base=Path(__file__).resolve().parent
repo=base.parents[1]
import json
lab=json.loads((repo/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
c=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['name']],text=True))[0]
assert c['Id']==lab['container_id'] and c['State']['Running']
assert lab['port']==5441 and lab['cluster']=='7694680278363095064'
passfile=Path(lab['passfile']);assert passfile.stat().st_mode&0o077==0
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):
    os.environ.pop(key,None)
os.environ.update(AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5441/aos_meta',
    AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5441',
    AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',
    AOS_TEST_RETAIN_DATABASE='1',AOS_TEST_USE_SHARED_DATABASE='0',AOS_DOTENV_DISABLED='1')
sys.path.insert(0,str(repo/'services/aos-api'))
sys.path.insert(0,str(base))
sys.path.insert(0,str(repo/'services/aos-api/tests/aip'))
import json
claim=base/'worker-commit-attempt-1696.json'
with claim.open('x') as handle:
    json.dump({'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'authority':'AOS-001696','provider_calls':0,'scope':'new retained random test database; original synthetic callback primitive regressions'},handle)
# The original issuer forbids global credential variables. Only the exact
# owned admin login receives its existing passfile as a connection parameter.
import psycopg
from psycopg.conninfo import conninfo_to_dict
original_connect=psycopg.connect
def owned_connect(*args,**kwargs):
    assert len(args)<=1
    parameters=conninfo_to_dict(args[0] if args else kwargs.get('conninfo',''))
    for key in ('user','host','port','dbname'):
        if key in kwargs:parameters[key]=kwargs[key]
    if parameters.get('user')=='aos_app':
        assert parameters.get('host')=='127.0.0.1' and str(parameters.get('port'))=='5441'
        assert parameters.get('dbname')=='aos_meta' or parameters.get('dbname','').startswith('aos_test_')
        kwargs['passfile']=str(passfile)
    return original_connect(*args,**kwargs)
psycopg.connect=owned_connect
import json
from datetime import datetime, timezone
import pytest
class Recorder:
    def __init__(self): self.database=None; self.results=[]
    def pytest_runtest_call(self,item):
        from aos_api.db import get_dsn
        self.database=conninfo_to_dict(get_dsn())['dbname']
        assert self.database.startswith('aos_test_')
    def pytest_runtest_logreport(self,report):
        if report.when=='call' or report.failed:
            self.results.append({'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome})
recorder=Recorder()
targets=[str(base/'test-worker-commit-1696.py')]
code=pytest.main([*targets,'-q','-s','-p','no:cacheprovider'],plugins=[recorder])
(base/'worker-commit-result-1696.json').write_text(json.dumps({'observed_at':datetime.now(timezone.utc).isoformat(),'database':recorder.database,'pytest_exit':int(code),'results':recorder.results,'scope':'Original content worker/consumer primitive only; synthetic callback/transport and reduced test schemas, not natural Model quality or execution authorization'},indent=2)+'\n')
for module in list(sys.modules.values()):
    if getattr(module,'__file__',None)==str(base/'test-worker-commit-1696.py'):
        (base/'worker-commit-proof-1696.json').open('x').write(json.dumps(module.PROOFS,indent=2,default=str)+'\n')
raise SystemExit(code)
