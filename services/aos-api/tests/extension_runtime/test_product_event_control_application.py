"""Package control contract tests; ports are doubles, not live authorization."""
from copy import deepcopy
from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5
import pytest
from test_product_event_binding import pair, body
from test_product_event_command import dispatch
from test_product_event_application import RecordingPort, APPROVAL
from ecommerce_growth.ecommerce_business_investigation_application import EcommerceGrowthApplication
from ecommerce_growth.ecommerce_product_event_control import build_event_control_command
from ecommerce_growth.ecommerce_business_investigation_case import canonical_hash
from aos_api.ecommerce_product_event_control_contracts import ProductEventControlCommand


def ref(): return replace(dispatch(),operation_id='ecommerce_growth_event_control')

def command(policy,intent='enable'):
    return build_event_control_command(policy,dispatch_ref=ref(),approval_ref=APPROVAL if intent=='enable' else None,
        idempotency_key='original-control',expected_binding_revision=0,intent=intent)


def receipt(policy,intent='enable'):
    c=command(policy,intent)
    binding=dict(org_id=ref().org_id,project_id=ref().project_id,policy_id=policy.policy_id,
        policy_revision=policy.revision,policy_hash=policy.content_hash,revision=1,cadence='event',
        enabled=intent=='enable',approved=True)
    authority=dict(schemaVersion='aos.ecommerce.product-event-control-receipt/v1',actor='current-user',command=c,binding=binding)
    return dict(receiptRef=dict(resourceType='EventPolicyControlReceipt',resourceId=str(uuid5(NAMESPACE_URL,
        canonical_hash(dict(scope=[ref().org_id,ref().project_id],controlKey=c['idempotencyKey'])))),
        revision=1,contentHash=canonical_hash(authority)),authority=authority,replayed=False)


def invoke(port,policy,intent='enable'):
    return EcommerceGrowthApplication(RecordingPort(),control_port=port).control_event_policy(policy=policy,
        dispatch_ref=ref(),approval_ref=APPROVAL if intent=='enable' else None,idempotency_key='original-control',
        expected_binding_revision=0,intent=intent)


@pytest.mark.parametrize('intent',['enable','disable'])
def test_wire_and_original_receipt_recovery(pair,intent):
    policy=pair[1]
    assert ProductEventControlCommand.model_validate(command(policy,intent)).model_dump(by_alias=True,mode='json')==command(policy,intent)
    port=RecordingPort(receipt(policy,intent))
    assert invoke(port,policy,intent)['replayed'] is False
    port.response['replayed']=True
    assert invoke(port,policy,intent)['replayed'] is True
    assert port.calls[0]==port.calls[1]


def test_timeout_calls_once(pair):
    port=RecordingPort(error=TimeoutError('unknown'))
    with pytest.raises(TimeoutError):invoke(port,pair[1])
    assert len(port.calls)==1


@pytest.mark.parametrize('field',['tenant','enabled','revision','command','hash','uuid','replayed'])
def test_receipt_drift_rejected_even_with_recomputed_hash(pair,field):
    p=pair[1];result=receipt(p);a=result['authority']
    if field=='tenant':a['binding']['org_id']='dev-org'
    if field=='enabled':a['binding']['enabled']=False
    if field=='revision':a['binding']['revision']=True
    if field=='command':a['command']['idempotencyKey']='other'
    if field=='uuid':result['receiptRef']['resourceId']='bad'
    if field=='replayed':result['replayed']=1
    result['receiptRef']['contentHash']=canonical_hash(a) if field!='hash' else 'sha256:'+'0'*64
    port=RecordingPort(result)
    with pytest.raises(ValueError,match='receipt'):invoke(port,p)
    assert len(port.calls)==1


def test_no_port_is_not_executable(pair):
    with pytest.raises(RuntimeError,match='control port'):
        EcommerceGrowthApplication(RecordingPort()).control_event_policy(policy=pair[1],dispatch_ref=ref(),
            approval_ref=APPROVAL,idempotency_key='key',expected_binding_revision=0,intent='enable')


@pytest.mark.parametrize('changes',[{'expected_binding_revision':True},{'intent':'toggle'},
    {'approval_ref':None},{'idempotency_key':' bad'},{'dispatch_ref':replace(ref(),org_id='dev-org')}])
def test_invalid_intent_fails_before_execution(pair,changes):
    kwargs=dict(dispatch_ref=ref(),approval_ref=APPROVAL,idempotency_key='key',expected_binding_revision=0,intent='enable')
    kwargs.update(changes)
    with pytest.raises((ValueError,TypeError)):build_event_control_command(pair[1],**kwargs)
