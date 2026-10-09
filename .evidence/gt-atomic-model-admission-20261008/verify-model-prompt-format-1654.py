"""Retained attempts reconciled independently with SERIAL READ ONLY."""
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

B = Path(__file__).resolve().parent
R = B.parents[1]
sys.path.insert(0, str(R/'services/aos-api'))
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import CreateEvalContractRequest
from aos_api.tenant_scope import TenantScope

lab = json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
container = json.loads(subprocess.check_output(['docker', '--context', lab['context'], 'inspect', lab['name']], text=True))[0]
assert container['Id'] == lab['container_id'] and container['RestartCount'] == 0
names = ['model-prompt-format-red-1654-r1', 'model-prompt-format-red-1654-r2',
         'model-prompt-format-green-1654-r1', 'model-prompt-format-green-1654-r2']
names += [f'model-prompt-format-negative-1654-r{i}' for i in range(1, 13)]
names += ['model-prompt-format-adjacent-native-1654-r1']
reports = []
scope = TenantScope('org-org', 'dev-project')
for name in names:
    result = json.loads((B/(name+'-result.json')).read_text())
    attempt = json.loads((B/(name+'-attempt.json')).read_text())
    assert result['pytest_exit'] == (1 if name in names[:3] else 0)
    assert result['old_evidence_unchanged']
    assert container['State']['StartedAt'] == attempt['started_at']
    for path, digest in attempt['file_hashes'].items():
        assert hashlib.sha256((R/path).read_bytes()).hexdigest() == digest
    proof_path = B/name/(name+'-whole-rollback-input.json')
    proof = json.loads(proof_path.read_text()) if proof_path.exists() else None
    with psycopg.connect(host='127.0.0.1', port=5441, user='aos_app', dbname=result['database'],
                         passfile=lab['passfile'], options='-c default_transaction_read_only=on', row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == '7694680278363095064'
        counts = {t: c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in (
            'aip_agent_run', 'aip_model_capacity_reservation', 'aip_model_eval_budget_reservation',
            'aos_model_eval_execution_private.case_result')}
        assert all(v == 0 for v in counts.values())
        originals = []
        if proof is not None:
            assert c.execute('SELECT pg_xact_status(%s::xid8) AS state', (proof['caller']['xid'],)).fetchone()['state'] == 'aborted'
            for app in proof['applications']:
                row = c.execute('SELECT request_json,request_hash FROM aip_model_eval_request WHERE org_id=%s AND project_id=%s AND request_id=%s', (*scope.key, app['request_id'])).fetchone()
                assert canonical_hash(row['request_json']) == row['request_hash'] == app['request_hash']
                req = ModelEvalRequestCreate.model_validate(row['request_json'])
                contract = AipProductionContractStore().get_eval_contract(scope, req.eval_contract_ref.asset_id, req.eval_contract_ref.revision, conn=c)
                body = CreateEvalContractRequest(**{k: getattr(contract, k) for k in CreateEvalContractRequest.model_fields})
                assert canonical_hash(body.model_dump(mode='json', by_alias=True)) == contract.content_hash == req.eval_contract_ref.content_hash
                suite_row = c.execute('SELECT * FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s', (*scope.key, req.suite_ref.asset_id, req.suite_ref.revision)).fetchone()
                suite = AipEvalPackRegistry._suite_from_row(suite_row)
                assert compute_eval_suite_hash(suite) == suite.content_hash == req.suite_ref.content_hash
                originals.append({'request_id': app['request_id'], 'request_hash': row['request_hash'],
                    'contract_hash': contract.content_hash, 'format': contract.gate_policy.get('modelInputFormat'),
                    'suite_hash': suite.content_hash, 'input_hashes': [case.input_artifact.content_hash for case in suite.cases]})
            prompt_path = B/name/(name+'-whole-rollback-prompt-format.json')
            if prompt_path.exists():
                prompts = json.loads(prompt_path.read_text())
                assert prompts['input_hash'] in originals[0]['input_hashes']
                if prompts['variant'] == 'valid':
                    expected = '  原模型输入🙂\n保持空白  '.encode('utf-8')
                    assert all(p['sha256'] == hashlib.sha256(expected).hexdigest() and p['bytesLength'] == len(expected) for p in prompts['prompts'])
                    assert len(prompts['prompts']) == len(originals[0]['input_hashes'])
                else:
                    assert prompts['rejected'] and not prompts['prompts']
        assert c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] == 'on'
        c.rollback()
    for path, digest in result['old_evidence_hashes_before'].items():
        assert hashlib.sha256((R/path).read_bytes()).hexdigest() == digest
    reports.append({'attempt': name, 'database': result['database'], 'pytest_exit': result['pytest_exit'],
                    'caller_aborted': proof is not None, 'originals': originals, 'business_counts': counts})
tree = ast.parse((R/'services/aos-api/aos_api/aip_model_eval_execution_owner.py').read_bytes())
method = next(x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef) and x.name == 'prepare_original_model_plan_prompt_bytes')
calls = {x.func.attr for x in ast.walk(method) if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)}
assert not calls & {'execute', 'commit', 'rollback', 'connect', 'post', 'dispatch', 'admit'}
library = subprocess.check_output(['docker', '--context', lab['context'], 'exec', lab['name'], 'sha256sum', '/usr/local/lib/postgresql/aos_ed25519.so'], text=True).split()[0]
assert library == '6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'
out = {'result': 'ORIGINAL_APPROVED_FIXED_PROMPT_PRODUCER_NECESSARY_STAGE_VERIFIED', 'reports': reports,
       'source_verifier_unchanged': True, 'old_evidence_unchanged': True, 'method_no_direct_effects': True,
       'execution_allowed': False, 'full_model_admission': False,
       'limitations': 'Isolated new prompt Dataset and original signed approvals only. No Model quality/Judge-input/tokenizer/wire/Source-completion/executor identity grant.'}
with (B/'model-prompt-format-independent-1654.json').open('x') as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print(json.dumps({'result': out['result'], 'databases': len(reports), 'negative_variants': 12, 'all_business_counts_zero': True}))
