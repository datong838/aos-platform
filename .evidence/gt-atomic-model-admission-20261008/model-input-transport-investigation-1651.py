"""Read original historical authorities and encode requests without dispatch."""
import ast
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

base = Path(__file__).resolve().parent
repo = base.parents[1]
sys.path.insert(0, str(repo / 'services/aos-api'))
import httpx
import psycopg
from psycopg.rows import dict_row
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_exact_provider_invoker import ExactProviderInvoker
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_runtime_contracts import RegisteredModelRevision
from aos_api.aip_model_governance_policy_contracts import QuotaPolicyRevision

assert subprocess.check_output(['docker', '--context', 'colima-aos-a0v-test-only', 'inspect',
    'aos-capacity-publication-scram-20261006', '--format', '{{.Id}}'], text=True).strip() == '4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
passfile = Path('/tmp/aos-capacity-publication-scram-20261006.pgpass')
assert passfile.stat().st_mode & 0o077 == 0
prior = json.loads((base / 'original-source-whole-plan-cumulative-r2-result.json').read_text())
assert prior['database'] == 'aos_test_b6e266c45981_ti4_test' and prior['pytest_exit'] == 0
plan = json.loads((base / 'original-source-whole-plan-cumulative-r2-source-whole-source-plan-input.json').read_text())['plan']
paths = ['aip_exact_provider_invoker.py', 'aip_llm_adapter.py', 'aip_model_eval_execution_owner.py',
         'aip_eval_runner.py', 'aip_physical_capacity_occupation_authority.py']
bindings = {}
for name in paths:
    p = repo / 'services/aos-api/aos_api' / name
    raw = p.read_bytes()
    bindings[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'tree': ast.parse(raw)}
adapter_calls = [n for n in ast.walk(bindings['aip_llm_adapter.py']['tree'])
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == '_provider_invoker']
assert len(adapter_calls) == 1
assert 'max_output_tokens' not in [k.arg for k in adapter_calls[0].keywords]
owner_tokens = sorted({n.id for n in ast.walk(bindings['aip_model_eval_execution_owner.py']['tree'])
    if isinstance(n, ast.Name) and ('token' in n.id.lower() or 'transport' in n.id.lower())})
records = []
tables = ['aip_model_eval_budget_reservation', 'aos_physical_capacity_occupation_private.prepared_execution_intent',
          'aos_model_eval_execution_private.case_result']
with psycopg.connect(dbname=prior['database'], user='aos_app', host='127.0.0.1', port=5434,
                     passfile=str(passfile), options='-c default_transaction_read_only=on', row_factory=dict_row) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == '7693564235776004128'
    assert c.execute('SELECT version_num FROM alembic_version').fetchone()['version_num'] == 'a0v_158'
    before = {t: c.execute('SELECT count(*) AS n FROM ' + t).fetchone()['n'] for t in tables}
    # Resolve exactly the original approved parent records. Their old approval is
    # historical evidence only and never reused as current execution authority.
    for parent in plan['parentBudgetLimits']:
        row = c.execute('SELECT request_json,request_hash FROM aip_model_eval_request WHERE org_id=%s AND project_id=%s AND request_id=%s',
            ('org-org', 'dev-project', parent['requestId'])).fetchone()
        request = ModelEvalRequestCreate.model_validate(row['request_json'])
        assert canonical_hash(row['request_json']) == row['request_hash'] == parent['requestHash']
        mr = c.execute('SELECT payload,content_hash FROM aip_registered_model_revision WHERE org_id=%s AND project_id=%s AND registered_model_id=%s AND revision=%s',
            ('org-org', 'dev-project', request.source_ref.asset_id, request.source_ref.revision)).fetchone()
        qr = c.execute("SELECT payload,content_hash FROM aip_model_governance_policy_revision WHERE org_id=%s AND project_id=%s AND policy_id=%s AND revision=%s AND policy_kind='quota'",
            ('org-org', 'dev-project', request.quota_policy_ref.asset_id, request.quota_policy_ref.revision)).fetchone()
        model = RegisteredModelRevision.model_validate(mr['payload'])
        quota = QuotaPolicyRevision.model_validate(qr['payload'])
        for obj, rec, ref, exclusions in [(model,mr,request.source_ref,{'tenant','contentHash','createdBy','createdAt','revision'}),
                                          (quota,qr,request.quota_policy_ref,{'tenant','contentHash','createdBy','createdAt'})]:
            assert obj.content_hash == rec['content_hash'] == ref.content_hash
            assert canonical_hash({k:v for k,v in obj.model_dump(mode='json',by_alias=True).items() if k not in exclusions}) == ref.content_hash
        # Synthetic Unicode sample is deliberate: no historical prompt is replayed.
        prompt = '边界调查🙂\n模型输入'
        payload = ExactProviderInvoker._request_payload('text', model, prompt, max_output_tokens=quota.max_output_tokens)
        encoded = httpx.Request('POST', 'https://invalid.example/v1/chat/completions', json=payload).content
        assert json.loads(encoded) == payload and payload['max_tokens'] == quota.max_output_tokens
        without_limit = ExactProviderInvoker._request_payload('text', model, prompt)
        assert 'max_tokens' not in without_limit
        artifact_hash = canonical_hash(prompt)
        wire_hash = hashlib.sha256(encoded).hexdigest()
        assert artifact_hash != wire_hash
        records.append({'request_id':parent['requestId'], 'request_hash':row['request_hash'],
            'model_ref':request.source_ref.model_dump(mode='json',by_alias=True),
            'quota_ref':request.quota_policy_ref.model_dump(mode='json',by_alias=True),
            'context_window':model.context_window, 'max_input_tokens':quota.max_input_tokens,
            'max_output_tokens':quota.max_output_tokens, 'conservative_occupation_tokens':quota.max_input_tokens+quota.max_output_tokens,
            'wire_bytes_length':len(encoded), 'wire_sha256':wire_hash, 'artifact_value_hash':artifact_hash,
            'output_limit_maps_to':'max_tokens', 'omitted_output_limit_is_unbounded_by_payload':True,
            'tokenizer_used':False, 'sample_is_synthetic':True})
    after = {t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in tables}
    assert before == after
    readonly = c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']
    assert readonly == 'on'
    c.rollback()
out = {'observed_at':datetime.now(timezone.utc).isoformat(), 'authority':'AOS-001651',
       'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
       'source_hashes':{k:v['sha256'] for k,v in bindings.items()}, 'database':prior['database'],
       'read_only':readonly, 'before_counts':before, 'after_counts':after, 'original_parents':records,
       'adapter_passes_output_limit':False, 'owner_token_transport_identifiers':owner_tokens,
       'provider_calls':0, 'execution_allowed':False,
       'result':'INPUT_ENVELOPE_AND_OWNER_TRANSPORT_BINDING_NOT_IMPLEMENTED',
       'limitations':['Historical approvals are expired and not execution authority.',
           'Pure HTTPX encoding is actual current encoder output but no request was sent.',
           'Byte length is not token count; no tokenizer or context admission is certified.',
           'Owner identifier scan is routing evidence, not proof of all transitive behavior.']}
with (base/'model-input-transport-investigation-1651.json').open('x') as f:
    json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({'result':out['result'],'parents':len(records),'read_only':readonly,'counts_unchanged':before==after,'provider_calls':0}))
