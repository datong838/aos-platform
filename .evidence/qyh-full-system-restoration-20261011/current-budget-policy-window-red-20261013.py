import os,sys,json,subprocess,hashlib
from pathlib import Path
from datetime import datetime,timezone,timedelta
R=Path.cwd();P=R/'.evidence/qyh-full-system-restoration-20261011';out=P/'current-budget-policy-window-red-20261013.json';assert not out.exists()
candidate=json.loads((P/'restart-api-20261013-032343.json').read_text());sys.path.insert(0,str(Path(candidate['source'])/'services/aos-api'));os.environ['AOS_DOTENV_DISABLED']='1'
from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevision
from pydantic import ValidationError
query="""BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT r.payload FROM aip_model_governance_policy_head h JOIN aip_model_governance_policy_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id AND r.revision=h.current_revision WHERE h.org_id='org-org' AND h.project_id='dev-project' AND h.policy_kind='budget' AND h.policy_id='a0v-ecommerce-budget-policy-v1';
COMMIT;"""
raw=subprocess.check_output(['docker','--context','colima-aos-extension','exec','-i','qyh-restored-pg-20261011','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','aos_app','-d','aos_meta_head'],input=query,text=True)
payload=json.loads(raw);old=BudgetPolicyRevision.model_validate(payload);now=datetime.now(timezone.utc);assert old.effective_until<now
candidate_payload=old.model_dump(mode='json',by_alias=True);candidate_payload.update({'revision':old.revision+1,'effectiveFrom':now.isoformat(),'effectiveUntil':(now+timedelta(minutes=30)).isoformat()})
try:BudgetPolicyRevision.model_validate(candidate_payload)
except ValidationError as e:
 messages=[x['msg'] for x in e.errors(include_input=False)];assert any('policy window exceeds development cost authorization' in x for x in messages)
else:raise AssertionError('Old expired authorization wrongly accepted a fresh policy window')
out.write_text(json.dumps({'outcome':'REAL_CURRENT_POLICY_EXPIRY_RENEWAL_WITH_OLD_AUTHORIZATION_REJECTED','sourceHead':candidate['head'],'currentPolicyId':old.policy_id,'currentRevision':old.revision,'originalPayloadHash':hashlib.sha256(raw.encode()).hexdigest(),'oldPolicyExpired':True,'oldAuthorizationPreservedInMemoryTest':True,'newWindowWithOldAuthorizationRejected':True,'rejectionMessages':messages,'databaseReadOnlyTransaction':True,'databaseWrites':False,'providerCalls':False,'actualApprovalCreated':False,'eightConfigurationsAccepted':False},ensure_ascii=False,indent=2)+'\n')
print('Actual current policy13 validated; attempted in-memory renewal using old authorization rejected by original contract. No writes or Provider calls.')
