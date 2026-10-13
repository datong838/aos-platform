"""Read original helper implementations using frozen sources and original runtime role."""
import sys,json,os,hashlib
from pathlib import Path
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[2];P=Path(__file__).resolve().parent;F=R/'.evidence/qyh-full-system-restoration-20261011'
r=json.loads((F/'successor-cockpit-current-api-20261013.json').read_text());source=Path(r['source']);sys.path[:0]=[str(source/'services/aos-api'),str(source/'scripts')];os.environ.update(r['startupFlags']);os.environ.update({'AOS_BUNDLE_ROOT':str(F/'selected-public-bundles'),'AOS_BUNDLE_TRUST_ROOTS_FILE':str(F/'restoration-public-trust-roots.json'),'AOS_LOCAL_MANAGEMENT_OIDC_CONFIG':'/Users/ddt/.aos-local-identities/qyh-20261013/aos-management-oidc.json','AOS_INSTALLED_READONLY_CATALOG':json.dumps({'installationId':'ab2fd72f-d81c-400d-bbbc-e1589a159d6b','orgId':'org-org','projectId':'dev-project'})})
import psycopg
from psycopg.conninfo import conninfo_to_dict,make_conninfo
from aos_api import db
from aos_api.tenant_scope import TenantScope,bind_tenant_scope
from aos_api.routers import ecommerce_workshop as routes
v=json.loads((F/'private/current-runtime-host-identities-20261013.json').read_text())['runtime'];params=conninfo_to_dict(v['dsn']);assert params['host']=='127.0.0.1' and params['port']=='18446';params['options']='-c default_transaction_read_only=on -c statement_timeout=10000';dsn=make_conninfo(**params);db.get_dsn=lambda:dsn
scope=TenantScope('org-org','dev-project')
with psycopg.connect(dsn) as conn:
 actual=conn.execute("SELECT current_user,rolsuper,rolbypassrls,current_setting('transaction_read_only') FROM pg_roles WHERE rolname=current_user").fetchone();assert actual==(v['role'],False,False,'on')
with bind_tenant_scope(scope):
 with db.connect_read_only(scope) as conn:assert conn.execute('SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*scope.key,'6f31cfdc-a26c-4f1f-ad6b-95a8559cc657')).fetchone()['role']=='admin'
 from datetime import datetime,UTC
 result={'sourceHead':r['head'],'normalRole':actual[0],'superuser':False,'bypassRls':False,'transactionReadOnly':True,'realAdminMembershipVerified':True,'diagnosticOnly':True,'results':{},'businessComplete':False}
 for name in ('fullVideo','drafts'):
  try:
   if name=='fullVideo':
    obj=routes.get_ecommerce_workshop_full_video_scenario().read(scope=scope,cutoff=datetime.now(UTC));result['results'][name]={'status':'READ_OK','blockers':[b.code for b in obj.blockers],'commands':obj.commands.model_dump(mode='json',by_alias=True)}
   else:
    obj=routes.get_ecommerce_media_internal_workflow().list(scope);result['results'][name]={'status':'READ_OK','count':obj.count,'tenant':obj.tenant.model_dump(mode='json',by_alias=True)}
  except Exception as exc:result['results'][name]={'status':'UNAVAILABLE','errorType':type(exc).__name__,'causeType':type(exc.__cause__).__name__ if exc.__cause__ else None}
result['scriptSha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
out=P/'native-two-r1.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result['results'],ensure_ascii=False))
