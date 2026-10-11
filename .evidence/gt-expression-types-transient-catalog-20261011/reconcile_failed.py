import json
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg import sql
B=Path(__file__).resolve().parent; R=B.parents[1];lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text()); result=json.loads((B/'result-r2.json').read_text());previous=json.loads((R/'.evidence/gt-expression-types-full-source-20261011/r2/independent-readback.json').read_text())
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=result['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('BEGIN READ ONLY'); assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 counts={}
 for t in previous['table_counts']:
  exists=c.execute('SELECT to_regclass(%s) AS id',(t,)).fetchone()['id'];counts[t]=c.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(*t.split('.')))).fetchone()['n'] if exists else None
 other=c.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend'").fetchone()['n'];assert other==0
 config=c.execute('SELECT setconfig FROM pg_db_role_setting WHERE setdatabase=(SELECT oid FROM pg_database WHERE datname=current_database()) AND setrole=0').fetchone();assert not config or not any(v.startswith('track_functions=') for v in config['setconfig']);c.rollback()
(B/'r1-reconciliation.json').write_text(json.dumps({'database':result['databases'][0],'cluster':lab['cluster'],'pytest_exit':result['pytest_exit'],'failure':'Missing shared_identity_certificate_fixture','table_counts':counts,'missing_not_zero':True,'other_clients':other,'profile_reset':True,'old_source_replayed':False},indent=2)+'\n');print('FAILED_ATTEMPT_RECONCILED')
