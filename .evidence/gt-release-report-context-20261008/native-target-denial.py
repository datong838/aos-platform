"""Fresh native Model release denial, no execution or business authority."""
import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

BASE=Path(__file__).resolve().parent
REPO=BASE.parents[1]
TEMPLATE='aos_test_f2ef54f0da1d_ti4_test'
CLUSTER='7693564235776004128'
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):
    os.environ.pop(key,None)
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
assert subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect',
    'aos-capacity-publication-scram-20261006','--format','{{.Id}}'],text=True).strip()=='4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
def connect(name,**kw):
    return psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=name,
        passfile=str(passfile),row_factory=dict_row,**kw)

import sys
from datetime import UTC,datetime
sys.path.insert(0,str(REPO/'services/aos-api'))
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,AssetType,EvalRunAuthorityRecord,EvalRunStatus,
    EvalReportRevision,EvalCaseResultEvidence,EvalContractRevisionRef,
)
from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
from aos_api.aip_eval_runner import AipEvalRunner,compute_eval_report_hash
from aos_api.aip_release_publication_service import AipReleasePublicationService
from aos_api.aip_release_publication_models import DeriveReleaseGateRequest
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope,apply_transaction_scope

application=json.loads((REPO/'.evidence/gt-shared-physical-atomic-contract-20261007/legal-eval-application-result-r4.json').read_text())
template=application['database']
assert template.startswith('aos_test_')
tables=('aip_eval_run','aip_eval_run_event','aip_eval_report_revision','aip_release_gate_decision',
    'aip_publication_event','aip_eval_execution_receipt','aip_eval_case_execution_proof',
    'aip_model_eval_budget_reservation','aip_budget_reservation','aip_agent_run','aip_model_capacity_reservation')
def snapshot(name):
    with connect(name) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==CLUSTER
        heads=c.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()
        assert heads==[{'version_num':'a0v_157'}]
        return {'heads':heads,'counts':{t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in tables}}
before=snapshot(template)
database='aos_test_model_report_gate_'+uuid4().hex[:12]
with connect('aos_meta',autocommit=True) as c:
    c.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(database),sql.Identifier(template)))
assert snapshot(database)==before
print('Retained negative test database',database,flush=True)
scope=TenantScope('org-org','dev-project')
actor='isolated-negative-report-writer'
nonce=uuid4().hex
with connect(database) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE')
    c.execute('SET LOCAL ROLE aos_runtime')
    apply_transaction_scope(c,scope)
    assert c.pgconn.used_password
    identity=c.execute("SELECT session_user AS login,current_user AS role,pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid").fetchone()
    assert identity['login']=='aos_app' and identity['role']=='aos_runtime'
    bound=TransactionBoundConnectFactory(HostTransaction(c),scope)
    suite=AipEvalPackRegistry(bound).get_suite_revision(scope,application['suite_id'],1)
    assert suite.target.asset_type is AssetType.REGISTERED_MODEL and suite.target.asset_id==application['model_id']
    request=c.execute('SELECT request_json FROM aip_model_eval_request WHERE request_id=%s',(application['request_id'],)).fetchone()['request_json']
    ref=request['evalContractRef']
    contract=EvalContractRevisionRef(resource_id=ref['assetId'],revision=ref['revision'],content_hash=ref['contentHash'])
    tenant=TenantContext(org_id=scope.org_id,project_id=scope.project_id)
    suite_ref=AssetRevisionRef(asset_type=AssetType.EVAL_SUITE,asset_id=suite.suite_id,revision=str(suite.revision),content_hash=suite.content_hash)
    run_id='negative-model-eval-'+nonce
    run=EvalRunAuthorityRecord(tenant=tenant,run_id=run_id,suite_ref=suite_ref,eval_contract_ref=contract,
        target=suite.target,dataset=suite.dataset,judge=suite.judge,status=EvalRunStatus.QUEUED,
        idempotency_key=run_id,created_by=actor,created_at=datetime.now(UTC),version=1)
    authority=AipEvalAuthorityStore(bound)
    authority.create_eval_run(scope,run,AipEvalRunner._event(tenant,run_id,1,None,EvalRunStatus.QUEUED,actor))
    authority.transition_eval_run(scope,AipEvalRunner._event(tenant,run_id,2,EvalRunStatus.QUEUED,EvalRunStatus.RUNNING,actor),expected_version=1)
    # Explicit forgery for a negative boundary: no target, judge, Model or Provider execution.
    report=EvalReportRevision(tenant=tenant,report_id='negative-model-report-'+nonce,revision=1,content_hash='0'*64,
        run_id=run_id,suite_ref=suite_ref,eval_contract_ref=contract,target=suite.target,dataset=suite.dataset,judge=suite.judge,
        results=[EvalCaseResultEvidence(case_id=case.case_id,passed=True,actual_hash='1'*64,
            expected_hash='2'*64 if case.expected_artifact else None,detail_code='FORGED_NEGATIVE_BOUNDARY_ONLY',duration_ms=0) for case in suite.cases],
        passed=len(suite.cases),failed=0,total=len(suite.cases),pass_rate=1.0,gate_passed=True,created_at=datetime.now(UTC))
    report=report.model_copy(update={'content_hash':compute_eval_report_hash(report)})
    AipEvalRunner(bound)._append_report(scope,report)
    authority.transition_eval_run(scope,AipEvalRunner._event(tenant,run_id,3,EvalRunStatus.RUNNING,EvalRunStatus.SUCCEEDED,actor),expected_version=2)
    assert c.execute('SELECT count(*) AS n FROM aip_eval_case_execution_proof WHERE run_id=%s',(run_id,)).fetchone()['n']==0
    assert c.execute('SELECT count(*) AS n FROM aip_eval_execution_receipt WHERE run_id=%s',(run_id,)).fetchone()['n']==0
    from aos_api.aip_release_publication_service import AipReleaseGateRejected
    try:
        AipReleasePublicationService(bound).derive_gate(scope,actor=actor,request=DeriveReleaseGateRequest(
            report_id=report.report_id,report_revision=1,report_hash=report.content_hash,idempotency_key='negative-gate-'+nonce))
    except AipReleaseGateRejected as exc:
        assert 'signed execution' in str(exc)
        rejection=str(exc)
    else:
        raise AssertionError('Unsupported Model report gained release gate')
    assert c.execute('SELECT count(*) AS n FROM aip_release_gate_decision').fetchone()['n']==before['counts']['aip_release_gate_decision']
    c.rollback()
after=snapshot(database)
assert after==before and snapshot(template)==before
result={'status':'ORIGINAL_MODEL_RELEASE_EXPLICIT_DENIAL_ROLLED_BACK',
    'database':database,'template':template,'baseline':before,'after_rollback':after,
    'template_unchanged':True,'rejection':rejection,'actual_commit_calls':0,
    'provider_calls':0,'gate_created':False,'model_quality_measured':False,
    'trusted_test_admin_negative_only':True}
(BASE/'native-target-denial-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2),flush=True)
