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





from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES
from psycopg import sql
ids=[x.pipeline_id for x in CANONICAL_QYH_SOURCES];selected='ab2fd72f-d81c-400d-bbbc-e1589a159d6b';counts={}
with db.connect_read_only(scope) as conn:
 for table in ['pipeline_runtime_control_revision','pipeline_source_selection_revision','pipeline_schedule_control_binding','pipeline_snapshot_schedule_definition_head']:
  where='org_id=%s AND project_id=%s';args=scope.key
  if table!='pipeline_snapshot_schedule_definition_head':where+=' AND pipeline_id=ANY(%s)';args=(*args,ids)
  query=sql.SQL('SELECT count(*) AS tenant_total,count(*) FILTER(WHERE installation_id=%s::uuid) AS selected_total FROM {} WHERE '+where).format(sql.Identifier(table))
  row=conn.execute(query,(selected,*args)).fetchone();counts[table]=row
result={'authority':'AOS-002023','readonlyIdentityVerified':True,'selectedInstallationId':selected,'exactCounts':counts,'previousR3SampleLimit100NotGlobalProof':True,'sourceFetches':0,'commandsExecuted':0,'businessComplete':False}
out=P/'current-selected-control-exact-counts-r4.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
