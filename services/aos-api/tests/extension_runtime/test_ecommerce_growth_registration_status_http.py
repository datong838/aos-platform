import pytest
from test_ecommerce_growth_registration_http import harness, url


@pytest.fixture
def status_http(harness):
    def status(**kw):
        harness.calls.append(kw)
        if harness.service.error:raise harness.service.error
        return dict(state='registered',allowedActions=[],executable=False)
    harness.service.registration_status=status
    return harness


def test_status_without_manual_key_uses_trusted_scope(status_http):
    h=status_http
    response=h.client.get(url()+'/status')
    assert response.status_code==200,response.text
    assert response.json()['allowedActions']==[]
    assert h.calls[0]['scope'].key==('org-org','dev-project')
    assert h.calls[0]['actor']=='signed-user' and h.calls[0]['installation_id'] in url()


def test_unconfigured_is_not_unregistered(status_http):
    h=status_http;h.app.state.extension_runtime_control_plane.first_dispatch_registration_service=None
    response=h.client.get(url()+'/status')
    assert response.status_code==503 and not h.calls


@pytest.mark.parametrize('error,code',[(PermissionError('secret-sentinel'),403),(ValueError('secret-sentinel'),409),(OSError('secret-sentinel'),503)])
def test_status_errors_are_safe(status_http,error,code):
    h=status_http;h.service.error=error
    response=h.client.get(url()+'/status')
    assert response.status_code==code and 'secret-sentinel' not in response.text
