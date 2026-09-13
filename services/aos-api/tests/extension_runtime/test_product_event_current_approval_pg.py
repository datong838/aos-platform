"""Current reviewer checks on disposable migrated tables, no live approvals."""
from datetime import datetime,timezone,timedelta
import pytest
from psycopg.types.json import Jsonb
from test_product_event_host_service import service_case,stored,pair,body
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.ecommerce_growth_cutover_proposal_gate import action_snapshot_from_row
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_product_event_approval import require_current_event_approval


@pytest.fixture
def governed(service_case):
    conn,_,_,command,_,proposal=service_case
    row=dict(id='ecommerce_growth_schedule_put',name='schedule',object_type='Case',parameters=[],required_markings=[],submission_criteria=[])
    snapshot=action_snapshot_from_row(row)
    risk=classify_action_risk(row['id'],snapshot,proposal['payload'],None)
    policy=dict(floor=risk.floor.value,reasons=list(risk.reasons),**risk.approval_policy)
    conn.execute('RESET ROLE')
    conn.execute('''INSERT INTO meta_action_type(id,name,object_type,parameters,required_markings,submission_criteria)
        VALUES(%s,%s,%s,%s,%s,%s)''',(row['id'],row['name'],row['object_type'],Jsonb([]),Jsonb([]),Jsonb([])))
    conn.execute('''UPDATE aip_action_proposal SET action_type_snapshot=%s,policy_snapshot=%s,
        approval_policy_hash=%s,risk_level=%s WHERE proposal_id='fixture-proposal' ''',
        (Jsonb(snapshot),Jsonb(policy),canonical_hash(policy),risk.level.value))
    conn.execute("UPDATE aip_action_approval_event SET approval_policy_hash=%s WHERE approval_event_id='fixture-approval'",(canonical_hash(policy),))
    conn.execute("INSERT INTO meta_org(id,name) VALUES('org-org','fixture') ON CONFLICT DO NOTHING")
    conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES('org-org','dev-project','fixture') ON CONFLICT DO NOTHING")
    for subject,role in [('fixture-maker','operator'),('fixture-approver','approver'),('fixture-host','admin')]:
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES('org-org','dev-project',%s,%s)",(subject,role))
    conn.execute('SET LOCAL ROLE aos_runtime')
    return conn,command


def check(data,executor='fixture-host'):
    conn,command=data
    return require_current_event_approval(transaction=HostTransaction(conn),scope=TenantScope('org-org','dev-project'),
        case_id=command['caseAuthority']['caseId'],policy_id=command['policy']['schedulePolicyId'],
        approval_ref=InvestigationExactRef.model_validate(command['approvalRef']),executor=executor)


def test_current_member_can_consume_independent_approval(governed):
    assert check(governed) is None


@pytest.mark.parametrize('change',['revoked','wrong-role','maker-checker','policy-hash','snapshot','expired','executor-checker'])
def test_current_authority_drift_rejected(governed,change):
    conn,_=governed
    conn.execute('RESET ROLE')
    if change=='revoked':conn.execute("DELETE FROM meta_membership WHERE subject='fixture-approver'")
    elif change=='wrong-role':conn.execute("UPDATE meta_membership SET role='viewer' WHERE subject='fixture-approver'")
    elif change=='maker-checker':conn.execute("UPDATE aip_action_proposal SET created_by='fixture-approver'")
    elif change=='policy-hash':conn.execute("UPDATE aip_action_proposal SET approval_policy_hash=%s",('b'*64,))
    elif change=='snapshot':conn.execute("UPDATE meta_action_type SET name='changed' WHERE id='ecommerce_growth_schedule_put'")
    elif change=='expired':conn.execute("UPDATE aip_action_proposal SET expires_at=%s",(datetime.now(timezone.utc)-timedelta(seconds=1),))
    conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises((ValueError,PermissionError)):
        check(governed,'fixture-approver' if change=='executor-checker' else 'fixture-host')


def test_actual_current_gate_inside_host_save(governed,service_case,monkeypatch):
    import aos_api.ecommerce_product_event_host_service as module
    from test_product_event_host_service import execute
    monkeypatch.setattr(module,'require_current_event_approval',require_current_event_approval)
    conn,command=governed
    actual=(conn,service_case[1],HostTransaction(conn),command,None,None)
    assert execute(actual)['replayed'] is False


def test_r3_requires_two_current_independent_reviewers(governed):
    from aos_api.aip_contracts import ActionRiskLevel
    conn,_=governed;conn.execute('RESET ROLE')
    p=conn.execute("SELECT * FROM aip_action_proposal WHERE proposal_id='fixture-proposal'").fetchone()
    risk=classify_action_risk(p['action_type_id'],p['action_type_snapshot'],p['payload'],ActionRiskLevel.R3)
    policy=dict(floor=risk.floor.value,reasons=list(risk.reasons),**risk.approval_policy)
    conn.execute("UPDATE aip_action_proposal SET risk_level='R3',policy_snapshot=%s,approval_policy_hash=%s",(Jsonb(policy),canonical_hash(policy)))
    conn.execute("UPDATE aip_action_approval_event SET approval_policy_hash=%s",(canonical_hash(policy),))
    conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises(ValueError,match='quorum'):check(governed)


def test_current_marking_required_for_reviewers(governed):
    conn,_=governed;conn.execute('RESET ROLE')
    conn.execute("UPDATE meta_action_type SET required_markings=%s WHERE id='ecommerce_growth_schedule_put'",(Jsonb(['sensitive']),))
    row=conn.execute("SELECT id,name,object_type,parameters,required_markings,submission_criteria FROM meta_action_type WHERE id='ecommerce_growth_schedule_put'").fetchone()
    conn.execute("UPDATE aip_action_proposal SET action_type_snapshot=%s",(Jsonb(action_snapshot_from_row(row)),))
    conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises(PermissionError,match='marking'):check(governed)
