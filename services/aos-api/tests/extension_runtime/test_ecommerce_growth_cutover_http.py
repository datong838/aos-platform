from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg import errors
from test_ecommerce_growth_registration_http import harness
from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverConflict


@pytest.fixture
def cutover_http(harness):
    def read(**kwargs):
        harness.calls.append(kwargs)
        if harness.service.error:raise harness.service.error
        return dict(historical=True,executable=False)
    harness.service.read_prepare_receipt=read
    harness.service.read_activation_history=read
    harness.app.state.extension_runtime_control_plane.ecommerce_growth_cutover_service=harness.service
    return harness


def url(kind='history'):
    return '/v1/bundle-runtime-installations/97aeb2e7-59ba-40f6-89a3-fb0293bc0497/ecommerce-growth-cutovers/'+kind


@pytest.mark.parametrize('kind',['receipt','history'])
def test_read_principal_and_original_key(cutover_http,kind):
    h=cutover_http
    response=h.client.get(url(kind)+'?actor=other&org_id=other',headers={'Idempotency-Key':'original-prepare'})
    assert response.status_code==200,response.text
    assert response.json()==dict(historical=True,executable=False)
    assert len(h.calls)==1
    assert h.calls[0]['actor']=='signed-user' and h.calls[0]['scope'].key==('org-org','dev-project')
    assert h.calls[0]['idempotency_key']=='original-prepare'


@pytest.mark.parametrize('error,code',[(LookupError('private-sentinel'),404),(PermissionError('private-sentinel'),403),
    (EcommerceGrowthCutoverConflict('private-sentinel'),409),(errors.SerializationFailure('private-sentinel'),409),
    (errors.InsufficientPrivilege('private-sentinel'),403),(RuntimeError('private-sentinel'),503)])
def test_safe_errors(cutover_http,error,code):
    h=cutover_http;h.service.error=error
    response=h.client.get(url(),headers={'Idempotency-Key':'original-prepare'})
    assert response.status_code==code,response.text
    assert 'private-sentinel' not in response.text


@pytest.mark.parametrize('headers',[{},[('Idempotency-Key','first'),('Idempotency-Key','second')]])
def test_bad_key_never_calls(cutover_http,headers):
    h=cutover_http
    response=h.client.get(url(),headers=headers)
    assert response.status_code in (400,422,428)
    assert not h.calls


def test_missing_service(cutover_http):
    h=cutover_http;h.app.state.extension_runtime_control_plane.ecommerce_growth_cutover_service=None
    assert h.client.get(url(),headers={'Idempotency-Key':'key'}).status_code==503
    assert not h.calls


def test_openapi_reads_only_and_once(cutover_http):
    paths=cutover_http.app.openapi()['paths']
    for suffix,operation in [('receipt','get_ecommerce_growth_cutover_prepare_receipt'),('history','get_ecommerce_growth_cutover_history')]:
        path='/v1/bundle-runtime-installations/{installation_id}/ecommerce-growth-cutovers/'+suffix
        assert set(paths[path])=={'get'}
        assert paths[path]['get']['operationId']==operation
        assert sum(item.get('operationId')==operation for methods in paths.values() for item in methods.values() if isinstance(item,dict))==1


def test_invalid_path_is_not_echoed(cutover_http):
    response=cutover_http.client.get('/v1/bundle-runtime-installations/private-sentinel/ecommerce-growth-cutovers/history',headers={'Idempotency-Key':'key'})
    assert response.status_code==422
    assert 'private-sentinel' not in response.text
    assert not cutover_http.calls
