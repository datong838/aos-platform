"""Independent readback of original drafts and exact receipt references."""
import hashlib,json
from pathlib import Path
import real_contract as C
from aos_api.aip_production_contract_store import AipProductionContractStore
R=C.R
first=json.loads((R/'impact-preview-business-result.json').read_text())
intent=json.loads((R/'impact-preview-intent.json').read_text())
assert intent['scriptHash']==hashlib.sha256((R/'real_impact_preview.py').read_bytes()).hexdigest()
store=AipProductionContractStore(lambda scope:C.runtime(scope,read_only=True))
for name in ['created','revised']:
 expected=first[name]
 actual=store.get_impact_preview(C.SCOPE,expected['previewId'],expected['revision']).model_dump(mode='json',by_alias=True)
 assert actual['version']==first['revised']['version']
 assert {k:v for k,v in actual.items() if k!='version'}=={k:v for k,v in expected.items() if k!='version'}
 assert actual['lifecycle']=='draft' and actual['readiness']!='ready' and actual['blockers']
 assert all(v['quality']=='unknown' and v['value'] is None for v in actual['impact'].values())
with C.runtime(C.SCOPE,read_only=True) as c:
 rows=c.execute("SELECT operation,idempotency_key,result_ref FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND idempotency_key IN ('qyh-impact-create','qyh-impact-revise') ORDER BY idempotency_key",C.SCOPE.key).fetchall()
 assert len(rows)==2
 for row,name in zip(rows,['created','revised']):
  x=first[name];assert row['result_ref']=={'resourceType':'ImpactPreviewRevision','resourceId':x['previewId'],'revision':x['revision'],'contentHash':x['contentHash']}
 assert c.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND idempotency_key IN ('qyh-impact-rollback','qyh-impact-freeze-denied','qyh-impact-stale','qyh-impact-canary')",C.SCOPE.key).fetchone()['n']==0
 assert not c.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(C.ROLE,)).fetchone()
 assert not c.execute("SELECT 1 FROM pg_trigger WHERE tgname='qyh_impact_rollback'").fetchone()
 counts={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in first['finalCounts']};assert counts==first['finalCounts']
 assert c.execute('SELECT status FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s',(*C.SCOPE.key,first['created']['taskId'])).fetchone()['status']=='cancelled'
with C.runtime(C.TenantScope('dev-org','dev-project'),read_only=True) as c:
 assert c.execute('SELECT count(*) AS n FROM aip_impact_preview_head WHERE org_id=%s AND project_id=%s AND preview_id=%s',('dev-org','dev-project',first['created']['previewId'])).fetchone()['n']==0
result={'task':'qyh-source-boundary-rehearsal-20261011','authority':'AOS-001899','twoOriginalRevisionsExact':True,'twoReceiptReferencesExact':True,'allEightImpactDimensionsUnknown':True,'failedOperationsNoReceipt':True,'oldTaskStillCancelled':True,'noNewRunOrStep':True,'canaryNoRows':True,'temporaryRoleAndTriggerAbsent':True,'positiveOriginalOperations':['impact_preview.create','impact_preview.revise'],'freezeAccepted':False,'formalRestorationAccepted':False,'experimentCounts':counts,'scriptHash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with (R/'impact-preview-independent-readback.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'independentReadback':'PASS','positiveOriginalOperations':2,'formalRestorationAccepted':False}))
