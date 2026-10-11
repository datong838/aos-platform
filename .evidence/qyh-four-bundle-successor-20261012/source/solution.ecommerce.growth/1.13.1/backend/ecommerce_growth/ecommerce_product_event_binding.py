"""Prepare a coherent policy/Case pair; no persistence or execution authority."""
from dataclasses import dataclass

from .ecommerce_business_investigation_case import (
    BusinessInvestigationCase, CaseLifecycle, canonical_hash, _ref_payload,
)
from .ecommerce_product_event_schedule import ProductEventSchedulePolicy
from .sdk_ports import ExactRef


@dataclass(frozen=True, slots=True)
class EventCaseBinding:
    policy: ProductEventSchedulePolicy
    case: BusinessInvestigationCase

    @property
    def request_hash(self):
        return canonical_hash({'policy':self.policy.authority_payload(), 'case':self.case.authority_payload()})


def prepare_event_case_binding(current_case, policy, *, previous_policy=None):
    if type(current_case) is not BusinessInvestigationCase or type(policy) is not ProductEventSchedulePolicy:
        raise TypeError('exact package Case and event policy required')
    current_case=BusinessInvestigationCase.from_authority(current_case.authority_payload())
    policy=ProductEventSchedulePolicy.from_authority(policy.authority_payload())
    expected_case=ExactRef('BusinessInvestigationCaseRevision',current_case.case_id,
        current_case.revision,current_case.content_hash,None)
    if (current_case.lifecycle is not CaseLifecycle.ACTIVE or policy.tenant!=current_case.tenant
            or policy.case_ref!=expected_case or policy.method_ref!=current_case.investigation_profile_ref
            or policy.created_at<current_case.created_at):
        raise ValueError('event policy does not bind the current active Case and method')
    if previous_policy is None:
        if policy.revision!=1 or current_case.schedule_policy_ref is not None:
            raise ValueError('first event policy requires an unbound Case')
    else:
        if type(previous_policy) is not ProductEventSchedulePolicy:
            raise TypeError('exact preceding event policy required')
        previous_policy=ProductEventSchedulePolicy.from_authority(previous_policy.authority_payload())
        policy.validate_successor(previous_policy)
        expected_previous=ExactRef('SchedulePolicyRevision',previous_policy.policy_id,
            previous_policy.revision,previous_policy.content_hash,None)
        if current_case.schedule_policy_ref!=expected_previous:
            raise ValueError('Case does not bind the preceding event policy')
    payload=current_case.authority_payload(include_hash=False)
    payload.update(revision=current_case.revision+1,version=current_case.version+1,
        priorRef=_ref_payload(expected_case),
        schedulePolicyRef=_ref_payload(ExactRef('SchedulePolicyRevision',policy.policy_id,
            policy.revision,policy.content_hash,None)),
        createdBy=policy.created_by,createdAt=policy.created_at.isoformat().replace('+00:00','Z'))
    payload['contentHash']=canonical_hash(payload)
    successor=BusinessInvestigationCase.from_authority(payload)
    successor.validate_successor(current_case)
    return EventCaseBinding(policy,successor)
