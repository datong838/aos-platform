"""Product resume uses real private files and TLS identity; IPC is a capture fixture."""
import json
import os
from pathlib import Path

import pytest

from aos_api import aip_network_issuer_application as application
from aos_api import aip_network_issuer_product as product
from aos_api.aip_network_issuer_application import IssuerApplicationBlocked, IssuerApplicationConfig
from aos_api.aip_network_issuer_contracts import NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry
from tests.aip.test_network_issuer_application import configuration, decision, principal
from tests.aip.test_network_consumer_application import client
from tests.aip.test_network_consumer_signed_https_pg import https_signer


def test_reloaded_product_reads_original_hash_without_resubmitting(configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    auth = 'Bearer '+sign('checker')
    calls = []
    def capture(endpoint, request):
        calls.append(request)
        return {'status': 'unresolved'}
    monkeypatch.setattr(application, 'request_issuer', capture)
    monkeypatch.setattr(product, 'request_issuer', capture)
    assert product.inquire_product_decision(configuration, 'proposal-1', 1, principal(), auth) == {'status': 'not_attempted'}
    assert not calls and not list(configuration.attempt_directory.iterdir())
    assert product.decide_product(configuration, 'proposal-1', decision(), principal(), auth) == {'status': 'unresolved'}
    restored = IssuerApplicationConfig(configuration.endpoint, configuration.attempt_directory)
    assert product.inquire_product_decision(restored, 'proposal-1', 1, principal(), auth) == {'status': 'unresolved'}
    assert product.decide_product(restored, 'proposal-1', decision(), principal(), auth) == {'status': 'unresolved'}
    assert [type(x) for x in calls] == [NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry, NetworkIssuerDecisionInquiry]
    assert calls[0].request_hash == calls[1].request_hash == calls[2].request_hash
    with pytest.raises(IssuerApplicationBlocked) as exc:
        product.decide_product(restored, 'proposal-1', decision('rejected'), principal(), auth)
    assert exc.value.status_code == 409
    assert len(calls) == 3


@pytest.mark.parametrize('bad', ['broken', 'mismatch', 'symlink', 'fifo'])
def test_untrusted_saved_marker_never_becomes_not_attempted(configuration, https_signer, monkeypatch, bad):
    sign, _ = https_signer
    auth = 'Bearer '+sign('checker')
    monkeypatch.setattr(application, 'request_issuer', lambda *a: {'status': 'unresolved'})
    product.decide_product(configuration, 'proposal-1', decision(), principal(), auth)
    path = next(configuration.attempt_directory.iterdir())
    if bad == 'broken': path.write_text('{broken')
    elif bad == 'mismatch':
        data = json.loads(path.read_text()); data['principalSubject'] = 'other'; path.write_text(json.dumps(data))
    else:
        path.unlink()
        if bad == 'symlink': path.symlink_to(configuration.attempt_directory/'missing')
        else: os.mkfifo(path, 0o600)
    monkeypatch.setattr(product, 'request_issuer', lambda *a: pytest.fail('untrusted marker must not send'))
    with pytest.raises(IssuerApplicationBlocked) as exc:
        product.inquire_product_decision(configuration, 'proposal-1', 1, principal(), auth)
    assert exc.value.status_code == 503


def test_actor_and_version_own_separate_slots_and_expired_identity_cannot_read(configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    calls = []
    monkeypatch.setattr(application, 'request_issuer', lambda e, r: calls.append(r) or {'status': 'unresolved'})
    product.decide_product(configuration, 'proposal-1', decision(), principal(), 'Bearer '+sign('checker'))
    for actor, version in [('other', 1), ('checker', 2)]:
        assert product.inquire_product_decision(configuration, 'proposal-1', version,
            principal(actor), 'Bearer '+sign(actor)) == {'status': 'not_attempted'}
    with pytest.raises(IssuerApplicationBlocked) as exc:
        product.inquire_product_decision(configuration, 'proposal-1', 1, principal(),
                                         'Bearer '+sign('checker', changes={'exp': 1}))
    assert exc.value.status_code == 403
    assert len(calls) == 1


def test_product_http_has_no_client_key_and_get_reads_original_attempt(client, configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    calls = []
    def capture(e, r):
        calls.append(r)
        return {'status': 'unresolved'}
    monkeypatch.setattr(application, 'request_issuer', capture)
    monkeypatch.setattr(product, 'request_issuer', capture)
    monkeypatch.setattr(client.app.state, 'network_issuer_config', configuration, raising=False)
    headers = {'Authorization': 'Bearer '+sign('checker'), 'X-Org-Id': 'org-org', 'X-Project-Id': 'dev-project'}
    url = '/v1/aip/runtime-guard-policies/networks/activation-proposals/proposal-1/decision-intent'
    assert client.get(url+'?version=1', headers=headers).json() == {'status': 'not_attempted'}
    body = decision().model_dump(mode='json', by_alias=True)
    assert client.post(url, headers=headers, json=body).status_code == 202
    response = client.get(url+'?version=1', headers=headers)
    assert response.status_code == 202 and response.json() == {'status': 'unresolved'}
    assert [type(x) for x in calls] == [NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry]
    assert client.post(url, headers=headers, json={**body, 'orgId': 'injected'}).status_code == 400
