"""Original release regressions in a new retained test-only database."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

base=Path(__file__).resolve().parent
repo=base.parents[1]
assert subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect','aos-capacity-publication-scram-20261006','--format','{{.Id}}'],text=True).strip()=='4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):
    os.environ.pop(key,None)
os.environ.update(AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5434/aos_meta',
    AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5434',
    AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',
    AOS_TEST_RETAIN_DATABASE='1',AOS_TEST_USE_SHARED_DATABASE='0',AOS_DOTENV_DISABLED='1')
sys.path.insert(0,str(repo/'services/aos-api'))
sys.path.insert(0,str(base))
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
        assert parameters.get('host')=='127.0.0.1' and str(parameters.get('port'))=='5434'
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
targets=[str(repo/'services/aos-api/tests/aip'/name) for name in [
 'test_release_report_context.py', 'test_aip_release_publication_service.py',
 'test_aip_release_publication_api.py', 'test_aip_release_publication_signed_skill_pg.py',
 'test_aip_eval_report_proof_reader.py']]
code=pytest.main([*targets,'-q','-s'],plugins=[recorder])
(base/'native-adjacent-result.json').write_text(json.dumps({'observed_at':datetime.now(timezone.utc).isoformat(),'database':recorder.database,'pytest_exit':int(code),'results':recorder.results,'scope':'Original release and signed Skill/proof regressions in retained test-only full schema; no formal Model execution'},indent=2)+'\n')
raise SystemExit(code)
