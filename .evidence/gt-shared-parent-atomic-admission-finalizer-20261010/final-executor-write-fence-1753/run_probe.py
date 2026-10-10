import hashlib
import json
import subprocess
import uuid
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
lab = json.loads((ROOT / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
def docker(*args):
    return subprocess.check_output(['docker', '--context', lab['context'], *args], text=True).strip()
item = json.loads(docker('inspect', lab['name']))[0]
assert item['Id'] == lab['container_id'] and item['Image'] == lab['image'] and item['State']['Running']
token = uuid.uuid4().hex
schema = 'test_final_fence_' + token
library = '/tmp/aos_final_fence_' + token + '.so'
container = 'aos-final-fence-artifact-' + token
image = docker('image', 'inspect', 'aos-final-executor-fence-1753:probe', '--format', '{{.Id}}')
with (OUT / 'attempt.json').open('x') as file:
    json.dump({'schema': schema, 'library': library, 'image': image, 'artifact_container': container,
               'database': 'aos_test_05f1a1dcd51f_ti4_test', 'effects': 'rollback-only owned SQL/epoch probes'}, file)
docker('create', '--name', container, image)
docker('cp', container + ':/aos_final_fence_probe.so', str(OUT / 'probe.so'))
docker('cp', str(OUT / 'probe.so'), lab['name'] + ':' + library)
ids = {name: 'final-fence-' + token + '-' + name for name in ('existing', 'missing', 'cte', 'after')}
signature = 'public.aos_capacity_evidence_epoch_lock(text,text,text)'
metadata = 'SELECT prosrc,proacl::text,pg_get_userbyid(proowner),proconfig FROM pg_proc WHERE oid=%s::regprocedure'
connection = dict(host='127.0.0.1', port=lab['port'], user='aos_app',
                  dbname='aos_test_05f1a1dcd51f_ti4_test', passfile=lab['passfile'])
proof = {}
with psycopg.connect(**connection) as conn:
    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
    assert conn.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0] == lab['cluster']
    before = conn.execute(metadata, (signature,)).fetchone()
    xid = conn.execute('SELECT pg_current_xact_id()::text').fetchone()[0]
    conn.execute(sql.SQL('CREATE SCHEMA {} AUTHORIZATION aos_app').format(sql.Identifier(schema)))
    conn.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(schema)))
    conn.execute(sql.SQL("CREATE FUNCTION {}.probe(text,boolean) RETURNS bigint LANGUAGE C VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS {},'probe_final_epoch'").format(sql.Identifier(schema), sql.Literal(library)))
    conn.execute(sql.SQL('REVOKE ALL ON FUNCTION {}.probe(text,boolean) FROM PUBLIC,aos_runtime').format(sql.Identifier(schema)))
    probe = sql.SQL('SELECT {}.probe(%s,%s)').format(sql.Identifier(schema))
    try:
        with conn.transaction():
            conn.execute(probe, (ids['missing'], False))
    except psycopg.Error as error:
        assert 'TEST_ONLY_FINAL_FENCE_ADMIN_REQUIRED' in str(error)
        proof['missing_guc_denied'] = True
    else:
        raise AssertionError('Missing scope was admitted')
    conn.execute("SET LOCAL aos.org_id='org-org'")
    conn.execute("SET LOCAL aos.project_id='dev-project'")
    for name in ('existing',):
        assert conn.execute('SELECT public.aos_capacity_evidence_epoch_lock(%s,%s,%s)', ('org-org', 'dev-project', ids[name])).fetchone()[0] == 0
    baseline = conn.execute("SELECT n_tup_ins FROM pg_stat_xact_user_tables WHERE relid='public.aip_capacity_evidence_epoch'::regclass").fetchone()[0]
    assert conn.execute(probe, (ids['existing'], False)).fetchone()[0] == 0
    proof['guarded_existing_epoch_passed'] = True
    for name, modifying_cte in (('missing', False), ('cte', True)):
        try:
            with conn.transaction():
                conn.execute(probe, (ids[name], modifying_cte))
        except psycopg.Error as error:
            assert error.sqlstate == '25006' and 'FINAL_VALIDATION_NESTED_WRITE_FORBIDDEN' in str(error)
            proof[name + '_write_rejected'] = error.sqlstate
        else:
            raise AssertionError(name + ' was admitted')
        assert conn.execute('SELECT count(*) FROM public.aip_capacity_evidence_epoch WHERE bundle_id=%s', (ids[name],)).fetchone()[0] == 0
    assert conn.execute("SELECT n_tup_ins FROM pg_stat_xact_user_tables WHERE relid='public.aip_capacity_evidence_epoch'::regclass").fetchone()[0] == baseline
    proof['guarded_insert_statistics_delta'] = 0
    assert conn.execute('SELECT public.aos_capacity_evidence_epoch_lock(%s,%s,%s)', ('org-org', 'dev-project', ids['after'])).fetchone()[0] == 0
    assert conn.execute('SELECT count(*) FROM public.aip_capacity_evidence_epoch WHERE bundle_id=%s', (ids['after'],)).fetchone()[0] == 1
    proof['ordinary_writer_after_error_passed'] = True
    assert conn.execute(probe, (ids['existing'], False)).fetchone()[0] == 0
    proof['guard_restored_and_reentrant_after_error'] = True
    assert conn.execute(metadata, (signature,)).fetchone() == before
    conn.rollback()
with psycopg.connect(**connection) as readback:
    readback.execute('SET TRANSACTION READ ONLY')
    assert readback.execute(metadata, (signature,)).fetchone() == before
    assert readback.execute('SELECT count(*) FROM public.aip_capacity_evidence_epoch WHERE bundle_id=ANY(%s)', (list(ids.values()),)).fetchone()[0] == 0
    assert readback.execute('SELECT to_regnamespace(%s)', (schema,)).fetchone()[0] is None
    assert readback.execute('SELECT pg_xact_status(%s::xid8)', (xid,)).fetchone()[0] == 'aborted'
    readback.rollback()
report = {'status': 'NATIVE_FIXED_EXECUTOR_WRITE_FENCE_COMPONENT_GREEN_FULL_VALIDATOR_PENDING',
          'authority': 'AOS-001753', 'task': 'gt-shared-parent-atomic-admission-finalizer-20261010',
          'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'proof': proof, 'xid': xid, 'independent_xid_status': 'aborted',
          'independent_all_probe_rows_and_schema_absent': True,
          'original_epoch_body_acl_owner_unchanged': True,
          'binary_sha256': hashlib.sha256((OUT / 'probe.so').read_bytes()).hexdigest(),
          'source_sha256': hashlib.sha256((OUT / 'probe.c').read_bytes()).hexdigest(),
          'library': library, 'artifact_image': image,
          'limitations': ['Executor hook test only: utilities and native direct effects not covered.',
                         'Existing hook ownership/chain and immutable loaded-package closure still required.',
                         'No full Source invocation, all-eight-node Receipt, final clock/native event/RI or actual COMMIT positive.'],
          'full_task_delivered': False, 'goal_complete': False, 'execution_allowed': False}
(OUT / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'proof': proof, 'rollback_independently_verified': True}))
