"""Original Target wire facts reconciled against retained native authorities."""
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
from aos_api.aip_model_runtime_contracts import RegisteredModelRevision, ModelRuntimeLifecycle
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, evaluation_candidate_ref
from aos_api.aip_model_governance_policy_contracts import QuotaPolicyRevision
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import CreateEvalContractRequest
from aos_api.tenant_scope import TenantScope

lab = json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
container = json.loads(subprocess.check_output(['docker', '--context', lab['context'], 'inspect', lab['name']], text=True))[0]
assert container['Id'] == lab['container_id'] and container['RestartCount'] == 0
names = ['model-target-wire-red-1655-r1', 'model-target-wire-green-1655-r1']
names += [f'model-target-wire-negative-1655-r{i}' for i in range(1, 6)]
names += ['model-target-wire-adjacent-native-1655-r1']
scope = TenantScope('org-org', 'dev-project')
reports = []
old_files = {'services/aos-api/tests/aip/test_model_eval_execution_owner_pg.py': B/'model-target-wire-test-before-context-1655.py',
             'services/aos-api/aos_api/aip_model_eval_execution_owner.py': B/'model-target-wire-owner-before-implementation-1655.py'}
for name in names:
    result = json.loads((B/(name+'-result.json')).read_text())
    attempt = json.loads((B/(name+'-attempt.json')).read_text())
    assert result['pytest_exit'] == (1 if '-red-' in name else 0) and result['old_evidence_unchanged']
    assert container['State']['StartedAt'] == attempt['started_at']
    for path, digest in attempt['file_hashes'].items():
        current = hashlib.sha256((R/path).read_bytes()).hexdigest()
        assert current == digest or (path in old_files and hashlib.sha256(old_files[path].read_bytes()).hexdigest() == digest)
    proof = json.loads((B/name/(name+'-whole-rollback-input.json')).read_text())
    records = []
    with psycopg.connect(host='127.0.0.1', port=5441, user='aos_app', dbname=result['database'],
                         passfile=lab['passfile'], options='-c default_transaction_read_only=on', row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == '7694680278363095064'
        assert c.execute('SELECT pg_xact_status(%s::xid8) AS state', (proof['caller']['xid'],)).fetchone()['state'] == 'aborted'
        counts = {t: c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in (
            'aip_agent_run', 'aip_model_capacity_reservation', 'aip_model_eval_budget_reservation',
            'aos_model_eval_execution_private.case_result')}
        assert all(v == 0 for v in counts.values())
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
            mr = c.execute('SELECT payload,content_hash FROM aip_registered_model_revision WHERE org_id=%s AND project_id=%s AND registered_model_id=%s AND revision=%s', (*scope.key, req.source_ref.asset_id, req.source_ref.revision)).fetchone()
            qr = c.execute("SELECT payload,content_hash FROM aip_model_governance_policy_revision WHERE org_id=%s AND project_id=%s AND policy_id=%s AND revision=%s AND policy_kind='quota'", (*scope.key, req.quota_policy_ref.asset_id, req.quota_policy_ref.revision)).fetchone()
            model = RegisteredModelRevision.model_validate(mr['payload'])
            quota = QuotaPolicyRevision.model_validate(qr['payload'])
            for obj, rec, ref, excluded in ((model, mr, req.source_ref, AipModelRuntimeStore._META_FIELDS),
                    (quota, qr, req.quota_policy_ref, {'tenant', 'contentHash', 'createdBy', 'createdAt'})):
                assert obj.content_hash == rec['content_hash'] == ref.content_hash
                assert canonical_hash({k: v for k,v in obj.model_dump(mode='json', by_alias=True).items() if k not in excluded}) == ref.content_hash
            assert evaluation_candidate_ref(model.model_copy(update={'revision': model.revision+1,
                'lifecycle': ModelRuntimeLifecycle.ACTIVE, 'eval_gate_ref': None})) == req.target_ref
            records.append({'request_id': app['request_id'], 'request_hash': row['request_hash'],
                'source_ref': req.source_ref.model_dump(mode='json', by_alias=True),
                'candidate_ref': req.target_ref.model_dump(mode='json', by_alias=True),
                'contract_hash': contract.content_hash, 'wire_policy': contract.gate_policy.get('modelTargetWireFormat'),
                'model_context': model.context_window, 'quota_output': quota.max_output_tokens,
                'input_capacity': min(quota.max_input_tokens, model.context_window-quota.max_output_tokens)})
            if app == proof['applications'][0]:
                expected = {'model': model.provider_model_id, 'messages': [{'role': 'user', 'content': '  原模型输入🙂\n保持空白  '}], 'max_tokens': quota.max_output_tokens}
                expected_wire = json.dumps(expected, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
        wire_file = B/name/(name+'-whole-rollback-target-wire.json')
        if wire_file.exists():
            wire = json.loads(wire_file.read_text())
            if wire['variant'] == 'valid':
                assert len(wire['wire_hashes']) == 2
                assert all(p['sha256'] == hashlib.sha256(expected_wire).hexdigest() and p['bytesLength'] == len(expected_wire) for p in wire['wire_hashes'])
                assert records[0]['input_capacity'] == 6000
            else:
                assert wire['rejected'] and not wire['wire_hashes']
                if wire['variant'] == 'no-input-window': assert records[0]['input_capacity'] == 0
        assert c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] == 'on'
        c.rollback()
    for path, digest in result['old_evidence_hashes_before'].items():
        assert hashlib.sha256((R/path).read_bytes()).hexdigest() == digest
    reports.append({'attempt': name, 'database': result['database'], 'caller_aborted': True,
                    'originals': records, 'business_counts': counts})
tree = ast.parse((R/'services/aos-api/aos_api/aip_model_eval_execution_owner.py').read_bytes())
method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'prepare_original_model_target_wire_bytes')
calls = [n for n in ast.walk(method) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
assert not {n.func.attr for n in calls} & {'post', 'send', 'dispatch', 'admit', 'commit', 'rollback', 'connect'}
for n in calls:
    if n.func.attr == 'execute': assert isinstance(n.args[0], ast.Constant) and n.args[0].value.strip().upper().startswith('SELECT ')
library = subprocess.check_output(['docker', '--context', lab['context'], 'exec', lab['name'], 'sha256sum', '/usr/local/lib/postgresql/aos_ed25519.so'], text=True).split()[0]
assert library == '6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'
out = {'result': 'ORIGINAL_TARGET_FIXED_WIRE_PREPARATION_VERIFIED', 'reports': reports, 'old_evidence_unchanged': True,
       'source_verifier_unchanged': True, 'direct_sql_read_only': True, 'execution_allowed': False,
       'actual_token_count_known': False, 'full_model_admission': False,
       'limitations': 'Pure actual body encoding only, not Provider compatibility, token proof, Judge output, Model quality, Source completion or execution identity/permission.'}
with (B/'model-target-wire-independent-1655.json').open('x') as f: json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps({'result': out['result'], 'databases': len(reports), 'all_callers_aborted': True, 'all_business_counts_zero': True}))
