"""Reconcile expected Artifact/Suite/Contract/approval facts in retained PG."""
import hashlib
import json
import sys
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent
R=B.parents[1]
sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_action_store import canonical_hash
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import CreateEvalContractRequest
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.tenant_scope import TenantScope
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
scope=TenantScope('org-org','dev-project')
raw='  原Judge期望🙂\n保留空白  '.encode('utf-8')
reports=[]
for phase, suffix in (('red','red-1659-r1'),('green','green-1659-r1'),('adjacent-failed','adjacent-1659-r1'),('adjacent','adjacent-1659-r2')):
    name='judge-expected-bytes-'+suffix
    result=json.loads((B/(name+'-result.json')).read_text())
    attempt=json.loads((B/(name+'-attempt.json')).read_text())
    assert result['pytest_exit']==(1 if phase in ('red','adjacent-failed') else 0) and result['old_evidence_unchanged']
    for path,digest in attempt['file_hashes'].items():
        actual=hashlib.sha256((R/path).read_bytes()).hexdigest()
        if phase=='red' and path.endswith('/aip_model_eval_execution_owner.py'):
            actual=hashlib.sha256((B/'judge-expected-owner-before-1659.py').read_bytes()).hexdigest()
        assert actual==digest
    for path,digest in result['old_evidence_hashes_before'].items():
        assert hashlib.sha256((R/path).read_bytes()).hexdigest()==digest
    root=B/name
    schemas=[]
    with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=result['database'],passfile=lab['passfile'],
                         options='-c default_transaction_read_only=on',row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
        rows=c.execute("SELECT request_id,request_json,request_hash FROM aip_model_eval_request WHERE org_id=%s AND project_id=%s ORDER BY request_id",scope.key).fetchall()
        assert len(rows)==2
        for row in rows:
            assert canonical_hash(row['request_json'])==row['request_hash']
            req=ModelEvalRequestCreate.model_validate(row['request_json'])
            suite_row=c.execute('SELECT * FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s',
                (*scope.key,req.suite_ref.asset_id,req.suite_ref.revision)).fetchone()
            suite=AipEvalPackRegistry._suite_from_row(suite_row)
            assert compute_eval_suite_hash(suite)==suite.content_hash==req.suite_ref.content_hash
            contract=AipProductionContractStore().get_eval_contract(scope,req.eval_contract_ref.asset_id,req.eval_contract_ref.revision,conn=c)
            body=CreateEvalContractRequest(**{k:getattr(contract,k) for k in CreateEvalContractRequest.model_fields})
            assert canonical_hash(body.model_dump(mode='json',by_alias=True))==contract.content_hash==req.eval_contract_ref.content_hash
            cases=[]
            for case in suite.cases:
                ref=case.expected_artifact
                if phase=='adjacent':
                    assert ref is None
                elif phase=='adjacent-failed':
                    assert ref is not None and ref.content_hash!=hashlib.sha256(raw).hexdigest()
                else:
                    assert ref is not None and ref.content_hash==hashlib.sha256(raw).hexdigest()
                    artifact=c.execute('SELECT artifact_type,content_hash,content_ref FROM aip_artifact WHERE org_id=%s AND project_id=%s AND artifact_id=%s',(*scope.key,ref.artifact_id)).fetchone()
                    assert artifact['artifact_type']=='eval_expected' and artifact['content_hash']==ref.content_hash and artifact['content_ref']=='test-only://'+ref.artifact_id
                cases.append({'case_id':case.case_id,'expected_hash':None if ref is None else ref.content_hash})
            schemas.append({'request_id':row['request_id'],'request_hash':row['request_hash'],'suite_hash':suite.content_hash,'contract_hash':contract.content_hash,'cases':cases})
        states={}
        if phase not in ('red','adjacent-failed'):
            proof=json.loads((root/(name+'-whole-plan-proof.json')).read_text())
            output=json.loads((root/(name+'-expected-bytes.json')).read_text())
            assert len(output['cases'])==2 and len(output['faults_rejected'])==10
            expected_hash=None if phase=='adjacent' else hashlib.sha256(raw).hexdigest()
            assert all(x['sha256']==expected_hash for x in output['cases'])
            assert output['caller']==proof['caller']
            for label,xid in [('whole',proof['caller']['xid']),('deadline',proof['reader_database_clock_deadline']['caller']['xid'])]:
                state=c.execute('SELECT pg_xact_status(%s::xid8) AS state',(xid,)).fetchone()['state']
                assert state=='aborted';states[label]=state
            for table,key in [('aip_model_eval_budget_reservation','target_parent_id'),('aip_model_judge_budget_reservation','judge_parent_id')]:
                assert c.execute('SELECT count(*) AS n FROM '+table+' WHERE reservation_id=%s',(proof[key],)).fetchone()['n']==0
        counts={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in ('aip_agent_run','aip_model_capacity_reservation','aos_model_eval_execution_private.case_result')}
        assert all(v==0 for v in counts.values())
        holds={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in ('aip_model_eval_budget_reservation','aip_model_judge_budget_reservation')}
        assert c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']=='on'
        c.rollback()
    reports.append({'phase':phase,'database':result['database'],'originals':schemas,'caller_states':states,
                    'execution_counts':counts,'separate_test_holds':holds,'read_only':True})
out={'result':'ORIGINAL_JUDGE_EXPECTED_BYTES_NECESSARY_GATE_VERIFIED','reports':reports,'old_evidence_unchanged':True,
     'execution_allowed':False,'actual_target_output_certified':False,'full_task_delivered':False,
     'limitations':'Test-owned expected artifact reference/bytes; no formal Artifact provenance, Target output, encoding/quality, tokens, actual-end, joint Intent or Provider identity.'}
with (B/'judge-expected-independent-1659.json').open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({'result':out['result'],'databases':len(reports),'execution_counts_zero':True,'execution_allowed':False}))
