"""Original frozen input origin audit: readonly DB and pure wire encoding only."""
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psycopg
from psycopg.rows import dict_row

B = Path(__file__).resolve().parent
R = B.parents[1]
sys.path.insert(0, str(R / 'services/aos-api'))
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
from aos_api.aip_eval_contracts import AssetRevisionRef
from aos_api.ecommerce_content_pre_review_pack import build_content_pre_review_eval_packs
from aos_api.aip_exact_provider_invoker import ExactProviderInvoker
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_runtime_contracts import RegisteredModelRevision
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_model_governance_policy_contracts import QuotaPolicyRevision
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.tenant_scope import TenantScope

spec = importlib.util.spec_from_file_location('mc', R / 'scripts/memory/memoryctl.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
assert m.load_authority()['project_revision'] == 'AOS-001653'
lease = next(x for x in m.load_leases(m.DEFAULT_PATHS)['leases']
             if x['task_id'] == 'gt-atomic-model-admission-20261008')
assert lease['owner'] == 'codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
assert lease['status'] == 'ACTIVE'
assert datetime.fromisoformat(lease['lease_expires_at']) > datetime.now(timezone.utc)
overlap = [x['task_id'] for x in m.load_leases(m.DEFAULT_PATHS)['leases']
           if x['task_id'] != lease['task_id'] and m.scopes_overlap(x['scope'], lease['scope'])]
assert not overlap, overlap
name = 'model-original-input-bytes-green-1652-r2'
prior = json.loads((B / (name + '-result.json')).read_text())
proof = json.loads((B / name / (name + '-whole-rollback-input.json')).read_text())
lab = json.loads((R / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
container = json.loads(subprocess.check_output(
    ['docker', '--context', lab['context'], 'inspect', lab['name']], text=True))[0]
assert container['Id'] == lab['container_id'] and container['RestartCount'] == 0
assert prior['pytest_exit'] == 0 and prior['database'] == 'aos_test_841069306b60_ti4_test'
tables = ('aip_agent_run', 'aip_model_capacity_reservation', 'aip_model_eval_budget_reservation',
          'aos_model_eval_execution_private.case_result')
scope = TenantScope('org-org', 'dev-project')
records = []
with psycopg.connect(host='127.0.0.1', port=5441, user='aos_app', dbname=prior['database'],
                     passfile=lab['passfile'], options='-c default_transaction_read_only=on',
                     row_factory=dict_row) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == '7694680278363095064'
    before = {t: c.execute('SELECT count(*) AS n FROM ' + t).fetchone()['n'] for t in tables}
    assert all(v == 0 for v in before.values())
    for app in proof['applications']:
        row = c.execute('SELECT request_json,request_hash FROM aip_model_eval_request WHERE org_id=%s AND project_id=%s AND request_id=%s', (*scope.key, app['request_id'])).fetchone()
        assert canonical_hash(row['request_json']) == row['request_hash'] == app['request_hash']
        req = ModelEvalRequestCreate.model_validate(row['request_json'])
        contract = AipProductionContractStore().get_eval_contract(scope, req.eval_contract_ref.asset_id, req.eval_contract_ref.revision, conn=c)
        assert contract.content_hash == req.eval_contract_ref.content_hash
        assert contract.lifecycle.value == 'frozen'
        assert contract.gate_policy == {'subjectKind': 'model_eval', 'executionAllowed': False}
        suite_row = c.execute('SELECT * FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s', (*scope.key, req.suite_ref.asset_id, req.suite_ref.revision)).fetchone()
        suite = AipEvalPackRegistry._suite_from_row(suite_row)
        assert compute_eval_suite_hash(suite) == suite.content_hash == req.suite_ref.content_hash
        graph = c.execute("SELECT target_ref FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND dataset_ref=%s::jsonb AND target_ref->>'assetType'='logic_graph' LIMIT 1", (*scope.key, json.dumps(suite_row['dataset_ref']))).fetchone()
        _, pack = build_content_pre_review_eval_packs(AssetRevisionRef.model_validate(graph['target_ref']))
        # Reuse actual original pack; never fabricate a Model input producer.
        case = suite.cases[0]
        value = pack.artifacts[(case.input_artifact.artifact_id, case.input_artifact.revision)]
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        assert hashlib.sha256(raw).hexdigest() == suite.cases[0].input_artifact.content_hash
        mr = c.execute('SELECT payload,content_hash FROM aip_registered_model_revision WHERE org_id=%s AND project_id=%s AND registered_model_id=%s AND revision=%s', (*scope.key, req.source_ref.asset_id, req.source_ref.revision)).fetchone()
        qr = c.execute("SELECT payload,content_hash FROM aip_model_governance_policy_revision WHERE org_id=%s AND project_id=%s AND policy_id=%s AND revision=%s AND policy_kind='quota'", (*scope.key, req.quota_policy_ref.asset_id, req.quota_policy_ref.revision)).fetchone()
        model = RegisteredModelRevision.model_validate(mr['payload'])
        quota = QuotaPolicyRevision.model_validate(qr['payload'])
        for obj, rec, ref, excluded in (
            (model, mr, req.source_ref, AipModelRuntimeStore._META_FIELDS),
            (quota, qr, req.quota_policy_ref, {'tenant', 'contentHash', 'createdBy', 'createdAt'})):
            assert obj.content_hash == rec['content_hash'] == ref.content_hash
            body = obj.model_dump(mode='json', by_alias=True)
            assert canonical_hash({k: v for k, v in body.items() if k not in excluded}) == ref.content_hash
        variants = []
        for label, prompt in (('unapproved-whole-json', raw.decode()), ('unapproved-case-id', json.loads(raw)['caseId'])):
            payload = ExactProviderInvoker._request_payload('text', model, prompt, max_output_tokens=quota.max_output_tokens)
            wire = httpx.Request('POST', 'https://no-dispatch.invalid', json=payload).content
            variants.append({'conversion': label, 'wire_sha256': hashlib.sha256(wire).hexdigest(), 'wire_bytes': len(wire), 'max_tokens': payload['max_tokens'], 'approved': False})
        assert variants[0]['wire_sha256'] != variants[1]['wire_sha256']
        records.append({'request_id': app['request_id'], 'request_hash': row['request_hash'],
                        'contract_hash': contract.content_hash, 'artifact_schema_ref': contract.artifact_schema_ref.model_dump(mode='json', by_alias=True),
                        'gate_policy': contract.gate_policy, 'input_sha256': hashlib.sha256(raw).hexdigest(),
                        'variants': variants, 'model_context': model.context_window,
                        'quota_output': quota.max_output_tokens})
    after = {t: c.execute('SELECT count(*) AS n FROM ' + t).fetchone()['n'] for t in tables}
    assert before == after
    assert c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] == 'on'
    c.rollback()
out = {'result': 'RED_ORIGINAL_MODEL_INPUT_PRODUCER_NOT_FROZEN', 'authority': 'AOS-001653',
       'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=R, text=True).strip(),
       'observed_at': datetime.now(timezone.utc).isoformat(), 'database': prior['database'],
       'read_only': True, 'records': records, 'counts_before': before, 'counts_after': after,
       'provider_calls': 0, 'execution_allowed': False, 'tokenizer_certified': False,
       'limitation': 'Historical fixture Contract has no Model renderer policy. Alternative encodings are counterexamples only, never approved prompts.'}
with (B / 'model-producer-origin-audit-1653.json').open('x') as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print(json.dumps({'result': out['result'], 'original_applications': len(records), 'business_counts_unchanged': True, 'provider_calls': 0}))
