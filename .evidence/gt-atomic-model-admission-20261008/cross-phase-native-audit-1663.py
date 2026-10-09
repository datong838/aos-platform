"""Read-only native stage provenance audit; never installs or grants execution."""
from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
sys.path.insert(0, str(REPO / 'services/aos-api'))
from aos_api.aip_model_eval_execution_contracts import ModelEvalTargetJudgeExecutionManifest

TASK = 'gt-atomic-model-admission-20261008'
THREAD = '01a107a2-e9e4-7670-bc44-1144fa9b27e2'
CONTEXT = REPO.parent / 'docs/palantier/AOS项目开发上下文/memory'
authority = json.loads((CONTEXT / 'authority.json').read_text())
assert authority['project_revision'] == 'AOS-001663'
task = json.loads((CONTEXT / 'receipts/tasks' / (TASK + '.json')).read_text())
leases = json.loads((CONTEXT / 'leases.json').read_text())['leases']
assert [v for v in leases if v['task_id'] == TASK] == [task]
assert task['status'] == 'ACTIVE' and task['owner'] == 'codex-' + THREAD
assert not (CONTEXT / 'receipts/deliveries' / (TASK + '.json')).exists()

prefix = '.evidence/gt-judge-call-authority-20261008/'
name = 'judge-expected-bytes-green-1659-r1'
proof_path = prefix + name + '/' + name + '-whole-plan-proof.json'
result_path = prefix + name + '-result.json'
proof = json.loads((REPO / proof_path).read_text())
old_result = json.loads((REPO / result_path).read_text())
assert old_result['pytest_exit'] == 0
plan = ModelEvalTargetJudgeExecutionManifest.model_validate(proof['manifest'])
lab_path = '.evidence/gt-source-desktop-shm-lab-20261009/lab.json'
lab = json.loads((REPO / lab_path).read_text())
assert lab['port'] == 5441 and lab['cluster'] == '7694680278363095064'
db = old_result['database']
assert db == 'aos_test_bcd5c43891be_ti4_test'
# Do not inherit credentials/service/options intended for another database.
for key in ('PGPASSWORD', 'PGPASSFILE', 'PGSERVICE', 'PGOPTIONS'):
    os.environ.pop(key, None)

paths = [proof_path, result_path, lab_path,
    'services/aos-api/aos_api/aip_model_eval_execution_owner.py',
    'services/aos-api/aos_api/aip_model_eval_execution_authority.py',
    'services/aos-api/aos_api/aip_model_eval_execution_reader.py',
    'services/aos-api/aos_api/aip_model_eval_execution_contracts.py',
    str(Path(__file__).relative_to(REPO)),
    str((BASE / 'cross-phase-protocol-plan-1663.md').relative_to(REPO))]
hashes = {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in paths}
tree = ast.parse((REPO / paths[3]).read_text())
owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ModelEvalExecutionOwner')
guard = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == 'validate_original_target_judge_manifest')
guard_text = ast.get_source_segment((REPO / paths[3]).read_text(), guard)
assert "original['origin_xid'] != identity['xid']" in guard_text
authority_text = (REPO / paths[4]).read_text()
assert "pg_xact_status(result.origin_xid) IS DISTINCT FROM 'committed'" in authority_text

with psycopg.connect(host='127.0.0.1', port=5441, user='aos_app', dbname=db,
        passfile=lab['passfile'], options='-c default_transaction_read_only=on',
        row_factory=dict_row) as conn:
    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == lab['cluster']
    identity = conn.execute("SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid,current_database() AS database,current_setting('transaction_read_only') AS read_only,current_setting('transaction_isolation') AS isolation,clock_timestamp() AS now").fetchone()
    assert identity['read_only'] == 'on' and identity['isolation'] == 'serializable'
    assert identity['now'] < datetime.fromisoformat(task['lease_expires_at'])
    original_status = conn.execute('SELECT pg_xact_status(%s::xid8) AS status', (proof['caller']['xid'],)).fetchone()['status']
    assert original_status == 'aborted'
    original_rows = {}
    for table, parent in (
            ('aip_model_eval_budget_reservation', plan.target_parent_budget),
            ('aip_model_judge_budget_reservation', plan.judge_parent_budget)):
        row = conn.execute('SELECT xmin::text AS origin_xid,content_hash FROM ' + table + ' WHERE org_id=%s AND project_id=%s AND request_id=%s AND approval_event_id=%s AND reservation_id=%s',
            ('org-org', 'dev-project', parent.request_id, parent.approval_ref.resource_id, parent.parent_hold_ref.resource_id)).fetchone()
        assert row is None
        original_rows[table] = 0
    durable = []
    # These are independent legacy Judge holds, NOT valid v2 whole-plan parents.
    for table in ('aip_model_eval_budget_reservation', 'aip_model_judge_budget_reservation'):
        rows = conn.execute('SELECT reservation_id,request_id,content_hash,xmin::text AS origin_xid FROM ' + table + ' WHERE org_id=%s AND project_id=%s ORDER BY reservation_id', ('org-org', 'dev-project')).fetchall()
        for row in rows:
            row['reservation_id'] = str(row['reservation_id'])
            status = conn.execute('SELECT pg_xact_status(%s::xid8) AS status', (row['origin_xid'],)).fetchone()['status']
            assert status == 'committed' and row['origin_xid'] != identity['xid']
            durable.append({'table': table, **row, 'native_status': status, 'passes_fresh_xid_predicate': False})
    assert durable, 'native committed hold required for phase counterexample'
    inventory = {}
    for table in ('aos_model_eval_execution_private.manifest', 'aos_model_eval_execution_private.case_result', 'aos_model_eval_issuer_private.executor_certificate', 'aos_model_eval_issuer_private.target_result_origin'):
        exists = conn.execute('SELECT to_regclass(%s)::text AS name', (table,)).fetchone()['name']
        inventory[table] = None if exists is None else conn.execute('SELECT count(*) AS n FROM ' + table).fetchone()['n']
    assert inventory['aos_model_eval_execution_private.manifest'] == 0
    assert inventory['aos_model_eval_execution_private.case_result'] == 0
    assert conn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] == 'on'
    xid = identity['xid']
    conn.rollback()
    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    reader_status = conn.execute('SELECT pg_xact_status(%s::xid8) AS status', (xid,)).fetchone()['status']
    assert reader_status == 'aborted'
    conn.rollback()

for p, h in hashes.items():
    assert hashlib.sha256((REPO / p).read_bytes()).hexdigest() == h, 'source changed during audit'
identity['now'] = identity['now'].isoformat()
out = {'authority_revision': authority['project_revision'], 'task': TASK, 'thread': THREAD,
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
    'file_hashes': hashes, 'cluster': lab['cluster'], 'caller': identity,
    'read_only_caller_end_status': reader_status, 'original_whole_prepare_xid': proof['caller']['xid'],
    'original_whole_prepare_status': original_status, 'original_whole_parent_rows': original_rows,
    'independent_committed_holds': durable, 'inventory': inventory,
    'result': 'NATIVE_FRESH_PREPARE_VERSUS_DURABLE_CONSUME_PHASE_BOUNDARY',
    'product_bug_claimed': False, 'actual_v2_cross_phase_admission_tested': False,
    'execution_allowed': False, 'full_task_delivered': False,
    'limitations': 'Independent committed legacy holds prove xid mismatch only. Original v2 whole preparation was aborted; no durable whole plan/result exists. No role/function/install/write/transport/replay/COMMIT performed; future durable consumer remains required.'}
serialized = json.dumps(out, ensure_ascii=False, indent=2)
with (BASE / 'cross-phase-native-result-r2-1663.json').open('x') as f:
    f.write(serialized + '\n')
print(json.dumps({'result': out['result'], 'committed_holds': len(durable), 'reader_end': reader_status, 'execution_allowed': False}))
