from copy import deepcopy
from uuid import uuid4
import pytest
from aos_api.ecommerce_event_action_binding import internal_event_binding_hash
from aos_api.ecommerce_growth_cutover_proposal_gate import action_snapshot_from_row
from aos_api.tenant_scope import TenantScope


def inputs(kind='ecommerce_growth_schedule_put'):
    action=action_snapshot_from_row(dict(id=kind,name='event review',object_type='Case',parameters=[],required_markings=[],submission_criteria=[]))
    payload=dict(caseId='actual-case',schedulePolicyId='actual-policy')
    if kind=='ecommerce_growth_schedule_put':payload.update(expectedCaseVersion=2,expectedPolicyRevision=0,policyHash='sha256:'+'a'*64)
    elif kind=='ecommerce_growth_event_control':payload['controlIntent']=dict(schemaVersion='aos.ecommerce.product-event-control-command/v1',idempotencyKey='event-enable',policyRef=dict(resourceType='SchedulePolicyRevision',resourceId='actual-policy',revision=1,contentHash='sha256:'+'b'*64),expectedBindingRevision=0,intent='enable')
    else:payload['dispatchIntent']=dict(**payload,schemaVersion='aos.ecommerce.event-control-dispatch/v1',phase='expand',installationRef=dict(installationId=str(uuid4()),revision=5,lockHash='sha256:'+'c'*64,overlayRevision='current'),generation=str(uuid4()),executionEpoch=3,runtimeRevision=6,cutoverGroupId=str(uuid4()),expectedGroupRevision=5,idempotencyKey='event-expand')
    return action,payload

@pytest.mark.parametrize('kind',['ecommerce_growth_schedule_put','ecommerce_growth_event_control','ecommerce_growth_event_dispatch'])
def test_event_bindings_are_exact_and_tenant_bound(kind):
    action,payload=inputs(kind);scope=TenantScope('org-org','dev-project')
    bound=internal_event_binding_hash(scope=scope,action_snapshot=action,payload=payload)
    assert len(bound)==64 and bound==internal_event_binding_hash(scope=scope,action_snapshot=deepcopy(action),payload=deepcopy(payload))
    assert bound!=internal_event_binding_hash(scope=TenantScope('dev-org','dev-project'),action_snapshot=action,payload=payload)

@pytest.mark.parametrize('fault',['unknown','bool','snapshot','subject','extra-control','extra-dispatch'])
def test_event_binding_refuses_unreviewed_material(fault):
    kind='ecommerce_growth_event_control' if fault in ('subject','extra-control') else ('ecommerce_growth_event_dispatch' if fault=='extra-dispatch' else 'ecommerce_growth_schedule_put')
    action,payload=inputs(kind)
    if fault=='unknown':payload['approved']=True
    elif fault=='bool':payload['expectedCaseVersion']=True
    elif fault=='snapshot':action['name']='changed'
    elif fault=='subject':payload['controlIntent']['policyRef']['resourceId']='other'
    elif fault=='extra-control':payload['controlIntent']['approvalRef']={}
    else:payload['dispatchIntent']['caseId']='other'
    with pytest.raises(ValueError):internal_event_binding_hash(scope=TenantScope('org-org','dev-project'),action_snapshot=action,payload=payload)
