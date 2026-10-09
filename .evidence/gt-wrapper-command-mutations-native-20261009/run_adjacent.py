import os,sys
from pathlib import Path
R=Path(__file__).resolve().parents[2]
os.environ.update(AOS_DOTENV_DISABLED='1',AOS_TEST_USE_SHARED_DATABASE='1',AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:9/never_unit_db')
sys.path.insert(0,str(R/'services/aos-api'))
import psycopg,pytest
def forbidden(*a,**k):raise AssertionError('PURE_UNIT_DATABASE_CONNECTION_FORBIDDEN')
psycopg.connect=forbidden
files=['services/aos-api/tests/aip/test_model_eval_execution_contracts.py','services/aos-api/tests/aip/test_model_eval_authorization.py','services/aos-api/tests/aip/test_model_eval_execution_gate.py','services/aos-api/tests/aip/test_model_eval_judge_action_boundary.py','services/aos-api/tests/aip/test_provider_capacity_source_contracts.py','.evidence/gt-occupation-preparation-types-20261009/test_preparation_types.py']
raise SystemExit(pytest.main(['-q',*[str(R/f) for f in files]]))
