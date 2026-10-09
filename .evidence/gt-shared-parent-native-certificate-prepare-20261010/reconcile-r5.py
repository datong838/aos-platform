from pathlib import Path
import json,os,psycopg
from psycopg.rows import dict_row
R=Path.cwd();B=R/'.evidence/gt-shared-parent-native-certificate-prepare-20261010';lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname='aos_test_e0d5c979b7a1_ti4_test',passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 tables=['aos_capacity_publication_private.source_publication','aos_model_eval_issuer_private.issuer_root','aos_model_eval_issuer_private.executor_certificate','aos_model_eval_execution_private.manifest','aos_model_eval_issuer_private.shared_parent_certificate_identity_binding']
 counts={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in tables}
 out=dict(database=c.info.dbname,read_only=True,counts=counts,native_positive_verified=False,execution_allowed=False)
 (B/'failure-readback-r5.json').open('x').write(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
