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
ids=[x.pipeline_id for x in CANONICAL_QYH_SOURCES];selected='ab2fd72f-d81c-400d-bbbc-e1589a159d6b'
with db.connect_read_only(scope) as conn:
 controls=conn.execute("SELECT pipeline_id,installation_id::text,generation::text,control_id::text,revision,selection_revision,selection_hash,content_hash,payload->'draft'->>'expiresAt' AS expires_at FROM pipeline_runtime_control_revision WHERE org_id=%s AND project_id=%s AND pipeline_id=ANY(%s) ORDER BY pipeline_id,revision DESC LIMIT 100",(*scope.key,ids)).fetchall()
 selections=conn.execute("SELECT pipeline_id,installation_id::text,generation::text,selection_id::text,revision,source_id,source_configuration_revision::text,content_hash,payload->'draft'->>'expiresAt' AS expires_at FROM pipeline_source_selection_revision WHERE org_id=%s AND project_id=%s AND pipeline_id=ANY(%s) ORDER BY pipeline_id,revision DESC LIMIT 100",(*scope.key,ids)).fetchall()
 bindings=conn.execute("SELECT schedule_id,pipeline_id,installation_id::text,generation::text,revision,control_revision,control_hash FROM pipeline_schedule_control_binding WHERE org_id=%s AND project_id=%s AND pipeline_id=ANY(%s) ORDER BY pipeline_id,revision DESC LIMIT 100",(*scope.key,ids)).fetchall()
 definitions=conn.execute("SELECT definition_id::text,revision,state,installation_id::text,generation::text,content_hash FROM pipeline_snapshot_schedule_definition_head WHERE org_id=%s AND project_id=%s ORDER BY definition_id LIMIT 100",scope.key).fetchall()
 budgets=conn.execute("SELECT r.budget_id,r.revision,r.lifecycle,r.environment,r.hard_stop,r.effective_from,r.effective_until,r.content_hash FROM aip_budget_head h JOIN aip_budget_revision r ON (r.org_id,r.project_id,r.budget_id,r.revision)=(h.org_id,h.project_id,h.budget_id,h.current_revision) WHERE h.org_id=%s AND h.project_id=%s ORDER BY r.budget_id LIMIT 100",scope.key).fetchall()
 runs=conn.execute("SELECT r.status,count(*) AS count FROM meta_schedule_run r JOIN meta_schedule s ON (r.org_id,r.project_id,r.schedule_id)=(s.org_id,s.project_id,s.id) WHERE r.org_id=%s AND r.project_id=%s AND s.pipeline_id=ANY(%s) GROUP BY r.status ORDER BY r.status",(*scope.key,ids)).fetchall()
result={'authority':'AOS-002023','readonlyIdentityVerified':True,'selectedInstallationId':selected,'controls':controls,'selections':selections,'bindings':bindings,'scheduleDefinitions':definitions,'canonicalBudgetHeads':budgets,'historicalScheduleRunStatusCounts':runs,'currentSelectedInstallationCounts':{k:sum(x['installation_id']==selected for x in rows) for k,rows in [('controls',controls),('selections',selections),('bindings',bindings),('scheduleDefinitions',definitions)]},'sourceFetches':0,'commandsExecuted':0,'businessComplete':False}
out=P/'current-control-budget-metadata-r3.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({'counts':{k:len(result[k]) for k in ['controls','selections','bindings','scheduleDefinitions','canonicalBudgetHeads']},'selectedCounts':result['currentSelectedInstallationCounts'],'budgets':budgets,'runCounts':runs},ensure_ascii=False,default=str))
