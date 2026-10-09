"""Next registered wave: current owned-lab issuer origins, read-only only."""
from pathlib import Path
import json,os,hashlib,subprocess
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[1]
N=R/'.evidence/gt-atomic-model-admission-20261008/shared-parent-certificate-native-1673-r3'
result=json.loads((N/'result-r3.json').read_text());lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=result['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY')
 i=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert i['cluster']==lab['cluster'] and i['readonly']=='on'
 tables=c.execute("SELECT tablename FROM pg_tables WHERE schemaname='aos_model_eval_issuer_private' ORDER BY tablename").fetchall()
 counts={x['tablename']:c.execute(psycopg.sql.SQL('SELECT count(*) AS n FROM {}.{}').format(psycopg.sql.Identifier('aos_model_eval_issuer_private'),psycopg.sql.Identifier(x['tablename']))).fetchone()['n'] for x in tables}
 body=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-001674',identity=i,issuer_table_counts=counts,
 signed_certificates_in_evidence=4,descriptive_signatures_do_not_establish_persisted_root=True,
 root_provenance_verified=False,issuer_metadata_current=False,execution_allowed=False,
 next_required='Independent v3 identity binding and original persisted issuer/certificate/withdrawal current-head reconciliation; lab roots do not confer production trust')
(B/'shared-certificate-issuer-origin-audit-1674.json').open('x').write(json.dumps(body,indent=2)+'\n')
print(json.dumps(body))
