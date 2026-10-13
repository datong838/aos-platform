"""Exact frozen candidate, original normal role DSNs in memory, readonly readers only."""
from pathlib import Path
import sys,json,os,hashlib,datetime
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[2]
P=Path(__file__).resolve().parent
F=R/'.evidence/qyh-full-system-restoration-20261011'
report=json.loads((F/'successor-root8-current-api-20261013.json').read_text())
source=Path(report['source']);assert report['head']=='32bd5090045b6303f47c7e457b664be00016b406'
sys.path[:0]=[str(source/'services/aos-api'),str(source/'scripts')]
os.environ.update(report['startupFlags'])
os.environ['AOS_BUNDLE_ROOT']=str(F/'selected-public-bundles')
os.environ['AOS_BUNDLE_TRUST_ROOTS_FILE']=str(F/'restoration-public-trust-roots.json')
os.environ['AOS_LOCAL_MANAGEMENT_OIDC_CONFIG']='/Users/ddt/.aos-local-identities/qyh-20261013/aos-management-oidc.json'
os.environ['AOS_INSTALLED_READONLY_CATALOG']=json.dumps({'installationId':'ab2fd72f-d81c-400d-bbbc-e1589a159d6b','orgId':'org-org','projectId':'dev-project'})
import psycopg
from psycopg.conninfo import conninfo_to_dict,make_conninfo
from psycopg.rows import dict_row
from aos_api import db
from aos_api.tenant_scope import TenantScope,bind_tenant_scope
from aos_api.routers import ecommerce_workshop as routes
from aos_api.asset_registry.errors import AssetNotFoundError
assert Path(sys.modules['aos_api.db'].__file__).resolve()==source/'services/aos-api/aos_api/db.py'
identities=json.loads((F/'private/current-runtime-host-identities-20261013.json').read_text())
roles=[];current_dsn=None
db.get_dsn=lambda:current_dsn
root_names=['task-cockpit','operations','content-campaign','creator-growth','media-studio','analyst','price-governance','customer']
for key in ['directory','runtime','web']:
 info=identities[key];params=conninfo_to_dict(info['dsn']);assert params.get('host')=='127.0.0.1' and params.get('port')=='18446' and params.get('dbname')=='aos_meta_head'
 params['options']='-c default_transaction_read_only=on -c statement_timeout=10000';current_dsn=make_conninfo(**params)
 with psycopg.connect(current_dsn,row_factory=dict_row) as conn:
  row=conn.execute("SELECT current_user,rolsuper,rolbypassrls,rolcanlogin,current_setting('transaction_read_only') AS readonly FROM pg_roles WHERE rolname=current_user").fetchone()
  assert row['current_user']==info['role'] and row['rolsuper'] is False and row['rolbypassrls'] is False and row['readonly']=='on'
  role_record={'plane':key,'role':row['current_user'],'superuser':False,'bypassRls':False,'transactionReadOnly':True,'modules':[],'canary':[]}
 scope=TenantScope('org-org','dev-project')
 with bind_tenant_scope(scope):
  try:
   with db.connect_read_only(scope) as conn:
    membership=conn.execute('SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*scope.key,'6f31cfdc-a26c-4f1f-ad6b-95a8559cc657')).fetchone()
    assert membership and membership['role']=='admin'
   role_record['originalHumanAdminMembershipVerified']=True
  except Exception as exc:
   role_record['membershipRead']={'exception':type(exc).__name__,'sqlstate':getattr(exc,'sqlstate',None)}
  catalog=routes.get_ecommerce_workshop_read_catalog(routes.get_ecommerce_workshop_catalog())
  for module in root_names:
   result={'module':'ecommerce.'+module}
   try:
    readiness=catalog.get_readiness(module_id='ecommerce.'+module,org_id=scope.org_id,project_id=scope.project_id,roles=['admin'],markings=[])
    result.update({'admitted':True,'readiness':readiness.item.readiness.value,'installationRevision':readiness.item.installation_ref.revision,'blockerCodes':[b.reason_code for b in readiness.item.blockers]})
    service=getattr(routes,'get_ecommerce_workshop_'+module.replace('-','_'))()
    method=service.read_core if module=='task-cockpit' else service.read
    view=method(org_id=scope.org_id,project_id=scope.project_id)
    raw=view.model_dump(mode='json',by_alias=True)
    result.update({'businessReadReturned':True,'dto':type(view).__name__,'topLevelFields':sorted(raw),'topLevelListCounts':{k:len(v) for k,v in raw.items() if isinstance(v,list)}})
   except Exception as exc:
    result.update({'businessReadReturned':False,'exception':type(exc).__name__,'sqlstate':getattr(exc,'sqlstate',None),'errorCode':str(getattr(exc,'code',''))})
   role_record['modules'].append(result)
  for module in root_names:
   try:catalog.get_readiness(module_id='ecommerce.'+module,org_id='dev-org',project_id='dev-project',roles=['admin'],markings=[]);role_record['canary'].append({'module':module,'denied':False})
   except AssetNotFoundError:role_record['canary'].append({'module':module,'denied':True})
   except Exception as exc:role_record['canary'].append({'module':module,'denied':True,'exception':type(exc).__name__})
 roles.append(role_record)
result={'schema':'aos-native-root8-readonly/v1','head':report['head'],'roleResults':roles,'currentDatabaseWrites':False,'runtimeActivation':False,'providerCalls':False,'businessComplete':False,'sourceManifestSha256':report['manifestSha256'],'scriptSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'Normal original roles and frozen root readers, no HTTP/browser proof; admin role corresponds to preserved real subject, no test Principal or approval'}
output=P/'native-readonly-r1.json';assert not output.exists();output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
for role in roles:print(json.dumps({'plane':role['plane'],'membershipVerified':role.get('originalHumanAdminMembershipVerified',False),'admitted':sum(x.get('admitted',False) for x in role['modules']),'returned':sum(x.get('businessReadReturned',False) for x in role['modules']),'canaryDenied':sum(x['denied'] for x in role['canary'])}))
