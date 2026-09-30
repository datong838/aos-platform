"""Budget review sources from real disposable PostgreSQL, without activation."""
from uuid import uuid4
import pytest
from aos_api.aip_budget_activation_store import AipBudgetActivationStore, BudgetActivationDenied
from aos_api.auth import Principal
from tests.aip.test_aip_budget_activation_store_pg import setup_case, SCOPE
from tests.aip.test_budget_preview_inquiry_pg import counts, http_client
from tests.aip.test_network_consumer_signed_https_pg import https_signer


def test_candidate_matches_current_draft_and_head_without_write():
    maker, _, _, target = setup_case(); store = AipBudgetActivationStore(); before = counts()
    result = store.get_candidate(maker, target.budget_id)
    assert result == {'headVersion': 1, 'draftRevision': 1,
        'target': target.model_dump(mode='json', by_alias=True), 'activationEligible': False}
    assert counts() == before


def test_decision_review_reports_revocation_without_authorizing_execution():
    maker, checker, other, target = setup_case(); store = AipBudgetActivationStore()
    preview = store.create_preview(maker, target, checker.subject, 'p-'+uuid4().hex, expected_head_version=1)
    decision = store.decide(checker, preview['previewId'], 'd-'+uuid4().hex, decision='approved')
    before = counts(); result = store.get_decision_review(maker, decision['decisionId'])
    assert result == {'decision': decision, 'preview': preview, 'revoked': False}
    assert counts() == before
    store.revoke(checker, decision['decisionId'], 'r-'+uuid4().hex, reason='changed')
    before = counts()
    assert store.get_decision_review(checker, decision['decisionId'])['revoked'] is True
    with pytest.raises(BudgetActivationDenied): store.get_decision_review(other, decision['decisionId'])
    assert counts() == before


def test_candidate_foreign_scope_and_dev_identity_denied():
    maker, _, _, target = setup_case(); store = AipBudgetActivationStore()
    with pytest.raises(BudgetActivationDenied, match='MEMBERSHIP'):
        store.get_candidate(Principal(maker.subject, 'dev-org', SCOPE.project_id, token_kind='oidc'), target.budget_id)
    with pytest.raises(BudgetActivationDenied, match='IDENTITY'):
        store.get_candidate(Principal(maker.subject, *SCOPE.key, token_kind='dev'), target.budget_id)


def test_real_http_candidate_and_review(http_client, https_signer):
    sign, fetched = https_signer
    maker, checker, _, target = setup_case(); store = AipBudgetActivationStore()
    headers={'Authorization':'Bearer '+sign(maker.subject),'X-Org-Id':SCOPE.org_id,'X-Project-Id':SCOPE.project_id}
    candidate = http_client.get('/v1/aip/budgets/activation-candidates/'+target.budget_id, headers=headers)
    assert candidate.status_code == 200, candidate.text
    assert candidate.json()['target'] == target.model_dump(mode='json', by_alias=True)
    preview = store.create_preview(maker,target,checker.subject,'p-'+uuid4().hex,expected_head_version=1)
    decision = store.decide(checker,preview['previewId'],'d-'+uuid4().hex,decision='approved')
    original=http_client.get('/v1/aip/budgets/activation-previews/'+preview['previewId'],headers=headers)
    assert original.status_code==200 and original.headers['cache-control']=='no-store'
    before=counts()
    review=http_client.get('/v1/aip/budgets/activation-decisions/'+decision['decisionId'],headers=headers)
    assert review.status_code == 200 and review.json()['decision']['activationEligible'] is False
    from aos_api.aip_budget_activation_contracts import BudgetActivationPreviewView
    assert review.json()['preview']==BudgetActivationPreviewView.model_validate(preview).model_dump(mode='json',by_alias=True)
    assert fetched and counts()==before
    for response in (candidate,review): assert response.headers['cache-control']=='no-store'
