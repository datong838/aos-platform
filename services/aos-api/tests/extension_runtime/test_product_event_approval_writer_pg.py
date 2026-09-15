"""Consume real AIP decision rows; only commit stays inside the fixture rollback."""
from contextlib import contextmanager
import pytest
from psycopg.types.json import Jsonb
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_contracts import ActionRiskLevel

from aos_api.aip_action_store import AipActionStore
from aos_api.aip_action_models import DecideActionProposalRequest
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_product_event_approval import require_current_event_approval, require_current_event_dispatch_approval, _HASH_FIELDS
from aos_api.ecommerce_growth_cutover_proposal_gate import action_snapshot_from_row
from test_event_control_dispatch_lifecycle import payload as dispatch_payload
from aos_api.tenant_scope import TenantScope
from test_product_event_current_approval_pg import governed, service_case, stored, pair, body


@pytest.mark.parametrize('reviewers', [1, 2])
@pytest.mark.parametrize('action', ['schedule', 'dispatch'])
def test_current_gate_consumes_actual_aip_decision(governed, reviewers, action):
    conn, command = governed
    scope = TenantScope('org-org', 'dev-project')
    conn.execute('RESET ROLE')
    conn.execute("DELETE FROM aip_action_approval_event WHERE proposal_id='fixture-proposal'")
    conn.execute("UPDATE aip_action_proposal SET status='drafted',version=1,proposal_hash=%s,action_type_revision_hash=%s WHERE proposal_id='fixture-proposal'",
                 ('c'*64, 'd'*64))
    conn.execute('''INSERT INTO aip_action_draft(org_id,project_id,draft_id,proposal_id,
        proposal_version,proposal_hash,snapshot,approval_policy,created_by)
        VALUES('org-org','dev-project','writer-draft','fixture-proposal',1,%s,'{}','{}','fixture-maker')''', ('c'*64,))
    intent = dispatch_payload()
    intent.pop('approvalRef')
    intent.update(caseId=command['caseAuthority']['caseId'], schedulePolicyId=command['policy']['schedulePolicyId'])
    if action == 'dispatch':
        row = dict(id='ecommerce_growth_event_dispatch', name='dispatch', object_type='Case',
                   parameters=[], required_markings=[], submission_criteria=[])
        conn.execute('''INSERT INTO meta_action_type(id,name,object_type,parameters,required_markings,submission_criteria)
            VALUES(%s,%s,%s,'[]','[]','[]')''', (row['id'], row['name'], row['object_type']))
        conn.execute("UPDATE aip_action_proposal SET action_type_id=%s,action_type_snapshot=%s,payload=%s WHERE proposal_id='fixture-proposal'",
            (row['id'], Jsonb(action_snapshot_from_row(row)), Jsonb(dict(caseId=intent['caseId'],
                schedulePolicyId=intent['schedulePolicyId'], dispatchIntent=intent))))
    if reviewers == 2 or action == 'dispatch':
        proposal = conn.execute("SELECT * FROM aip_action_proposal WHERE proposal_id='fixture-proposal'").fetchone()
        risk = classify_action_risk(proposal['action_type_id'], proposal['action_type_snapshot'],
                                   proposal['payload'], ActionRiskLevel.R3 if reviewers == 2 else None)
        policy = dict(floor=risk.floor.value, reasons=list(risk.reasons), **risk.approval_policy)
        conn.execute("UPDATE aip_action_proposal SET risk_level=%s,policy_snapshot=%s,approval_policy_hash=%s WHERE proposal_id='fixture-proposal'",
                     (risk.level.value, Jsonb(policy), canonical_hash(policy)))
    if reviewers == 2:
        conn.execute("INSERT INTO meta_membership VALUES('org-org','dev-project','second-approver','approver')")

    class RollbackOwnedConnection:
        execute = conn.execute

        def commit(self):
            # Keep all rows isolated within governed/stored's rollback boundary.
            pass

    @contextmanager
    def connect(_scope):
        assert _scope == scope
        yield RollbackOwnedConnection()

    bundle = AipActionStore(connect).decide(scope, 'fixture-approver', 'fixture-proposal',
        'writer-approve', DecideActionProposalRequest(expectedProposalVersion=1,
            expectedProposalHash='c'*64, decision='approved'), actor_roles=('approver',))
    if reviewers == 2:
        assert bundle.proposal.status.value == 'drafted'
        bundle = AipActionStore(connect).decide(scope, 'second-approver', 'fixture-proposal',
            'writer-approve-2', DecideActionProposalRequest(expectedProposalVersion=2,
                expectedProposalHash='c'*64, decision='approved'), actor_roles=('approver',))
    assert bundle.proposal.version == reviewers+1
    assert sorted(item.proposal_version for item in bundle.approvals) == list(range(1, reviewers+1))
    event = conn.execute('SELECT * FROM aip_action_approval_event WHERE proposal_id=%s ORDER BY proposal_version', ('fixture-proposal',)).fetchone()
    ref = InvestigationExactRef(resourceType='ActionApprovalEvent', resourceId=event['approval_event_id'],
        revision=event['proposal_version'], contentHash=canonical_hash({key:event[key] for key in _HASH_FIELDS}, prefixed=True))
    conn.execute('SET LOCAL ROLE aos_runtime')
    def check():
        kwargs = dict(transaction=HostTransaction(conn), scope=scope,
            case_id=command['caseAuthority']['caseId'], policy_id=command['policy']['schedulePolicyId'],
            approval_ref=ref, executor='fixture-host')
        if action == 'dispatch':
            return require_current_event_dispatch_approval(**kwargs, dispatch_intent=intent)
        return require_current_event_approval(**kwargs)
    assert check() is None
    conn.execute('RESET ROLE')
    conn.execute("UPDATE aip_action_proposal SET version=version+1 WHERE proposal_id='fixture-proposal'")
    conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises(ValueError, match='version chain differs'):
        check()
