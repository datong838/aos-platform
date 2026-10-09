from pathlib import Path
import sys,os,json,hashlib
B=Path(__file__).resolve().parent;R=B.parents[1]
os.environ['AOS_DOTENV_DISABLED']='1';sys.path[:0]=[str(R/'services/aos-api'),str(R/'.evidence/gt-model-typed-proof-20261008')]
import psycopg
calls=[]
def denied(*a,**k):calls.append(True);raise AssertionError('pure native connections denied')
psycopg.connect=denied
import pytest
paths=['services/aos-api/tests/aip/test_model_eval_execution_contracts.py','.evidence/gt-atomic-model-admission-20261008/test_shared_description_contract_1672.py','.evidence/gt-model-typed-proof-20261008/test_shared_certificate_1673.py','services/aos-api/tests/aip/test_model_shared_parent_certificate_identity_pg.py::test_artifact_keeps_runtime_denied','services/aos-api/tests/aip/test_shared_parent_description_origin_reader_pg.py::test_reader_artifact_has_no_mutations_or_table_grants']
code=pytest.main(['--noconftest',*[str(R/p) for p in paths],'-q','-p','no:cacheprovider']);assert not calls
files=['services/aos-api/aos_api/aip_shared_parent_description_origin_reader.py','services/aos-api/tests/aip/test_shared_parent_description_origin_reader_pg.py']
(B/'expiry-pure-result-r5-1676.json').write_text(json.dumps(dict(pytest_exit=int(code),database_connections=0,file_hashes={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in files},execution_allowed=False),indent=2)+'\n')
raise SystemExit(code)
