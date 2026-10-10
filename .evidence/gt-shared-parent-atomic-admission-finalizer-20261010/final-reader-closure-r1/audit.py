"""Freeze concrete write-reachable readers; does not claim complete SQL purity."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'services/aos-api'))
from aos_api import aip_shared_parent_atomic_admission as main
from aos_api import aip_physical_capacity_occupation_authority as physical

OUT = Path(__file__).resolve().parent
GROUPS = (
    main.shared_parent_initial_call_authority_statements,
    main.shared_parent_initial_intent_statements,
    main.shared_parent_live_physical_fact_statements,
    physical.occupation_account_guard_statements,
)
definitions = {}
for generator in GROUPS:
    for sql in generator():
        match = re.match(r'CREATE FUNCTION\s+([\w.]+)\s*\(', sql.strip(), re.I)
        if match:
            definitions[match.group(1)] = sql

edges = (
    (main.READ_INITIAL_CALL.split('(')[0], main.INITIAL_INTENT.split('(')[0]),
    (main.READ_LIVE_PHYSICAL.split('(')[0], physical.GUARD.split('(')[0]),
)
findings = []
for reader, producer in edges:
    reader_sql, producer_sql = definitions[reader], definitions[producer]
    assert re.search(re.escape(producer) + r'\s*\(', reader_sql)
    writes = re.findall(r'\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+[\w.]+', producer_sql, re.I)
    assert writes, f'Expected direct write missing: {producer}'
    findings.append({'reader': reader, 'reaches': producer, 'direct_dml': writes,
                     'final_read_only_contract': 'RED', 'complete_call_graph_proven': False})
    for name, sql in ((reader, reader_sql), (producer, producer_sql)):
        (OUT / (name.replace('.', '_') + '.sql')).write_text(sql + '\n')

source_hashes = {}
for module in (main, physical):
    path = Path(module.__file__)
    source_hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
report = {
    'status': 'FINAL_READER_WRITE_REACHABILITY_RED',
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'authority': 'AOS-001750', 'task': 'gt-shared-parent-atomic-admission-finalizer-20261010',
    'source_hashes': source_hashes, 'findings': findings,
    'sql_hashes': {name: hashlib.sha256(sql.encode()).hexdigest() for name, sql in definitions.items()},
    'limitations': ['Static concrete edges only; remaining called functions unclassified.',
                    'No native transaction or deferred event claim from this audit.',
                    'ON CONFLICT DO NOTHING does not establish a read-only call contract.',
                    'Existing PLAN_FACT itself is not assumed to require prepared debit rows.'],
    'database_operations': 0, 'product_modified': False, 'execution_allowed': False,
    'full_task_delivered': False, 'goal_complete': False,
}
(OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'concrete_write_paths': len(findings)}))
sys.exit(1)
