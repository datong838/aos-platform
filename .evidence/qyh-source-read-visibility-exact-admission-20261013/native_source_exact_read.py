"""Read original Store with exact management API connection parameters; no HTTP effect."""
import json,sys,os,hashlib
from pathlib import Path
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[2];P=Path(__file__).resolve().parent;F=R/'.evidence/qyh-full-system-restoration-20261011'
r=json.loads((F/'successor-source-exact-r5-api-20261013.json').read_text());source=Path(r['source']);os.environ.update(r['startupFlags']);os.environ['AOS_BUNDLE_ROOT']=str(F/'selected-public-bundles');os.environ['AOS_BUNDLE_TRUST_ROOTS_FILE']=str(F/'restoration-public-trust-roots.json');os.environ['AOS_LOCAL_MANAGEMENT_OIDC_CONFIG']='/Users/ddt/.aos-local-identities/qyh-20261013/aos-management-oidc.json';os.environ['AOS_INSTALLED_READONLY_CATALOG']=json.dumps({'installationId':'ab2fd72f-d81c-400d-bbbc-e1589a159d6b','orgId':'org-org','projectId':'dev-project'});sys.path[:0]=[str(source/'scripts'),str(source/'services/aos-api')]
import a0v_qyh_restored_http as entry
from psycopg.conninfo import make_conninfo
identity=entry._identity_parameters(F/'private/restored-identity.json')
assert identity['host']=='127.0.0.1' and str(identity['port'])=='18446'
dsn=make_conninfo(host=identity['host'],port=identity['port'],dbname=identity['dbname'],user=identity['user'],options='-c default_transaction_read_only=on')
os.environ['PGPASSFILE']=identity['pgpassFile']
from aos_api import db
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_media_internal_workflow import EcommerceMediaInternalWorkflow
scope=TenantScope('org-org','dev-project');db.get_dsn=lambda:dsn
with db.connect(scope) as conn:
 actual=conn.execute("SELECT current_setting('transaction_read_only') AS ro, session_user AS login,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=session_user").fetchone()
 assert actual['ro']=='on' and not actual['rolsuper'] and not actual['rolbypassrls'] and actual['login']==identity['user']

from aos_api.tenant_scope import bind_tenant_scope
from aos_api.auth import Principal
from aos_api.routers import ecommerce_workshop as routes
from aos_api.errors import ApiError
subject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
with bind_tenant_scope(scope):
 with db.connect_read_only(scope) as conn:
  row=conn.execute('SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*scope.key,subject)).fetchone()
  assert row and row['role']=='admin'
 principal=Principal(subject=subject,org_id=scope.org_id,project_id=scope.project_id,roles=['admin'],markings=[])
 legacy=routes.get_ecommerce_workshop_catalog();read=routes.get_ecommerce_workshop_read_catalog(legacy)
 assert legacy.list_modules(org_id=scope.org_id,project_id=scope.project_id,roles=principal.roles,markings=principal.markings).count==0
 routes._require_visible_read_workshop_installation(principal=principal,catalog=legacy,read_catalog=read)
 envelope=routes.get_ecommerce_workshop_source_readiness().read(org_id=scope.org_id,project_id=scope.project_id)
 assert envelope.status.value=='blocked' and len(envelope.sources)==12
 result={'sourceHead':r['head'],'actualManagementIdentityReadonly':True,'originalAdminMembershipVerified':True,'legacyCount':0,'selectedReadAdmission':True,'canonicalStatus':envelope.status.value,'pipelines':[{'pipelineId':x.pipeline_id,'status':x.status.value,'blockers':x.blockers} for x in envelope.sources],'nativeOnlyNotOIDCProof':True,'noBusinessEffects':True,'businessComplete':False}
 canaryScope=TenantScope('dev-org','dev-project')
 with bind_tenant_scope(canaryScope):
  canary=Principal(subject=subject,org_id=canaryScope.org_id,project_id=canaryScope.project_id,roles=['admin'],markings=[])
  try:routes._require_visible_read_workshop_installation(principal=canary,catalog=legacy,read_catalog=read)
  except ApiError as exc:assert exc.code=='WORKSHOP_NOT_INSTALLED';result['canaryDenied']=True
  else:raise AssertionError('canary must deny')
out=P/'native-source-exact-read-r1.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='pipelines'}))
