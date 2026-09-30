"""Real disposable PG and TLS identity; never a formal installation proof."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from aos_api import aip_network_proposal_product as product
from aos_api.aip_network_issuer_application import IssuerApplicationBlocked
from tests.aip.test_network_issuer_application import configuration, principal
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_application import client
from tests.aip.test_network_proposal_reconcile_pg import saved_request, counts


def setup_request(signer):
    _, body, actor, _ = saved_request()
    return body, actor, 'Bearer '+signer(actor.subject)


def read(config, body, actor, auth):
    return product.inquire_product_proposal(config, body.candidate.policy_id,
        body.candidate.revision, 0, actor, auth)


def test_commit_response_lost_then_reload_only_reads_original(configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    body, actor, auth = setup_request(sign)
    assert read(configuration, body, actor, auth) == {'status': 'not_attempted'}
    before = counts()
    original = product.propose_network_activation
    calls = []
    def lost(*args, **kwargs):
        calls.append(1)
        original(*args, **kwargs)
        raise OSError('lost after committed creation')
    monkeypatch.setattr(product, 'propose_network_activation', lost)
    first = product.submit_product_proposal(configuration, body, 0, actor, auth)
    assert first['status'] == 'observed' and first['proposalId']
    for _ in range(2):
        assert read(configuration, body, actor, auth) == first
        assert product.submit_product_proposal(configuration, body, 0, actor, auth) == first
    assert calls == [1]
    after = counts()
    assert after[:2] == (before[0]+1, before[1]+1) and after[2:] == before[2:]
    content = next(configuration.attempt_directory.iterdir()).read_text()
    assert auth.removeprefix('Bearer ') not in content
    changed = body.model_copy(update={'expires_at': body.expires_at+timedelta(seconds=1)})
    with pytest.raises(IssuerApplicationBlocked) as e:
        product.submit_product_proposal(configuration, changed, 0, actor, auth)
    assert e.value.status_code == 409 and calls == [1]


def test_parallel_requests_reserve_once(configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    body, actor, auth = setup_request(sign)
    original = product.propose_network_activation
    calls = []
    def create(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(product, 'propose_network_activation', create)
    def run():
        try:
            return product.submit_product_proposal(configuration, body, 0, actor, auth)
        except IssuerApplicationBlocked as e:
            assert e.status_code == 503  # Incomplete reservation is never permission to send.
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: run(), range(2)))
    assert calls == [1] and read(configuration, body, actor, auth)['status'] == 'observed'


def test_failure_before_creation_remains_unresolved_without_retry(configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    body, actor, auth = setup_request(sign)
    before = counts()
    calls = []
    def failed(*args, **kwargs):
        calls.append(1)
        raise OSError('unavailable; do not infer nonexecution from transport')
    monkeypatch.setattr(product, 'propose_network_activation', failed)
    assert product.submit_product_proposal(configuration, body, 0, actor, auth) == {'status': 'unresolved'}
    assert product.submit_product_proposal(configuration, body, 0, actor, auth) == {'status': 'unresolved'}
    assert read(configuration, body, actor, auth) == {'status': 'unresolved'}
    assert calls == [1] and counts() == before


def test_fsync_failure_never_dispatches_or_erases_reservation(configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    body, actor, auth = setup_request(sign)
    original = os.fsync
    monkeypatch.setattr(product, 'propose_network_activation', lambda *a, **k: pytest.fail('must not send'))
    def fail(fd): raise OSError('disk error')
    monkeypatch.setattr(os, 'fsync', fail)
    with pytest.raises(IssuerApplicationBlocked) as e:
        product.submit_product_proposal(configuration, body, 0, actor, auth)
    assert e.value.status_code == 503 and len(list(configuration.attempt_directory.iterdir())) == 1
    monkeypatch.setattr(os, 'fsync', original)
    assert product.submit_product_proposal(configuration, body, 0, actor, auth) == {'status': 'unresolved'}


@pytest.mark.parametrize('bad', ['broken', 'actor', 'symlink', 'fifo'])
def test_bad_saved_request_cannot_recreate(configuration, https_signer, monkeypatch, bad):
    sign, _ = https_signer
    body, actor, auth = setup_request(sign)
    product.submit_product_proposal(configuration, body, 0, actor, auth)
    path = next(configuration.attempt_directory.iterdir())
    if bad == 'broken': path.write_text('{')
    elif bad == 'actor':
        data = json.loads(path.read_text()); data['subject'] = 'another'; path.write_text(json.dumps(data))
    else:
        path.unlink()
        if bad == 'fifo': os.mkfifo(path, 0o600)
        else: path.symlink_to(configuration.attempt_directory/'missing')
    monkeypatch.setattr(product, 'propose_network_activation', lambda *a, **k: pytest.fail('must not recreate'))
    with pytest.raises(IssuerApplicationBlocked) as e:
        read(configuration, body, actor, auth)
    assert e.value.status_code == 503


def test_http_recovers_without_original_body_and_rejects_other_identity(client, configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    body, actor, auth = setup_request(sign)
    monkeypatch.setattr(client.app.state, 'network_issuer_config', configuration, raising=False)
    url = '/v1/aip/runtime-guard-policies/networks/proposal-intent'
    headers = {'Authorization': auth, 'X-Org-Id': actor.org_id, 'X-Project-Id': actor.project_id, 'If-Match': '0'}
    query = {'policyId': body.candidate.policy_id, 'revision': 1, 'headVersion': 0}
    assert client.get(url, headers=headers, params=query).json() == {'status': 'not_attempted'}
    r = client.post(url, headers=headers, json=body.model_dump(mode='json', by_alias=True))
    assert r.status_code == 200 and r.json()['status'] == 'observed'
    assert client.get(url, headers=headers, params=query).json() == r.json()
    assert read(configuration, body, principal('other'), 'Bearer '+sign('other')) == {'status': 'not_attempted'}
    denied = client.get(url, headers={**headers, 'Authorization': 'Bearer '+sign(actor.subject, changes={'exp': 1})}, params=query)
    assert denied.status_code == 401
