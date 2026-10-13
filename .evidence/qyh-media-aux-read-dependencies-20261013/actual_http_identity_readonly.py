"""Read original Store with exact management API connection parameters; no HTTP effect."""
import json,sys,os,hashlib
from pathlib import Path
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[2];P=Path(__file__).resolve().parent;F=R/'.evidence/qyh-full-system-restoration-20261011'
r=json.loads((F/'successor-media-reviewgate-restored-api-20261013.json').read_text());source=Path(r['source']);sys.path[:0]=[str(source/'scripts'),str(source/'services/aos-api')]
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
obj=EcommerceMediaInternalWorkflow().list(scope)
result={'sourceHead':r['head'],'actualManagementIdentityParametersUsed':True,'rolePrivilege':{'superuser':False,'bypassRls':False},'genericStoreConnectTransactionReadOnly':True,'readonlyAppliedViaSameServeManagementOptions':True,'draftCount':obj.count,'tenant':obj.tenant.model_dump(mode='json',by_alias=True),'writesInitiated':False,'diagnosticOnly':True,'notLiveCandidateHttpAcceptance':True,'scriptSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'businessComplete':False}
out=P/'actual-http-identity-readonly-r1.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
