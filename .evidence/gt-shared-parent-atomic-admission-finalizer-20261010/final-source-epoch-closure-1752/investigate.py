"""Original neutral epoch-lock write branch in retained isolated PG only."""
import hashlib
import importlib.util
import json
import subprocess
import uuid
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
lab = json.loads((ROOT / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
item = json.loads(subprocess.check_output(['docker', '--context', lab['context'], 'inspect', lab['name']]))[0]
assert item['Id'] == lab['container_id'] and item['Image'] == lab['image'] and item['State']['Running']
paths = list((ROOT / 'services/aos-api/alembic/versions').glob('a0v_149*'))
assert len(paths) == 1
spec = importlib.util.spec_from_file_location('frozen_epoch_migration', paths[0])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
signature = 'public.aos_capacity_evidence_epoch_lock(text,text,text)'
metadata_sql = '''SELECT prosrc,pg_get_userbyid(proowner),prosecdef,proconfig,proacl::text
                  FROM pg_proc WHERE oid=%s::regprocedure'''
connection = dict(host='127.0.0.1', port=lab['port'], user='aos_app',
                  dbname='aos_test_05f1a1dcd51f_ti4_test', passfile=lab['passfile'])
probe = 'final-epoch-closure-' + uuid.uuid4().hex
attempt = OUT / 'attempt.json'
with attempt.open('x') as file:
    json.dump({'probe_id': probe, 'database': connection['dbname'],
               'operation': 'one original epoch lock and replay; rollback only'}, file)
with psycopg.connect(**connection) as conn:
    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
    assert conn.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0] == lab['cluster']
    before = conn.execute(metadata_sql, (signature,)).fetchone()
    assert before[0] == module.LOCK_BODY
    assert before[1:4] == ('aos_capacity_evidence_epoch_owner', True, ['search_path=pg_catalog'])
    assert conn.execute("SELECT has_function_privilege('aos_runtime',%s,'EXECUTE')", (signature,)).fetchone()[0]
    xid = conn.execute('SELECT pg_current_xact_id()::text').fetchone()[0]
    conn.execute("SET LOCAL aos.org_id='org-org'")
    conn.execute("SET LOCAL aos.project_id='dev-project'")
    def count():
        return conn.execute('SELECT count(*) FROM public.aip_capacity_evidence_epoch WHERE org_id=%s AND project_id=%s AND bundle_id=%s', ('org-org', 'dev-project', probe)).fetchone()[0]
    assert count() == 0
    baseline = conn.execute("SELECT n_tup_ins FROM pg_stat_xact_user_tables WHERE relid='public.aip_capacity_evidence_epoch'::regclass").fetchone()[0]
    conn.execute('SET LOCAL ROLE aos_runtime')
    first = conn.execute('SELECT public.aos_capacity_evidence_epoch_lock(%s,%s,%s)', ('org-org', 'dev-project', probe)).fetchone()[0]
    conn.execute('RESET ROLE')
    inserted = count()
    after_insert = conn.execute("SELECT n_tup_ins FROM pg_stat_xact_user_tables WHERE relid='public.aip_capacity_evidence_epoch'::regclass").fetchone()[0]
    conn.execute('SET LOCAL ROLE aos_runtime')
    repeated = conn.execute('SELECT public.aos_capacity_evidence_epoch_lock(%s,%s,%s)', ('org-org', 'dev-project', probe)).fetchone()[0]
    conn.execute('RESET ROLE')
    after_repeat = conn.execute("SELECT n_tup_ins FROM pg_stat_xact_user_tables WHERE relid='public.aip_capacity_evidence_epoch'::regclass").fetchone()[0]
    assert inserted == count() == 1 and first == repeated == 0
    assert after_insert - baseline == 1 and after_repeat == after_insert
    conn.rollback()
with psycopg.connect(**connection) as readback:
    readback.execute('SET TRANSACTION READ ONLY')
    assert readback.execute(metadata_sql, (signature,)).fetchone() == before
    assert readback.execute('SELECT count(*) FROM public.aip_capacity_evidence_epoch WHERE bundle_id=%s', (probe,)).fetchone()[0] == 0
    readback.rollback()
report = {'status': 'ORIGINAL_SOURCE_NESTED_EPOCH_LAZY_WRITE_NATIVE_PROVEN',
          'authority': 'AOS-001752', 'task': 'gt-shared-parent-atomic-admission-finalizer-20261010',
          'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'probe_id': probe, 'xid': xid, 'database': connection['dbname'], 'cluster': lab['cluster'],
          'original_lock_body_sha256': hashlib.sha256(before[0].encode()).hexdigest(),
          'original_lock_metadata_unchanged': True, 'first_missing_row_inserted': 1,
          'repeat_added_rows': 0, 'returned_epoch': first, 'independent_rollback_absent': True,
          'full_source_invoked': False, 'deferred_queue_claim': False,
          'full_task_delivered': False, 'execution_allowed': False, 'goal_complete': False,
          'next': 'Bind all original Source/Evidence epochs before drain; exact final profile rejects absent epochs, never lazy creates. Complete Receipt/native ending still required.'}
(OUT / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'first_missing_row_inserted': 1, 'repeat_added_rows': 0, 'independent_rollback_absent': True}))
