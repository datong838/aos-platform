"""Original low-privilege readonly connection, bounded metadata only."""
import os,sys,json,subprocess
from pathlib import Path
R=Path.cwd();P=R/'.evidence/qyh-full-system-restoration-20261011';D=Path(__file__).resolve().parent;out=D/'original-current-owner-metadata.json';assert not out.exists()
s=json.loads((P/'restart-api-20261013-032343.json').read_text())['source']
env={k:v for k,v in os.environ.items() if not k.startswith(('AOS_','PG')) and k not in {'PYTHONPATH','PYTHONHOME'}}
env.update({'AOS_DOTENV_DISABLED':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':s+'/services/aos-api','AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE':str((P/'private/current-runtime-host-identities-20261013.json').resolve())})
code="""
import json
from psycopg import IsolationLevel
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.aip_budget_activation_store import _require_inquiry_connection
from aos_api.tenant_scope import TenantScope
scope=TenantScope('org-org','dev-project')
with runtime_worker_connection() as conn:
 conn.read_only=True;conn.isolation_level=IsolationLevel.REPEATABLE_READ
 apply_asset_transaction_scope(conn,org_id=scope.org_id,project_id=scope.project_id)
 _require_inquiry_connection(conn,scope)
 policy=conn.execute("SELECT h.current_revision,h.version,r.lifecycle,r.effective_until<clock_timestamp() AS expired FROM aip_model_governance_policy_head h JOIN aip_model_governance_policy_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id AND r.revision=h.current_revision WHERE h.org_id=%s AND h.project_id=%s AND h.policy_kind='budget' AND h.policy_id='a0v-ecommerce-budget-policy-v1'",scope.key).fetchall()
 budget=conn.execute("SELECT count(*) AS n FROM aip_budget_head h JOIN aip_budget_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.budget_id=h.budget_id AND r.revision=h.current_revision WHERE h.org_id=%s AND h.project_id=%s AND h.budget_id='a0v-ecommerce-hard-stop-budget-v1' AND r.lifecycle='active' AND r.effective_from<=clock_timestamp() AND r.effective_until>clock_timestamp()",scope.key).fetchone()
 member=conn.execute("SELECT count(*) AS n FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s AND role IN ('owner','admin')",(*scope.key,'6f31cfdc-a26c-4f1f-ad6b-95a8559cc657')).fetchone()
 print(json.dumps({'normalRoleReadonlyScopeVerified':True,'policyMetadata':policy,'activeBudgetCount':budget['n'],'canonicalHumanAdminMembershipCount':member['n'],'makerOidcIdentityVerified':False,'approvalOrPolicyPublished':False,'activationEligible':False,'currentDatabaseWrites':False}))
"""
r=subprocess.run([sys.executable,'-c',code],cwd=s,env=env,capture_output=True,text=True,timeout=45)
if r.returncode:
 result={'exitCode':r.returncode,'failureLastLine':r.stderr.splitlines()[-1][:180] if r.stderr else 'No response','currentDatabaseWrites':False,'activationEligible':False}
else:result=json.loads(r.stdout.splitlines()[-1])
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result));assert r.returncode==0
