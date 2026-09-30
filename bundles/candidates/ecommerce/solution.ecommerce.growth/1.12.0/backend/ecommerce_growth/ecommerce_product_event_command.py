"""Build business-only wire input; Host restores tenant from its trusted scope."""
from aos_extension_sdk import DispatchRef
from .sdk_ports import ExactRef
from .ecommerce_product_event_binding import EventCaseBinding
from .ecommerce_product_event_schedule import ProductEventSchedulePolicy
from .ecommerce_business_investigation_case import BusinessInvestigationCase, _ref_payload


def build_event_policy_command(binding, *, dispatch_ref, approval_ref, idempotency_key):
    if type(binding) is not EventCaseBinding or type(dispatch_ref) is not DispatchRef or type(approval_ref) is not ExactRef:
        raise TypeError('exact binding, dispatch and approval references required')
    dispatch_ref=DispatchRef.from_payload(dispatch_ref.to_payload())
    policy=ProductEventSchedulePolicy.from_authority(binding.policy.authority_payload())
    case=BusinessInvestigationCase.from_authority(binding.case.authority_payload())
    if (dispatch_ref.operation_id!='ecommerce_growth_schedule_put' or dispatch_ref.handler_kind!='extension'
            or (dispatch_ref.org_id,dispatch_ref.project_id)!=(policy.tenant.org_id,policy.tenant.project_id)
            or case.tenant!=policy.tenant or case.prior_ref!=policy.case_ref
            or case.schedule_policy_ref!=ExactRef('SchedulePolicyRevision',policy.policy_id,policy.revision,policy.content_hash,None)
            or approval_ref.resource_type!='ActionApprovalEvent' or approval_ref.receipt_id is not None):
        raise ValueError('event command exact authority differs')
    if type(idempotency_key) is not str or not 1<=len(idempotency_key)<=200 or idempotency_key.strip()!=idempotency_key:
        raise ValueError('event command key invalid')
    p,c=policy.authority_payload(),case.authority_payload()
    p.pop('tenant');c.pop('tenant')
    return dict(idempotencyKey=idempotency_key,expectedPolicyRevision=policy.revision-1,
        expectedCaseVersion=case.revision-1,policy=p,caseAuthority=c,approvalRef=_ref_payload(approval_ref))
