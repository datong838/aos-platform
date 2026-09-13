from copy import deepcopy
import pytest
from aos_api.ecommerce_growth_registration_withdrawal import RegistrationWithdrawalRequest, require_pristine_withdrawal
from test_ecommerce_growth_registration_origin import inputs


def args():
    source=inputs()
    request=RegistrationWithdrawalRequest(registrationReceiptRef=source['receipt_ref'],
        expectedInstallationEtag=5,idempotencyKey='withdraw-first-1')
    return dict(row=source['row'],scope=source['scope'],request=request,
        dispatch_snapshot=source['dispatch_snapshot'],cutover_count=0,dependency_count=0)


def test_pristine_origin_only_no_execution_authority():
    value=args();before=deepcopy(value)
    result=require_pristine_withdrawal(**value)
    assert result.request_hash()==value['row']['request_hash']
    assert value==before


@pytest.mark.parametrize('field,value',[('cutover_count',1),('cutover_count',True),
    ('dependency_count',1),('dependency_count',False),('dependency_count',-1),('dependency_count',0.0)])
def test_any_cutover_or_dependency_blocks(field,value):
    data=args();data[field]=value
    with pytest.raises(ValueError):require_pristine_withdrawal(**data)


@pytest.mark.parametrize('mutation',['partial','extra','active','revision','group','ref','tenant'])
def test_changed_origin_or_dispatch_blocks(mutation):
    data=args()
    if mutation=='partial':data['dispatch_snapshot'].pop()
    elif mutation=='extra':data['dispatch_snapshot'].append(deepcopy(data['dispatch_snapshot'][0]))
    elif mutation=='active':data['dispatch_snapshot'][0]['operationFence']=False
    elif mutation=='revision':data['dispatch_snapshot'][0]['revision']=3
    elif mutation=='group':data['dispatch_snapshot'][0]['cutoverGroupRevision']=2
    elif mutation=='tenant':
        from aos_api.tenant_scope import TenantScope
        data['scope']=TenantScope('other','project-a')
    else:
        body=data['request'].model_dump();body['registrationReceiptRef']['contentHash']='sha256:'+'0'*64
        data['request']=RegistrationWithdrawalRequest.model_validate(body)
    with pytest.raises(ValueError):require_pristine_withdrawal(**data)


@pytest.mark.parametrize('change',[{'expectedInstallationEtag':True},{'expectedInstallationEtag':0},
    {'idempotencyKey':' '},{'idempotencyKey':'x\n'},{'schemaVersion':'other'},{'force':True}])
def test_request_rejects_ambiguous_or_bypass_fields(change):
    body=args()['request'].model_dump();body.update(change)
    with pytest.raises(ValueError):RegistrationWithdrawalRequest.model_validate(body)


def test_hash_binds_receipt_etag_and_key():
    request=args()['request'];body=request.model_dump();body['expectedInstallationEtag']=6
    assert RegistrationWithdrawalRequest.model_validate(body).request_hash()!=request.request_hash()
    body=request.model_dump();body['idempotencyKey']='other'
    assert RegistrationWithdrawalRequest.model_validate(body).request_hash()!=request.request_hash()
