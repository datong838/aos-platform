"""Read-only reconciliation after terminal native result; never retry effects."""
from pathlib import Path
import json, os, hashlib
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[2]
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
result=json.loads((B/'result-r3.json').read_text());assert result['pytest_exit']==0 and result['old_files_unchanged']
proof=json.loads((B/'native-description-proof.json').read_text());cert=json.loads((B/'native-certificate-proof.json').read_text())
assert len(cert['certificates'])==4 and proof['actual_commit_rejected']
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=result['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY')
 identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly,pg_xact_status(%s::xid8)::text AS status FROM pg_control_system()",(proof['xid'],)).fetchone()
 assert identity['cluster']==lab['cluster'] and identity['status']=='aborted'
 counts={n:c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+n).fetchone()['n'] for n in ('prepared_plan_risk','prepared_shared_risk_description','prepared_parent_debit','prepared_execution_intent')}
 assert set(counts.values())=={0}
 source=c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.source_publication').fetchone()['n'];assert source==1
 acl=c.execute("SELECT has_table_privilege('aos_runtime','aos_physical_capacity_occupation_private.prepared_shared_risk_description','SELECT') AS select_allowed,has_table_privilege('aos_runtime','aos_physical_capacity_occupation_private.prepared_shared_risk_description','INSERT') AS insert_allowed").fetchone();assert not any(acl.values())
 match=all(hashlib.sha256((R/p).read_bytes()).hexdigest()==sha for p,sha in result['file_hashes'].items());assert match
 output=dict(identity=identity,counts=counts,source=source,runtime_table_acl=acl,frozen_product_hashes_match=match,
 certificate_count=4,presented_root_only=True,issuer_metadata_current=False,executors_authenticated=False,
 historical_fixture_restored=False,execution_allowed=False,full_task_delivered=False)
(B/'independent-readback.json').open('x').write(json.dumps(output,indent=2)+'\n')
print(json.dumps(output))
