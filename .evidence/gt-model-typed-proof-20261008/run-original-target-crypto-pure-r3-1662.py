"""Pure regression with every database connection explicitly denied."""
from pathlib import Path
import os,sys,json,hashlib
B=Path(__file__).resolve().parent;R=B.parents[1]
os.environ['AOS_DOTENV_DISABLED']='1';sys.path.insert(0,str(R/'services/aos-api'))
import psycopg
connections=[]
def denied(*args,**kwargs):
    connections.append(True)
    raise AssertionError('pure signing verification must not connect to any database')
psycopg.connect=denied
import pytest
code=pytest.main(['--noconftest',str(R/'services/aos-api/tests/aip/test_model_eval_execution_contracts.py'),'-q','-p','no:cacheprovider'])
assert not connections
paths=['services/aos-api/aos_api/aip_model_eval_execution_contracts.py','services/aos-api/tests/aip/test_model_eval_execution_contracts.py']
with (B/'original-target-crypto-pure-result-r3-1662.json').open('x') as f:
 json.dump({'pytest_exit':int(code),'database_connections':0,'file_hashes':{p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in paths},'execution_allowed':False,'actual_target_certified':False,'full_task_delivered':False},f,indent=2)
raise SystemExit(code)
