import pytest
from pydantic import ValidationError
from aos_api.ecommerce_product_event_control_contracts import ProductEventControlCommand
from aos_api.ecommerce_growth_host_ports import _reject_authority_overrides


def payload():
    ref=dict(resourceType='SchedulePolicyRevision',resourceId='policy-1',revision=1,
             contentHash='sha256:'+'a'*64,receiptId=None)
    return dict(schemaVersion='aos.ecommerce.product-event-control-command/v1',idempotencyKey='original-key',
        policyRef=ref,expectedBindingRevision=0,intent='enable',
        approvalRef=dict(ref,resourceType='ActionApprovalEvent',resourceId='approval-1'))


def test_wire_is_business_intent_not_host_authority():
    raw=payload();command=ProductEventControlCommand.model_validate(raw)
    assert command.model_dump(by_alias=True,mode='json')==raw
    _reject_authority_overrides(raw)


@pytest.mark.parametrize('field,value', [('expectedBindingRevision',True),('expectedBindingRevision',-1),
    ('expectedBindingRevision',2**63),('intent','enabled'),('idempotencyKey',' key'),
    ('idempotencyKey','key\n'),('approved',True),('tenant',{}),('installationId','fake'),
    ('enabled',True),('approvalRef',None)])
def test_invalid_or_self_authorizing_commands_rejected(field,value):
    raw=payload();raw[field]=value
    with pytest.raises(ValidationError):ProductEventControlCommand.model_validate(raw)


@pytest.mark.parametrize('key', ['policyRef','approvalRef'])
@pytest.mark.parametrize('field,value',[('resourceType','Other'),('resourceId',' id'),('revision',True),('receiptId','substitute')])
def test_exact_reference_purpose_and_canonical_identity(key,field,value):
    raw=payload();raw[key][field]=value
    with pytest.raises(ValidationError):ProductEventControlCommand.model_validate(raw)


def test_disable_can_be_prepared_without_stale_approval():
    raw=payload();raw.update(intent='disable',approvalRef=None)
    assert ProductEventControlCommand.model_validate(raw).intent=='disable'


def test_copied_models_cannot_bypass_current_validation():
    command=ProductEventControlCommand.model_validate(payload())
    forged=command.model_copy(update={'expected_binding_revision':True})
    with pytest.raises(ValidationError):ProductEventControlCommand.model_validate(forged)
