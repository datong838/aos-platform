"""Read original Store with exact management API connection parameters; no HTTP effect."""
import json,sys,os,hashlib
from pathlib import Path
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[2];P=Path(__file__).resolve().parent;F=R/'.evidence/qyh-full-system-restoration-20261011'
r=json.loads((F/'successor-analyst-learning-r5-api-20261013.json').read_text());source=Path(r['source']);sys.path[:0]=[str(source/'scripts'),str(source/'services/aos-api')]
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
import traceback
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseStore
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
from aos_api.ecommerce_business_investigation_review_command import EcommerceBusinessInvestigationReviewCommandService
from aos_api.source_readiness import build_source_readiness_service
cases=BusinessInvestigationCaseStore().list(scope,limit=200)
runs=BusinessInvestigationRunStore()
result={'sourceHead':r['head'],'actualManagementIdentityReadonly':True,'superuser':False,'bypassRls':False,'businessComplete':False,'reviewObservations':[]}
for case in cases:
 for run in runs.list_for_case(scope,case.case_id,limit=200):
  obs={'currentCaseRevision':case.revision,'runCaseRefRevision':run.authority.case_ref.revision,'caseHashMatches':case.content_hash==run.authority.case_ref.content_hash,'lifecycle':run.state.lifecycle.value,'control':run.state.control.value}
  try:
   view=EcommerceBusinessInvestigationReviewCommandService().projection(scope,run.authority.run_id)
   obs.update({'status':'READ_OK','reviewItemCount':len(view.items)})
  except Exception as exc:obs.update({'status':'BLOCKED','exceptionType':type(exc).__name__,'blockedCode':getattr(exc,'code',None)})
  result['reviewObservations'].append(obs)
try:
 envelope=build_source_readiness_service().read(org_id=scope.org_id,project_id=scope.project_id)
 result['canonicalSourceReadiness']={'status':envelope.status.value,'sources':[{'pipelineId':x.pipeline_id,'status':x.status.value,'blockers':x.blockers} for x in envelope.sources] if hasattr(envelope,'sources') else {'fieldNames':list(envelope.model_fields)}}
except Exception as exc:
 result['canonicalSourceReadiness']={'status':'FAILED_CLOSED','causeChain':[]};seen=set()
 while exc is not None and id(exc) not in seen:
  seen.add(id(exc));result['canonicalSourceReadiness']['causeChain'].append({'type':type(exc).__name__,'sqlstate':getattr(exc,'sqlstate',None),'frames':[{'file':Path(f.f_code.co_filename).name,'function':f.f_code.co_name,'line':i} for f,i in traceback.walk_tb(exc.__traceback__)]});exc=exc.__cause__ or exc.__context__
out=P/'native-read-gates-r1.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
