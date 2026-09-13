from uuid import uuid4
import pytest
from test_ecommerce_growth_cutover_registration_contract import payload,registration_ref


def command_type():
    from aos_api.ecommerce_growth_cutover_command import CutoverProductCommand
    return CutoverProductCommand


def prepare_payload():
    from aos_api.ecommerce_growth_cutover import CutoverPrepareRequest
    return CutoverPrepareRequest(**payload(),registrationReceiptRef=registration_ref()).model_dump(mode='json',by_alias=True)


def test_prepare_requires_real_origin():
    body=prepare_payload()
    result=command_type().model_validate(dict(phase='prepare',request=body))
    assert result.request.registration_receipt_ref is not None
    body.pop('registrationReceiptRef')
    with pytest.raises(ValueError):command_type().model_validate(dict(phase='prepare',request=body))


@pytest.mark.parametrize('phase',['pause','commit','validate','resume','rollback-prepare','rollback-commit','unknown'])
def test_wrong_stage_rejects_prepare_request(phase):
    with pytest.raises(ValueError):command_type().model_validate(dict(phase=phase,request=prepare_payload()))


def phase_payload(phase):
    reference=lambda kind:dict(resourceType=kind,resourceId=str(uuid4()),revision=1,contentHash='sha256:'+'a'*64)
    if phase=='prepare':request=prepare_payload()
    elif phase in ('pause','commit'):
        request=dict(cutoverOperationId=str(uuid4()),idempotencyKey='phase-key',prepareReceiptRef=reference('CutoverPrepareReceipt'))
    elif phase in ('validate','resume'):
        request=dict(cutoverOperationId=str(uuid4()),idempotencyKey='phase-key',commitReceiptRef=reference('CutoverCommitReceipt'))
    else:
        request=dict(rollbackOperationId=str(uuid4()),activationOperationId=str(uuid4()),idempotencyKey='phase-key',
            commitReceiptRef=reference('CutoverCommitReceipt'),approvalRef=reference('ActionApprovalEvent'),failureReason='failed validation')
    value=dict(phase=phase,request=request)
    if phase=='resume':value['validateReceiptRef']=reference('CutoverValidateReceipt')
    return value


@pytest.mark.parametrize('phase',['prepare','pause','commit','validate','resume','rollback-prepare','rollback-commit'])
def test_all_exact_phase_shapes(phase):
    value=phase_payload(phase)
    assert command_type().model_validate(value).phase==phase
    if phase=='resume':
        value.pop('validateReceiptRef')
        with pytest.raises(ValueError):command_type().model_validate(value)
