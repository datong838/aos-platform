from pathlib import Path
import json,hashlib,os,subprocess
import psycopg
from psycopg.rows import dict_row
from psycopg import sql
B=Path(__file__).resolve().parent;R=B.parents[1]
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
c=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['name']],text=True))[0]
assert c['Id']==lab['container_id'] and c['State']['Running']
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
result=json.loads((B/'worker-commit-result-1696-r2.json').read_text());assert result['pytest_exit']==0
proof=json.loads((B/'worker-commit-proof-1696-r2.json').read_text());assert len(proof)==2
observations=[]
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=result['database'],passfile=lab['passfile'],row_factory=dict_row) as conn:
 conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 cluster=conn.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster'];assert cluster==lab['cluster']
 for case in proof:
  conn.execute(sql.SQL('SET LOCAL search_path TO {},public').format(sql.Identifier(case['schema'])))
  row=conn.execute('SELECT state,provider_request_receipt_ref,xmin::text AS xmin,pg_xact_status(xmin::text::xid8) AS origin_state FROM aip_budget_reservation WHERE reservation_id=%s',(case['reservation_id'],)).fetchone()
  buckets=conn.execute('SELECT held_minor,submitted_minor,unknown_minor FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s ORDER BY bucket_kind',('org-org','dev-project')).fetchall()
  assert dict(row)==case['after']['reservation'] and [dict(x) for x in buckets]==case['after']['buckets']
  canary=conn.execute('SELECT count(*) AS n FROM aip_budget_reservation WHERE org_id=%s',('dev-org',)).fetchone()['n'];assert canary==0
  observations.append(dict(outcome=case['outcome'],reservation=dict(row),buckets=[dict(x) for x in buckets],canary_reservations=canary))
 conn.rollback()
bind=json.loads((B/'worker-commit-source-binding-1696.json').read_text());assert all(hashlib.sha256((R/p).read_bytes()).hexdigest()==h for p,h in bind.items())
logs={n:hashlib.sha256((B/n).read_bytes()).hexdigest() for n in ('worker-commit-1696.local.log','worker-commit-1696-r2.local.log')}
(B/'worker-commit-independent-1696.json').open('x').write(json.dumps(dict(cluster=cluster,database=result['database'],readonly=True,observations=observations,source_hashes_unchanged=True,log_sha256=logs,real_provider_calls=0,full_joint_pass=False,execution_allowed=False),indent=2)+'\n')
print('independent risk readback PASS; product sources unchanged')
