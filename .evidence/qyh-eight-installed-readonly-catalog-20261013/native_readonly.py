"""Fresh current installation inquiry, no writes or runtime activation."""
import os,sys,json,hashlib
from pathlib import Path
from contextlib import contextmanager
R=Path.cwd();P=R/'.evidence/qyh-full-system-restoration-20261011';D=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'services/aos-api'))
os.environ['AOS_DOTENV_DISABLED']='1'
os.environ['AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE']=str(P/'private/current-runtime-host-identities-20261013.json')
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
from aos_api.asset_registry.workshop_catalog_source import PostgresWorkshopCatalogSource
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.signature import FileTrustRootProvider
from aos_api.ecommerce_installed_readonly_catalog import InstalledReadonlyWorkshopCatalog
@contextmanager
def readonly():
 with runtime_worker_connection() as conn:
  conn.read_only=True
  yield conn
root=P/'selected-public-bundles'
trust=FileTrustRootProvider(P/'restoration-public-trust-roots.json').snapshot()
catalog=InstalledReadonlyWorkshopCatalog(source=PostgresWorkshopCatalogSource(readonly),
 loader=ManifestLoader({'a0v-canonical':root,'a0v-qyh-current':root,'a0v-current':root},trust_roots=trust),
 installation_id='ab2fd72f-d81c-400d-bbbc-e1589a159d6b',org_id='org-org',project_id='dev-project')
result=catalog.list_modules(org_id='org-org',project_id='dev-project',roles=['admin','operator'],markings=['public'])
assert result.count==8,result.count
assert all(x.readiness.value=='disabled' for x in result.items)
canary=catalog.list_modules(org_id='dev-org',project_id='dev-project',roles=['admin','operator'],markings=['public'])
assert canary.count==0
out={'outcome':'CURRENT_SIGNED_INSTALLED_EIGHT_READONLY_MODULES_VERIFIED','modules':result.model_dump(mode='json',by_alias=True),'canaryCount':canary.count,'writes':False,'runtimeGranted':False,'browserAccepted':False,'principalInjectedForDirectoryInquiry':True,'moduleSha256':hashlib.sha256((R/'services/aos-api/aos_api/ecommerce_installed_readonly_catalog.py').read_bytes()).hexdigest()}
(D/'native-readonly-result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('Current signed installation: eight readonly modules, canary zero, no writes/runtime grant.')
