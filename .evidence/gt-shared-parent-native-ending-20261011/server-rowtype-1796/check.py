"""Compile the existing isolated function without invoking its business body."""
import hashlib
import json
import subprocess
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

B = Path(__file__).resolve().parent
R = B.parents[2]
lab = json.loads((R / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
c = json.loads(subprocess.check_output(['docker', '--context', lab['context'], 'inspect', lab['name']], text=True))[0]
assert c['Id'] == lab['container_id'] and c['Image'] == lab['image'] and c['State']['Running']
signature = 'public.build_shared_parent_admission_origin(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text)'
with psycopg.connect(host='127.0.0.1', port=lab['port'], user='aos_app',
                     dbname='aos_test_2687abc41131_ti4_test', passfile=lab['passfile'],
                     row_factory=dict_row) as conn:
    conn.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == lab['cluster']
    version = conn.execute('SHOW server_version_num').fetchone()['server_version_num']
    assert int(version) // 10000 == 16
    f = conn.execute('SELECT oid,pg_get_functiondef(oid) AS body FROM pg_proc WHERE oid=to_regprocedure(%s)', (signature,)).fetchone()
    assert f and 'prepared_plan_risk%ROWTYPE' in f['body']
    fields = conn.execute("""SELECT attnum,attname,format_type(atttypid,atttypmod) AS type
        FROM pg_attribute WHERE attrelid='aos_physical_capacity_occupation_private.prepared_plan_risk'::regclass
        AND attnum>0 AND NOT attisdropped ORDER BY attnum""").fetchall()
    shape = {r['attname']: r['type'] for r in fields}
    assert shape['immutable'] == 'jsonb' and shape['content_hash'] == 'text'
    assert shape['target_request'] == 'text' and shape['judge_request'] == 'text'
    before = conn.execute("SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.prepared_plan_risk").fetchone()['n']
    conn.execute('SET LOCAL check_function_bodies=on')
    conn.execute('SELECT pg_catalog.plpgsql_validator(%s::oid)', (f['oid'],)).fetchone()
    after = conn.execute("SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.prepared_plan_risk").fetchone()['n']
    assert before == after == 0
    assert conn.execute('SELECT pg_get_functiondef(%s::oid) AS body', (f['oid'],)).fetchone()['body'] == f['body']
    conn.rollback()
result = dict(server_version_num=version, cluster=lab['cluster'], signature=signature,
              body_sha256=hashlib.sha256(f['body'].encode()).hexdigest(), fields=fields,
              native_plpgsql_compilation=True, business_function_invoked=False,
              rowtype_binding=True, expressions_planned=False, runtime_closure=False,
              formal_root=False, execution_allowed=False)
(B / 'result.json').open('x').write(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'fields'}))
