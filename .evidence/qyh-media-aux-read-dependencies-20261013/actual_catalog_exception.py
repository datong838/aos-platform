"""Read original Store with exact management API connection parameters; no HTTP effect."""
import json,sys,os,hashlib
from pathlib import Path
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[2];P=Path(__file__).resolve().parent;F=R/'.evidence/qyh-full-system-restoration-20261011'
r=json.loads((F/'successor-media-aux-current-api-20261013.json').read_text());source=Path(r['source']);sys.path[:0]=[str(source/'scripts'),str(source/'services/aos-api')]
import a0v_qyh_restored_http as entry
from psycopg.conninfo import make_conninfo
identity=entry._identity_parameters(F/'private/restored-identity.json')
assert identity['host']=='127.0.0.1' and str(identity['port'])=='18446'
dsn=make_conninfo(host=identity['host'],port=identity['port'],dbname=identity['dbname'],user=identity['user'],options='-c default_transaction_read_only=on')
os.environ['PGPASSFILE']=identity['pgpassFile']
from aos_api import db
from aos_api.tenant_scope import TenantScope,bind_tenant_scope
from aos_api.ecommerce_media_internal_workflow import EcommerceMediaInternalWorkflow
scope=TenantScope('org-org','dev-project');db.get_dsn=lambda:dsn
with db.connect(scope) as conn:
 actual=conn.execute("SELECT current_setting('transaction_read_only') AS ro, session_user AS login,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=session_user").fetchone()
 assert actual['ro']=='on' and not actual['rolsuper'] and not actual['rolbypassrls'] and actual['login']==identity['user']
os.environ.update(r['startupFlags'])
os.environ.update({'AOS_BUNDLE_ROOT':str(F/'selected-public-bundles'),'AOS_BUNDLE_TRUST_ROOTS_FILE':str(F/'restoration-public-trust-roots.json'),'AOS_INSTALLED_READONLY_CATALOG':json.dumps({'installationId':'ab2fd72f-d81c-400d-bbbc-e1589a159d6b','orgId':'org-org','projectId':'dev-project'})})
from fastapi import FastAPI
from fastapi.testclient import TestClient
from aos_api.auth import Principal,require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_workshop as routes
app=FastAPI();register_exception_handlers(app);app.include_router(routes.router)
# Explicit test fixture only; no user identity/approval/operation is fabricated.
app.dependency_overrides[require_principal]=lambda:Principal(subject='test:media-read-admission-only',org_id='org-org',project_id='dev-project',roles=['admin'],markings=[])
result={'diagnosticOnly':True,'notHumanAuthentication':True,'causeChain':[],'businessComplete':False}
try:
 with bind_tenant_scope(scope):
  gate=routes.get_ecommerce_workshop_read_catalog(routes.get_ecommerce_workshop_catalog())
  gate.get_readiness(module_id='ecommerce.media-studio',org_id=scope.org_id,project_id=scope.project_id,roles=['admin'],markings=[])
except Exception as exc:
 seen=set()
 while exc is not None and id(exc) not in seen:
  seen.add(id(exc));result['causeChain'].append({'type':type(exc).__name__,'sqlstate':getattr(exc,'sqlstate',None),'primary':getattr(getattr(exc,'diag',None),'message_primary',None)})
  exc=exc.__cause__ or exc.__context__
out=P/'actual-catalog-exception-r1.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
