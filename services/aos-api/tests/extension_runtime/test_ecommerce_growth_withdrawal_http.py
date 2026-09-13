import pytest
from test_ecommerce_growth_registration_http import harness, url
from test_ecommerce_growth_registration_withdrawal import args


def body():return args()['request'].model_dump(mode='json')
def endpoint():return url()+'/withdrawals'
def headers(request):return {'Idempotency-Key':request['idempotencyKey'],'If-Match':'"'+str(request['expectedInstallationEtag'])+'"'}


@pytest.fixture
def withdrawal_http(harness):
    def withdraw(**kw):
        harness.calls.append(('withdraw',kw))
        if harness.service.error:raise harness.service.error
        return dict(receiptId='fixture-withdrawal',releasedOperationCount=9,executable=False,replayed=harness.service.replayed)
    def read(**kw):
        harness.calls.append(('withdraw-read',kw))
        if harness.service.error:raise harness.service.error
        return dict(receiptId='fixture-withdrawal',historical=True,executable=False)
    harness.service.withdraw=withdraw;harness.service.read_withdrawal_receipt=read
    return harness


@pytest.mark.parametrize('replay',[False,True])
def test_withdraw_receipt_and_trusted_identity(withdrawal_http,replay):
    h=withdrawal_http;h.service.replayed=replay;request=body()
    response=h.client.post(endpoint(),json=request,headers=headers(request))
    assert response.status_code==(200 if replay else 201),response.text
    method,kw=h.calls[0]
    assert method=='withdraw' and kw['actor']=='signed-user' and kw['scope'].key==('org-org','dev-project')
    assert kw['installation_id'] in endpoint() and kw['request'].idempotencyKey==request['idempotencyKey']
    assert response.json()['executable'] is False


@pytest.mark.parametrize('change',['key','etag','missing-key','missing-etag','duplicate-key','duplicate-etag','actor','scope','force'])
def test_bad_envelope_never_calls_owner(withdrawal_http,change):
    h=withdrawal_http;request=body();head=headers(request)
    if change=='key':head['Idempotency-Key']='other'
    elif change=='etag':head['If-Match']='"999"'
    elif change=='missing-key':head.pop('Idempotency-Key')
    elif change=='missing-etag':head.pop('If-Match')
    elif change=='duplicate-key':head=list(head.items())+[('Idempotency-Key','other')]
    elif change=='duplicate-etag':head=list(head.items())+[('If-Match','"999"')]
    else:request[change]='sensitive-sentinel'
    response=h.client.post(endpoint(),json=request,headers=head)
    assert response.status_code in (400,409,412,422,428),response.text
    assert not h.calls and 'sensitive-sentinel' not in response.text


def test_receipt_is_current_permission_read_only(withdrawal_http):
    h=withdrawal_http;request=body()
    response=h.client.get(endpoint()+'/receipt',headers=headers(request))
    assert response.status_code==200 and response.json()['historical'] is True
    assert h.calls[0][0]=='withdraw-read' and h.calls[0][1]['actor']=='signed-user'


def test_unconfigured_endpoint_is_unavailable(withdrawal_http):
    h=withdrawal_http;h.app.state.extension_runtime_control_plane.first_dispatch_registration_service=None
    request=body();response=h.client.post(endpoint(),json=request,headers=headers(request))
    assert response.status_code==503 and not h.calls


@pytest.mark.parametrize('error,status',[(ValueError('private-sentinel'),409),(PermissionError('private-sentinel'),403),(OSError('private-sentinel'),503)])
def test_error_details_not_exposed(withdrawal_http,error,status):
    h=withdrawal_http;h.service.error=error;request=body()
    response=h.client.post(endpoint(),json=request,headers=headers(request))
    assert response.status_code==status,response.text
    assert 'private-sentinel' not in response.text
