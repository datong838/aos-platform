"""Fresh independent SERIAL READ ONLY observation of both lock experiments."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

base=Path(__file__).resolve().parent
snapshot=json.loads((base/'snapshot-lock-verification.json').read_text())
upgrade=json.loads((base/'upgrade-lock-verification.json').read_text())
assert snapshot['database']==upgrade['database']=='aos_test_snapshot_lock_9314bde51c58'
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
for key in ('PGPASSWORD','PGPASSFILE','PGOPTIONS','PGSERVICE','PGSERVICEFILE'):
    os.environ.pop(key,None)
observations={}
for database in (snapshot['database'],snapshot['template']):
    with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=database,
        passfile=str(passfile),row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        identity=c.execute("SELECT current_database() AS database,current_setting('transaction_read_only') AS readonly,system_identifier::text AS cluster FROM pg_control_system()").fetchone()
        assert identity==dict(database=database,readonly='on',cluster=snapshot['cluster'])
        counts={t:c.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(t))).fetchone()['n']
            for t in ('aip_agent_run','aip_model_capacity_reservation','aip_model_capacity_event')}
        assert not any(counts.values())
        heads=c.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()
        assert heads==snapshot['migration_heads']
        item=dict(identity=identity,counts=counts,heads=heads)
        if database==snapshot['database']:
            rows=c.execute('SELECT case_id,count(*) AS n,sum(units) AS units FROM gt_snapshot_probe.obligation GROUP BY case_id ORDER BY case_id').fetchall()
            assert rows==[dict(case_id=name,n=1,units=1) for name in ('advisory_only','row_lock_unchanged','versioned_row_update')]
            guards=c.execute('SELECT case_id,epoch FROM gt_snapshot_probe.guard ORDER BY case_id').fetchall()
            assert guards==[dict(case_id=name,epoch=epoch) for name,epoch in (
                ('advisory_only',0),('row_lock_unchanged',0),('share_to_update',1),('versioned_row_update',1))]
            canary=c.execute("SELECT count(*) AS n FROM gt_snapshot_probe.obligation WHERE org_id='dev-org'").fetchone()['n']
            assert canary==0
            item.update(rows=rows,guard_rows=guards,canary=canary)
        else:
            assert c.execute("SELECT to_regnamespace('gt_snapshot_probe') AS schema").fetchone()['schema'] is None
        observations[database]=item
names=['snapshot_lock_probe.py','upgrade_lock_probe.py','verify_lock_probes.py',
    'snapshot-lock-verification.json','upgrade-lock-verification.json','snapshot-lock-r1.log','upgrade-lock-r1.log']
result=dict(status='LOCK_PRIMITIVE_DURABLE_STATE_INDEPENDENTLY_VERIFIED',databases=observations,
    file_sha256={name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in names},
    limitations=['Native blocking pids, stale reads and 40001/40P01 are original live-run observations',
        'Independent read proves final retained state only; no claim of original joint business authority'])
(base/'lock-probes-independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],'3 committed primitive rows; upgrade epoch1; template unchanged; AgentRun=0 canary=0')
