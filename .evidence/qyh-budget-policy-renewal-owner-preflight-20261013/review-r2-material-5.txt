"""Read-only acceptance against the retained independent full-restore database."""
import os,sys,json,importlib.util,hashlib
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime,timezone,timedelta
from psycopg import IsolationLevel
R=Path.cwd();D=Path(__file__).resolve().parent;P=R/'.evidence/qyh-full-system-restoration-20261011'
out=D/'native-readonly-result-r3.json';assert not out.exists()
source=Path(json.loads((P/'renewal-preflight-baseline-20261013.json').read_text())['source'])
sys.path.insert(0,str(source/'services/aos-api'))
os.environ['AOS_DOTENV_DISABLED']='1'
os.environ['AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE']=str((R/'.evidence/qyh-installation-preparation-full-restore-20261013/private/lab-identities.json').resolve())
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.aip_budget_policy_renewal_proposal import BudgetPolicyRenewalProposal
from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevision
from aos_api.auth import Principal
s=importlib.util.spec_from_file_location('aos_api.aip_budget_policy_renewal_preflight',R/'services/aos-api/aos_api/aip_budget_policy_renewal_preflight.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
@contextmanager
def normal(scope):
 with runtime_worker_connection() as c:
  c.read_only=True;c.isolation_level=IsolationLevel.REPEATABLE_READ
  apply_asset_transaction_scope(c,org_id=scope.org_id,project_id=scope.project_id)
  yield c
from aos_api.tenant_scope import TenantScope
scope=TenantScope('org-org','dev-project')
with normal(scope) as c:
 row=c.execute("SELECT h.version,r.payload FROM aip_model_governance_policy_head h JOIN aip_model_governance_policy_revision r USING(org_id,project_id,policy_kind,policy_id) WHERE h.org_id=%s AND h.project_id=%s AND h.policy_kind='budget' AND h.policy_id='a0v-ecommerce-budget-policy-v1' AND r.revision=h.current_revision",scope.key).fetchone()
 old=BudgetPolicyRevision.model_validate(row['payload']);now=c.execute("SELECT clock_timestamp() AS now").fetchone()['now']
 members=c.execute("SELECT subject FROM meta_membership WHERE org_id=%s AND project_id=%s AND role IN ('admin','owner') AND subject IN ('6f31cfdc-a26c-4f1f-ad6b-95a8559cc657','user:dev')",scope.key).fetchall()
 assert len(members)==2,'Two existing fixture members required, no member creation'
 target={k:v for k,v in old.model_dump(mode='json',by_alias=True).items() if k not in {'tenant','contentHash','createdBy','createdAt'}}
 target.update(revision=old.revision+1,lifecycle='draft',approvalRef='proposal:readonly-lab-renewal',effectiveFrom=now.isoformat(),effectiveUntil=(now+timedelta(minutes=30)).isoformat())
 target['developmentCostAuthorization'].update(approvalRef=target['approvalRef'],effectiveFrom=target['effectiveFrom'],effectiveUntil=target['effectiveUntil'])
 p=BudgetPolicyRenewalProposal(schemaVersion=1,tenant=old.tenant,sourcePolicy=old,targetPolicy=target,expectedHeadVersion=row['version'],makerSubject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657',checkerSubject='user:dev')
principal=Principal(subject=p.maker_subject,org_id='org-org',project_id='dev-project',roles=['admin'],token_kind='oidc')
reader=m.BudgetPolicyRenewalPreflight(normal)
result=reader.inquire(principal,p);assert result['activationEligible'] is False and result['approvalVerified'] is False
negatives={}
for name,mutate in [
 ('headVersion',lambda x:x.update(expectedHeadVersion=p.expected_head_version+1)),
 ('unknownMaker',lambda x:x.update(makerSubject='unknown-maker')),
 ('unknownChecker',lambda x:x.update(checkerSubject='unknown-checker')),
]:
 raw=p.canonical_payload();mutate(raw);changed=BudgetPolicyRenewalProposal.model_validate(raw)
 actor=Principal(subject=changed.maker_subject,org_id='org-org',project_id='dev-project',token_kind='oidc')
 try:reader.inquire(actor,changed)
 except Exception as e:negatives[name]=type(e).__name__+':'+str(e);continue
 raise AssertionError('Negative gate unexpectedly observed')
wrong=Principal(subject=p.maker_subject,org_id='dev-org',project_id='dev-project',token_kind='oidc')
try:reader.inquire(wrong,p)
except m.BudgetPolicyRenewalBlocked:negatives['crossTenant']='REJECTED'
else:raise AssertionError('Cross-tenant inquiry observed')
@contextmanager
def writable(scope):
 with runtime_worker_connection() as c:
  c.read_only=False;c.isolation_level=IsolationLevel.REPEATABLE_READ
  apply_asset_transaction_scope(c,org_id=scope.org_id,project_id=scope.project_id)
  yield c
try:m.BudgetPolicyRenewalPreflight(writable).inquire(principal,p)
except m.BudgetPolicyRenewalBlocked:negatives['writableConnection']='REJECTED'
else:raise AssertionError('Writable source inquiry accepted')
out.write_text(json.dumps({'outcome':'INDEPENDENT_RESTORED_PG_READONLY_OWNER_PREFLIGHT_GREEN','sourceFrozenHead':source.name,'newModuleSha256':hashlib.sha256((R/'services/aos-api/aos_api/aip_budget_policy_renewal_preflight.py').read_bytes()).hexdigest(),'native':result,'negativeGates':negatives,'principalInjectedTestFixture':True,'realOidcAuthenticationAccepted':False,'humanApprovalCreated':False,'sourceCurrentDatabaseTouched':False,'labDatabaseWrites':False,'providerCalls':False},indent=2)+'\n')
print('Independent full-restore PG normal-role readonly owner inquiry passed; five native negative gates rejected. No auth/approval/publication claims.')
