"""Run original installation preparation only on the precisely admitted owned clone."""
import os,json,asyncio,hashlib
from pathlib import Path
from uuid import UUID
import psycopg
from psycopg.rows import dict_row
from aos_api.tenant_scope import TenantScope
from aos_api.asset_registry.control_wiring import build_runtime_control_plane,_allowlist_roots
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.control_policy import APPLY_INSTALLATION_OPERATION,VERIFY_INSTALLATION_OPERATION,ENABLE_RUNTIME_OPERATION,DISABLE_RUNTIME_OPERATION
from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
from aos_api.extension_runtime.production_preparation import ProductionPreparationDependencies
from aos_api.extension_runtime.production_runtime import RuntimeWorkerDependencies,select_production_runtime_host
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection,runtime_directory_connection,runtime_web_identity_connection
from aos_api.extension_runtime.current_permission import CurrentControlPermission
from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
from aos_api.extension_runtime.oci_driver import OciDriver,CleanupOnlyOciDriver
P=Path(os.environ['QYH_ISOLATED_EVIDENCE_DIRECTORY']);INSTALL=UUID('ab2fd72f-d81c-400d-bbbc-e1589a159d6b');ACTOR='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657';SCOPE=TenantScope('org-org','dev-project')
def record(name,value):
 with (P/name).open('x') as f:json.dump(value,f,indent=2,default=str)
def observation():
 from aos_api.extension_runtime.consumer_connection import consumer_connection
 with consumer_connection(runtime_worker_connection,{'org_id':SCOPE.org_id,'project_id':SCOPE.project_id}) as conn:
  # Catalog facts only; no old operation/Run/Source execution.
  return conn.execute("SELECT version_num FROM alembic_version").fetchone()['version_num']
async def run():
 assert observation()=='a0v_161'
 control=build_runtime_control_plane(disable_dependent=EcommerceGrowthDisableDependent())
 policy=control.revalidator._release_policy
 loader=ManifestLoader(_allowlist_roots(repository_root=Path.cwd()),trust_roots=policy._trust_roots)
 driver=OciDriver(context='colima-aos-extension')
 deps=ProductionPreparationDependencies(connect=runtime_worker_connection,installation_store=control.installation_store,revalidator=control.revalidator,policy=policy,loader=loader,apply_permission=CurrentControlPermission(operation=APPLY_INSTALLATION_OPERATION),verification_permission=CurrentControlPermission(operation=VERIFY_INSTALLATION_OPERATION),enable_permission=CurrentControlPermission(operation=ENABLE_RUNTIME_OPERATION),configuration_authorize=control.configuration_authorize,driver=driver,platform='linux/arm64',live_directory=control.live_job_directory)
 workers=RuntimeWorkerDependencies(installation_store=control.installation_store,configuration_authorize=control.configuration_authorize,disable_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION),drain_reader=GenerationDrainReader(),cleanup_driver=CleanupOnlyOciDriver(driver),disable_dependent=control.disable_dependent,preparation=deps)
 selected=select_production_runtime_host(enabled=True,preparation_only=True,directory_connect=runtime_directory_connection,runtime_connect=runtime_worker_connection,web_connect=runtime_web_identity_connection,dependencies=workers)
 record('original-lab-selection-r4.json',{'status':selected.status,'errorCode':selected.error_code,'preparationOnly':selected.preparation_only,'currentAuthority':False,'hostStarted':False})
 assert selected.status=='ACTIVE' and selected.preparation_only
 assignments=selected.host._current_assignments()
 assert len(assignments)==1 and assignments[0].scope==SCOPE
 scheduler=assignments[0].lifecycle
 assert scheduler is not None
 initial_descriptors=scheduler.directory.read_descriptors()
 assert all(d.mode=='pending' for d in initial_descriptors)
 record('initial-original-preparation-descriptors-r4.json',{'installations':[str(d.installation_id) for d in initial_descriptors],'oldDeliveriesExecuted':False})
 from aos_api.extension_runtime.consumer_connection import consumer_connection
 with consumer_connection(runtime_worker_connection,{'org_id':SCOPE.org_id,'project_id':SCOPE.project_id}) as conn:
  assert conn.execute("SELECT count(*) AS n FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND status NOT IN ('succeeded','failed','cancelled')",SCOPE.key).fetchone()['n']==1
  assert conn.execute("SELECT count(*) AS n FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s AND role='admin'",(*SCOPE.key,ACTOR)).fetchone()['n']==1
  current=conn.execute("SELECT i.etag_version,r.state FROM bundle_installation i JOIN bundle_installation_revision r ON r.installation_pk=i.installation_pk AND r.org_id=i.org_id AND r.project_id=i.project_id AND r.revision=i.current_revision WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s",(*SCOPE.key,INSTALL)).fetchone()
  assert current=={'etag_version':5,'state':'approved'}
 from aos_api.asset_registry.installation_store import CommandReceipt
 saved=json.loads((P/'original-lab-apply-receipt-r3.json').read_text())
 with consumer_connection(runtime_worker_connection,{'org_id':SCOPE.org_id,'project_id':SCOPE.project_id}) as conn:
  command=conn.execute("SELECT status_code,response_json,response_etag,subject FROM bundle_installation_command WHERE org_id=%s AND project_id=%s AND operation='runtime_installations.runtime-apply' AND idempotency_key='qyh-isolated-original-apply-r3-20261013'",SCOPE.key).fetchone()
  assert command['status_code']==saved['statusCode'] and command['response_json']==saved['response'] and command['response_etag']==saved['etag'] and command['subject']==ACTOR
  op=conn.execute('SELECT status,phase,deadline>clock_timestamp() AS fresh FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s',(*SCOPE.key,UUID(saved['response']['operationId']))).fetchone()
  assert op=={'status':'accepted','phase':'accepted','fresh':True}
 receipt=CommandReceipt(status_code=saved['statusCode'],response_json=saved['response'],response_etag=saved['etag'],replayed=saved['replayed'])
 record('original-lab-continue-accepted-operation-r4.json',{'operationId':saved['response']['operationId'],'originalCommandReceiptMatched':True,'deadlineFresh':True,'newRequestSubmitted':False,'resetReplayed':False,'currentDatabaseWrites':False})
 try:
  descriptors=scheduler.directory.read_descriptors();target=[d for d in descriptors if d.installation_id==INSTALL]
  assert len(target)==1 and target[0].mode=='pending'
  assert {d.installation_id for d in descriptors if d.installation_id!=INSTALL}=={d.installation_id for d in initial_descriptors if d.installation_id!=INSTALL}
  apply_ticks=[]
  for _ in range(32):
   tick=await asyncio.wait_for(scheduler.run_selected_once(INSTALL),timeout=120)
   apply_ticks.append(repr(tick))
   with consumer_connection(runtime_worker_connection,{'org_id':SCOPE.org_id,'project_id':SCOPE.project_id}) as conn:
    status=conn.execute('SELECT status,phase FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s',(*SCOPE.key,UUID(receipt.response_json['operationId']))).fetchone()
   if status['status'] in ('succeeded','failed','cancelled'):break
  assert status=={'status':'succeeded','phase':'succeeded'}
  owner=scheduler.find_owner(INSTALL);assert owner is not None and owner.enable_allowed is False
  record('original-lab-apply-tick-r4.json',{'installationId':str(INSTALL),'ticks':apply_ticks,'enableAllowed':False,'currentDatabaseWrites':False,'old407DeliveriesExecuted':False,'ownerRetainedInOriginalScheduler':True})
  def verify_admitted():return selected.host.has_current_preparation_assignment(SCOPE,kind='runtime-verify',installation_id=INSTALL)
  assert verify_admitted()
  record('original-lab-verify-intent-r4.json',{'installationId':str(INSTALL),'ifMatch':'"6"','cloneOnly':True,'originalHostCurrentOwnerObserved':True})
  verified=control.lifecycle_service.request_preparation(installation_id=str(INSTALL),kind='runtime-verify',org_id=SCOPE.org_id,project_id=SCOPE.project_id,actor=ACTOR,roles=['admin'],markings=[],idempotency_key='qyh-isolated-original-verify-r3-20261013',if_match='"6"',preparation_admission=verify_admitted)
  record('original-lab-verify-receipt-r4.json',{'statusCode':verified.status_code,'response':verified.response_json,'etag':verified.response_etag,'replayed':verified.replayed})
  assert verified.status_code==202 and not verified.replayed
  verify_ticks=[]
  for _ in range(32):
   assert scheduler.find_owner(INSTALL) is owner
   tick=await asyncio.wait_for(scheduler.run_selected_once(INSTALL),timeout=120);verify_ticks.append(repr(tick))
   with consumer_connection(runtime_worker_connection,{'org_id':SCOPE.org_id,'project_id':SCOPE.project_id}) as conn:
    status=conn.execute('SELECT status,phase,failure_code FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s',(*SCOPE.key,UUID(verified.response_json['operationId']))).fetchone()
   if status['status'] in ('succeeded','failed','cancelled'):break
  record('original-lab-verify-tick-r4.json',{'ticks':verify_ticks,'status':status,'sameOriginalOwner':True,'enableAllowed':False,'currentDatabaseWrites':False})
  assert status['status']=='succeeded' and status['phase']=='succeeded'

 finally:
  await scheduler.stop()
 record('original-lab-preparation-run-finished-r4.json',{'cloneOnly':True,'hostStarted':False,'schedulerClosed':True,'currentDatabaseWrites':False,'eightPagesAccepted':False,'verifyRequested':True,'enableRequested':False})
if __name__=='__main__':
 try:asyncio.run(run())
 except Exception as e:
  record('original-lab-preparation-failure-r4.json',{'type':type(e).__name__,'message':str(e)[:1200],'unknownEffectsMustReconcile':True,'currentDatabaseWrites':False});raise
