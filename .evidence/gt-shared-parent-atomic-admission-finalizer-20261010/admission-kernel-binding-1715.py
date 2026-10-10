"""Static original SQL binding; no database connection or runtime installation."""
import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path

E = Path(__file__).resolve().parent
R = E.parents[1]
source = R / 'services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py'
spec = importlib.util.spec_from_file_location('original_capacity_artifact', source)
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
before = json.loads((E / 'capacity-kernel-sql-beforeimage-1699.json').read_text())['generators']
bindings = []
for name, expected in before.items():
    statements = list(getattr(original, name)())
    assert statements == expected, name + ': original SQL drift'
    sql = '\n'.join(statements)
    bindings.append({
        'generator': name,
        'original_sql_byte_identical': True,
        'sql_sha256': hashlib.sha256(sql.encode()).hexdigest(),
        'created_tables': re.findall(r'CREATE TABLE\s+([\w.]+)', sql),
        'insert_targets': re.findall(r'INSERT INTO\s+([\w.]+)', sql),
        'update_targets': re.findall(r'UPDATE\s+([\w.]+)\s+SET', sql),
        'constraint_triggers': re.findall(r'CREATE CONSTRAINT TRIGGER\s+(\w+)', sql),
        'for_update_count': len(re.findall(r'\bFOR UPDATE\b', sql)),
        'for_share_count': len(re.findall(r'\bFOR SHARE\b', sql)),
        'clock_reads': sql.count('clock_timestamp()'),
        'unconditional_preparation_reject_calls': sql.count('EXECUTE FUNCTION ' + original.SCHEMA + '.reject_unfinalized_parent_debit()'),
    })
physical = original._physical_call_capacity_guard_sql('target')
parent = original._parent_debit_capacity_guard_sql('target')
assert physical in parent
assert original.SCHEMA + '.prepared_parent_debit' in parent
assert 'p_minor' not in physical and 'allocated_minor' not in physical
assert sum(x['unconditional_preparation_reject_calls'] for x in bindings) == 7
product = R / 'services/aos-api/aos_api/aip_shared_parent_atomic_admission.py'
assert not product.exists(), 'New product input requires separate review'
report = {
    'status': 'STATIC_NEW_VERSION_REUSE_AND_LEGACY_RISK_DEPENDENCIES_BOUND',
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=R, text=True).strip(),
    'authority': 'AOS-001715',
    'task': E.name,
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'original_generators': bindings,
    'original_preparation_denial_triggers': 7,
    'legacy_counted_relation': original.SCHEMA + '.prepared_parent_debit',
    'shared_physical_guard_requires_trusted_locked_combined_totals': True,
    'remaining_full_implementation': [
        'Explicit versioned admitted ledger and immutable lifecycle; original preparation remains closed',
        'Complete old unresolved risk mapping and account-global lock order; no empty-table authority',
        'Original signed Source and both independently approved parent holds; no copied simplified fact validator',
        'All-case certificates and Target Intent with Judge pending actual Target dependency',
        'Actual write-event closure and exact deferred/RI checks before final decision clock',
        'Single trusted COMMIT channel, unknown retained and independently reconciled; no TTL refund',
        'Native full positive/rollback/replay/canary/withdrawal/deadline/early-end matrix',
    ],
    'database_access': False,
    'runtime_installation': False,
    'full_admission_pass': False,
    'business_runtime_authorized': False,
}
with (E / 'admission-kernel-binding-1715.json').open('x') as out:
    json.dump(report, out, ensure_ascii=False, indent=2)
    out.write('\n')
print('14 original SQL generators exact; seven denial guards retained; new-version dependencies bound')
