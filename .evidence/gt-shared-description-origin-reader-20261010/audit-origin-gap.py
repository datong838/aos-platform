from pathlib import Path
import json,os,hashlib,ast
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[1]
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
old=R/'.evidence/gt-shared-parent-certificate-identity-20261010'
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
n=json.loads((old/'native-r6/result-r6.json').read_text());assert n['pytest_exit']==0
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=n['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY')
 identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert identity['cluster']==lab['cluster'] and identity['readonly']=='on'
 risk={t:c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+t).fetchone()['n'] for t in ['prepared_plan_risk','prepared_shared_risk_description']};assert set(risk.values())=={0}
 cert=c.execute('SELECT count(*) AS n FROM aos_model_eval_issuer_private.shared_parent_certificate_identity_binding').fetchone()['n'];assert cert==4
 roots=c.execute("SELECT bootstrap_hash,count(*) AS n FROM aos_model_eval_issuer_private.issuer_root GROUP BY bootstrap_hash ORDER BY bootstrap_hash").fetchall()
 constraints=c.execute("SELECT conname,contype,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conrelid='aos_model_eval_issuer_private.issuer_root'::regclass ORDER BY conname").fetchall()
 assert not any(x['contype']=='f' for x in constraints)
 funcs=c.execute("SELECT proname,pg_get_userbyid(proowner) AS owner,prosecdef,prosrc FROM pg_proc WHERE proname='prepare_capacity_shared_risk_description'").fetchall();assert len(funcs)==1
 f=funcs[0];body=f.pop('prosrc');f['body_hash']=hashlib.sha256(body.encode()).hexdigest();f['inserts_description']='INSERT INTO aos_physical_capacity_occupation_private.prepared_shared_risk_description' in body;assert f['inserts_description']
 missing=c.execute("SELECT count(*) AS n FROM pg_proc WHERE proname='read_capacity_shared_risk_description_origin'").fetchone()['n'];assert missing==0
 acl=c.execute("SELECT has_table_privilege('aos_runtime','aos_physical_capacity_occupation_private.prepared_shared_risk_description','SELECT') AS direct_read,has_table_privilege('aos_runtime','aos_physical_capacity_occupation_private.prepared_shared_risk_description','INSERT') AS direct_insert").fetchone();assert not any(acl.values())
 product=R/'services/aos-api/aos_api/aip_shared_parent_description_origin_reader.py';assert not product.exists()
 out=dict(identity=identity,prepared_rows=risk,committed_identity_bindings=cert,root_bootstrap_groups=roots,root_constraints=constraints,existing_producer=f,origin_reader_count=missing,runtime_direct_access=acl,red_reason='NO_READONLY_NATIVE_DESCRIPTION_ORIGIN_ENTRY',root_provenance_verified=False,physical_description_origin_authenticated=False,execution_allowed=False,full_task_delivered=False)
(B/'origin-gap-red.json').open('x').write(json.dumps(out,indent=2)+'\n')
print('Native READ ONLY gap confirmed: risk/description=0, identity=4; producer writes; origin-reader absent; runtime table access denied')
