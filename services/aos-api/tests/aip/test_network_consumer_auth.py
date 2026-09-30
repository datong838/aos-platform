"""Consumer identity adapter tests; not current external-identity acceptance."""
import pytest
from aos_api.auth import Principal
from aos_api.aip_network_consumer_contracts import NetworkConsumerCommand
from aos_api.aip_network_consumer_auth import authenticate_consumer_request, ConsumerAuthBlocked
from tests.aip.test_network_consumer_contracts import raw
from tests.aip.test_aip_network_issuer_auth import _external_config


@pytest.mark.parametrize('name,value', [
    ('AOS_AUTH_ALLOW_DEV', '1'), ('AOS_AUTH_EXTERNAL_ONLY', '0'),
    ('AOS_OIDC_ISSUER', ''), ('AOS_OIDC_AUDIENCE', ''),
    ('AOS_OIDC_JWKS_URL', 'http://127.0.0.1/jwks'),
])
def test_consumer_rejects_incomplete_config(monkeypatch, name, value):
    _external_config(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(ConsumerAuthBlocked):
        authenticate_consumer_request(NetworkConsumerCommand.model_validate(raw()))


def test_real_dev_signed_token_rejected(monkeypatch):
    _external_config(monkeypatch)
    from aos_api.oidc import issue_dev_token
    token = issue_dev_token(subject='maker', org_id='org-org', project_id='dev-project')['accessToken']
    with pytest.raises(ConsumerAuthBlocked) as error:
        authenticate_consumer_request(NetworkConsumerCommand.model_validate(raw(bearerToken=token)))
    assert token not in str(error.value)


@pytest.mark.parametrize('changes', [
    {'org_id': 'dev-org'}, {'project_id': 'other'}, {'token_kind': 'dev'},
    {'subject': ''}, {'subject': 'unknown'}, {'subject': ' maker'}, {'subject': 'maker\n'},
])
def test_adapter_rejects_unbound_resolver_result(monkeypatch, changes):
    _external_config(monkeypatch)
    from aos_api import aip_network_consumer_auth as module
    principal = Principal(**{'subject': 'maker', 'org_id': 'org-org',
                             'project_id': 'dev-project', 'token_kind': 'oidc', **changes})
    monkeypatch.setattr(module, 'resolve_principal', lambda **kw: principal)
    with pytest.raises(ConsumerAuthBlocked):
        authenticate_consumer_request(NetworkConsumerCommand.model_validate(raw()))


def test_each_command_and_inquiry_reverifies_exact_scope(monkeypatch):
    _external_config(monkeypatch)
    from aos_api import aip_network_consumer_auth as module
    calls = []
    def resolve(**kw):
        calls.append(kw)
        return Principal(subject='maker', org_id='org-org', project_id='dev-project', token_kind='oidc')
    monkeypatch.setattr(module, 'resolve_principal', resolve)
    command = NetworkConsumerCommand.model_validate(raw())
    for request in (command, command.inquiry()):
        assert authenticate_consumer_request(request).subject == 'maker'
    assert calls == [{'token': 'header.payload.signature', 'header_org': 'org-org',
                      'header_project': 'dev-project'}] * 2


def test_errors_redacted_and_raw_dict_rejected(monkeypatch):
    _external_config(monkeypatch)
    from aos_api import aip_network_consumer_auth as module
    def fail(**kw):
        raise RuntimeError(kw['token'])
    monkeypatch.setattr(module, 'resolve_principal', fail)
    for request in (raw(), NetworkConsumerCommand.model_validate(raw())):
        with pytest.raises(ConsumerAuthBlocked) as error:
            authenticate_consumer_request(request)
        assert 'header.payload.signature' not in str(error.value)
