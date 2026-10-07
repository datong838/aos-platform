"""Independent native read-only verification of retained legacy counterexample."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

base = Path(__file__).resolve().parent
record = json.loads((base / 'legacy-ttl-r2.json').read_text())
passfile = Path(tempfile.gettempdir()) / 'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
for key in ('PGPASSWORD','PGOPTIONS','PGSERVICE','PGSERVICEFILE'):
    os.environ.pop(key, None)
os.environ['PGPASSFILE'] = str(passfile)
verified = {}
for database in (record['database'], record['template']):
    assert database.startswith('aos_test_') and database.replace('_','').isalnum()
    with psycopg.connect(f'postgresql://aos_app@127.0.0.1:5434/{database}', row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert str(conn.execute('SELECT system_identifier FROM pg_control_system()').fetchone()['system_identifier']) == record['cluster']
        heads = conn.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()
        assert heads == record['template_heads']
        counts = {}
        for table in ('aip_model_capacity_reservation','aip_model_capacity_event','aip_agent_run'):
            counts[table] = conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(table))).fetchone()['n']
        if database == record['template']:
            assert set(counts.values()) == {0}
        else:
            assert counts == dict(aip_model_capacity_reservation=4,aip_model_capacity_event=7,aip_agent_run=0)
            for case in record['observations']:
                assert case['before']['expired'] and case['before']['status'] == case['initial']
                for expected in case['rows']:
                    actual = conn.execute('SELECT status,expires_at FROM aip_model_capacity_reservation WHERE reservation_id=%s', (expected['reservation_id'],)).fetchone()
                    assert actual['status'] == expected['status'] and str(actual['expires_at']) == expected['expires_at']
                expiry = conn.execute('''SELECT bool_and(e.occurred_at >= r.expires_at) AS valid
                    FROM aip_model_capacity_event e JOIN aip_model_capacity_reservation r
                    USING(org_id,project_id,reservation_id) WHERE e.event_type='expired' ''').fetchone()['valid']
                assert expiry is True
            assert conn.execute("SELECT count(*) AS n FROM aip_model_capacity_reservation WHERE org_id='dev-org'").fetchone()['n'] == 0
        verified[database] = dict(heads=heads,counts=counts)
result = dict(status='NATIVE_READ_ONLY_VERIFIED', databases=verified,
    log_sha256=hashlib.sha256((base/'legacy-ttl-r2.log').read_bytes()).hexdigest(),
    record_sha256=hashlib.sha256((base/'legacy-ttl-r2.json').read_bytes()).hexdigest(),
    business_admission_proven=False,unknown_agent_run_pg_proven=False)
(base/'legacy-ttl-independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'], 'reservations=4 events=7 AgentRun=0 canary=0 template unchanged')
