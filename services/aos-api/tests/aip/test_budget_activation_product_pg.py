"""Durable budget product requests with real disposable PG and signed TLS JWT."""
import importlib
from pathlib import Path
from uuid import uuid4

import pytest

from aos_api.aip_budget_activation_contracts import (
    CreateBudgetActivationPreviewRequest, DecideBudgetActivationRequest,
    RevokeBudgetActivationDecisionRequest,
)
from aos_api.aip_budget_activation_store import AipBudgetActivationStore
from tests.aip.test_aip_budget_activation_store_pg import setup_case, SCOPE
from tests.aip.test_budget_preview_inquiry_pg import counts, http_client
from tests.aip.test_network_consumer_signed_https_pg import https_signer


@pytest.fixture
def product():
    return importlib.import_module('aos_api.aip_budget_activation_product')


@pytest.fixture
def directory(tmp_path):
    path = tmp_path / 'budget-requests'; path.mkdir(mode=0o700)
    return path


def case(product, operation):
    maker, checker, _, target = setup_case()
    if operation == 'preview':
        return (product.BudgetRequestRef(operation, target.budget_id, target.revision, 1),
                CreateBudgetActivationPreviewRequest(target=target, checkerSubject=checker.subject), maker, checker)
    store = AipBudgetActivationStore()
    preview = store.create_preview(maker, target, checker.subject, 'p-'+uuid4().hex, expected_head_version=1)
    if operation == 'decision':
        return (product.BudgetRequestRef(operation, preview['previewId']),
                DecideBudgetActivationRequest(decision='approved'), checker, maker)
    decision = store.decide(checker, preview['previewId'], 'd-'+uuid4().hex, decision='approved')
    return (product.BudgetRequestRef(operation, decision['decisionId']),
            RevokeBudgetActivationDecisionRequest(reason='configuration changed'), maker, checker)


@pytest.mark.parametrize('operation', ['preview', 'decision', 'revoke'])
def test_commit_response_lost_reload_and_repeat_only_query(product, directory, https_signer, monkeypatch, operation):
    sign, _ = https_signer
    ref, body, actor, _ = case(product, operation)
    auth = 'Bearer '+sign(actor.subject)
    assert product.inquire_request(directory, ref, actor, auth) == {'status': 'not_attempted'}
    before = counts(); calls = []
    name = {'preview': 'create_preview', 'decision': 'decide', 'revoke': 'revoke'}[operation]
    original = getattr(AipBudgetActivationStore, name)
    def lost(*args, **kwargs):
        calls.append(1); original(*args, **kwargs)
        raise OSError('response lost after commit')
    monkeypatch.setattr(AipBudgetActivationStore, name, lost)
    result = product.submit_request(directory, ref, body, actor, auth)
    assert result['status'] == 'observed' and result['activationEligible'] is False
    for _ in range(2):
        assert product.inquire_request(Path(str(directory)), ref, actor, auth) == result
        assert product.submit_request(directory, ref, body, actor, auth) == result
    assert calls == [1]
    after = counts(); index = {'preview': 0, 'decision': 1, 'revoke': 2}[operation]
    assert after == tuple(n+(1 if i in (index, 3) else 0) for i, n in enumerate(before))
    assert auth.removeprefix('Bearer ') not in next(directory.iterdir()).read_text()


import json
import os
from concurrent.futures import ThreadPoolExecutor
from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.aip_budget_activation_store import BudgetActivationDenied


@pytest.mark.parametrize('operation', ['preview', 'decision', 'revoke'])
def test_same_source_changed_input_is_conflict(product, directory, https_signer, operation):
    sign, _ = https_signer
    ref, body, actor, _ = case(product, operation); auth = 'Bearer '+sign(actor.subject)
    result = product.submit_request(directory, ref, body, actor, auth)
    before = counts()
    changed = (body.model_copy(update={'target': body.target.model_copy(update={'daily_limit_minor': 501})})
        if operation=='preview' else body.model_copy(update={
            'decision' if operation=='decision' else 'reason': 'rejected' if operation=='decision' else 'other reason'}))
    with pytest.raises(product.BudgetProductBlocked) as exc:
        product.submit_request(directory, ref, changed, actor, auth)
    assert exc.value.status_code == 409
    assert product.inquire_request(directory, ref, actor, auth) == result and counts() == before


@pytest.mark.parametrize('operation', ['preview', 'decision', 'revoke'])
def test_failure_before_store_remains_unknown_and_is_not_retried(product, directory, https_signer, monkeypatch, operation):
    sign, _ = https_signer
    ref, body, actor, _ = case(product, operation); auth = 'Bearer '+sign(actor.subject)
    calls = []; before = counts()
    def failed(*args, **kwargs):
        calls.append(1); raise OSError('cannot establish whether original request executed')
    monkeypatch.setattr(AipBudgetActivationStore, {'preview':'create_preview','decision':'decide','revoke':'revoke'}[operation], failed)
    for _ in range(2):
        assert product.submit_request(directory, ref, body, actor, auth) == {'status': 'unresolved'}
    assert product.inquire_request(directory, ref, actor, auth) == {'status': 'unresolved'}
    assert calls == [1] and counts() == before


@pytest.mark.parametrize('fsync_index', [1, 2])
def test_persistence_failure_never_dispatches_or_deletes_slot(product, directory, https_signer, monkeypatch, fsync_index):
    sign, _ = https_signer
    ref, body, actor, _ = case(product, 'preview'); auth = 'Bearer '+sign(actor.subject)
    original = os.fsync; calls = []
    def fail(fd):
        calls.append(1)
        if len(calls) == fsync_index: raise OSError('disk error')
        return original(fd)
    monkeypatch.setattr(os, 'fsync', fail)
    monkeypatch.setattr(AipBudgetActivationStore, 'create_preview', lambda *a, **k: pytest.fail('must not dispatch'))
    before = counts()
    with pytest.raises(product.BudgetProductBlocked) as exc:
        product.submit_request(directory, ref, body, actor, auth)
    assert exc.value.status_code == 503 and len(list(directory.iterdir())) == 1
    monkeypatch.setattr(os, 'fsync', original)
    assert product.submit_request(directory, ref, body, actor, auth) == {'status': 'unresolved'}
    assert counts() == before


@pytest.mark.parametrize('bad', ['broken', 'actor', 'hash', 'permissions', 'symlink', 'fifo'])
def test_untrusted_request_cannot_be_treated_as_absence(product, directory, https_signer, monkeypatch, bad):
    sign, _ = https_signer
    ref, body, actor, _ = case(product, 'preview'); auth = 'Bearer '+sign(actor.subject)
    product.submit_request(directory, ref, body, actor, auth)
    path = next(directory.iterdir())
    if bad == 'broken': path.write_text('{')
    elif bad in ('actor', 'hash'):
        saved = json.loads(path.read_text()); saved['subject' if bad=='actor' else 'requestHash'] = 'wrong'
        path.write_text(json.dumps(saved))
    elif bad == 'permissions': path.chmod(0o644)
    else:
        path.unlink()
        if bad == 'fifo': os.mkfifo(path, 0o600)
        else: path.symlink_to(directory/'missing')
    monkeypatch.setattr(AipBudgetActivationStore, 'create_preview', lambda *a, **k: pytest.fail('must not recreate'))
    for call in (lambda: product.inquire_request(directory, ref, actor, auth),
                 lambda: product.submit_request(directory, ref, body, actor, auth)):
        with pytest.raises(product.BudgetProductBlocked) as exc: call()
        assert exc.value.status_code == 503


def test_parallel_original_submission_only_one_store_call(product, directory, https_signer, monkeypatch):
    sign, _ = https_signer
    ref, body, actor, _ = case(product, 'preview'); auth = 'Bearer '+sign(actor.subject)
    original = AipBudgetActivationStore.create_preview; calls = []
    def saved(*a, **kw):
        calls.append(1); return original(*a, **kw)
    monkeypatch.setattr(AipBudgetActivationStore, 'create_preview', saved)
    def run(_):
        try: return product.submit_request(directory, ref, body, actor, auth)
        except product.BudgetProductBlocked as exc: assert exc.status_code == 503
    with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(run, range(2)))
    assert calls == [1]
    assert product.inquire_request(directory, ref, actor, auth)['status'] == 'observed'


def test_identity_tenant_and_current_member_before_file_access(product, directory, https_signer):
    sign, _ = https_signer
    ref, body, actor, other = case(product, 'preview'); auth = 'Bearer '+sign(actor.subject)
    with pytest.raises(product.BudgetProductBlocked) as exc:
        product.submit_request(directory, ref, body, actor, 'Bearer '+sign(other.subject))
    assert exc.value.status_code == 403 and not list(directory.iterdir())
    product.submit_request(directory, ref, body, actor, auth)
    assert product.inquire_request(directory, ref, other, 'Bearer '+sign(other.subject)) == {'status': 'not_attempted'}
    foreign = Principal(actor.subject, 'dev-org', SCOPE.project_id, token_kind='oidc')
    with pytest.raises((product.BudgetProductBlocked, BudgetActivationDenied)):
        product.inquire_request(directory, ref, foreign, 'Bearer '+sign(actor.subject, changes={'org_id': 'dev-org'}))
    with connect(SCOPE) as conn:
        conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                     (*SCOPE.key, actor.subject)); conn.commit()
    with pytest.raises(BudgetActivationDenied, match='MEMBERSHIP'):
        product.inquire_request(directory, ref, actor, auth)


@pytest.mark.parametrize('operation', ['preview', 'decision', 'revoke'])
def test_http_refresh_uses_only_safe_reference(product, directory, http_client, https_signer, monkeypatch, operation):
    sign, fetched = https_signer
    ref, body, actor, _ = case(product, operation)
    monkeypatch.setenv('AOS_BUDGET_REQUEST_DIRECTORY', str(directory))
    if operation=='preview':
        url = '/v1/aip/budgets/activation-previews/intent'
        query = {'budgetId': ref.resource_id, 'revision': ref.revision, 'headVersion': ref.head_version}
    else:
        url = ('/v1/aip/budgets/activation-previews/'+ref.resource_id+'/decision-intent' if operation=='decision'
               else '/v1/aip/budgets/activation-decisions/'+ref.resource_id+'/revocation-intent')
        query = {}
    headers = {'Authorization': 'Bearer '+sign(actor.subject), 'X-Org-Id': SCOPE.org_id,
               'X-Project-Id': SCOPE.project_id, 'If-Match': '1'}
    before = http_client.get(url, params=query, headers=headers)
    assert before.status_code == 200 and before.json() == {'status': 'not_attempted'}
    created = http_client.post(url, json=body.model_dump(mode='json', by_alias=True), headers=headers)
    assert created.status_code == 200, created.text
    assert created.json()['status'] == 'observed' and created.json()['activationEligible'] is False
    unchanged = counts()
    reread = http_client.get(url, params=query, headers=headers)
    assert reread.status_code == 200 and reread.json() == created.json()
    assert counts() == unchanged and fetched
    for response in (before, created, reread): assert response.headers['cache-control'] == 'no-store'
    assert 'request' not in reread.json() and 'reason' not in reread.json()
    monkeypatch.delenv('AOS_BUDGET_REQUEST_DIRECTORY')
    missing = http_client.get(url, params=query, headers=headers)
    assert missing.status_code == 503 and missing.json()['code'] == 'BUDGET_PRODUCT_DIRECTORY_REQUIRED'
    assert counts() == unchanged
