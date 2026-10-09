from pathlib import Path
import importlib.util,sys,json
from datetime import datetime,timezone,timedelta
E=Path(__file__).resolve().parent;R=E.parents[1]
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001674'
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008','gt-original-target-persisted-reader-20261010','gt-shared-parent-certificate-identity-20261010']
expiry=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat();out=[]
for task in tasks:
 receipt=m.read_json(m.DEFAULT_PATHS.receipts_path/'tasks'/f'{task}.json')
 assert receipt['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and receipt['status']=='ACTIVE'
 assert [x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']==task]==[receipt]
 assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{task}.json').exists()
 new=m.renew_task(m.DEFAULT_PATHS,task_id=task,owner=receipt['owner'],expected_revision=a['project_revision'],expected_task=receipt,lease_expires_at=expiry,reconciliation='Unique m1 writer/head7f1d67e9d, no other active agent. Previous v3 signature wave committed; owned native identity R1/R2 terminal failures independently zero-reconciled, R3 metadata COMMITTED/risk and waiting reader ABORTED with frozen hashes and old files unchanged. R4 expanded native test has live original handle; no unknown effects retried or leases removed. Formal DB read-only, no Provider. Same-owner continuation only.')
 out.append(dict(task_id=task,before=receipt['lease_expires_at'],after=new['lease_expires_at']))
(E/'lease-renewal.json').open('x').write(json.dumps(dict(authority_revision=a['project_revision'],renewals=out,no_scope_changes=True),indent=2)+'\n')
print('Same-owner renewals:',len(out))
