"""Actual TLS/JWT/files; captured IPC only checks dispatch, not formal effects."""
import os
import pytest
from pydantic import ValidationError
from aos_api.auth import Principal
from aos_api.aip_network_consumer_contracts import NetworkConsumerReferences, NetworkConsumerCommand, NetworkConsumerInquiry
from aos_api.aip_network_consumer_client import ConsumerEndpoint
from aos_api.aip_network_consumer_application import ConsumerApplicationConfig, ConsumerApplicationBlocked, execute_consumer
from aos_api import aip_network_consumer_application as application
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_contracts import raw
from tests.aip.test_network_consumer_boundary_pg import isolated_owner


@pytest.fixture
def client():
    # The shared legacy client deletes formal metadata. Keep this HTTP app isolated.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from aos_api.errors import register_exception_handlers
    from aos_api.routers.aip_runtime_guard_policies import router
    with isolated_owner() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','isolated test') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','isolated test') ON CONFLICT DO NOTHING")
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    with TestClient(app) as test_client:
        yield test_client


def references():
    return {k: v for k, v in raw().items() if k not in {'bearerToken', 'orgId', 'projectId'}}


@pytest.fixture
def configuration(tmp_path):
    attempts = tmp_path/'attempts'
    attempts.mkdir(mode=0o700)
    return ConsumerApplicationConfig(ConsumerEndpoint(tmp_path/'consumer.sock', os.geteuid(),
        os.geteuid()+1, os.getegid()), attempts)


def principal(subject='maker'):
    return Principal(subject, 'org-org', 'dev-project', ['owner'], token_kind='oidc')


def test_real_identity_and_persistent_once_then_inquiry(configuration, https_signer, monkeypatch):
    sign, fetched = https_signer
    calls = []
    def capture(endpoint, request):
        calls.append(request)
        return {'status': 'unresolved'}
    monkeypatch.setattr(application, 'request_consumer', capture)
    ref = NetworkConsumerReferences.model_validate(references())
    token = sign('maker')
    for inquiry in (False, False, True):
        assert execute_consumer(configuration, ref, principal(), 'Bearer '+token,
                                inquiry=inquiry) == {'status': 'unresolved'}
    assert [type(x) for x in calls] == [NetworkConsumerCommand, NetworkConsumerInquiry, NetworkConsumerInquiry]
    assert all(x.org_id == 'org-org' and x.project_id == 'dev-project' for x in calls)
    files = list(configuration.attempt_directory.iterdir())
    assert len(files) == 1
    assert token not in files[0].read_text()
    assert len(fetched) >= 3


@pytest.mark.parametrize('bad', ['subject', 'expired', 'dev'])
def test_bad_identity_never_sends_or_reserves(configuration, https_signer, monkeypatch, bad):
    sign, _ = https_signer
    calls = []
    monkeypatch.setattr(application, 'request_consumer', lambda *a: calls.append(a))
    token = 'dev' if bad == 'dev' else sign('other' if bad == 'subject' else 'maker', changes={'exp': 1} if bad == 'expired' else None)
    with pytest.raises(ConsumerApplicationBlocked):
        execute_consumer(configuration, NetworkConsumerReferences.model_validate(references()),
                         principal(), 'Bearer '+token, inquiry=False)
    assert not calls
    assert not list(configuration.attempt_directory.iterdir())


@pytest.mark.parametrize('extra', ['orgId', 'bearerToken', 'endpoint', 'roles'])
def test_reference_body_rejects_identity_and_connection_injection(extra):
    with pytest.raises(ValidationError):
        NetworkConsumerReferences.model_validate({**references(), extra: 'untrusted'})


def test_default_http_entry_is_disabled(client):
    headers = {'Authorization': 'Bearer dev', 'X-Org-Id': 'org-org', 'X-Project-Id': 'dev-project'}
    for suffix in ('', '/inquiry'):
        result = client.post('/v1/aip/runtime-guard-policies/networks/activation-consumptions'+suffix,
                             headers=headers, json=references())
        assert result.status_code == 503
        assert 'CONSUMER_APPLICATION_UNCONFIGURED' in result.text


def test_http_signed_request_unknown_then_readonly(client, configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    calls = []
    monkeypatch.setattr(client.app.state, 'network_consumer_config', configuration, raising=False)
    def capture(endpoint, request):
        calls.append(type(request))
        return {'status': 'unresolved'}
    monkeypatch.setattr(application, 'request_consumer', capture)
    headers = {'Authorization': 'Bearer '+sign('maker'), 'X-Org-Id': 'org-org', 'X-Project-Id': 'dev-project'}
    url = '/v1/aip/runtime-guard-policies/networks/activation-consumptions'
    for path in (url, url, url+'/inquiry'):
        response = client.post(path, headers=headers, json=references())
        assert response.status_code == 202, response.text
        assert response.json() == {'status': 'unresolved'}
    assert calls == [NetworkConsumerCommand, NetworkConsumerInquiry, NetworkConsumerInquiry]
    response = client.post(url, headers=headers, json={**references(), 'orgId': 'other'})
    assert response.status_code == 400
    assert len(calls) == 3
