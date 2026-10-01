"""Read-only review snapshots from real disposable PG and signed issuer history."""
import pytest
from aos_api.aip_budget_cost_proposal_store import BudgetCostProposalStore
from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
from aos_api.aip_budget_activation_store import BudgetActivationDenied
from aos_api.auth import Principal
from aos_api.db import connect
from tests.aip.test_budget_cost_issuer_pg import prepared, command, issuer_factory
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE, isolated_owner
from tests.aip.test_budget_preview_inquiry_pg import http_client


@pytest.mark.parametrize('choice', ['approved', 'rejected'])
def test_current_snapshot_includes_original_decision_and_revocation(choice, issuer_factory, https_signer):
    sign, _ = https_signer
    maker, checker, _, _, saved = prepared()
    store = BudgetCostProposalStore()
    assert store.review(checker, saved['proposalId']) == dict(proposal=saved, decision=None, revocation=None)
    issuer = BudgetCostIssuer(issuer_factory)
    approved = issuer.execute(command(sign, checker, saved, decision=choice))
    view = store.review(maker, saved['proposalId'])
    assert view['decision']['decisionId'] == approved['decisionId']
    assert view['decision']['decision'] == choice
    assert view['decision']['checkerSubject'] == checker.subject
    assert view['decision']['activationEligible'] is False
    assert view['revocation'] is None
    if choice == 'approved':
        result = issuer.execute(command(sign, maker, saved, operation='revoke', decision=None, reason='withdraw'))
        view = store.review(checker, saved['proposalId'])
        assert view['revocation']['revocationId'] == result['revocationId']
        assert view['revocation']['actorSubject'] == maker.subject
        assert view['revocation']['reason'] == 'withdraw'
        assert view['revocation']['decisionId'] == approved['decisionId']
    assert store.get(maker, saved['proposalId']) == saved


def test_review_requires_current_member_and_exact_scope():
    maker, checker, other, _, saved = prepared()
    store = BudgetCostProposalStore()
    for actor in (other, Principal(checker.subject, 'dev-org', SCOPE.project_id, token_kind='oidc')):
        with pytest.raises(BudgetActivationDenied): store.review(actor, saved['proposalId'])
    with connect(SCOPE) as conn:
        conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s', (*SCOPE.key, checker.subject)); conn.commit()
    with pytest.raises(BudgetActivationDenied): store.review(checker, saved['proposalId'])
    assert store.review(maker, saved['proposalId'])['decision'] is None


def test_signed_http_read_is_no_store_and_does_not_write(http_client, https_signer):
    sign, _ = https_signer
    _, checker, _, _, saved = prepared()
    def counts():
        with isolated_owner() as conn:
            return [conn.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in
                    ('aip_budget_cost_decision', 'aip_budget_cost_revocation', 'aip_budget_revision')]
    before = counts()
    r = http_client.get('/v1/aip/budgets/cost-proposals/'+saved['proposalId']+'/review', headers={
        'Authorization': 'Bearer '+sign(checker.subject), 'X-Org-Id': SCOPE.org_id, 'X-Project-Id': SCOPE.project_id})
    assert r.status_code == 200, r.text
    assert r.json() == dict(proposal=saved, decision=None, revocation=None)
    assert r.headers['cache-control'] == 'no-store'
    assert counts() == before


def test_invalid_signed_source_history_is_conflict_not_unreviewed(issuer_factory):
    from aos_api.aip_budget_activation_store import BudgetActivationConflict
    _, checker, _, _, saved = prepared()
    with issuer_factory(SCOPE, False) as conn:
        conn.execute('''INSERT INTO aip_budget_cost_decision(org_id,project_id,decision_id,proposal_id,
            proposal_hash,actor_subject,decision,source_ref,expires_at)
            VALUES(%s,%s,%s,%s,%s,%s,'approved','{}'::jsonb,%s)''',
            (*SCOPE.key, 'drift-'+saved['proposalId'], saved['proposalId'], saved['proposalHash'], checker.subject, saved['expiresAt']))
        conn.commit()
    with pytest.raises(BudgetActivationConflict, match='REVIEW_DRIFT'):
        BudgetCostProposalStore().review(checker, saved['proposalId'])


def test_read_failure_is_unavailable_not_absent(monkeypatch):
    from contextlib import contextmanager
    from aos_api import aip_budget_cost_proposal_store as module
    from aos_api.aip_budget_activation_store import BudgetActivationInquiryUnavailable
    _, checker, _, _, saved = prepared()
    @contextmanager
    def unavailable(scope):
        raise OSError('test-only read failure')
        yield
    monkeypatch.setattr(module, 'connect_read_only', unavailable)
    with pytest.raises(BudgetActivationInquiryUnavailable):
        BudgetCostProposalStore().review(checker, saved['proposalId'])
