from pathlib import Path
import json,os
import psycopg
from psycopg.rows import dict_row
E=Path(__file__).resolve().parent;R=E.parents[1]
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
for label in ('r1','r2'):
 B=E/('native-'+label);result=json.loads((B/('result-'+label+'.json')).read_text());assert result['pytest_exit']==1 and result['old_files_unchanged']
 with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=result['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
  c.execute('SET TRANSACTION READ ONLY')
  i=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert i['cluster']==lab['cluster']
  counts={}
  for relation in ('aos_physical_capacity_occupation_private.prepared_plan_risk','aos_physical_capacity_occupation_private.prepared_shared_risk_description','aos_physical_capacity_occupation_private.prepared_parent_debit','aos_physical_capacity_occupation_private.prepared_execution_intent','aos_model_eval_issuer_private.issuer_root','aos_model_eval_issuer_private.executor_certificate','aos_model_eval_issuer_private.identity_epoch','aos_model_eval_issuer_private.shared_parent_certificate_identity_binding'):
   exists=c.execute('SELECT to_regclass(%s)::text AS r',(relation,)).fetchone()['r']
   counts[relation]=None if exists is None else c.execute('SELECT count(*) AS n FROM '+relation).fetchone()['n']
  assert all(v is None or v==0 for v in counts.values())
  source=c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.source_publication').fetchone()['n'];assert source==1
  out=dict(identity=i,counts=counts,source=source,old_files_unchanged=True,whole_node_passed=False,execution_allowed=False)
  (B/'failure-independent-readback.json').open('x').write(json.dumps(out,indent=2)+'\n')
  print(label,'isolated Source1, prepared risk and issuer metadata absent/zero')
