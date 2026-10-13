"""Construct real frozen preparation dependencies, never runs the Host or commands."""
from pathlib import Path
import sys,importlib.util,os,json,subprocess
P=Path(__file__).resolve().parent;ROOT=P.parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import a0v_qyh_restored_http as entry
source=entry.require_api_source_candidate(P/'directory-preparation-api-20261013.json')
identity=entry._identity_parameters((P/'private/restored-identity.json').resolve())
from psycopg.conninfo import make_conninfo
ENV={**os.environ,'AOS_DOTENV_DISABLED':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(source/'services/aos-api'),'AOS_DATABASE_URL':make_conninfo(**{k:identity[k] for k in ('host','port','dbname','user')}),'PGPASSFILE':identity['pgpassFile'],'AOS_CURRENT_RESTORED_API_IDENTITY_FILE':str((P/'private/restored-identity.json').resolve()),'AOS_CURRENT_RESTORED_INSTALLATION_ID':'ab2fd72f-d81c-400d-bbbc-e1589a159d6b','AOS_BUNDLE_ROOT':str((P/'selected-public-bundles').resolve()),'AOS_BUNDLE_TRUST_ROOTS_FILE':str((P/'restoration-public-trust-roots.json').resolve()),'AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE':str((P/'private/current-runtime-host-identities-20261013.json').resolve()),'AOS_EXTENSION_RUNTIME_HOST_ENABLED':'1','AOS_EXTENSION_RUNTIME_PREPARATION_ONLY':'1','AOS_EXTENSION_RUNTIME_UI_READ_ENABLED':'0','AOS_EXTENSION_RUNTIME_CONFIGURATION_STAGE_ENABLED':'0','AOS_EXTENSION_OCI_CONTEXT':'colima-aos-extension','AOS_EXTENSION_RUNTIME_PLATFORM':'linux/arm64'}
CODE="""import json,inspect,hashlib
from pathlib import Path
from uuid import UUID
from aos_api.asset_registry.control_wiring import build_runtime_control_plane,build_production_runtime_host_selection
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
from aos_api.ecommerce_growth_registration_connection import configured_registration_connection
control=build_runtime_control_plane(disable_dependent=EcommerceGrowthDisableDependent(),registration_connect=configured_registration_connection())
selection=build_production_runtime_host_selection(control_plane=control)
observed=False
if selection.host is not None:
 observed=selection.host.has_current_preparation_assignment(TenantScope(org_id='org-org',project_id='dev-project'),kind='runtime-apply',installation_id=UUID('ab2fd72f-d81c-400d-bbbc-e1589a159d6b'))
print(json.dumps({'controlPlaneDependentType':type(control.disable_dependent).__name__,'dependentExactType':type(control.disable_dependent) is EcommerceGrowthDisableDependent,'dependentSourceSHA256':hashlib.sha256(Path(inspect.getfile(EcommerceGrowthDisableDependent)).read_bytes()).hexdigest(),'eightPagesAccepted':False,'selectionStatus':selection.status,'errorCode':selection.error_code,'preparationOnly':selection.preparation_only,'observedOriginalPreparationAssignment':observed,'hostStarted':False,'workerTickCalled':False,'runtimeOperationRequested':False,'apiStarted':False}))
raise SystemExit(0 if selection.status=='ACTIVE' and selection.preparation_only and observed else 2)
"""
def inventory():
 return subprocess.check_output(['docker','--context','colima-aos-extension','ps','--no-trunc','--format','{{.ID}} {{.Names}}'],text=True).splitlines()
if __name__=='__main__':
 before=inventory();r=subprocess.run([sys.executable,'-c',CODE],cwd=source,env=ENV,text=True,capture_output=True,timeout=90);after=inventory()
 output=json.loads(r.stdout.splitlines()[-1]) if r.stdout.strip() else {}
 with (P/'unstarted-preparation-graph-qualification-r3-20261013.json').open('x') as f:json.dump({'candidateHead':json.loads((P/'directory-preparation-api-20261013.json').read_text())['head'],'exitCode':r.returncode,'nativeProductionGraph':output,'dockerInventoryUnchanged':before==after,'liveAPIFlagsChanged':False,'currentDatabaseWrites':False,'stderr':r.stderr},f,indent=2)
 print(json.dumps(output));assert before==after;assert r.returncode==0
