"""Read retained RED/GREEN effects independently; no writes or replay."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[1]
sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry,compute_eval_suite_hash
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
container=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['name']],text=True))[0]
assert container['Id']==lab['container_id'] and container['RestartCount']==0
names=['model-original-input-bytes-red-1652-r1','model-original-input-bytes-red-1652-r2',
       'model-original-input-bytes-green-1652-r1','model-original-input-bytes-red-1652-r3',
       'model-original-input-bytes-green-1652-r2']
reports=[]
for name in names:
    result=json.loads((B/(name+'-result.json')).read_text());attempt=json.loads((B/(name+'-attempt.json')).read_text())
    expected=0 if '-green-' in name else 1
    assert result['pytest_exit']==expected and result['old_evidence_unchanged']
    assert result['database'].startswith('aos_test_') and container['State']['StartedAt']==attempt['started_at']
    assert all(x['phase']=='call' for x in result['results'])
    proof=json.loads((B/name/(name+'-whole-rollback-input.json')).read_text())
    with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=result['database'],passfile=lab['passfile'],
                         options='-c default_transaction_read_only=on',row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
        assert c.execute('SELECT pg_xact_status(%s::xid8) AS state',(proof['caller']['xid'],)).fetchone()['state']=='aborted'
        for app in proof['applications']:
            row=c.execute('SELECT request_json,request_hash FROM aip_model_eval_request WHERE org_id=%s AND project_id=%s AND request_id=%s',('org-org','dev-project',app['request_id'])).fetchone()
            assert canonical_hash(row['request_json'])==row['request_hash']==app['request_hash']
        counts={table:c.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] for table in (
            'aip_agent_run','aip_model_capacity_reservation','aip_model_eval_budget_reservation','aos_model_eval_execution_private.case_result')}
        assert all(v==0 for v in counts.values())
        if '-green-' in name:
            suite_proof=json.loads((B/name/(name+'-whole-rollback-suite-input.json')).read_text());ref=suite_proof['manifest']['request']['suiteRef']
            row=c.execute('SELECT * FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s',('org-org','dev-project',ref['assetId'],ref['revision'])).fetchone()
            suite=AipEvalPackRegistry._suite_from_row(row)
            assert compute_eval_suite_hash(suite)==suite.content_hash==ref['contentHash']
            inputs=json.loads((B/name/(name+'-whole-rollback-original-input-bytes.json')).read_text())
            assert [(x['caseId'],x['sha256']) for x in inputs['case_hashes']]==[(x.case_id,x.input_artifact.content_hash) for x in suite.cases]
            assert inputs['rejected_sets']==(14 if name.endswith('r2') else 12)
            assert inputs['execution_allowed'] is False and inputs['tokenizer_used'] is False
        readonly=c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'];assert readonly=='on';c.rollback()
    for path,digest in result['old_evidence_hashes_before'].items():assert hashlib.sha256((R/path).read_bytes()).hexdigest()==digest
    reports.append({'attempt':name,'database':result['database'],'pytest_exit':expected,'caller_xid':proof['caller']['xid'],
        'caller_state':'aborted','approved_original_applications':len(proof['applications']),'read_only':readonly,'counts':counts})
owner=R/'services/aos-api/aos_api/aip_model_eval_execution_owner.py'
tree=ast.parse(owner.read_bytes());method=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name=='validate_original_model_plan_input_bytes')
calls=[x.func.attr for x in ast.walk(method) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute)]
assert not set(calls)&{'execute','commit','rollback','connect','post','dispatch','admit'}
library=subprocess.check_output(['docker','--context',lab['context'],'exec',lab['name'],'sha256sum','/usr/local/lib/postgresql/aos_ed25519.so'],text=True).split()[0]
assert library=='6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'
out={'result':'ORIGINAL_MODEL_COMPLETE_INPUT_BYTES_NECESSARY_GATE_VERIFIED','reports':reports,
    'owner_sha256':hashlib.sha256(owner.read_bytes()).hexdigest(),'method_has_no_direct_sql_or_effect':True,
    'old_evidence_unchanged':True,'source_verifier_unchanged':True,'execution_allowed':False,'full_model_admission':False,
    'limitations':'Content governance fixture inputs only; no trusted Model formatting/producer/tokenizer/transport or Source completion proof.'}
with (B/'model-original-input-bytes-independent-1652.json').open('x') as f:json.dump(out,f,indent=2)
print(json.dumps({'result':out['result'],'retained_databases':len(reports),'all_callers_aborted':True,'all_business_counts_zero':True}))
