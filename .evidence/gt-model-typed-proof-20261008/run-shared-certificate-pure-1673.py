from pathlib import Path
import os, sys, json, hashlib
B = Path(__file__).resolve().parent; R = B.parents[1]
os.environ['AOS_DOTENV_DISABLED'] = '1'
sys.path[:0] = [str(R/'services/aos-api'),str(B)]
import psycopg
connections=[]
def denied(*args,**kwargs):
    connections.append(True)
    raise AssertionError('pure verification cannot connect to database')
psycopg.connect=denied
import pytest
paths=[R/'services/aos-api/tests/aip/test_model_eval_execution_contracts.py',
 R/'.evidence/gt-atomic-model-admission-20261008/test_shared_description_contract_1672.py',
 B/'test_shared_certificate_1673.py']
code=pytest.main(['--noconftest',*[str(p) for p in paths],'-q','-p','no:cacheprovider'])
assert not connections
(B/'shared-certificate-pure-result-1673.json').write_text(json.dumps(dict(pytest_exit=int(code),database_connections=0,
 product_sha256=hashlib.sha256((R/'services/aos-api/aos_api/aip_model_eval_execution_contracts.py').read_bytes()).hexdigest(),
 execution_allowed=False,full_task_delivered=False),indent=2)+'\n')
raise SystemExit(code)
