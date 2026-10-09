"""Pure original encoder audit; no native query or transport invocation."""
import ast
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

base = Path(__file__).resolve().parent
repo = base.parents[1]
sys.path.insert(0, str(repo/'services/aos-api'))
import httpx
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_exact_provider_invoker import ExactProviderInvoker
from aos_api.aip_model_governance_policy_contracts import QuotaPolicyRevision

source = base/'whole-plan-allocation-readonly-r2.json'
historical = json.loads(source.read_text())
assert historical['read_only']=='on' and historical['before_counts']==historical['after_counts']
bindings={}
for name in ['aip_exact_provider_invoker.py','aip_llm_adapter.py','aip_model_eval_execution_owner.py',
             'aip_eval_runner.py','aip_physical_capacity_occupation_authority.py']:
    p=repo/'services/aos-api/aos_api'/name
    raw=p.read_bytes()
    bindings[name]={'sha256':hashlib.sha256(raw).hexdigest(),'tree':ast.parse(raw)}
adapter_calls=[n for n in ast.walk(bindings['aip_llm_adapter.py']['tree'])
    if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='_provider_invoker']
assert len(adapter_calls)==1 and not adapter_calls[0].keywords
invoker_tree=bindings['aip_exact_provider_invoker.py']['tree']
assert not [n for n in ast.walk(invoker_tree) if isinstance(n,ast.Attribute) and n.attr in ('context_window','max_input_tokens')]
records=[]
for parent in historical['parents']:
    quota=QuotaPolicyRevision.model_validate(parent['quota'])
    assert canonical_hash({k:v for k,v in quota.model_dump(mode='json',by_alias=True).items()
        if k not in {'tenant','contentHash','createdBy','createdAt'}})==quota.content_hash
    # This is a historical identifier, not a current RegisteredModel authority.
    model=SimpleNamespace(provider_model_id=parent['price']['developmentCostAuthorization']['providerModelId'])
    samples=[]
    for prompt in ['ASCII input','中文🙂\n输入']:
        payload=ExactProviderInvoker._request_payload('text',model,prompt,max_output_tokens=quota.max_output_tokens)
        body=httpx.Request('POST','https://invalid.example/v1/chat/completions',json=payload).content
        assert json.loads(body)==payload and payload['max_tokens']==quota.max_output_tokens
        samples.append({'utf8_request_length':len(body),'request_sha256':hashlib.sha256(body).hexdigest(),
            'canonical_artifact_hash':canonical_hash(prompt),'same_hash':canonical_hash(prompt)==hashlib.sha256(body).hexdigest()})
        assert not samples[-1]['same_hash']
    unlimited=ExactProviderInvoker._request_payload('text',model,'synthetic boundary')
    assert 'max_tokens' not in unlimited
    over=ExactProviderInvoker._request_payload('text',model,'synthetic boundary',max_output_tokens=quota.max_output_tokens+1)
    assert over['max_tokens']==quota.max_output_tokens+1
    records.append({'historical_request_id':parent['request_id'],'quota_hash_verified':quota.content_hash,
        'historical_model_context':parent['model_context_window'],'quota_input':quota.max_input_tokens,
        'quota_output':quota.max_output_tokens,'conservative_occupation':parent['upper_bound_tokens'],
        'samples':samples,'encoder_accepts_output_above_quota':True,'encoder_without_output_has_no_max_tokens':True})
out={'observed_at':datetime.now(timezone.utc).isoformat(),'authority':'AOS-001651',
    'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    'historical_snapshot_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'source_hashes':{k:v['sha256'] for k,v in bindings.items()},'parents':records,
    'adapter_passes_output_limit':False,'invoker_direct_input_context_attributes':False,
    'native_database_queries':0,'provider_calls':0,'tokenizer_calls':0,'execution_allowed':False,
    'result':'FULL_MODEL_INPUT_TRANSPORT_BINDING_REMAINS_RED',
    'r1_failure':{'stage':'private-passfile-stat-before-connect','code':'FileNotFoundError',
        'path':'/tmp/aos-capacity-publication-scram-20261006.pgpass','native_queries':0,'replayed':False},
    'limitations':['Pure current HTTPX encoder only, not a Provider request or tokenizer.',
        'Historical model identifier is not a current RegisteredModel authority.',
        'Encoder accepts excess output; this alone does not prove complete invoker dispatch.',
        'Current quota/model head and approvals were not queried; no new authority is granted.']}
with (base/'model-input-transport-investigation-1651-r2.json').open('x') as f:
    json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({'result':out['result'],'parents':len(records),'encoding_samples':sum(len(x['samples']) for x in records),
    'provider_calls':0,'native_database_queries':0}))
