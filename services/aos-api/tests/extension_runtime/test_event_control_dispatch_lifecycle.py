from copy import deepcopy

import pytest
from pydantic import ValidationError

from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest


def payload():
    return {
        'schemaVersion': 'aos.ecommerce.event-control-dispatch/v1',
        'phase': 'expand',
        'installationRef': {'installationId': '11111111-1111-4111-8111-111111111111',
            'revision': 2, 'lockHash': 'sha256:'+'a'*64, 'overlayRevision': 'overlay-2'},
        'generation': '22222222-2222-4222-8222-222222222222',
        'executionEpoch': 3, 'runtimeRevision': 4,
        'cutoverGroupId': '33333333-3333-4333-8333-333333333333',
        'expectedGroupRevision': 5, 'caseId': 'case-current',
        'schedulePolicyId': 'policy-current',
        'approvalRef': {'resourceType': 'ActionApprovalEvent', 'resourceId': 'approval-current',
            'revision': 1, 'contentHash': 'sha256:'+'b'*64},
        'idempotencyKey': 'event-dispatch-expand-1',
    }


def test_request_roundtrip_and_approval_payload_are_exact():
    raw = payload(); original = deepcopy(raw)
    request = EventControlDispatchRequest.model_validate(raw)
    assert request.wire() == original
    intent = request.approval_intent()
    assert 'approvalRef' not in intent and intent['installationRef']['lockHash'] == raw['installationRef']['lockHash']
    assert raw == original


@pytest.mark.parametrize(('path', 'value'), [
    (('phase',), 'enable'), (('generation',), 'not-uuid'),
    (('executionEpoch',), True), (('caseId',), ' case-current'),
    (('approvalRef','resourceType'), 'Other'), (('installationRef','lockHash'), 'bad'),
])
def test_request_drift_is_rejected(path, value):
    raw = payload(); target = raw
    for key in path[:-1]: target = target[key]
    target[path[-1]] = value
    with pytest.raises((ValidationError, ValueError)):
        EventControlDispatchRequest.model_validate(raw)


def test_dispatch_change_has_independent_r2_maker_checker_floor():
    risk = classify_action_risk('ecommerce_growth_event_dispatch', {}, {}, None)
    assert risk.floor is ActionRiskLevel.R2
    assert risk.approval_policy['makerChecker'] is True
    assert risk.approval_policy['executionAllowed'] is True
