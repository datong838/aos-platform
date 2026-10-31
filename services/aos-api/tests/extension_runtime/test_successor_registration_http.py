import pytest
from psycopg import errors

from test_ecommerce_growth_registration_contracts import payload as registration_payload
from test_ecommerce_growth_registration_http import harness as original_harness


def payload():
    return dict(schemaVersion='aos.ecommerce.successor-dispatch-registration/v1',
        registration=registration_payload(), expectedGroupRevision=367,
        predecessorDetachReceiptRef=dict(resourceType='DispatchDisableDetachReceipt',
            resourceId='55555555-5555-4555-8555-555555555555', revision=1,
            contentHash='sha256:'+'5'*64))


@pytest.fixture
def harness():
    original = original_harness.__wrapped__()
    def register(**kw):
        original.calls.append(('successor', kw))
        if original.service.error:
            raise original.service.error
        return dict(receiptId='successor-fixture', executable=False,
                    replayed=original.service.replayed)
    def read(**kw):
        original.calls.append(('successor-read', kw))
        if original.service.error:
            raise original.service.error
        return dict(receiptId='successor-fixture', executable=False, historical=True)
    original.service.register_successor = register
    original.service.read_successor_receipt = read
    return original


def url(installation=None):
    installation = installation or registration_payload()['installationRef']['installationId']
    return '/v1/bundle-runtime-installations/'+installation+'/ecommerce-growth-successor-registrations'


def headers():
    registration = registration_payload()
    return {'Idempotency-Key': registration['idempotencyKey'],
            'If-Match': f'"{registration["installationRef"]["revision"]}"'}


@pytest.mark.parametrize('replayed', [False, True])
def test_successor_exact_contract_uses_authenticated_identity(harness, replayed):
    harness.service.replayed = replayed
    response = harness.client.post(url(), json=payload(), headers=headers())
    assert response.status_code == (200 if replayed else 201), response.text
    assert response.json()['executable'] is False
    assert len(harness.calls) == 1
    method, kw = harness.calls[0]
    assert method == 'successor'
    assert kw['actor'] == 'signed-user'
    assert kw['scope'].key == ('org-org', 'dev-project')
    assert kw['request'].model_dump(mode='json', by_alias=True) == payload()


@pytest.mark.parametrize('defect', ['path', 'key', 'version', 'actor', 'scope',
    'nested-actor', 'missing-key', 'missing-version', 'duplicate-key', 'duplicate-version',
    'missing-detach', 'wrong-detach-kind'])
def test_invalid_successor_never_calls_service(harness, defect):
    body, head, path = payload(), headers(), url()
    if defect == 'path': path = url('99999999-9999-4999-8999-999999999999')
    elif defect == 'key': head['Idempotency-Key'] = 'different'
    elif defect == 'version': head['If-Match'] = '"999"'
    elif defect in ('actor', 'scope'): body[defect] = 'private-sentinel'
    elif defect == 'nested-actor': body['registration']['actor'] = 'private-sentinel'
    elif defect == 'missing-key': head.pop('Idempotency-Key')
    elif defect == 'missing-version': head.pop('If-Match')
    elif defect == 'duplicate-key': head = list(head.items())+[('Idempotency-Key', 'other')]
    elif defect == 'duplicate-version': head = list(head.items())+[('If-Match', '"999"')]
    elif defect == 'missing-detach': body.pop('predecessorDetachReceiptRef')
    else: body['predecessorDetachReceiptRef']['resourceType'] = 'private-sentinel'
    response = harness.client.post(path, json=body, headers=head)
    assert response.status_code in (400, 409, 412, 422, 428), response.text
    assert not harness.calls
    assert 'private-sentinel' not in response.text


def test_successor_history_uses_own_read_method(harness):
    response = harness.client.get(url()+'/receipt', headers=headers())
    assert response.status_code == 200, response.text
    assert response.json()['historical'] is True
    assert response.json()['executable'] is False
    assert len(harness.calls) == 1
    method, kw = harness.calls[0]
    assert method == 'successor-read'
    assert kw == dict(scope=kw['scope'], actor='signed-user',
        installation_id=registration_payload()['installationRef']['installationId'],
        idempotency_key=registration_payload()['idempotencyKey'])
    assert kw['scope'].key == ('org-org', 'dev-project')


@pytest.mark.parametrize('read', [False, True])
@pytest.mark.parametrize('error, expected', [(PermissionError('private-sentinel'), 403),
    (LookupError('private-sentinel'), 404), (ValueError('private-sentinel'), 409),
    (RuntimeError('private-sentinel'), 503), (errors.SerializationFailure('private-sentinel'), 409),
    (errors.InsufficientPrivilege('private-sentinel'), 403),
    (errors.InvalidParameterValue('private-sentinel'), 422),
    (errors.OperationalError('private-sentinel'), 503)])
def test_errors_are_sanitized_without_retry(harness, read, error, expected):
    harness.service.error = error
    response = (harness.client.get(url()+'/receipt', headers=headers()) if read else
                harness.client.post(url(), json=payload(), headers=headers()))
    assert response.status_code == expected, response.text
    assert len(harness.calls) == 1
    assert 'private-sentinel' not in response.text


def test_unconfigured_service_is_closed(harness):
    harness.app.state.extension_runtime_control_plane.first_dispatch_registration_service = None
    response = harness.client.post(url(), json=payload(), headers=headers())
    assert response.status_code == 503
    assert not harness.calls


def test_real_app_has_unique_successor_routes():
    from aos_api.main import app
    paths = app.openapi()['paths']
    path = '/v1/bundle-runtime-installations/{installation_id}/ecommerce-growth-successor-registrations'
    for suffix, method, operation in [('', 'post', 'create_ecommerce_growth_successor_registration'),
        ('/receipt', 'get', 'get_ecommerce_growth_successor_registration_receipt')]:
        assert paths[path+suffix][method]['operationId'] == operation
        assert sum(item.get('operationId') == operation for methods in paths.values()
                   for item in methods.values() if isinstance(item, dict)) == 1
