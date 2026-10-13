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


from aos_api import source_readiness as sr
facts=sr.PostgresSourceReadinessFactSource().read_atomic(org_id=scope.org_id,project_id=scope.project_id)
policy=sr._json_file(sr._FRESHNESS_POLICY_PATH)
query=facts.query_capability
query_check={'expectedBindingId':sr._QUERY_BINDING_ID,'expectedCapabilityId':'strategy.plan','observed':None if query is None else {'bindingId':query.binding_id,'capabilityId':query.capability_id,'version':query.version,'status':query.status,'snapshotHashPresent':bool(query.dependency_snapshot_hash),'snapshotHashLength':len(query.dependency_snapshot_hash or '')},'canonicalExactRefAvailable':sr._query_capability_ref(query) is not None}
items=[]
for f in facts.sources:
 expected=sr._expected_cron(policy,f.pipeline_id)
 items.append({'pipelineId':f.pipeline_id,'objectType':f.object_type,'pipelinePresent':f.pipeline_present,'sourcePresent':f.source_present,'actualSourceId':f.source_id,'actualTarget':f.target,'scheduleId':f.schedule_id,'enabled':f.schedule_enabled,'actualCron':f.cron,'expectedPolicyCron':expected,'cronMatches':f.cron==expected,'ingestKind':f.ingest_kind,'ingestPipelineId':f.ingest_pipeline_id,'ingestSourceId':f.ingest_source_id,'expectedIngestSourceId':'niushop-qyh','pipelineSourceMatchesIngest':f.source_id==f.ingest_source_id,'latestRunStatus':f.latest_run.status.value,'latestRunErrorCode':f.latest_run.error_code,'latestRunStartedAt':str(f.latest_run.started_at) if f.latest_run.started_at else None})
with db.connect_read_only(scope) as conn:
 # Metadata-only queries, never source props, credentials or customer rows.
 binding=conn.execute("SELECT binding_id,version,status,capability_ref->>'assetId' AS asset_id,capability_ref->>'capabilityId' AS capability_id,dependency_snapshot_hash IS NOT NULL AS hash_present FROM aip_capability_binding WHERE org_id=%s AND project_id=%s AND (binding_id=%s OR binding_id LIKE 'ecommerce.data_advisor.%%') ORDER BY binding_id LIMIT 100",(*scope.key,sr._QUERY_BINDING_ID)).fetchall()
 columns=conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='data_source_configuration_revision' ORDER BY ordinal_position").fetchall()
result={'sourceHead':r['head'],'authority':'AOS-002023','readonlyIdentityVerified':True,'queryCapabilityCheck':query_check,'pipelines':items,'relatedBindingMetadata':binding,'configurationRevisionColumnNames':[x['column_name'] for x in columns],'freshnessPolicyPath':str(sr._FRESHNESS_POLICY_PATH.relative_to(source)),'freshnessPolicyFileSha256':hashlib.sha256(sr._FRESHNESS_POLICY_PATH.read_bytes()).hexdigest(),'sourcePropertiesNeverRead':True,'sourceFetches':0,'commandsExecuted':0,'businessComplete':False}
out=P/'current-source-prerequisites-r1.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps(result,ensure_ascii=False,default=str))
