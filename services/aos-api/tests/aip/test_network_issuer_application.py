"""TLS/JWT, durable files and HTTP; captured IPC is not real approval proof."""
import os
import pytest

from aos_api.auth import Principal
from aos_api.aip_action_models import DecideActionProposalRequest
from aos_api.aip_network_issuer_client import IssuerEndpoint
from aos_api.aip_network_issuer_contracts import NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry
from aos_api.aip_network_issuer_application import IssuerApplicationConfig, IssuerApplicationBlocked, execute_issuer
from aos_api import aip_network_issuer_application as application
from tests.aip.test_network_consumer_application import client
from tests.aip.test_network_consumer_signed_https_pg import https_signer


def decision(value='approved'):
    return DecideActionProposalRequest(expected_proposal_version=1,
        expected_proposal_hash='a'*64, decision=value, reason='reviewed')


def principal(subject='checker'):
    return Principal(subject, 'org-org', 'dev-project', ['owner'], token_kind='oidc')


@pytest.fixture
def configuration(tmp_path):
    directory = tmp_path/'api-attempts'
    directory.mkdir(mode=0o700)
    return IssuerApplicationConfig(IssuerEndpoint(tmp_path/'issuer.sock', os.geteuid(),
        os.geteuid()+1, os.getegid()), directory)


def execute(config, token, *, inquiry=False, body=None, actor=None):
    return execute_issuer(config, 'proposal-1', 'key-1', body or decision(),
                          actor or principal(), 'Bearer '+token, inquiry=inquiry)


def test_durable_unknown_then_recreated_config_only_inquires(configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    token = sign('checker')
    calls = []
    def lost(endpoint, request):
        calls.append(request)
        raise OSError('private diagnostic must not escape')
    monkeypatch.setattr(application, 'request_issuer', lost)
    assert execute(configuration, token) == {'status': 'unresolved'}
    restored = IssuerApplicationConfig(configuration.endpoint, configuration.attempt_directory)
    assert execute(restored, token) == {'status': 'unresolved'}
    assert execute(restored, token, inquiry=True) == {'status': 'unresolved'}
    assert [type(x) for x in calls] == [NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry, NetworkIssuerDecisionInquiry]
    files = list(configuration.attempt_directory.iterdir())
    assert len(files) == 1
    assert token not in files[0].read_text()
    files[0].write_text('{broken')
    execute(restored, token)
    assert type(calls[-1]) is NetworkIssuerDecisionInquiry


def test_conflict_never_sends_second_decision(configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    calls = []
    monkeypatch.setattr(application, 'request_issuer', lambda e, r: calls.append(r) or {'status': 'unresolved'})
    token = sign('checker')
    execute(configuration, token)
    with pytest.raises(IssuerApplicationBlocked) as error:
        execute(configuration, token, body=decision('rejected'))
    assert error.value.status_code == 409
    assert len(calls) == 1


@pytest.mark.parametrize('bad', ['expired', 'subject', 'dev'])
def test_auth_rechecked_before_any_write(configuration, https_signer, monkeypatch, bad):
    sign, _ = https_signer
    token = 'dev' if bad == 'dev' else sign('other' if bad == 'subject' else 'checker',
                                          changes={'exp': 1} if bad == 'expired' else None)
    calls = []
    monkeypatch.setattr(application, 'request_issuer', lambda *a: calls.append(a))
    with pytest.raises(IssuerApplicationBlocked) as error:
        execute(configuration, token)
    assert error.value.status_code == 403
    assert not calls and not list(configuration.attempt_directory.iterdir())


def test_explicit_inquiry_does_not_reserve(configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    calls = []
    monkeypatch.setattr(application, 'request_issuer', lambda e, r: calls.append(r) or {'status': 'unresolved'})
    execute(configuration, sign('checker'), inquiry=True)
    assert type(calls[0]) is NetworkIssuerDecisionInquiry
    assert not list(configuration.attempt_directory.iterdir())


@pytest.mark.parametrize('failure', ['permissions', 'storage'])
def test_storage_failure_never_dispatches(configuration, https_signer, monkeypatch, failure):
    sign, _ = https_signer
    calls = []
    monkeypatch.setattr(application, 'request_issuer', lambda *a: calls.append(a))
    if failure == 'permissions':
        configuration.attempt_directory.chmod(0o755)
    else:
        def fail(*a): raise OSError('disk failure')
        monkeypatch.setattr(application, 'reserve_decision_attempt', fail)
    with pytest.raises(IssuerApplicationBlocked) as error:
        execute(configuration, sign('checker'))
    assert error.value.status_code == 503
    assert not calls and not list(configuration.attempt_directory.iterdir())


def test_http_default_disabled(client):
    headers = {'Authorization': 'Bearer dev', 'X-Org-Id': 'org-org', 'X-Project-Id': 'dev-project', 'Idempotency-Key': 'key-1'}
    url = '/v1/aip/runtime-guard-policies/networks/activation-proposals/proposal-1/decision-attempts'
    for suffix in ('', '/inquiry'):
        result = client.post(url+suffix, headers=headers, json=decision().model_dump(mode='json', by_alias=True))
        assert result.status_code == 503
        assert 'ISSUER_APPLICATION_UNCONFIGURED' in result.text


def test_signed_http_replay_and_body_injection(client, configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    calls = []
    monkeypatch.setattr(application, 'request_issuer', lambda e, r: calls.append(r) or {'status': 'unresolved'})
    monkeypatch.setattr(client.app.state, 'network_issuer_config', configuration, raising=False)
    headers = {'Authorization': 'Bearer '+sign('checker'), 'X-Org-Id': 'org-org', 'X-Project-Id': 'dev-project', 'Idempotency-Key': 'key-1'}
    body = decision().model_dump(mode='json', by_alias=True)
    url = '/v1/aip/runtime-guard-policies/networks/activation-proposals/proposal-1/decision-attempts'
    for suffix in ('', '', '/inquiry'):
        result = client.post(url+suffix, headers=headers, json=body)
        assert result.status_code == 202, result.text
    assert [type(x) for x in calls] == [NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry, NetworkIssuerDecisionInquiry]
    for key in ('orgId', 'actorId', 'bearerToken', 'endpoint'):
        result = client.post(url, headers=headers, json={**body, key: 'injected'})
        assert result.status_code == 400
    assert len(calls) == 3
