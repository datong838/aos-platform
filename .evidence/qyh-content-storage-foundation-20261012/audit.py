import json,sys,os,subprocess,importlib.util,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=ROOT/'.evidence/qyh-content-storage-foundation-20261012'
sys.path.insert(0,str(ROOT/'.evidence/qyh-full-system-restoration-20261011'))
import release_transition as T
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
def budget():
 with T.factory() as conn:
  conn.execute('SET TRANSACTION READ ONLY')
  apply_asset_transaction_scope(conn,org_id='org-org',project_id='dev-project')
  row=conn.execute("""SELECT
   (SELECT count(*) FROM aip_budget_head WHERE org_id=%s AND project_id=%s) AS heads,
   count(*) AS revisions,
   count(*) FILTER(WHERE lifecycle='active') AS active_rows,
   count(*) FILTER(WHERE lifecycle='active' AND effective_from<=clock_timestamp() AND clock_timestamp()<effective_until) AS active_effective_rows,
   count(*) FILTER(WHERE effective_until<=clock_timestamp()) AS expired_windows
   FROM aip_budget_revision WHERE org_id=%s AND project_id=%s""",('org-org','dev-project','org-org','dev-project')).fetchone()
  assert conn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']=='on'
  return dict(row)
def context(name):
 try:
  p=subprocess.run(['docker','--context',name,'ps','--format','{{json .}}'],capture_output=True,text=True,timeout=5)
 except subprocess.TimeoutExpired:return {'context':name,'observation':'TIMEOUT_UNKNOWN','services':[]}
 if p.returncode:return {'context':name,'observation':'DAEMON_QUERY_UNAVAILABLE','services':[]}
 services=[]
 for line in p.stdout.splitlines():
  d=json.loads(line)
  if any(x in (d['Names']+' '+d['Image']).lower() for x in ['minio','object-store','s3','ceph']):
   services.append({k:d[k] for k in ['Names','Image','State','Ports']})
 return {'context':name,'observation':'READ_SUCCESS','matchingObjectStorageServices':services}
assert not (OUT/'result.json').exists(),'Existing result: reconcile only'
a=budget();b=budget();assert a==b
contexts=['colima-aos-extension','colima-aos-a0v-test-only','desktop-linux','default']
with ThreadPoolExecutor(max_workers=4) as pool:observations=list(pool.map(context,contexts))
# Controlled offline default calculation only: clear inherited object-store configuration.
saved={k:v for k,v in os.environ.items() if k.startswith(('AOS_S3_','MINIO_')) or k=='AOS_WSL_IP'}
for k in saved:os.environ.pop(k)
try:
 from aos_api.object_store import get_config
 default_enabled=get_config().enabled
finally:os.environ.update(saved)
p=ROOT/'services/aos-api/aos_api/aip_content_draft_store.py'
d={'observedAt':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'scope':'org-org/dev-project','canonicalBudgetOwnerImplementationExists':True,'budgetAggregates':a,'twoIndependentBudgetReadsEqual':True,'budgetPayloadOrOwnerValuesRead':False,'storageContextObservations':observations,'defaultOnlyS3ConfigReportsEnabled':default_enabled,'offlineOnlyNoObjectNetworkRequests':True,'configuredGovernedObjectOwnerVerified':False,'canonicalArtifactIsBlobStore':False,'productionVerifier':'UnavailableContentObjectVerifier','sourceSha256':hashlib.sha256(p.read_bytes()).hexdigest(),'writes':0,'objectBodiesRead':0,'GoalAccepted':False}
with (OUT/'result.json').open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2);f.write(chr(10))
print(json.dumps({'budget':a,'storageObservations':[{k:v for k,v in x.items() if k not in ['services','matchingObjectStorageServices']} for x in observations],'offlineDefaultS3Enabled':default_enabled,'governedOwnerVerified':False},ensure_ascii=False))
