from pathlib import Path
import sys,json,importlib.util,datetime,subprocess
R=Path.cwd();B=R/'.evidence/gt-shared-parent-native-certificate-prepare-20261010';C=Path('/Users/ddt/work/projects/ai_agent/docs/palantier/AOS项目开发上下文/memory')
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001689';owner='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2';expiry=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=2)).isoformat();records=[]
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008','gt-original-target-persisted-reader-20261010','gt-shared-parent-certificate-identity-20261010','gt-shared-description-origin-reader-20261010','gt-shared-parent-native-executor-set-20261010',B.name]
for task in tasks:
 t=json.loads((C/'receipts/tasks'/(task+'.json')).read_text());L=m.load_leases(m.DEFAULT_PATHS)['leases'];assert [x for x in L if x['task_id']==task]==[t];assert t['owner']==owner and t['status']=='ACTIVE';assert not (C/'receipts/deliveries'/(task+'.json')).exists()
 assert not any(x['task_id']!=task and m.scopes_overlap(t['scope'],x['scope']) for x in L)
 renewed=m.renew_task(m.DEFAULT_PATHS,task_id=task,owner=owner,expected_revision=a['project_revision'],expected_task=t,lease_expires_at=expiry,reconciliation='Unique writer m1 6451bae; R23 and R24 terminal FAIL, R24 original replay conflict under investigation. All original protected file hashes unchanged. No second native run or unknown effect replay; same Task scopes/owner checked against all leases.')
 records.append(dict(task_id=task,before=t['lease_expires_at'],after=renewed['lease_expires_at']))
 (R/'.evidence'/task/'lease-renewal-reference-1689-combined.json').write_text(json.dumps(dict(authority='AOS-001689',task=renewed,execution_allowed=False),indent=2)+'\n')
(B/'lease-renewal-1689-combined.json').open('x').write(json.dumps(dict(authority='AOS-001689',records=records,same_owner=True,no_scope_overlap=True,execution_allowed=False),indent=2)+'\n');print(json.dumps(dict(renewed=len(records),expiry=expiry,authority='AOS-001689')))
