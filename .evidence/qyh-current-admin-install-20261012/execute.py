"""Original Registry transition for an existing authenticated development admin."""
import importlib.util,json,sys,os,hashlib,subprocess
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
ROOT=Path.cwd(); OUT=ROOT/'.evidence/qyh-current-admin-install-20261012'
sys.path.insert(0,str(ROOT/'.evidence/qyh-full-system-restoration-20261011'))
import release_transition as T
from aos_api.auth import resolve_principal
from aos_api.asset_registry.registry_service import RegistryService, _require_publisher_access, PUBLISH_ROLES
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.signature import FileTrustRootProvider
from aos_api.asset_registry.contracts import BundleVersionStatus
s=importlib.util.spec_from_file_location('readonly',ROOT/'.evidence/qyh-current159-fresh-backup-restore-20261012/backup_restore.py');ro=importlib.util.module_from_spec(s);s.loader.exec_module(ro)
def emit(name,data):
 with (OUT/name).open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def get(path):
 with urlopen(Request('http://127.0.0.1:18080'+path,headers={'Authorization':'Bearer dev','X-Org-Id':'org-org','X-Project-Id':'dev-project'}),timeout=15) as r:return json.load(r)
assert not (OUT/'preflight.json').exists(),'Existing run: reconcile only'
me=get('/v1/me');auth=get('/v1/auth/oidc')
assert me['orgId']=='org-org' and me['projectId']=='dev-project' and me['orgName']=='栖月汇商贸有限公司'
assert me['tokenKind']=='dev' and auth['allowDevToken'] is True
# Match the actual existing live development policy, not a new authentication identity.
os.environ['AOS_AUTH_ALLOW_DEV']='1'
principal=resolve_principal(token='dev',header_org='org-org',header_project='dev-project')
assert principal.subject==me['subject'] and 'admin' in principal.roles and 'aos' in principal.asset_publishers
identity=json.loads(subprocess.check_output(['docker','--context',ro.CONTEXT,'inspect',ro.SOURCE],text=True))[0]
assert identity['Id']=='84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c'
assert identity['State']['Running'] and identity['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011'
assert ro.current_sql('SELECT system_identifier FROM pg_control_system();').strip()=='7695302940039200809'
assert ro.current_sql('SELECT version_num FROM alembic_version;').strip()=='a0v_161'
assert ro.current_sql('SELECT count(*) FROM extension_runtime_binding WHERE enabled OR NOT operation_fence;').strip()=='0'
trust=FileTrustRootProvider(T.TRUST).snapshot()
loader=ManifestLoader({'a0v-canonical':T.LEGACY_ROOT,'a0v-qyh-current':T.CURRENT/'signed-bundles'},trust_roots=trust)
store=PostgresRegistryStore(connect_factory=T.factory)
service=RegistryService(store=store,loader=loader,clock=lambda:datetime.now(timezone.utc),trust_roots=trust)
rows=[]
for alias,b,v,retained in T.CASES:
 loaded=loader.load(f'bundle://{alias}/{b}/{v}');raw=store.get_version(b,v,'aos')
 T.OLD.assert_registry_version_exact(raw,T.OLD._expected_registry_version(loaded))
 assert raw['signature']==loaded.signature.model_dump(mode='json',by_alias=True)
 if not retained:
  _require_publisher_access(actor=principal.subject,roles=principal.roles,publisher_scopes=principal.asset_publishers,publisher='aos',allowed_roles=PUBLISH_ROLES)
  service._release_precondition(expected=BundleVersionStatus.VALIDATED,action='publish',actor=principal.subject,require_separation=True)(raw)
 else:assert raw['status']=='published'
 rows.append({'id':b,'version':v,'status':raw['status'],'contentHash':loaded.content_hash,'moduleCount':len(loaded.workshop_modules),'publishPending':not retained})
assert sum(r['moduleCount'] for r in rows)==8
before=ro.source_fingerprint();assert len(before)==650
emit('preflight.json',{'observedAt':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tenant':'org-org/dev-project','principalKind':'existing-dev-admin','authenticatedPrincipalMatchesLiveMe':True,'publisherScope':'aos','originalDutySeparationPassed':True,'versions':rows,'databaseWrites':0})
if '--apply' not in sys.argv:print('PREFLIGHT PASSED: existing admin publication is authorized by original policy');sys.exit(0)
private=OUT/'private';private.mkdir(mode=0o700)
backup={}
for n,argv in [('before.dump',['pg_dump','-U','aos_app','-d','aos_meta_head','-Fc']),('globals.sql',['pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'])]:
 p=private/n
 with os.fdopen(os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as f:
  result=subprocess.run(['docker','--context',ro.CONTEXT,'exec',ro.SOURCE,*argv],stdout=f,stderr=subprocess.PIPE,timeout=180)
 assert result.returncode==0,'Backup failed; no publish'
 second=p.with_name(n+'.second-copy')
 with os.fdopen(os.open(second,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as f:f.write(p.read_bytes())
 sha=hashlib.sha256(p.read_bytes()).hexdigest();assert sha==hashlib.sha256(second.read_bytes()).hexdigest()
 backup[n]={'sha256':sha,'bytes':p.stat().st_size,'secondCopyExact':True}
assert ro.source_fingerprint()==before
emit('backup.json',backup)
for r in rows:
 if not r['publishPending']:continue
 stem=r['id']+'-'+r['version']
 emit(stem+'-intent.json',{'action':'RegistryService.publish','actorKind':'existing-dev-admin','tenant':'org-org/dev-project','version':r,'sourceCluster':'7695302940039200809','runtimeEnabled':False})
 try:
  result=service.publish(bundle_id=r['id'],version=r['version'],publisher='aos',actor=principal.subject,roles=principal.roles,publisher_scopes=principal.asset_publishers)
 except Exception as e:
  emit(stem+'-failure.json',{'errorType':type(e).__name__,'error':str(e),'retryAuthorized':False});raise
 emit(stem+'-terminal.json',{'status':result['status'],'contentHash':result['contentHash']})
 assert store.get_version(r['id'],r['version'],'aos')['status']=='published'
after=ro.source_fingerprint();changed=[k for k in before if before[k]!=after[k]]
assert set(changed)<= {'public.asset_bundle_version','public.asset_bundle_version_event'},changed
assert ro.current_sql('SELECT count(*) FROM extension_runtime_binding WHERE enabled OR NOT operation_fence;').strip()=='0'
emit('result.json',{'outcome':'CURRENT_FOUR_PUBLISHED_EXISTING_ADMIN','changedTables':changed,'unchangedTables':650-len(changed),'publishedVersions':[{k:r[k] for k in ['id','version','contentHash']} for r in rows],'hostProviderWorkerEnabled':False,'installationCompleted':False,'eightPagesAccepted':False,'formalIdentityVerified':False})
print('Current four releases published; business tables preserved; installation approval remains separate.')
