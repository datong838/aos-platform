"""Package application orchestration; no real Host or release claim."""
from copy import deepcopy
from datetime import datetime, timezone
import pytest
from test_product_event_binding import pair, body
from test_product_event_command import dispatch
from ecommerce_growth.ecommerce_product_event_binding import prepare_event_case_binding
from ecommerce_growth.ecommerce_business_investigation_application import EcommerceGrowthApplication
from ecommerce_growth.sdk_ports import ExactRef

APPROVAL = ExactRef('ActionApprovalEvent', 'approval', 1, 'sha256:'+'a'*64, None)
NOW = datetime(2026,9,14,tzinfo=timezone.utc)


class RecordingPort:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []
    def commit(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        if self.error: raise self.error
        return deepcopy(self.response)


def payload(binding):
    policy=binding.policy
    return dict(receiptRef=dict(resourceType='SchedulePolicyRevision',resourceId=policy.policy_id,
        revision=policy.revision,contentHash=policy.content_hash),authority=policy.authority_payload(),
        caseAuthority=binding.case.authority_payload(),approvalRef=dict(resourceType=APPROVAL.resource_type,
        resourceId=APPROVAL.resource_id,revision=APPROVAL.revision,contentHash=APPROVAL.content_hash,receiptId=None),replayed=False)


def invoke(app, binding):
    return app.save_event_policy(binding=binding,dispatch_ref=dispatch(),approval_ref=APPROVAL,
                                 idempotency_key='original-key',occurred_at=NOW)


def test_save_and_original_key_recovery(pair):
    binding=prepare_event_case_binding(*pair);port=RecordingPort(payload(binding))
    app=EcommerceGrowthApplication(port)
    assert invoke(app,binding)['replayed'] is False
    port.response['replayed']=True
    assert invoke(app,binding)['replayed'] is True
    assert port.calls[0]==port.calls[1]
    assert port.calls[0]['command']['idempotencyKey']=='original-key'


def test_unknown_outcome_never_retries(pair):
    binding=prepare_event_case_binding(*pair);port=RecordingPort(error=TimeoutError('unknown'))
    with pytest.raises(TimeoutError):invoke(EcommerceGrowthApplication(port),binding)
    assert len(port.calls)==1


@pytest.mark.parametrize('field', ['authority','caseAuthority','approvalRef','receiptRef','replayed','extra'])
def test_mismatched_receipt_is_not_success(pair,field):
    binding=prepare_event_case_binding(*pair);result=payload(binding)
    if field=='replayed': result[field]=0
    elif field=='extra':result[field]=True
    else:result[field]['contentHash']='sha256:'+'0'*64
    port=RecordingPort(result)
    with pytest.raises(ValueError,match='receipt'):invoke(EcommerceGrowthApplication(port),binding)
    assert len(port.calls)==1


def test_invalid_dispatch_does_not_call_port(pair):
    from dataclasses import replace
    binding=prepare_event_case_binding(*pair);port=RecordingPort()
    with pytest.raises(ValueError):
        EcommerceGrowthApplication(port).save_event_policy(binding=binding,
            dispatch_ref=replace(dispatch(),org_id='dev-org'),approval_ref=APPROVAL,
            idempotency_key='original-key',occurred_at=NOW)
    assert port.calls==[]


def test_boolean_revision_cannot_match_integer_receipt(pair):
    binding=prepare_event_case_binding(*pair);result=payload(binding)
    result['receiptRef']['revision']=True
    with pytest.raises(ValueError,match='receipt'):
        invoke(EcommerceGrowthApplication(RecordingPort(result)),binding)


def test_old_generic_command_remains_unchanged():
    port=RecordingPort({'receiptRef': {'resourceId': 'old'}})
    app=EcommerceGrowthApplication(port)
    assert app.commit_case_or_schedule(dispatch_ref=dispatch(), command={'idempotencyKey':'old'},
        occurred_at=NOW)==port.response
    assert port.calls[0]['command']=={'idempotencyKey':'old'}
