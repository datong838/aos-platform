"""Historical preview reconciliation in disposable PG, never activation proof."""
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import time
from uuid import uuid4

import pytest

from aos_api import aip_budget_activation_store as module
from aos_api.aip_budget_activation_store import AipBudgetActivationStore
from aos_api.db import connect_read_only
from aos_api.db import connect
from aos_api.auth import Principal
from aos_api.aip_budget_contracts import BudgetLifecycle
from aos_api.aip_budget_store import AipBudgetAuthorityStore
from aos_api.aip_budget_activation_store import BudgetActivationDenied
from tests.aip.test_aip_budget_activation_store_pg import setup_case, SCOPE
from tests.aip.test_network_consumer_boundary_pg import isolated_owner
from tests.aip.test_network_consumer_signed_https_pg import https_signer


def counts():
    with isolated_owner() as conn:
        return tuple(conn.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] for table in
            ('aip_budget_activation_preview', 'aip_budget_activation_decision',
             'aip_budget_activation_revocation', 'aip_budget_activation_receipt', 'aip_budget_revision'))


def test_original_preview_read_uses_readonly_snapshot_and_never_writes(monkeypatch):
    maker, checker, _, target = setup_case(); store = AipBudgetActivationStore()
    key = 'preview-'+uuid4().hex
    saved = store.create_preview(maker, target, checker.subject, key, expected_head_version=1)
    before = counts(); seen = []
    @contextmanager
    def checked(scope):
        with connect_read_only(scope) as conn:
            seen.append(conn.execute("SELECT current_user AS role,current_setting('transaction_read_only') AS ro,"
                "current_setting('transaction_isolation') AS isolation").fetchone())
            yield conn
    monkeypatch.setattr(module, 'connect_read_only', checked)
    result = store.inquire_preview(maker, target, checker.subject, key, expected_head_version=1)
    assert result == {'status': 'observed', 'previewId': saved['previewId'],
                      'previewHash': saved['previewHash'], 'activationEligible': False}
    assert seen == [{'role': 'aos_runtime', 'ro': 'on', 'isolation': 'repeatable read'}]
    assert counts() == before


@pytest.mark.parametrize('change', ['target', 'checker', 'version', 'key'])
def test_original_request_drift_or_absence_does_not_return_preview(change):
    maker, checker, _, target = setup_case(); store = AipBudgetActivationStore()
    key = 'preview-'+uuid4().hex
    store.create_preview(maker, target, checker.subject, key, expected_head_version=1)
    before = counts()
    result = store.inquire_preview(maker,
        target.model_copy(update={'daily_limit_minor': 501}) if change=='target' else target,
        'different-checker' if change=='checker' else checker.subject,
        'unseen-'+uuid4().hex if change=='key' else key, expected_head_version=2 if change=='version' else 1)
    assert result == {'status': 'unresolved' if change=='key' else 'conflict'}
    assert counts() == before


def test_other_member_cannot_discover_original_maker_preview():
    maker, checker, _, target = setup_case(); store = AipBudgetActivationStore()
    key = 'preview-'+uuid4().hex
    store.create_preview(maker, target, checker.subject, key, expected_head_version=1)
    assert store.inquire_preview(checker, target, maker.subject, key, expected_head_version=1) == {'status': 'unresolved'}
    other_scope = Principal(maker.subject, 'dev-org', SCOPE.project_id, token_kind='oidc')
    with pytest.raises(BudgetActivationDenied, match='MEMBERSHIP'):
        store.inquire_preview(other_scope, target, checker.subject, key, expected_head_version=1)


def test_expired_preview_remains_only_historical_observation():
    maker, checker, _, target = setup_case(); store = AipBudgetActivationStore()
    until = datetime.now(UTC)+timedelta(seconds=4)
    draft = target.model_copy(update={'lifecycle': BudgetLifecycle.DRAFT, 'effective_until': until})
    AipBudgetAuthorityStore().publish(SCOPE, maker.subject, 'short-'+uuid4().hex, draft, expected_version=1)
    target = draft.model_copy(update={'lifecycle': BudgetLifecycle.ACTIVE, 'revision': 3})
    key = 'short-preview-'+uuid4().hex
    saved = store.create_preview(maker, target, checker.subject, key, expected_head_version=2)
    time.sleep(max(0, (until-datetime.now(UTC)).total_seconds())+.02)
    assert datetime.now(UTC)>datetime.fromisoformat(saved['expiresAt'])
    before = counts()
    result = store.inquire_preview(maker, target, checker.subject, key, expected_head_version=2)
    assert result['status'] == 'observed' and result['activationEligible'] is False
    assert counts() == before


def test_writeable_read_factory_is_denied(monkeypatch):
    maker, checker, _, target = setup_case()
    monkeypatch.setattr(module, 'connect_read_only', connect)
    with pytest.raises(BudgetActivationDenied, match='READ_IDENTITY_REQUIRED'):
        AipBudgetActivationStore().inquire_preview(maker, target, checker.subject, 'unseen', expected_head_version=1)


@pytest.fixture
def http_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from aos_api.errors import register_exception_handlers
    from aos_api.routers.aip_budgets import router
    app = FastAPI(); register_exception_handlers(app); app.include_router(router)
    with TestClient(app) as client:
        yield client


def test_real_signed_http_inquiry_returns_original_refs_and_no_store(http_client, https_signer):
    sign, fetched = https_signer
    maker, checker, _, target = setup_case(); store = AipBudgetActivationStore()
    key = 'http-preview-'+uuid4().hex
    saved = store.create_preview(maker, target, checker.subject, key, expected_head_version=1)
    before = counts()
    headers = {'Authorization': 'Bearer '+sign(maker.subject), 'Idempotency-Key': key, 'If-Match': '1',
               'X-Org-Id': SCOPE.org_id, 'X-Project-Id': SCOPE.project_id}
    body = {'target': target.model_dump(mode='json', by_alias=True), 'checkerSubject': checker.subject}
    url = '/v1/aip/budgets/activation-previews/inquiry'
    observed = http_client.post(url, headers=headers, json=body)
    assert observed.status_code == 200, observed.text
    assert observed.json() == {'status': 'observed', 'previewId': saved['previewId'],
        'previewHash': saved['previewHash'], 'activationEligible': False}
    conflict = http_client.post(url, headers={**headers, 'If-Match': '2'}, json=body)
    assert conflict.status_code == 409 and conflict.json() == {'status': 'conflict'}
    unknown = http_client.post(url, headers={**headers, 'Idempotency-Key': 'unseen'}, json=body)
    assert unknown.status_code == 202 and unknown.json() == {'status': 'unresolved'}
    for response in (observed, conflict, unknown):
        assert response.headers['cache-control'] == 'no-store'
    denied = http_client.post(url, headers={**headers, 'Authorization': 'Bearer dev'}, json=body)
    assert denied.status_code == 401 and denied.json()['code'] == 'AUTH_DEV_DISABLED'
    assert fetched and counts() == before


def test_read_failure_is_503_not_absence_or_secret_leak(http_client, https_signer, monkeypatch):
    sign, _ = https_signer
    maker, checker, _, target = setup_case()
    def unavailable(scope):
        raise RuntimeError('private-connection-sentinel')
    monkeypatch.setattr(module, 'connect_read_only', unavailable)
    result = http_client.post('/v1/aip/budgets/activation-previews/inquiry',
        headers={'Authorization': 'Bearer '+sign(maker.subject), 'Idempotency-Key': 'unknown', 'If-Match': '1',
                 'X-Org-Id': SCOPE.org_id, 'X-Project-Id': SCOPE.project_id},
        json={'target': target.model_dump(mode='json', by_alias=True), 'checkerSubject': checker.subject})
    assert result.status_code == 503 and 'private-connection-sentinel' not in result.text
    assert result.json()['code'] == 'BUDGET_ACTIVATION_INQUIRY_UNAVAILABLE'
