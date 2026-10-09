"""Original lifecycle audit: retained isolated PostgreSQL, read-only, no retry."""
import ast
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name('parent-cost-lifecycle-result-1665.json')
assert not OUT.exists(), 'do not replay an existing result'
files = ('aip_budget_reservation_store.py', 'aip_model_eval_budget_reservation.py',
         'aip_model_eval_judge_budget.py', 'aip_budget_cost_runtime.py')
sources = {}
for name in files:
    path = ROOT / 'services/aos-api/aos_api' / name
    raw = path.read_bytes()
    tree = ast.parse(raw)
    sources[name] = {'sha256': hashlib.sha256(raw).hexdigest(),
                     'classes': {n.name: [f.name for f in n.body
                         if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))]
                         for n in tree.body if isinstance(n, ast.ClassDef)}}
for name in ('PGPASSWORD', 'PGPASSFILE', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS'):
    os.environ.pop(name, None)
lab = json.loads((ROOT / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
database = 'aos_test_ff40de426907_ti4_test'
with psycopg.connect(host='127.0.0.1', port=lab['port'], user='aos_app',
                     dbname=database, passfile=lab['passfile'], row_factory=dict_row,
                     options='-c default_transaction_read_only=on') as conn:
    conn.execute('SET TRANSACTION READ ONLY')
    identity = conn.execute("SELECT current_database() AS database, (pg_control_system()).system_identifier::text AS cluster, current_setting('transaction_read_only') AS read_only, clock_timestamp() AS observed_at").fetchone()
    assert identity['database'] == database and identity['cluster'] == lab['cluster']
    assert identity['read_only'] == 'on'
    heads = conn.execute('SELECT version_num FROM alembic_version').fetchall()
    tables = ('aip_budget_reservation', 'aip_model_eval_budget_reservation',
              'aip_model_judge_budget_reservation')
    catalog = {}
    for table in tables:
        relation = 'public.' + table
        catalog[table] = {
            'checks': conn.execute("SELECT conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conrelid=%s::regclass AND contype='c' ORDER BY conname", (relation,)).fetchall(),
            'triggers': conn.execute("SELECT tgname,pg_get_triggerdef(oid) AS definition FROM pg_trigger WHERE tgrelid=%s::regclass AND NOT tgisinternal ORDER BY tgname", (relation,)).fetchall(),
            'states': conn.execute('SELECT state,count(*) AS n FROM ' + relation + ' GROUP BY state ORDER BY state').fetchall(),
        }
    prices = conn.execute("SELECT model_price_snapshot_id,revision,content_hash,payload->'inputTokenPrice' AS input_price,payload->'outputTokenPrice' AS output_price,payload->'cachedTokenPrice' AS cached_price,payload->'developmentCostAuthorization' IS NOT NULL AS has_development_authorization FROM public.aip_model_price_snapshot_revision ORDER BY model_price_snapshot_id,revision").fetchall()
    conn.rollback()
    result = {'schema': 'aos.parent-cost-lifecycle-audit/v1', 'authority_revision': 'AOS-001665',
              'task_id': 'gt-atomic-model-admission-20261008', 'identity': identity,
              'migration_heads': heads, 'sources': sources, 'catalog': catalog, 'prices': prices,
              'database_mutations': 0, 'provider_calls': 0, 'execution_allowed': False,
              'full_task_delivered': False, 'recorded_at': datetime.now(timezone.utc)}
    encoded = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    with OUT.open('x') as stream:
        stream.write(encoded + '\n')
print(json.dumps({'result': str(OUT), 'cluster_verified': True, 'read_only': True,
                  'price_rows': len(prices), 'execution_allowed': False}))
