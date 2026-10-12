import sys,os,json,hashlib,subprocess,importlib.util
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path.cwd();OUT=ROOT/'.evidence/qyh-current-admin-install-20261012'
os.environ['AOS_DOTENV_DISABLED']='1';sys.path.insert(0,str(ROOT/'.evidence/qyh-full-system-restoration-20261011'))
import release_transition as T
from aos_api.asset_registry.composition_contracts import CompositionRequest,StoredCompositionLock,CreateInstallationRequest,EmptyInstallationActionRequest,InstallationResponse
from aos_api.asset_registry.composition_service import CompositionService
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
from aos_api.extension_runtime.release_revalidation import RuntimeReleaseRevalidator
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.signature import FileTrustRootProvider
s=importlib.util.spec_from_file_location('ro',ROOT/'.evidence/qyh-current159-fresh-backup-restore-20261012/backup_restore.py');ro=importlib.util.module_from_spec(s);s.loader.exec_module(ro)
def emit(n,d):
 with (OUT/n).open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
assert not (OUT/'composition-intent.json').exists(),'Existing intent: reconcile only'
with urlopen(Request('http://127.0.0.1:18080/v1/me',headers={'Authorization':'Bearer dev','X-Org-Id':'org-org','X-Project-Id':'dev-project'})) as r:me=json.load(r)
assert me['subject']=='user:dev' and me['tokenKind']=='dev' and me['orgId']=='org-org' and me['projectId']=='dev-project'
actor=me['subject'];roles=me['roles'];markings=['public','restricted'];tenant=dict(org_id='org-org',project_id='dev-project')
store=PostgresInstallationStore(connect_factory=T.factory);cs=PostgresCompositionStore(connect_factory=T.factory)
old=store.get_installation(**tenant,installation_id='407059df-6f1f-4927-acd7-8e388692838e');assert old.active_revision==5
ref={'installationId':old.installation_id,'revision':old.active_revision,'lockHash':old.current.lock_hash,'overlayRevision':old.current.overlay_revision}
policy=ReleasePolicy(trust_roots=FileTrustRootProvider(T.TRUST).snapshot());reader=RegistrySnapshotReader(connect_factory=T.factory,release_policy=policy)
snapshot=reader.read();versions={b:v for _,b,v,_ in T.CASES}
request=CompositionRequest.model_validate({'requested':[{'publisher':'aos','id':b,'version':v} for b,v in versions.items()],'platformApiVersion':'1.7.0','platformRelease':'aos-platform/1.7.0','environment':'dev','registrySnapshotHash':snapshot.snapshot_hash,'currentInstallationRef':ref})
before=ro.source_fingerprint();assert len(before)==650
p=OUT/'private/install-before.dump'
with os.fdopen(os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as f:r=subprocess.run(['docker','--context',ro.CONTEXT,'exec',ro.SOURCE,'pg_dump','-U','aos_app','-d','aos_meta_head','-Fc'],stdout=f,stderr=subprocess.PIPE,timeout=180)
assert r.returncode==0
copy=p.with_name(p.name+'.second-copy')
with os.fdopen(os.open(copy,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as f:f.write(p.read_bytes())
sha=hashlib.sha256(p.read_bytes()).hexdigest();assert sha==hashlib.sha256(copy.read_bytes()).hexdigest();assert ro.source_fingerprint()==before
emit('install-backup.json',{'sha256':sha,'bytes':p.stat().st_size,'secondCopyExact':True})
svc=CompositionService(snapshot_reader=reader,composition_store=cs,command_store=store,baseline_reader=store)
base='qyh-current-admin-install-20261012'
emit('composition-intent.json',{'tenant':tenant,'versions':versions,'predecessor':ref,'actorKind':'existing-dev-admin','snapshotHash':snapshot.snapshot_hash})
receipt=svc.resolve(request=request,**tenant,actor=actor,roles=roles,markings=markings,idempotency_key=base+'-resolve')
lock=StoredCompositionLock.model_validate_json(json.dumps(receipt.response_json,default=str))
assert {(x.id,x.version) for x in lock.payload.resolved}==set(versions.items())
assert len(lock.payload.edges)==3 and sum(1 for x in lock.payload.resolved for c in x.contributions if c.kind=='ui' and c.slot=='workshop.primary.ecommerce')==8
emit('composition-terminal.json',{'compositionId':lock.composition_id,'lockRevision':lock.revision,'lockHash':lock.lock_hash,'moduleCount':8,'dependencyEdges':3})
service=InstallationService(store=store,composition_store=cs,revalidator=InstallationRevalidator(release_policy=policy),planning_revalidator=RuntimeReleaseRevalidator(release_policy=policy))
emit('installation-create-intent.json',{'compositionId':lock.composition_id,'actorKind':'existing-dev-admin','runtimeEnabled':False})
created=service.create(request=CreateInstallationRequest.model_validate({'compositionId':lock.composition_id,'lockRevision':lock.revision,'overlayRevision':'qyh-ecommerce-restoration-20261012','displayName':'栖月汇 · 电商资产包与八工作台恢复'}),**tenant,actor=actor,roles=roles,markings=markings,idempotency_key=base+'-create')
response=InstallationResponse.model_validate_json(json.dumps(created.response_json,default=str));iid=response.installation_id
current=store.get_installation(**tenant,installation_id=iid)
emit('installation-create-terminal.json',{'installationId':iid,'state':current.state,'etagVersion':current.etag_version})
assert current.state=='draft'
emit('installation-submit-intent.json',{'installationId':iid,'etagVersion':current.etag_version})
service.submit(installation_id=iid,request=EmptyInstallationActionRequest(),**tenant,actor=actor,roles=roles,markings=markings,idempotency_key=base+'-submit',if_match=f'"{current.etag_version}"')
current=store.get_installation(**tenant,installation_id=iid);assert current.state=='submitted'
after=ro.source_fingerprint();changes=[k for k in before if before[k]!=after[k]]
allowed={'public.bundle_composition','public.bundle_composition_lock','public.bundle_installation','public.bundle_installation_revision','public.bundle_installation_event','public.asset_control_command_receipt'}
assert set(changes)<=allowed,changes
emit('installation-result.json',{'installationId':iid,'state':current.state,'etagVersion':current.etag_version,'versions':versions,'moduleCount':8,'dependencyEdges':3,'changedTables':changes,'unchangedTables':650-len(changes),'predecessorPreserved':True,'independentApprovalPending':True,'runtimeEnabled':False,'eightPagesAccepted':False})
print('Real current eight-module installation submitted; independent approval required.')
