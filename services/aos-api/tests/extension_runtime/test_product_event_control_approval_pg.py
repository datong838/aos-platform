"""Current control eligibility on isolated DB rows, no real approvals created."""
import pytest
from test_product_event_current_approval_pg import governed,service_case,stored,pair,body
from test_product_event_control_contracts import payload
from aos_api.ecommerce_product_event_control_approval import require_current_event_disable_actor,require_current_event_control_approval
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_contracts import ActionRiskLevel


def test_control_has_independent_review_floor():
    risk=classify_action_risk('ecommerce_growth_event_control',{}, {},None)
    assert risk.floor is ActionRiskLevel.R2
    assert risk.approval_policy['makerChecker'] and not risk.approval_policy['draftOnly']


def test_current_admin_can_stop_without_source_or_approval(governed):
    conn,_=governed
    assert require_current_event_disable_actor(transaction=HostTransaction(conn),
        scope=TenantScope('org-org','dev-project'),actor='fixture-host') is None


@pytest.mark.parametrize('fault',['viewer','revoked','tenant'])
def test_disable_requires_current_tenant_controller(governed,fault):
    conn,_=governed;conn.execute('RESET ROLE')
    if fault=='viewer':conn.execute("UPDATE meta_membership SET role='viewer' WHERE subject='fixture-host'")
    if fault=='revoked':conn.execute("DELETE FROM meta_membership WHERE subject='fixture-host'")
    conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises(PermissionError):require_current_event_disable_actor(transaction=HostTransaction(conn),
        scope=TenantScope('dev-org' if fault=='tenant' else 'org-org','dev-project'),actor='fixture-host')


def test_schedule_save_approval_cannot_enable_events(governed):
    conn,saved=governed;command=payload()
    command['approvalRef']=dict(saved['approvalRef'],receiptId=None)
    command['policyRef'].update(resourceId=saved['policy']['schedulePolicyId'],contentHash=saved['policy']['contentHash'])
    with pytest.raises(ValueError):require_current_event_control_approval(transaction=HostTransaction(conn),
        scope=TenantScope('org-org','dev-project'),command=command,case_id=saved['caseAuthority']['caseId'],executor='fixture-host')


@pytest.fixture
def control_governed(governed):
    from psycopg.types.json import Jsonb
    from aos_api.aip_budget_reservation_store import canonical_hash
    from aos_api.ecommerce_growth_cutover_proposal_gate import action_snapshot_from_row
    conn,saved=governed;command=payload()
    command['approvalRef']=dict(saved['approvalRef'],receiptId=None)
    command['policyRef'].update(resourceId=saved['policy']['schedulePolicyId'],contentHash=saved['policy']['contentHash'])
    intent={key:value for key,value in command.items() if key!='approvalRef'}
    full=dict(caseId=saved['caseAuthority']['caseId'],schedulePolicyId=command['policyRef']['resourceId'],controlIntent=intent)
    row=dict(id='ecommerce_growth_event_control',name='event control',object_type='Case',parameters=[],required_markings=[],submission_criteria=[])
    snapshot=action_snapshot_from_row(row);risk=classify_action_risk(row['id'],snapshot,full,None)
    policy=dict(floor=risk.floor.value,reasons=list(risk.reasons),**risk.approval_policy)
    conn.execute('RESET ROLE')
    conn.execute('''INSERT INTO meta_action_type(id,name,object_type,parameters,required_markings,submission_criteria)
        VALUES(%s,%s,%s,%s,%s,%s)''',(row['id'],row['name'],row['object_type'],Jsonb([]),Jsonb([]),Jsonb([])))
    conn.execute('''UPDATE aip_action_proposal SET action_type_id=%s,action_type_snapshot=%s,payload=%s,
        policy_snapshot=%s,approval_policy_hash=%s,risk_level=%s WHERE proposal_id='fixture-proposal' ''',
        (row['id'],Jsonb(snapshot),Jsonb(full),Jsonb(policy),canonical_hash(policy),risk.level.value))
    conn.execute("UPDATE aip_action_approval_event SET approval_policy_hash=%s WHERE approval_event_id='fixture-approval'",(canonical_hash(policy),))
    conn.execute('SET LOCAL ROLE aos_runtime')
    return conn,command,full['caseId']


def test_exact_control_intent_uses_current_independent_approval(control_governed):
    conn,command,case_id=control_governed
    assert require_current_event_control_approval(transaction=HostTransaction(conn),scope=TenantScope('org-org','dev-project'),
        command=command,case_id=case_id,executor='fixture-host') is None


@pytest.mark.parametrize('field,value',[('idempotencyKey','different'),('expectedBindingRevision',1),('intent','disable')])
def test_control_intent_drift_cannot_reuse_approval(control_governed,field,value):
    conn,command,case_id=control_governed;command=dict(command);command[field]=value
    with pytest.raises(ValueError):require_current_event_control_approval(transaction=HostTransaction(conn),
        scope=TenantScope('org-org','dev-project'),command=command,case_id=case_id,executor='fixture-host')
