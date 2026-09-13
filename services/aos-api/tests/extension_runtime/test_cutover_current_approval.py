from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from test_cutover_action_binding import inputs
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.tenant_scope import TenantScope


@pytest.mark.parametrize('case', ['valid', 'binding', 'policy-hash', 'draft-only', 'maker-checker', 'missing-checker', 'expired', 'unbounded', 'same-person', 'revoked', 'two-required', 'two-valid'])
def test_current_cutover_approval_needs_independent_current_authority(monkeypatch, case):
    from aos_api.ecommerce_growth_cutover_current_approval import require_current_cutover_approval
    from aos_api.ecommerce_growth_cutover_action_binding import internal_cutover_binding_hash
    from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverBlocked
    scope = TenantScope('org-org', 'dev-project')
    snapshot, payload = inputs()
    now = datetime.now(timezone.utc)
    binding = internal_cutover_binding_hash(scope=scope, action_snapshot=snapshot, payload=payload)
    policy = dict(floor='R2', makerChecker=True, minimumApprovals=1, executionAllowed=True, draftOnly=False)
    if case in {'two-required','two-valid'}:
        policy['minimumApprovals'] = 2
    if case == 'draft-only': policy['draftOnly'] = True
    if case == 'maker-checker': policy['makerChecker'] = False
    proposal = dict(proposal_id='proposal', action_type_snapshot=snapshot, payload=payload,
        created_by='maker', task_id=None, run_id=None, impact_preview_id=None,
        risk_level='R3' if case in {'two-required','two-valid'} else 'R2',
        policy_snapshot=policy, approval_policy_hash=canonical_hash(policy),
        action_binding_hash=binding, proposal_hash='p'*64)
    event = dict(approval_event_id='approval', actor_id='checker', expires_at=now+timedelta(minutes=5),
        proposal_hash=proposal['proposal_hash'], action_binding_hash=binding)
    events = [event]
    if case == 'two-valid': events.append({**event,'actor_id':'checker2','approval_event_id':'approval2'})
    if case == 'missing-checker': events = []
    if case == 'binding': proposal['action_binding_hash'] = 'bad'
    if case == 'policy-hash': proposal['approval_policy_hash'] = 'bad'
    if case == 'expired': event['expires_at'] = now-timedelta(seconds=1)
    if case == 'unbounded': event['expires_at'] = None
    if case == 'same-person': event['actor_id'] = 'maker'
    statements = []
    class Connection:
        def execute(self, sql, params=None):
            statements.append(str(sql))
            return SimpleNamespace(fetchall=lambda: deepcopy(events))
    conn = Connection()
    calls = []
    def gate(**kwargs):
        assert kwargs['conn'] is conn
        calls.append((kwargs['actor'],kwargs['operation']))
        if case == 'revoked' and kwargs['actor'] == 'checker': raise ValueError('revoked')
        return binding, ('admin',)
    monkeypatch.setattr('aos_api.ecommerce_growth_cutover_proposal_gate.require_internal_cutover_binding', gate)
    if case in {'valid','two-valid'}:
        require_current_cutover_approval(conn=conn, scope=scope, proposal=proposal,
            approval_id='approval', checked_at=now, schema='public')
        assert calls[0] == ('maker','bundle_installations.apply')
        assert calls[1] == ('checker','bundle_installations.approve')
        assert len(calls) == (3 if case == 'two-valid' else 2)
        assert statements[-1] == 'SET LOCAL ROLE aos_extension_maintainer'
    else:
        with pytest.raises(EcommerceGrowthCutoverBlocked):
            require_current_cutover_approval(conn=conn, scope=scope, proposal=proposal,
                approval_id='approval', checked_at=now, schema='public')
