import pytest
from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverStore, EcommerceGrowthCutoverBlocked
from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService
from aos_api.tenant_scope import TenantScope
from test_ecommerce_growth_cutover_pg import database, pytestmark, _seed, _connection


def test_production_composition_rejects_old_fixture_approval_without_writes(database, monkeypatch):
    scope = TenantScope('org-org', 'dev-project')
    request = _seed(database, scope, pending_receipt=False)
    service = object.__new__(FirstDispatchRegistrationService)
    store = EcommerceGrowthCutoverStore(_connection(database), schema=database.schema, registration_service=service)
    # No current-approval replacement: the real consumer must deny the old proof.
    with pytest.raises(EcommerceGrowthCutoverBlocked, match='review policy'):
        store.prepare_activation(scope, request, actor='runtime-owner')
    assert database.owner.execute('SELECT count(*) AS n FROM extension_dispatch_cutover_operation').fetchone()['n'] == 0
    assert database.owner.execute("SELECT bool_and(handler_kind='legacy') AS valid FROM extension_operation_dispatch_binding").fetchone()['valid']


def test_current_consumer_reads_with_select_only_maintainer(database, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from test_cutover_action_binding import inputs
    from aos_api.ecommerce_growth_cutover_action_binding import internal_cutover_binding_hash
    from aos_api.ecommerce_growth_cutover_current_approval import require_current_cutover_approval
    from aos_api.aip_budget_reservation_store import canonical_hash
    scope = TenantScope('org-org', 'dev-project')
    snapshot, payload = inputs()
    now = datetime.now(timezone.utc)
    binding = internal_cutover_binding_hash(scope=scope, action_snapshot=snapshot, payload=payload)
    policy = dict(floor='R2', makerChecker=True, minimumApprovals=1, executionAllowed=True, draftOnly=False)
    proposal = dict(proposal_id='isolated-consumer-proposal', action_type_snapshot=snapshot, payload=payload,
        created_by='maker', task_id=None, run_id=None, impact_preview_id=None, risk_level='R2',
        policy_snapshot=policy, approval_policy_hash=canonical_hash(policy),
        action_binding_hash=binding, proposal_hash='p'*64)
    database.owner.execute('''INSERT INTO aip_action_approval_event(org_id,project_id,approval_event_id,
        proposal_id,proposal_version,proposal_hash,decision,actor_id,reason,expires_at,created_at,action_binding_hash)
        VALUES(%s,%s,'isolated-approval',%s,1,%s,'approved','checker','fixture',%s,%s,%s)''',
        (*scope.key,proposal['proposal_id'],proposal['proposal_hash'],now+timedelta(minutes=5),now,binding))
    calls = []
    def gate(**kwargs):
        state = kwargs['conn'].execute('SELECT current_user AS role,txid_current() AS tx').fetchone()
        assert state['role'] == 'aos_runtime'
        calls.append((kwargs['actor'], state['tx']))
        return binding, ('admin',)
    monkeypatch.setattr('aos_api.ecommerce_growth_cutover_proposal_gate.require_internal_cutover_binding', gate)
    with _connection(database)(scope) as conn:
        before = conn.execute('SELECT txid_current() AS tx').fetchone()['tx']
        assert not conn.execute("SELECT has_table_privilege(current_user,'aip_action_approval_event','UPDATE') AS allowed").fetchone()['allowed']
        require_current_cutover_approval(conn=conn, scope=scope, proposal=proposal,
            approval_id='isolated-approval', checked_at=now, schema=database.schema)
        assert conn.execute('SELECT current_user AS role').fetchone()['role'] == 'aos_extension_maintainer'
        assert calls == [('maker',before),('checker',before)]
