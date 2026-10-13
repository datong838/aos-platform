"""Run original installation-only maintenance on the precisely qualified current database."""
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
P=Path(os.environ['QYH_CURRENT_EVIDENCE_DIRECTORY']);INSTALL=UUID('ab2fd72f-d81c-400d-bbbc-e1589a159d6b');ACTOR='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657';SCOPE=TenantScope('org-org','dev-project')
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
 from aos_api.asset_registry.control_wiring import build_production_runtime_host_selection
 selected=build_production_runtime_host_selection(control_plane=control)
 record('current-selection.json',{'status':selected.status,'errorCode':selected.error_code,'preparationOnly':selected.preparation_only,'currentAuthority':True,'hostStarted':False})
 assert selected.status=='ACTIVE' and selected.preparation_only
 assignments=selected.host._current_assignments()
 assert len(assignments)==1 and assignments[0].scope==SCOPE
 scheduler=assignments[0].lifecycle
 assert scheduler is not None
 initial_descriptors=scheduler.directory.read_descriptors()
 assert all(d.mode=='pending' for d in initial_descriptors)
 record('current-original-descriptors.json',{'installations':[str(d.installation_id) for d in initial_descriptors],'oldDeliveriesExecuted':False})
 from aos_api.extension_runtime.consumer_connection import consumer_connection
 with consumer_connection(runtime_worker_connection,{'org_id':SCOPE.org_id,'project_id':SCOPE.project_id}) as conn:
  assert conn.execute("SELECT count(*) AS n FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND status NOT IN ('succeeded','failed','cancelled')",SCOPE.key).fetchone()['n']==0
  assert conn.execute("SELECT count(*) AS n FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s AND role='admin'",(*SCOPE.key,ACTOR)).fetchone()['n']==1
  current=conn.execute("SELECT i.etag_version,r.state FROM bundle_installation i JOIN bundle_installation_revision r ON r.installation_pk=i.installation_pk AND r.org_id=i.org_id AND r.project_id=i.project_id AND r.revision=i.current_revision WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s",(*SCOPE.key,INSTALL)).fetchone()
  assert current=={'etag_version':3,'state':'approved'}
 def admitted():return selected.host.has_current_preparation_assignment(SCOPE,kind='runtime-apply',installation_id=INSTALL)
 assert admitted()
 record('current-apply-intent.json',{'installationId':str(INSTALL),'ifMatch':'"3"','idempotencyKey':'qyh-current-original-apply-20261013','actor':ACTOR,'agentActingUnderExplicitHumanRestoreAuthorization':True,'humanInteractiveActionObserved':False,'noOldPendingOperations':True})
 receipt=control.lifecycle_service.request_preparation(installation_id=str(INSTALL),kind='runtime-apply',org_id=SCOPE.org_id,project_id=SCOPE.project_id,actor=ACTOR,roles=['admin'],markings=[],idempotency_key='qyh-current-original-apply-20261013',if_match='"3"',preparation_admission=admitted)
 record('current-apply-receipt.json',{'statusCode':receipt.status_code,'response':receipt.response_json,'etag':receipt.response_etag,'replayed':receipt.replayed})
 assert receipt.status_code==202 and not receipt.replayed
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
  record('current-apply-tick.json',{'installationId':str(INSTALL),'ticks':apply_ticks,'enableAllowed':False,'currentInstallationMaintenance':True,'old407DeliveriesExecuted':False,'ownerRetainedInOriginalScheduler':True})
  def verify_admitted():return selected.host.has_current_preparation_assignment(SCOPE,kind='runtime-verify',installation_id=INSTALL)
  assert verify_admitted()
  record('current-verify-intent.json',{'installationId':str(INSTALL),'ifMatch':'"4"','currentInstallationOnly':True,'originalHostCurrentOwnerObserved':True})
  verified=control.lifecycle_service.request_preparation(installation_id=str(INSTALL),kind='runtime-verify',org_id=SCOPE.org_id,project_id=SCOPE.project_id,actor=ACTOR,roles=['admin'],markings=[],idempotency_key='qyh-current-original-verify-20261013',if_match='"4"',preparation_admission=verify_admitted)
  record('current-verify-receipt.json',{'statusCode':verified.status_code,'response':verified.response_json,'etag':verified.response_etag,'replayed':verified.replayed})
  assert verified.status_code==202 and not verified.replayed
  verify_ticks=[]
  for _ in range(32):
   assert scheduler.find_owner(INSTALL) is owner
   tick=await asyncio.wait_for(scheduler.run_selected_once(INSTALL),timeout=120);verify_ticks.append(repr(tick))
   with consumer_connection(runtime_worker_connection,{'org_id':SCOPE.org_id,'project_id':SCOPE.project_id}) as conn:
    status=conn.execute('SELECT status,phase,failure_code FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND operation_id=%s',(*SCOPE.key,UUID(verified.response_json['operationId']))).fetchone()
   if status['status'] in ('succeeded','failed','cancelled'):break
  record('current-verify-tick.json',{'ticks':verify_ticks,'status':status,'sameOriginalOwner':True,'enableAllowed':False,'currentInstallationMaintenance':True})
  assert status['status']=='succeeded' and status['phase']=='succeeded'

 finally:
  await scheduler.stop()
 record('current-preparation-finished.json',{'currentInstallationOnly':True,'hostStarted':False,'schedulerClosed':True,'currentInstallationMaintenance':True,'eightPagesAccepted':False,'verifyRequested':True,'enableRequested':False})
if __name__=='__main__':
 try:asyncio.run(run())
 except Exception as e:
  record('current-preparation-failure.json',{'type':type(e).__name__,'message':str(e)[:1200],'unknownEffectsMustReconcile':True,'currentInstallationMaintenance':True});raise
