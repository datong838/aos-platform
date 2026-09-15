"""Real AIP create/decide and event eligibility in a disposable database."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest
from test_event_control_dispatch_service_pg import service_database
from test_product_event_write_pg import stored,pair,body
from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
from aos_api.aip_action_models import CreateActionProposalRequest,DecideActionProposalRequest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.ecommerce_growth_cutover_proposal_gate import action_snapshot_from_row
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_product_event_approval import require_current_event_approval,_HASH_FIELDS
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.tenant_scope import TenantScope

@pytest.mark.parametrize('fault',['none','revoked','case','action'])
def test_actual_event_proposal_has_binding_and_current_checker_guard(service_database,stored,fault):
    conn,binding=stored;conn.execute('RESET ROLE')
    scope=TenantScope('org-org','dev-project')
    action=dict(id='ecommerce_growth_schedule_put',name='real review',object_type='Case',parameters=[],required_markings=[],submission_criteria=[])
    conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','fixture') ON CONFLICT DO NOTHING")
    conn.execute("INSERT INTO meta_org(id,name) VALUES('org-org','fixture') ON CONFLICT DO NOTHING")
    conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES('org-org','dev-project','fixture') ON CONFLICT DO NOTHING")
    for actor,role in [('real-maker','owner'),('real-checker','approver'),('real-executor','admin')]:
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES('org-org','dev-project',%s,%s)",(actor,role))
    conn.execute("INSERT INTO meta_action_type(id,name,object_type,parameters,required_markings,submission_criteria) VALUES(%s,%s,%s,'[]','[]','[]') ON CONFLICT(id) DO UPDATE SET name=excluded.name,object_type=excluded.object_type,parameters=excluded.parameters,required_markings=excluded.required_markings,submission_criteria=excluded.submission_criteria",(action['id'],action['name'],action['object_type']))
    conn.commit()
    @contextmanager
    def connect(*_):
        with psycopg.connect(service_database,row_factory=dict_row,options='-c aos.org_id=org-org -c aos.project_id=dev-project') as current:
            current.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
            current.execute('SET LOCAL ROLE aos_runtime')
            yield current
    store=AipActionStore(connect);snapshot=action_snapshot_from_row(action)
    payload=dict(caseId=binding.case.case_id,schedulePolicyId=binding.policy.policy_id,expectedPolicyRevision=0,expectedCaseVersion=binding.case.revision-1,policyHash=canonical_hash(binding.policy.authority_payload(),prefixed=True))
    request=CreateActionProposalRequest(actionTypeId=action['id'],purpose='actual internal event review',payload=payload,expiresAt=datetime.now(timezone.utc)+timedelta(minutes=20))
    risk=classify_action_risk(action['id'],snapshot,payload,None)
    proposed=store.create_proposal(scope,'real-maker','event-proposal',request,snapshot,risk)
    with connect() as check:
        check.execute('RESET ROLE')
        row=check.execute('SELECT action_binding_hash FROM aip_action_proposal WHERE proposal_id=%s',(proposed.proposal.id,)).fetchone()
        assert isinstance(row['action_binding_hash'],str) and len(row['action_binding_hash'])==64
        if fault=='revoked':check.execute("DELETE FROM meta_membership WHERE subject='real-checker'")
        elif fault=='case':check.execute('UPDATE ecommerce_investigation_case_head SET current_revision=current_revision+1 WHERE case_id=%s',(binding.case.case_id,))
        elif fault=='action':check.execute("UPDATE meta_action_type SET name='changed' WHERE id=%s",(action['id'],))
    decision=DecideActionProposalRequest(expectedProposalVersion=proposed.proposal.version,expectedProposalHash=proposed.proposal.proposal_hash,decision='approved',approvalExpiresAt=datetime.now(timezone.utc)+timedelta(minutes=10))
    if fault!='none':
        with pytest.raises(AipActionTransitionBlocked):store.decide(scope,'real-checker',proposed.proposal.id,'event-decision',decision,('admin',))
        return
    approved=store.decide(scope,'real-checker',proposed.proposal.id,'event-decision',decision,('untrusted-client-role',))
    assert approved.proposal.status.value=='approved'
    with connect() as current:
        event=current.execute('SELECT * FROM aip_action_approval_event WHERE proposal_id=%s',(proposed.proposal.id,)).fetchone()
        ref=PipelineExactRef(resourceType='ActionApprovalEvent',resourceId=event['approval_event_id'],revision=event['proposal_version'],contentHash=canonical_hash({k:event[k] for k in _HASH_FIELDS},prefixed=True))
        require_current_event_approval(transaction=HostTransaction(current),scope=scope,case_id=payload['caseId'],policy_id=payload['schedulePolicyId'],approval_ref=ref,executor='real-executor')


def test_proposal_lock_is_tenant_scoped_and_does_not_grant_table_writes(service_database,stored):
    conn,binding=stored;conn.execute('RESET ROLE');conn.commit()
    case_id=binding.case.case_id
    with psycopg.connect(service_database,row_factory=dict_row) as runtime:
        runtime.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege),runtime.transaction():
            runtime.execute('SELECT ecommerce_product_event_proposal_lock_a0v_057(%s,%s)',(case_id,'new-policy'))
        runtime.execute('SET LOCAL ROLE aos_runtime')
        assert runtime.execute("SELECT has_table_privilege(current_user,'ecommerce_investigation_case_head','UPDATE') AS can_write").fetchone()['can_write'] is False
        runtime.execute('SELECT ecommerce_product_event_proposal_lock_a0v_057(%s,%s)',(case_id,'new-policy'))
        with psycopg.connect(service_database) as other:
            other.execute("SET LOCAL lock_timeout='100ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable),other.transaction():
                other.execute('UPDATE ecommerce_investigation_case_head SET version=version WHERE case_id=%s',(case_id,))
        with runtime.transaction():
            runtime.execute("SELECT set_config('aos.org_id','dev-org',true)")
            with pytest.raises(psycopg.errors.CheckViolation),runtime.transaction():
                runtime.execute('SELECT ecommerce_product_event_proposal_lock_a0v_057(%s,%s)',(case_id,'new-policy'))
        runtime.rollback()
