from pathlib import Path
import json,os,hashlib,psycopg
from psycopg.rows import dict_row
R=Path.cwd();B=R/'.evidence/gt-shared-parent-native-certificate-prepare-20261010';N=B/'native-r25';r=json.loads((N/'result-r25.json').read_text());assert r['pytest_exit']==1 and r['old_files_unchanged'];lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=r['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert identity['cluster']==lab['cluster'] and identity['readonly']=='on'
 tables=['aos_physical_capacity_occupation_private.'+t for t in ['account_guard','prepared_parent_debit','case_input_binding','prepared_execution_intent','prepared_judge_intent','prepared_plan_risk','prepared_shared_risk_description','prepared_call_occupation','call_occupation','call_occupation_event']]+['aos_model_eval_issuer_private.issuer_root','aos_model_eval_issuer_private.executor_certificate','aos_model_eval_issuer_private.shared_parent_certificate_identity_binding','aos_model_eval_execution_private.manifest'];counts={}
 for table in tables:
  present=c.execute('SELECT to_regclass(%s) IS NOT NULL AS p',(table,)).fetchone()['p'];counts[table]=c.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] if present else None
 assert all(v in (None,0) for k,v in counts.items() if not k.endswith('issuer_root'));assert counts['aos_model_eval_issuer_private.issuer_root']==1
 hashes={p:hashlib.sha256((R/p).read_bytes()).hexdigest()==h for p,h in r['file_hashes'].items()};assert all(hashes.values())
 out=dict(identity=identity,failure='runtime direct schema-qualified SET CONSTRAINTS denied 42501; expected exception in test was too narrow',counts=counts,all_existing_risk_metadata_rows_zero_except_prepublished_root=True,combined_installation_reached=True,current_frozen_source_hashes=hashes,replayed=False,execution_allowed=False)
 (B/'independent-combined-r25-failure.json').open('x').write(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(database=identity['database'],all_existing_risk_metadata_rows_zero_except_prepublished_root=True,combined_installation_reached=True)))
