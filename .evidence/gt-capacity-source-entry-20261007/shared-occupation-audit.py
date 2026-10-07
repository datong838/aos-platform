"""Reconcile the current existing GT-b4 RED in its retained isolated PG only."""
import ast
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path.cwd()
LOG = ROOT / '.evidence/gt-capacity-source-publication-20261006/shared-occupation-current-red-r1.log'
OUT = ROOT / '.evidence/gt-capacity-source-entry-20261007/shared-occupation-audit.json'
raw = LOG.read_text()
assert '2 failed, 6 passed' in raw
assert raw.count('DID NOT RAISE') >= 2
databases = set(re.findall(r'Retained isolated test database: (aos_test_[0-9a-f]+_ti4_test)', raw))
assert len(databases) == 1, databases
database = databases.pop()
assert not re.search(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', raw)
passfile = Path(tempfile.gettempdir()) / 'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
password = passfile.read_text().strip().split(':')[-1]
assert password not in raw
container = subprocess.check_output([
    'docker', '--context', 'colima-aos-a0v-test-only', 'inspect',
    'aos-capacity-publication-scram-20261006', '--format', '{{.Id}}'], text=True).strip()
assert container == '4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
with psycopg.connect(host='127.0.0.1', port=5434, dbname=database,
                     user='aos_app', password=password, row_factory=dict_row) as conn:
    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    identity = conn.execute("""SELECT current_database() AS database,
        current_setting('transaction_read_only') AS read_only,
        (SELECT system_identifier::text FROM pg_control_system()) AS cluster""").fetchone()
    assert identity == {'database': database, 'read_only': 'on', 'cluster': '7693564235776004128'}
    versions = conn.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()
    rows = conn.execute("""SELECT r.org_id,r.project_id,r.agent_run_id,r.pool_id,
        r.pool_revision,r.status,r.request_units,r.token_units,p.provider_id,
        p.max_concurrency,p.max_token_units
        FROM aip_model_capacity_reservation r
        JOIN aip_model_capacity_pool_revision p
          ON (p.org_id,p.project_id,p.pool_id,p.revision)=
             (r.org_id,r.project_id,r.pool_id,r.pool_revision)
        ORDER BY r.agent_run_id""").fetchall()
    assert len(rows) == 3, rows
    assert {r['agent_run_id'] for r in rows} == {
        'test:gtb4:no-physical-account', 'test:gtb4:ordinary:first', 'test:gtb4:ordinary:second'}
    assert all(r['org_id'] == 'org-org' and r['project_id'] == 'dev-project'
               and r['status'] == 'reserved' and r['request_units'] == 1
               and r['max_concurrency'] == 1 for r in rows)
    shared = [r for r in rows if r['agent_run_id'].startswith('test:gtb4:ordinary:')]
    assert len({r['provider_id'] for r in shared}) == 1
    assert len({r['pool_id'] for r in shared}) == 2
    events = conn.execute("""SELECT event_type,count(*) AS n
        FROM aip_model_capacity_event GROUP BY event_type ORDER BY event_type""").fetchall()
    assert events == [{'event_type': 'reserved', 'n': 3}], events
    source_counts = {}
    for name in ('source_publication', 'source_pending', 'source_provenance', 'global_account', 'provider_mapping'):
        qualified = 'aos_capacity_publication_private.' + name
        if conn.execute('SELECT to_regclass(%s) AS relation', (qualified,)).fetchone()['relation'] is not None:
            source_counts[name] = conn.execute(sql.SQL('SELECT count(*) AS n FROM {}.{}').format(
                sql.Identifier('aos_capacity_publication_private'), sql.Identifier(name))).fetchone()['n']
    assert source_counts.get('source_publication') == 0, source_counts
    canary = conn.execute("""SELECT
        (SELECT count(*) FROM aip_model_capacity_reservation WHERE org_id='dev-org') AS reservations,
        (SELECT count(*) FROM aip_model_capacity_event WHERE org_id='dev-org') AS events""").fetchone()
    assert canary == {'reservations': 0, 'events': 0}
    conn.rollback()

paths = [
    'services/aos-api/tests/aip/test_model_eval_shared_capacity_pg.py',
    'services/aos-api/aos_api/aip_model_capacity_reservation.py',
    'services/aos-api/aos_api/aip_model_capacity_authority.py',
    'services/aos-api/aos_api/aip_provider_capacity_source_consumer.py',
]
tree = ast.parse((ROOT / paths[1]).read_text())
reserve = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'reserve')
statements = [n.value for n in ast.walk(reserve) if isinstance(n, ast.Constant)
              and isinstance(n.value, str) and 'aip_model_capacity_' in n.value]
assert any('FOR UPDATE OF h' in s for s in statements)
assert any('COUNT(*)' in s and 'pool_id=%s' in s and 'pool_revision=%s' in s for s in statements)
assert any("status IN ('reserved','consumed')" in s and 'expires_at<=NOW()' in s for s in statements)
assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
           and n.func.attr == 'commit' for n in ast.walk(reserve))
report = {
    'schema': 'aos-current-shared-occupation-gap/v1',
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'identity': identity, 'migration_heads': versions, 'container': container,
    'log': str(LOG.relative_to(ROOT)), 'log_sha256': hashlib.sha256(LOG.read_bytes()).hexdigest(),
    'file_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
    'durable_reservations': rows, 'durable_events': events, 'source_counts': source_counts,
    'negative_canary': canary, 'existing_test_result': '2 failed, 6 passed; --runxfail; expected shared-authority RED',
    'established': [
        'Old entry committed a reservation with zero signed capacity Sources in this isolated database.',
        'Two distinct Route pools of one fixture Provider each committed one reservation.',
        'Native persisted rows and events agree with actual DID NOT RAISE failures.',
        'Current code counts/expires by pool and revision, and commits on its own connection.'
    ],
    'limits': [
        'Fixture manually seeds READY and pool rows: this is a negative counterexample, not a legitimate business positive.',
        'No supplier physical cap is established; two reservations do not prove any real supplier oversubscription.',
        'No unknown external send was produced; TTL code audit is a future integration requirement, not a real unknown-loss proof.',
        'No Source consumer/pool integration, cutover, budget+occupation+Intent atomicity, formal deployment or COMMIT-TTL resolution.'
    ],
    'formal_resources_touched': False, 'full_goal_complete': False,
}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'database': database, 'durable_reservations': len(rows),
                  'signed_sources': source_counts['source_publication'], 'negative_canary': canary}))
