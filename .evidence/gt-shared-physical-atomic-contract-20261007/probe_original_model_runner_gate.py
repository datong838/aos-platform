"""Read-only original Runner gate using persisted exact application inputs."""
from pathlib import Path
import sys,json,tempfile,hashlib
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
base=Path(__file__).resolve().parent
repo=base.parents[1]
sys.path.insert(0,str(repo/'services/aos-api'))
from aos_api.aip_eval_runner import AipEvalRunner
from aos_api.aip_eval_authority_store import AipEvalAuthorityConflict
from aos_api.tenant_scope import TenantScope,apply_transaction_scope
r=json.loads((base/'legal-eval-application-result-r3.json').read_text());scope=TenantScope('org-org','dev-project')
assert r['database'].startswith('aos_test_')
@contextmanager
def connect(scope):
    assert scope.key==('org-org','dev-project')
    with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=r['database'],passfile=str(Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'),row_factory=dict_row) as c:
        c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']=='7693564235776004128'
        c.execute('SET LOCAL ROLE aos_runtime');apply_transaction_scope(c,scope)
        yield c
with connect(scope) as c:
    request=c.execute('SELECT request_json FROM aip_model_eval_request WHERE request_id=%s',(r['request_id'],)).fetchone()['request_json']
def counts():
    with connect(scope) as c:
        return {t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in ['aip_eval_run','aip_eval_report_revision','aip_model_eval_request','aip_model_eval_budget_reservation','aip_agent_run']}
before=counts();calls=[]
def forbidden(*args,**kwargs):
    calls.append('unexpected');raise AssertionError('callback must not execute')
runner=AipEvalRunner(connect_factory=connect);observed=[]
for mode in ['run_by_contract','run']:
    common=dict(idempotency_key='read-only-runner-boundary-'+mode,actor=r['maker'],resolve_artifact=forbidden,execute_target=forbidden,execute_judge=forbidden)
    try:
        if mode=='run_by_contract':
            ref=request['evalContractRef'];runner.run_by_contract(scope,contract_id=ref['assetId'],contract_revision=ref['revision'],contract_content_hash=ref['contentHash'],**common)
        else:
            ref=request['suiteRef'];runner.run(scope,suite_id=ref['assetId'],suite_revision=ref['revision'],**common)
    except AipEvalAuthorityConflict as exc:
        assert str(exc)=='formal Model Eval executor authority unavailable'
        observed.append({'entry':mode,'error':str(exc),'callbacks':len(calls)})
    else:raise AssertionError('unavailable formal authority must deny')
after=counts();assert before==after and calls==[]
report={'status':'ORIGINAL_MODEL_RUNNER_DENIES_BEFORE_CALLBACK_READ_ONLY','database':r['database'],'entries':observed,'before':before,'after':after,'actual_source_sha256':hashlib.sha256((repo/'services/aos-api/aos_api/aip_eval_runner.py').read_bytes()).hexdigest(),'limitations':['No executable Model authority or Model quality result','New trusted application/joint/Intent Owner and typed Runner interface required; never delete original rejection unconditionally']}
(base/'original-model-runner-gate.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'entries':2,'callbacks':0,'writes':0}))
