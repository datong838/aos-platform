"""Read-only original tokenizer-origin audit; no Model registration or transport."""
import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from pydantic import ValidationError

B = Path(__file__).resolve().parent
R = B.parents[1]
sys.path.insert(0, str(R / 'services/aos-api'))
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_runtime_contracts import RegisteredModelRevision
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import CreateEvalContractRequest
from aos_api.tenant_scope import TenantScope

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

spec = importlib.util.spec_from_file_location('mc', R/'scripts/memory/memoryctl.py')
mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)
authority = mc.load_authority()
assert authority['project_revision'] == 'AOS-001656'
leases = mc.load_leases(mc.DEFAULT_PATHS)['leases']
lease = next(x for x in leases if x['task_id'] == B.name)
assert lease['status'] == 'ACTIVE' and lease['owner'] == 'codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
assert datetime.now(timezone.utc) < datetime.fromisoformat(lease['lease_expires_at'])
assert not [x for x in leases if x['status'] == 'ACTIVE' and x['owner'] != lease['owner']]
assert 'aos-platform/.evidence/'+B.name in lease['scope']
baseline = '730f5620eb8783de31057d709ef5f6d57da04cf0'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip() == baseline
files = ['services/aos-api/aos_api/aip_model_runtime_contracts.py',
         'services/aos-api/aos_api/aip_model_eval_execution_owner.py',
         'services/aos-api/aos_api/aip_exact_provider_invoker.py']
hashes = {p:digest(R/p) for p in files}
original = B/'model-target-wire-green-1655-r1/model-target-wire-green-1655-r1-whole-rollback-input.json'
original_hash = digest(original)
proof = json.loads(original.read_text())
lab = json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
container = json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['name']],text=True))[0]
assert container['Id'] == lab['container_id'] and container['RestartCount'] == 0
scope = TenantScope('org-org','dev-project')
reports=[]
fields = {'tokenizerRef':{'assetType':'TokenizerRevision','assetId':'undeclared','revision':1,'contentHash':'0'*64},
          'tokenizerArtifactHash':'0'*64, 'messageEnvelopeRef':'undeclared', 'inputTokenCount':1}
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname='aos_test_9f7e075e13ca_ti4_test',
                     passfile=lab['passfile'],options='-c default_transaction_read_only=on',row_factory=dict_row) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    cluster=c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']
    assert cluster=='7694680278363095064'
    caller=c.execute('SELECT pg_xact_status(%s::xid8) AS state',(proof['caller']['xid'],)).fetchone()['state']
    assert caller=='aborted'
    counts={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in (
        'aip_agent_run','aip_model_capacity_reservation','aip_model_eval_budget_reservation',
        'aos_model_eval_execution_private.case_result')}
    assert all(v==0 for v in counts.values())
    for app in proof['applications']:
        row=c.execute('SELECT request_json,request_hash FROM aip_model_eval_request WHERE org_id=%s AND project_id=%s AND request_id=%s',(*scope.key,app['request_id'])).fetchone()
        assert canonical_hash(row['request_json'])==row['request_hash']==app['request_hash']
        req=ModelEvalRequestCreate.model_validate(row['request_json'])
        mr=c.execute('SELECT payload,content_hash FROM aip_registered_model_revision WHERE org_id=%s AND project_id=%s AND registered_model_id=%s AND revision=%s',(*scope.key,req.source_ref.asset_id,req.source_ref.revision)).fetchone()
        model=RegisteredModelRevision.model_validate(mr['payload'])
        assert canonical_hash({k:v for k,v in model.model_dump(mode='json',by_alias=True).items() if k not in AipModelRuntimeStore._META_FIELDS})==mr['content_hash']==req.source_ref.content_hash
        contract=AipProductionContractStore().get_eval_contract(scope,req.eval_contract_ref.asset_id,req.eval_contract_ref.revision,conn=c)
        body=CreateEvalContractRequest(**{k:getattr(contract,k) for k in CreateEvalContractRequest.model_fields})
        assert canonical_hash(body.model_dump(mode='json',by_alias=True))==contract.content_hash==req.eval_contract_ref.content_hash
        assert contract.gate_policy['modelTargetWireFormat']['schemaVersion']=='aos.model-eval.chat-json-target/v1'
        assert not any('token' in k.lower() for k in contract.gate_policy)
        faults=[]
        for key,value in fields.items():
            candidate={**mr['payload'],key:value}
            try:
                RegisteredModelRevision.model_validate(candidate)
            except ValidationError as exc:
                errors=[{'loc':list(e['loc']),'type':e['type']} for e in exc.errors()]
                assert errors==[{'loc':[key],'type':'extra_forbidden'}],errors
                faults.append({'field':key,'errors':errors,'registered':False})
            else:
                raise AssertionError('undeclared token origin accepted: '+key)
        reports.append({'request_id':app['request_id'],'request_hash':row['request_hash'],
                        'model_hash':model.content_hash,'provider_model_id':model.provider_model_id,
                        'provider_ref':model.provider.model_dump(mode='json',by_alias=True),
                        'contract_hash':contract.content_hash,'context_window':model.context_window,
                        'token_origin_fields_rejected':faults,'token_policy_present':False})
    assert c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']=='on'
    c.rollback()
tree=ast.parse((R/files[2]).read_bytes())
send=[n.lineno for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
      and n.func.attr=='post' and ast.unparse(n.func.value)=='self._transport']
usage=[n.lineno for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
       and n.func.attr=='get' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='prompt_tokens']
assert len(send)==len(usage)==1 and send[0]<usage[0]
assert digest(original)==original_hash and hashes=={p:digest(R/p) for p in files}
out={'result':'TOKEN_AUTHORITY_ORIGIN_MISSING','observed_at':datetime.now(timezone.utc).isoformat(),
     'head':baseline,'authority_revision':authority['project_revision'],'task':B.name,'owner':lease['owner'],
     'database':'aos_test_9f7e075e13ca_ti4_test','cluster':cluster,'caller_status':caller,
     'business_counts':counts,'original_evidence_sha256':original_hash,'file_hashes':hashes,
     'requests':reports,'transport_send_line':send[0],'post_response_usage_line':usage[0],
     'counterexamples':sum(len(r['token_origin_fields_rejected']) for r in reports),
     'actual_input_token_count':None,'execution_allowed':False,'full_task_delivered':False,
     'next_required':'Immutable approved tokenizer artifact/version/hash and exact message overhead/model compatibility, verified server-side before joint admission; no char-count fallback.'}
with (B/'model-token-origin-audit-1656.json').open('x') as f:
    json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({'result':out['result'],'requests':len(reports),'counterexamples':out['counterexamples'],
                  'caller':caller,'business_counts_zero':True,'execution_allowed':False}))
