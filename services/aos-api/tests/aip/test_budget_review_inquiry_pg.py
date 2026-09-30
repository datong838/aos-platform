"""Original review receipts in disposable PG; historical success is not authority."""
from uuid import uuid4
import pytest
from aos_api.aip_budget_activation_store import AipBudgetActivationStore
from tests.aip.test_aip_budget_activation_store_pg import setup_case, SCOPE
from tests.aip.test_budget_preview_inquiry_pg import counts


def review_case(operation, decision='approved'):
    maker, checker, _, target = setup_case(); store = AipBudgetActivationStore()
    preview = store.create_preview(maker, target, checker.subject, 'p-'+uuid4().hex, expected_head_version=1)
    key = 'review-'+uuid4().hex
    saved = store.decide(checker, preview['previewId'], key, decision=decision)
    if operation == 'decision':
        return store, checker, maker, preview['previewId'], key, decision, saved['decisionId']
    key = 'revoke-'+uuid4().hex
    revoked = store.revoke(maker, saved['decisionId'], key, reason='configuration changed')
    return store, maker, checker, saved['decisionId'], key, 'configuration changed', revoked['revocationId']


def inquire(store, operation, actor, source, key, value):
    if operation == 'decision':
        return store.inquire_decision(actor, source, key, decision=value)
    return store.inquire_revocation(actor, source, key, reason=value)


@pytest.mark.parametrize('operation,decision', [('decision', 'approved'), ('decision', 'rejected'), ('revoke', 'approved')])
def test_original_review_receipt_observed_without_writes(operation, decision):
    store, actor, _, source, key, value, expected = review_case(operation, decision)
    before = counts()
    result = inquire(store, operation, actor, source, key, value)
    assert result == {'status': 'observed', 'decisionId' if operation=='decision' else 'revocationId': expected,
                      'activationEligible': False}
    assert counts() == before


@pytest.mark.parametrize('operation', ['decision', 'revoke'])
@pytest.mark.parametrize('change', ['value', 'source', 'key', 'actor'])
def test_request_drift_and_absence_never_expose_original_id(operation, change):
    store, actor, other, source, key, value, _ = review_case(operation)
    result = inquire(store, operation, other if change=='actor' else actor,
        source+'-other' if change=='source' else source, key+'-other' if change=='key' else key,
        ('rejected' if operation=='decision' else 'other reason') if change=='value' else value)
    assert result == {'status': 'unresolved' if change in ('key', 'actor') else 'conflict'}


from contextlib import contextmanager
from aos_api import aip_budget_activation_store as module
from aos_api.aip_budget_activation_store import BudgetActivationDenied
from aos_api.auth import Principal
from aos_api.db import connect, connect_read_only
from tests.aip.test_budget_preview_inquiry_pg import http_client
from tests.aip.test_network_consumer_signed_https_pg import https_signer


@pytest.mark.parametrize('operation', ['decision', 'revoke'])
def test_current_membership_and_scope_required(operation):
    store, actor, _, source, key, value, _ = review_case(operation)
    foreign = Principal(actor.subject, 'dev-org', SCOPE.project_id, token_kind='oidc')
    with pytest.raises(BudgetActivationDenied, match='MEMBERSHIP'):
        inquire(store, operation, foreign, source, key, value)
    with connect(SCOPE) as conn:
        conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                     (*SCOPE.key, actor.subject)); conn.commit()
    with pytest.raises(BudgetActivationDenied, match='MEMBERSHIP'):
        inquire(store, operation, actor, source, key, value)


@pytest.mark.parametrize('operation', ['decision', 'revoke'])
def test_read_snapshot_identity_and_writable_factory_rejection(operation, monkeypatch):
    store, actor, _, source, key, value, _ = review_case(operation)
    seen = []
    @contextmanager
    def checked(scope):
        with connect_read_only(scope) as conn:
            seen.append(conn.execute("SELECT current_user AS role,current_setting('transaction_read_only') AS ro,"
                "current_setting('transaction_isolation') AS isolation").fetchone())
            yield conn
    monkeypatch.setattr(module, 'connect_read_only', checked)
    assert inquire(store, operation, actor, source, key, value)['status'] == 'observed'
    assert seen == [{'role': 'aos_runtime', 'ro': 'on', 'isolation': 'repeatable read'}]
    monkeypatch.setattr(module, 'connect_read_only', connect)
    with pytest.raises(BudgetActivationDenied, match='READ_IDENTITY_REQUIRED'):
        inquire(store, operation, actor, source, key, value)


def test_revoked_approval_is_only_historical_observation():
    store, actor, maker, source, key, value, decision_id = review_case('decision')
    store.revoke(maker, decision_id, 'revoke-'+uuid4().hex, reason='changed')
    before = counts()
    assert inquire(store, 'decision', actor, source, key, value) == {
        'status': 'observed', 'decisionId': decision_id, 'activationEligible': False}
    assert counts() == before


@pytest.mark.parametrize('operation', ['decision', 'revoke'])
def test_signed_http_history_and_database_failure(operation, http_client, https_signer, monkeypatch):
    sign, fetched = https_signer
    store, actor, other, source, key, value, expected = review_case(operation)
    url = ('/v1/aip/budgets/activation-previews/'+source+'/decisions/inquiry' if operation=='decision'
           else '/v1/aip/budgets/activation-decisions/'+source+'/revoke/inquiry')
    field = 'decision' if operation=='decision' else 'reason'
    result_key = 'decisionId' if operation=='decision' else 'revocationId'
    headers = {'Authorization': 'Bearer '+sign(actor.subject), 'Idempotency-Key': key,
               'X-Org-Id': SCOPE.org_id, 'X-Project-Id': SCOPE.project_id}
    before = counts()
    observed = http_client.post(url, headers=headers, json={field: value})
    assert observed.status_code == 200, observed.text
    assert observed.json() == {'status': 'observed', result_key: expected, 'activationEligible': False}
    conflict = http_client.post(url, headers=headers, json={field: 'rejected' if operation=='decision' else 'changed'})
    assert conflict.status_code == 409 and conflict.json() == {'status': 'conflict'}
    missing = http_client.post(url, headers={**headers, 'Idempotency-Key': 'unknown'}, json={field: value})
    assert missing.status_code == 202 and missing.json() == {'status': 'unresolved'}
    other_actor = http_client.post(url, headers={**headers, 'Authorization': 'Bearer '+sign(other.subject)}, json={field: value})
    assert other_actor.status_code == 202 and other_actor.json() == {'status': 'unresolved'}
    for response in (observed, conflict, missing, other_actor):
        assert response.headers['cache-control'] == 'no-store'
    assert fetched and counts() == before
    def unavailable(scope):
        raise RuntimeError('private-connection-sentinel')
    monkeypatch.setattr(module, 'connect_read_only', unavailable)
    failed = http_client.post(url, headers=headers, json={field: value})
    assert failed.status_code == 503 and 'private-connection-sentinel' not in failed.text
    assert failed.json()['code'] == 'BUDGET_ACTIVATION_INQUIRY_UNAVAILABLE'
