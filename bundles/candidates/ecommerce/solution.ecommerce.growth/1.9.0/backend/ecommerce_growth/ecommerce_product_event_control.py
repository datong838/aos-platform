"""Business control intent and historical receipt checking; never authorization."""
from copy import deepcopy
import json
from uuid import NAMESPACE_URL, uuid5

from aos_extension_sdk import DispatchRef
from .sdk_ports import ExactRef
from .ecommerce_product_event_schedule import ProductEventSchedulePolicy
from .ecommerce_business_investigation_case import canonical_hash, _ref_payload


def build_event_control_command(policy, *, dispatch_ref, approval_ref, idempotency_key,
                                expected_binding_revision, intent):
    if type(policy) is not ProductEventSchedulePolicy or type(dispatch_ref) is not DispatchRef:
        raise TypeError('exact event policy and dispatch required')
    policy = ProductEventSchedulePolicy.from_authority(policy.authority_payload())
    dispatch = DispatchRef.from_payload(dispatch_ref.to_payload())
    if (dispatch.operation_id != 'ecommerce_growth_event_control' or dispatch.handler_kind != 'extension'
            or (dispatch.org_id, dispatch.project_id) != (policy.tenant.org_id, policy.tenant.project_id)):
        raise ValueError('event control dispatch differs')
    if (type(expected_binding_revision) is not int or not 0 <= expected_binding_revision < 2**63-1
            or type(intent) is not str or intent not in ('enable', 'disable')
            or type(idempotency_key) is not str or not 1 <= len(idempotency_key) <= 200
            or idempotency_key.strip() != idempotency_key or not idempotency_key.isprintable()):
        raise ValueError('event control intent invalid')
    if approval_ref is not None:
        if type(approval_ref) is not ExactRef:
            raise TypeError('exact approval reference required')
        approval_ref = ExactRef(approval_ref.resource_type, approval_ref.resource_id,
            approval_ref.revision, approval_ref.content_hash, approval_ref.receipt_id)
        if (approval_ref.resource_type != 'ActionApprovalEvent' or approval_ref.receipt_id is not None
                or approval_ref.resource_id.strip() != approval_ref.resource_id
                or not approval_ref.resource_id.isprintable() or approval_ref.revision >= 2**63):
            raise ValueError('event control approval differs')
    if intent == 'enable' and approval_ref is None:
        raise ValueError('enable requires an approval reference')
    return dict(schemaVersion='aos.ecommerce.product-event-control-command/v1',
        idempotencyKey=idempotency_key, expectedBindingRevision=expected_binding_revision, intent=intent,
        policyRef=_ref_payload(ExactRef('SchedulePolicyRevision', policy.policy_id, policy.revision,
                                     policy.content_hash)), approvalRef=_ref_payload(approval_ref))


def verify_event_control_receipt(result, *, command, dispatch_ref):
    """An original Receipt proves that operation only, not current enablement."""
    try:
        if type(result) is not dict or set(result) != {'receiptRef', 'authority', 'replayed'}:
            raise ValueError('envelope')
        json.dumps(result, allow_nan=False)
        authority, ref = result['authority'], result['receiptRef']
        if (type(result['replayed']) is not bool or type(authority) is not dict
                or set(authority) != {'schemaVersion', 'actor', 'command', 'binding'}
                or authority['schemaVersion'] != 'aos.ecommerce.product-event-control-receipt/v1'
                or type(authority['actor']) is not str or not 1 <= len(authority['actor']) <= 240
                or authority['actor'].strip() != authority['actor'] or not authority['actor'].isprintable()
                or canonical_hash(authority['command']) != canonical_hash(command)):
            raise ValueError('authority')
        binding, policy = authority['binding'], command['policyRef']
        expected_revision = command['expectedBindingRevision'] + 1
        if (type(binding) is not dict or type(binding.get('revision')) is not int
                or binding['revision'] != expected_revision or type(binding.get('policy_revision')) is not int
                or binding.get('policy_revision') != policy['revision']
                or binding.get('policy_id') != policy['resourceId'] or binding.get('policy_hash') != policy['contentHash']
                or (binding.get('org_id'), binding.get('project_id')) != (dispatch_ref.org_id, dispatch_ref.project_id)
                or binding.get('cadence') != 'event' or binding.get('enabled') is not (command['intent'] == 'enable')
                or type(binding.get('approved')) is not bool
                or (command['intent'] == 'enable' and binding['approved'] is not True)):
            raise ValueError('binding')
        expected_ref = dict(resourceType='EventPolicyControlReceipt', resourceId=str(uuid5(NAMESPACE_URL,
            canonical_hash(dict(scope=[dispatch_ref.org_id, dispatch_ref.project_id], controlKey=command['idempotencyKey'])))),
            revision=expected_revision, contentHash=canonical_hash(authority))
        if type(ref) is not dict or canonical_hash(ref) != canonical_hash(expected_ref):
            raise ValueError('reference')
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('event control receipt differs; outcome requires reconciliation') from exc
    return deepcopy(result)
