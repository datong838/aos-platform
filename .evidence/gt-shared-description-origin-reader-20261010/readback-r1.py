from pathlib import Path
import json,os,sys,hashlib
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[1];N=B/'native-r1'
sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_shared_parent_description_origin_reader import FUNCTION,shared_description_origin_statements,OWNER
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
result=json.loads((N/'result-r1.json').read_text());assert result['pytest_exit']==0 and result['old_files_unchanged']
p=json.loads((N/'native-description-proof.json').read_text());o=json.loads((N/'native-origin-reader-proof.json').read_text())
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=result['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY')
 identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert identity['cluster']==lab['cluster'] and identity['readonly']=='on'
 status=c.execute('SELECT pg_xact_status(%s::xid8) AS status',(p['xid'],)).fetchone()['status'];assert status=='aborted'
 counts={t:c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+t).fetchone()['n'] for t in ['prepared_plan_risk','prepared_shared_risk_description','prepared_parent_debit','prepared_execution_intent']};assert set(counts.values())=={0}
 f=c.execute('SELECT prosrc,prosecdef,proconfig,pg_get_userbyid(proowner) AS owner FROM pg_proc WHERE oid=%s::regprocedure',(FUNCTION,)).fetchone()
 expected=shared_description_origin_statements()[0].split('AS $origin$')[1].split('END $origin$')[0]+'END '
 assert f['prosrc']==expected and f['owner']==OWNER and f['prosecdef'] and f['proconfig']==['search_path=pg_catalog']
 f['body_hash']=hashlib.sha256(f.pop('prosrc').encode()).hexdigest()
 public=c.execute("SELECT count(*) AS n FROM pg_proc p,LATERAL aclexplode(p.proacl) x WHERE p.oid=%s::regprocedure AND x.grantee=0 AND x.privilege_type='EXECUTE'",(FUNCTION,)).fetchone()['n'];assert public==0
 acl=c.execute("SELECT has_table_privilege('aos_runtime','aos_physical_capacity_occupation_private.prepared_shared_risk_description','SELECT') AS read,has_table_privilege('aos_runtime','aos_physical_capacity_occupation_private.prepared_shared_risk_description','INSERT') AS write").fetchone();assert not any(acl.values())
 source=c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.source_publication').fetchone()['n'];assert source==1
 hashes=all(hashlib.sha256((R/p).read_bytes()).hexdigest()==h for p,h in result['file_hashes'].items());assert hashes
 out=dict(identity=identity,original_xid_status=status,risk_counts=counts,function=f,public_execute=public,runtime_table_access=acl,source=source,frozen_hashes_match=hashes,original_native_row_observed=o['exact_original_row'],root_provenance_verified=False,identity_same_caller_verified=False,execution_allowed=False,full_task_delivered=False,historical_fixture_restored=False)
(B/'independent-readback-r1.json').open('x').write(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
