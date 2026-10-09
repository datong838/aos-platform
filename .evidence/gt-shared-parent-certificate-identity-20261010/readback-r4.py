"""Independent native metadata and risk reconciliation, READ ONLY."""
from pathlib import Path
import json,os,hashlib
import psycopg
from psycopg.rows import dict_row
E=Path(__file__).resolve().parent;R=E.parents[1];B=E/'native-r4'
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());result=json.loads((B/'result-r4.json').read_text());assert result['pytest_exit']==0 and result['old_files_unchanged']
p=json.loads((B/'native-description-proof.json').read_text());n=json.loads((B/'native-identity-proof.json').read_text())
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=result['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY')
 i=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert i['cluster']==lab['cluster'] and i['readonly']=='on'
 statuses={k:c.execute('SELECT pg_xact_status(%s::xid8) AS status',(v,)).fetchone()['status'] for k,v in dict(metadata=n['producer_xid'],risk=p['xid'],wait=n['actual_wait']['caller_xid']).items()}
 assert statuses==dict(metadata='committed',risk='aborted',wait='aborted')
 counts={x:c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+x).fetchone()['n'] for x in ('prepared_plan_risk','prepared_shared_risk_description','prepared_parent_debit','prepared_execution_intent')};assert set(counts.values())=={0}
 meta={x:c.execute('SELECT count(*) AS n FROM aos_model_eval_issuer_private.'+x).fetchone()['n'] for x in ('issuer_root','executor_certificate','certificate_epoch','identity_epoch','shared_parent_certificate_identity_binding','certificate_identity_binding','identity_withdrawal')}
 assert meta['issuer_root']==1 and meta['executor_certificate']==4 and meta['shared_parent_certificate_identity_binding']==4 and meta['certificate_identity_binding']==0 and meta['identity_withdrawal']==0
 function=c.execute("SELECT prosrc,pg_get_userbyid(proowner) AS owner,prosecdef,proconfig FROM pg_proc WHERE oid='aos_model_eval_issuer_private.derive_shared_parent_identity()'::regprocedure").fetchone()
 function['body_hash']=hashlib.sha256(function.pop('prosrc').encode()).hexdigest()
 assert function['owner']=='aos_model_eval_issuer_owner' and function['prosecdef'] is False and function['proconfig']==['search_path=pg_catalog']
 acl=c.execute("SELECT has_table_privilege('aos_runtime','aos_model_eval_issuer_private.shared_parent_certificate_identity_binding','SELECT') AS read,has_table_privilege('aos_runtime','aos_model_eval_issuer_private.shared_parent_certificate_identity_binding','INSERT') AS write").fetchone();assert not any(acl.values())
 source=c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.source_publication').fetchone()['n'];assert source==1
 match=all(hashlib.sha256((R/file).read_bytes()).hexdigest()==sha for file,sha in result['file_hashes'].items());assert match
 out=dict(identity=i,statuses=statuses,risk_counts=counts,metadata_counts=meta,function=function,runtime_access=acl,source=source,frozen_product_hashes_match=match,root_provenance_verified=False,physical_description_origin_authenticated=False,execution_allowed=False,full_task_delivered=False,historical_fixture_restored=False)
(E/'independent-readback-r4.json').open('x').write(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
