"""Read retained native manifest; perturb descriptions only in memory."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from aos_api.aip_model_eval_execution_contracts import ModelEvalTargetJudgeExecutionManifest

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name('shared-parent-manifest-result-1668.json')
assert not OUT.exists(), 'existing/unknown result must not be replayed'
names = ('aip_model_eval_execution_contracts.py', 'aip_model_eval_execution_owner.py',
         'aip_physical_capacity_occupation_authority.py')
paths = [ROOT / 'services/aos-api/aos_api' / name for name in names]
before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
lab = json.loads((ROOT / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
for name in ('PGPASSWORD', 'PGPASSFILE', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS'):
    os.environ.pop(name, None)
database = 'aos_test_ff40de426907_ti4_test'
with psycopg.connect(host='127.0.0.1', port=lab['port'], user='aos_app', dbname=database,
        passfile=lab['passfile'], row_factory=dict_row,
        options='-c default_transaction_read_only=on') as conn:
    conn.execute('SET TRANSACTION READ ONLY')
    identity = conn.execute("SELECT current_database() AS database,(pg_control_system()).system_identifier::text AS cluster,current_setting('transaction_read_only') AS read_only,clock_timestamp() AS observed_at").fetchone()
    assert identity['database'] == database and identity['cluster'] == lab['cluster']
    assert identity['read_only'] == 'on'
    rows = conn.execute('SELECT body FROM aos_model_eval_execution_private.manifest WHERE org_id=%s AND project_id=%s ORDER BY execution_id', ('org-org', 'dev-project')).fetchall()
    candidates = []
    for row in rows:
        body = json.loads(bytes(row['body']))
        try:
            plan = ModelEvalTargetJudgeExecutionManifest.model_validate(body)
        except ValueError:
            continue
        if len(plan.cases) == 2:
            candidates.append(body)
    assert len(candidates) == 1, 'one exact retained original two-case manifest required'
    body = candidates[0]
    conn.rollback()

base = ModelEvalTargetJudgeExecutionManifest.model_validate(body)
assert base.target_parent_budget.upper_bound_minor == base.judge_parent_budget.upper_bound_minor == 10
results = []
for pair, expected in (((1, 1), True), ((5, 5), True), ((1, 9), True), ((6, 6), False), ((0, 0), False)):
    changed = copy.deepcopy(body)
    for case, amount in zip(changed['cases'], pair, strict=True):
        for purpose in ('target', 'judge'):
            case[purpose]['allocationUpperBoundMinor'] = amount
    try:
        ModelEvalTargetJudgeExecutionManifest.model_validate(changed)
        accepted = True
    except ValueError:
        accepted = False
    assert accepted == expected, (pair, accepted)
    results.append({'per_purpose_case_bounds': pair, 'total': sum(pair),
        'accepted_description': accepted, 'budget_authority_proven': False,
        'description_sha256': hashlib.sha256(json.dumps(changed, sort_keys=True, ensure_ascii=False).encode()).hexdigest()})
owner = paths[1].read_text()
tree = ast.parse(owner)
fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
    and n.name == 'validate_original_target_judge_manifest')
owner_body = ast.get_source_segment(owner, fn)
assert 'allocation_upper_bound_minor' not in owner_body
assert 'allocationUpperBoundMinor' not in owner_body
sql = paths[2].read_text()
assert "'riskMode','original_shared_parent_caps'" in sql
assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
result = {'schema': 'aos.shared-parent-manifest-audit/v1', 'authority_revision': 'AOS-001668',
    'task_id': 'gt-atomic-model-admission-20261008', 'identity': identity,
    'source_hashes': before, 'original_manifest_sha256': hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
    'case_count': 2, 'leg_count': 4, 'parent_bounds': {'target': 10, 'judge': 10},
    'description_variants': results, 'owner_direct_leg_allocation_derivation': False,
    'prepared_risk_mode': 'original_shared_parent_caps',
    'database_mutations': 0, 'provider_calls': 0, 'execution_allowed': False,
    'limitations': ['pure description acceptance is not native admission',
        'absence in this reader does not prove absence in every repository entry',
        'test-owned stored manifest is not formal trust or actual transport']}
with OUT.open('x') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2, default=str)
    stream.write('\n')
print(json.dumps({'result': str(OUT), 'variants_verified': len(results), 'read_only': True}))
