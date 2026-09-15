"""Canonical event review material; a content binding never grants execution."""
import json
from typing import Literal
from uuid import UUID
from pydantic import ConfigDict,Field,StrictInt,StrictStr,field_validator,model_validator
from aos_api.aip_contracts import AipContractModel
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef,PipelineInstallationRef
from aos_api.tenant_scope import TenantScope

EVENT_ACTION_TYPES=frozenset(('ecommerce_growth_schedule_put','ecommerce_growth_event_control','ecommerce_growth_event_dispatch'))


class _Identity(AipContractModel):
    model_config=ConfigDict(strict=True,extra='forbid',frozen=True)
    case_id: StrictStr=Field(min_length=1,max_length=240)
    schedule_policy_id: StrictStr=Field(min_length=1,max_length=240)

    @field_validator('case_id','schedule_policy_id')
    @classmethod
    def canonical_text(cls,value):
        if value!=value.strip() or not value.isprintable():raise ValueError('canonical event identity required')
        return value


class _Schedule(_Identity):
    expected_policy_revision: StrictInt=Field(ge=0,le=2**63-1)
    expected_case_version: StrictInt=Field(ge=1,le=2**63-1)
    policy_hash: StrictStr=Field(pattern=r'^sha256:[0-9a-f]{64}$')


class _ControlIntent(AipContractModel):
    model_config=ConfigDict(strict=True,extra='forbid',frozen=True)
    schema_version: Literal['aos.ecommerce.product-event-control-command/v1']
    idempotency_key: StrictStr=Field(min_length=1,max_length=200)
    policy_ref: PipelineExactRef
    expected_binding_revision: StrictInt=Field(ge=0,le=2**63-1)
    intent: Literal['enable','disable']

    @field_validator('idempotency_key')
    @classmethod
    def canonical_key(cls,value):
        return _Identity.canonical_text(value)


class _Control(_Identity):
    control_intent: _ControlIntent

    @model_validator(mode='after')
    def policy_matches(self):
        ref=self.control_intent.policy_ref
        if ref.resource_type!='SchedulePolicyRevision' or ref.resource_id!=self.schedule_policy_id or ref.receipt_id is not None:
            raise ValueError('exact event control policy required')
        return self


class _DispatchIntent(_Identity):
    schema_version: Literal['aos.ecommerce.event-control-dispatch/v1']
    phase: Literal['expand','fence','shrink']
    installation_ref: PipelineInstallationRef
    generation: StrictStr
    execution_epoch: StrictInt=Field(ge=1,le=2**63-1)
    runtime_revision: StrictInt=Field(ge=1,le=2**63-1)
    cutover_group_id: StrictStr
    expected_group_revision: StrictInt=Field(ge=1,le=2**63-1)
    idempotency_key: StrictStr=Field(min_length=1,max_length=160)

    @field_validator('generation','cutover_group_id')
    @classmethod
    def uuid_text(cls,value):
        if str(UUID(value))!=value:raise ValueError('canonical event dispatch UUID required')
        return value

    @field_validator('idempotency_key')
    @classmethod
    def canonical_key(cls,value):return _Identity.canonical_text(value)


class _Dispatch(_Identity):
    dispatch_intent: _DispatchIntent

    @model_validator(mode='after')
    def same_subject(self):
        if (self.case_id,self.schedule_policy_id)!=(self.dispatch_intent.case_id,self.dispatch_intent.schedule_policy_id):
            raise ValueError('event dispatch subject differs')
        return self


def internal_event_binding_hash(*,scope,action_snapshot,payload):
    if type(scope) is not TenantScope or type(action_snapshot) is not dict or type(payload) is not dict:
        raise TypeError('trusted event scope and JSON required')
    expected={'id','name','objectType','parameters','requiredMarkings','submissionCriteria','revisionHash'}
    if set(action_snapshot)!=expected or action_snapshot['id'] not in EVENT_ACTION_TYPES:
        raise ValueError('fixed event action snapshot required')
    if (any(type(action_snapshot[k]) is not str or not action_snapshot[k].strip() for k in ('id','name','objectType'))
        or any(type(action_snapshot[k]) is not list for k in ('parameters','requiredMarkings','submissionCriteria'))):
        raise ValueError('canonical event action snapshot required')
    json.dumps(action_snapshot,allow_nan=False);json.dumps(payload,allow_nan=False)
    if action_snapshot['revisionHash']!=canonical_hash({k:v for k,v in action_snapshot.items() if k!='revisionHash'}):
        raise ValueError('event action snapshot hash differs')
    kind={'ecommerce_growth_schedule_put':_Schedule,'ecommerce_growth_event_control':_Control,'ecommerce_growth_event_dispatch':_Dispatch}[action_snapshot['id']]
    checked=kind.model_validate(payload).model_dump(mode='json',by_alias=True,exclude_none=True)
    if checked!=payload:raise ValueError('canonical event payload required')
    return canonical_hash(dict(schemaVersion='aos.ecommerce.event-action-binding/v1',tenant=dict(orgId=scope.org_id,projectId=scope.project_id),actionType=action_snapshot,payload=checked))
