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
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseStore
import traceback
result={'sourceHead':r['head'],'actualManagementIdentityReadOnly':True,'superuser':False,'bypassRls':False,'applicationNotConstructed':True,'rawCustomerDataPersisted':False,'businessComplete':False}
try:
 items=BusinessInvestigationCaseStore().list(scope,business_entity_id=None,limit=200)
 result.update({'status':'READ_OK','caseCount':len(items)})
except Exception as exc:
 result['status']='FAILED_CLOSED';result['causeChain']=[];seen=set()
 while exc is not None and id(exc) not in seen:
  seen.add(id(exc));item={'type':type(exc).__name__,'sqlstate':getattr(exc,'sqlstate',None),'frames':[{'file':Path(frame.f_code.co_filename).name,'function':frame.f_code.co_name,'line':line} for frame,line in traceback.walk_tb(exc.__traceback__)]}
  if hasattr(exc,'errors'):
   item['validationErrors']=exc.errors(include_input=False,include_url=False,include_context=False)
  result['causeChain'].append(item);exc=exc.__cause__ or exc.__context__
out=P/'native-case-store-r1.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
