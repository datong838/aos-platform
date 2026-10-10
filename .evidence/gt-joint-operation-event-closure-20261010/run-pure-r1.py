from pathlib import Path
import sys,os,json,hashlib
B=Path(__file__).resolve().parent;R=B.parents[1]
os.environ['AOS_DOTENV_DISABLED']='1';sys.path.insert(0,str(R/'services/aos-api'))
import psycopg
calls=[]
def denied(*a,**k):calls.append(True);raise AssertionError('pure test database connection prohibited')
psycopg.connect=denied
import pytest
paths=['services/aos-api/tests/aip/test_physical_capacity_joint_events.py','services/aos-api/tests/aip/test_physical_capacity_joint_catalog.py','services/aos-api/tests/aip/test_shared_parent_executor_set_reader_pg.py','services/aos-api/tests/aip/test_shared_parent_certificate_prepare_pg.py']
code=pytest.main(['--noconftest',*[str(R/p) for p in paths],'-q','-p','no:cacheprovider']);assert not calls
files=['services/aos-api/aos_api/aip_physical_capacity_joint_events.py','services/aos-api/aos_api/aip_physical_capacity_joint_catalog.py',*paths]
(B/'pure-result-r1.json').open('x').write(json.dumps(dict(pytest_exit=int(code),database_connections=0,file_hashes={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in files},execution_allowed=False,finalizer_implemented=False),indent=2)+'\n')
raise SystemExit(code)
