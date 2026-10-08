"""Original caller post-expiry COMMIT probe in fresh retained owned fixture."""
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
os.environ.update(AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5434/aos_test_379975a6f96d_ti4_test',
    AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5434',
    AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',
    AOS_TEST_RETAIN_DATABASE='1',AOS_TEST_USE_SHARED_DATABASE='0',AOS_DOTENV_DISABLED='1')
sys.path.insert(0,str(repo/'services/aos-api'))
sys.path.insert(0,str(repo/'.evidence/gt-atomic-model-admission-20261008'))
sys.path.insert(0,str(repo/'services/aos-api/tests/extension_runtime'))
sys.path.insert(0,str(repo/'services/aos-api/tests'))
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
with original_connect(host='127.0.0.1',port=5434,user='aos_app',dbname='aos_test_379975a6f96d_ti4_test',passfile=str(passfile)) as audit:
    audit.execute('SET TRANSACTION READ ONLY')
    assert audit.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]=='7693564235776004128'
    assert audit.execute('SELECT version_num FROM alembic_version').fetchall()==[('a0v_159',)]
    assert audit.execute("SELECT count(*) FROM pg_constraint WHERE conrelid='public.aip_model_eval_judge_request'::regclass AND pg_get_constraintdef(oid) LIKE '%aos.model-judge-call-request/v2%'").fetchone()[0]==1
    assert audit.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state<>'idle'").fetchone()[0]==0
    assert audit.execute("SELECT id,name,description,published,properties,required_markings FROM meta_object_type WHERE id='ModelEvalRequest'").fetchone()==('ModelEvalRequest','模型首次评测申请','仅供独立审批的不可执行申请',True,[],[])
    baseline={'database':'aos_test_379975a6f96d_ti4_test','head':'a0v_159','cluster':'7693564235776004128','existing_v2_table':True,'prior_judge_draft_retained':True,'original_proposals':audit.execute('SELECT count(*) FROM aip_action_proposal').fetchone()[0]}
(base/'whole-reader-deadline-r2-1604-baseline.json').write_text(json.dumps(baseline,indent=2)+'\n')
with (base/'whole-reader-deadline-r2-1604-attempt.json').open('x') as h: json.dump({'head':'6c6c3b4679b0b7750e5503aa3df271be7e8913c0','authority':'AOS-001604','scope':'reused retained full159 Source/original Owner/all Model neighbors plus pretransport executor-set native expiry wait; no formal authority'},h)
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
class ClonedIsolatedBootstrap:
    @pytest.hookimpl(tryfirst=True)
    def pytest_fixture_setup(self,fixturedef,request):
        if fixturedef.argname!='_isolated_postgres_database':return None
        assert fixturedef.scope=='session'
        retained='aos_test_379975a6f96d_ti4_test'
        assert os.environ['AOS_TEST_USE_SHARED_DATABASE']=='0'
        assert retained.startswith('aos_test_') and retained.endswith('_ti4_test')
        os.environ['AOS_DATABASE_URL']='postgresql://aos_app@127.0.0.1:5434/'+retained
        with original_connect(host='127.0.0.1',port=5434,user='aos_app',dbname=retained,passfile=str(passfile)) as audit:
            audit.execute('SET TRANSACTION READ ONLY')
            assert audit.execute('SELECT version_num FROM alembic_version').fetchall()==[('a0v_159',)]
            assert audit.execute("SELECT count(*) FROM pg_constraint WHERE conrelid='public.aip_model_eval_judge_request'::regclass AND pg_get_constraintdef(oid) LIKE '%aos.model-judge-call-request/v2%'").fetchone()[0]==1
            assert audit.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state<>'idle'").fetchone()[0]==0
        fixturedef.cached_result=(True,fixturedef.cache_key(request),None)
        return True
os.environ['AOS_JUDGE_NATIVE_EVIDENCE_LABEL']='whole-reader-deadline-r2-1604'
recorder=Recorder()
code=pytest.main([str(repo/'services/aos-api/tests/aip/test_model_eval_judge_authority_pg.py')+'::test_exact_signed_rule_new_original_suite','-q','-s'],plugins=[recorder,ClonedIsolatedBootstrap()])
(base/'whole-reader-deadline-r2-1604-result.json').write_text(json.dumps({'observed_at':datetime.now(timezone.utc).isoformat(),'database':recorder.database,'pytest_exit':int(code),'results':recorder.results,'scope':'original legal sources then pending request; no transport'},indent=2)+'\n')
raise SystemExit(code)
