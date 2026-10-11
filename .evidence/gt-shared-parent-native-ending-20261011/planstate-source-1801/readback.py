import hashlib
import json
import subprocess
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

B = Path(__file__).resolve().parent
R = B.parents[2]
run = json.loads((B / 'result-r2.json').read_text())
assert run['pytest_exit'] == 0 and len(run['databases']) == 1
oids = json.loads((B / 'observed-oids.json').read_text())
assert oids and all(isinstance(i, int) and 0 < i < 2147483647 for i in oids)
lab = json.loads((R / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
c = json.loads(subprocess.check_output(['docker', '--context', lab['context'], 'inspect', lab['name']], text=True))[0]
assert c['Id'] == lab['container_id'] and c['Image'] == lab['image'] and c['State']['Running']
cleanup = json.loads((B / 'cleanup-proof.json').read_text())
previous = json.loads((B.parent / 'fixed-collector-source-1792-r2/independent-readback.json').read_text())
with psycopg.connect(host='127.0.0.1', port=lab['port'], user='aos_app',
                     dbname=run['databases'][0], passfile=lab['passfile'], row_factory=dict_row) as conn:
    conn.execute('BEGIN READ ONLY')
    assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == lab['cluster']
    assert conn.execute('SELECT pg_xact_status(%s::xid8) AS state', (cleanup['caller']['xid'],)).fetchone()['state'] == 'aborted'
    counts = {t: conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(*t.split('.')))).fetchone()['n'] for t in previous['table_counts']}
    assert not any(counts.values())
    assert conn.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend'").fetchone()['n'] == 0
    rows = conn.execute("""SELECT p.oid,p.oid::regprocedure::text AS signature,l.lanname AS language,
        p.proowner::regrole::text AS owner,p.provolatile,p.prosecdef,p.proconfig,
        p.prosupport::text AS support,p.prosrc,p.probin FROM pg_proc p
        JOIN pg_language l ON l.oid=p.prolang WHERE p.oid=ANY(%s::oid[]) ORDER BY p.oid""", (oids,)).fetchall()
    assert len(rows) == len(oids)
    for row in rows:
        row['source_sha256'] = hashlib.sha256(row.pop('prosrc').encode()).hexdigest()
    settings = conn.execute('SELECT setconfig FROM pg_db_role_setting WHERE setdatabase=(SELECT oid FROM pg_database WHERE datname=current_database()) AND setrole=0').fetchone()
    assert not settings or not any(v.startswith('track_functions=') for v in settings['setconfig'])
    conn.rollback()
result = dict(database=run['databases'][0], xid=cleanup['caller']['xid'], xid_aborted=True,
              table_counts=counts, other_clients=0, profile_reset=True, observed_functions=rows,
              observed_function_count=len(rows), full_closure=False, execution_allowed=False)
(B / 'independent-readback.json').open('x').write(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k not in ('observed_functions', 'table_counts')}))
