from pathlib import Path
import sys,os,json,hashlib
R=Path.cwd();B=R/'.evidence/gt-model-typed-proof-20261008'
os.environ['AOS_DOTENV_DISABLED']='1';sys.path[:0]=[str(R/'services/aos-api'),str(B)]
import psycopg
calls=[]
def denied(*a,**k):calls.append(True);raise AssertionError('pure verification forbids DB')
psycopg.connect=denied
import pytest
class Recorder:
 def __init__(self):self.reports=[]
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.reports.append(dict(nodeid=report.nodeid,phase=report.when,outcome=report.outcome))
rec=Recorder();paths=[B/'shared-judge-input-test-r2-1697.py',B/'shared-case-test-1694.py',B/'test_shared_certificate_1673.py',R/'services/aos-api/tests/aip/test_model_eval_execution_contracts.py']
code=pytest.main(['--noconftest',*[str(p) for p in paths],'-q','-p','no:cacheprovider'],plugins=[rec]);assert not calls
(B/'shared-judge-input-result-r2-1697.json').open('x').write(json.dumps(dict(pytest_exit=int(code),database_connections=0,reports=rec.reports,source_hashes={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [R/'services/aos-api/aos_api/aip_model_eval_execution_contracts.py',*paths]},execution_allowed=False,synthetic_facts=True,actual_transport=False),indent=2)+'\n');raise SystemExit(code)
