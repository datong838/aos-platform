from pathlib import Path
import json,os,psycopg,hashlib
from psycopg.rows import dict_row
B=Path('.evidence/gt-shared-parent-native-certificate-prepare-20261010');lab=json.loads(Path('.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
for r in (17,18):
 N=B/f'native-r{r}';a=json.loads((N/f'result-r{r}.json').read_text());assert a['pytest_exit']==1
 with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=a['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
  c.execute('SET TRANSACTION READ ONLY');identity=c.execute('SELECT current_database() AS database,system_identifier::text AS cluster FROM pg_control_system()').fetchone();assert identity['cluster']==lab['cluster']
  risk={t:c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+t).fetchone()['n'] if c.execute('SELECT to_regclass(%s) AS t',('aos_physical_capacity_occupation_private.'+t,)).fetchone()['t'] else None for t in ['prepared_plan_risk','prepared_shared_risk_description','prepared_parent_debit','prepared_execution_intent']};assert all(v in (None,0) for v in risk.values())
  counts={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in ['aos_model_eval_execution_private.manifest','aos_model_eval_issuer_private.executor_certificate','aos_model_eval_issuer_private.identity_epoch','aos_model_eval_issuer_private.identity_withdrawal']}
  published=None
  if (N/'published-identity-withdrawal.json').exists():
   p=json.loads((N/'published-identity-withdrawal.json').read_text());statuses={k:c.execute('SELECT pg_xact_status(%s::xid8) AS s',(p[k],)).fetchone()['s'] for k in ['identity_xid','withdrawal_xid']};assert set(statuses.values())=={'committed'}
   head=dict(c.execute("SELECT epoch,version,active FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id='target-identity'").fetchone());assert head==p['after']==dict(epoch=2,version=2,active=False)
   published=dict(statuses=statuses,head=head);assert set(counts.values())=={1}
  else:assert set(counts.values())=={0}
  (B/f'withdrawal-failure-readback-r{r}.json').open('x').write(json.dumps(dict(identity=identity,read_only=True,risk_counts=risk,metadata_counts=counts,published=published,whole_node_passed=False,withdrawal_v3_verified=False,execution_allowed=False),indent=2)+'\n')
print('known failed experiments reconciled; original metadata retained')
