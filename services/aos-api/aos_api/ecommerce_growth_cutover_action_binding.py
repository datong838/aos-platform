"""Content binding for internal cutover approvals; never an execution grant."""
import json
from uuid import UUID
from pydantic import StrictInt, StrictStr, Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.ecommerce_growth_cutover import CutoverExactRef
from aos_api.ecommerce_growth_registration_origin import RegistrationReceiptRef
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.tenant_scope import TenantScope

CONTROL_ACTION_TYPES = frozenset(('ecommerce_growth_cutover','ecommerce_growth_cutover_rollback'))


class _Target(AipContractModel):
    cutover_group_id: StrictStr
    expected_group_revision: StrictInt = Field(ge=1)
    target_installation_id: StrictStr
    target_generation: StrictStr
    target_execution_epoch: StrictInt = Field(ge=1)
    operation_ids: list[StrictStr]

    @field_validator('cutover_group_id','target_installation_id','target_generation')
    @classmethod
    def canonical_uuid(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('canonical target identity required')
        return value

    @field_validator('operation_ids')
    @classmethod
    def exact_operations(cls, value):
        if value != sorted(ECOMMERCE_GROWTH_OPERATIONS):
            raise ValueError('exact ordered cutover operations required')
        return value


class _Activation(_Target):
    target_runtime_revision: StrictInt = Field(ge=1)
    policy_ref: CutoverExactRef
    registration_receipt_ref: RegistrationReceiptRef


class _Rollback(_Target):
    activation_operation_id: StrictStr
    commit_receipt_ref: CutoverExactRef

    @model_validator(mode='after')
    def exact_parent(self):
        if (str(UUID(self.activation_operation_id)) != self.activation_operation_id
                or self.commit_receipt_ref.resource_type != 'CutoverCommitReceipt'
                or str(UUID(self.commit_receipt_ref.resource_id)) != self.commit_receipt_ref.resource_id):
            raise ValueError('exact activation and commit receipt required')
        return self


def internal_cutover_binding_hash(*, scope, action_snapshot, payload):
    if type(scope) is not TenantScope or type(action_snapshot) is not dict or type(payload) is not dict:
        raise TypeError('trusted scope and canonical material required')
    expected={'id','name','objectType','parameters','requiredMarkings','submissionCriteria','revisionHash'}
    if set(action_snapshot) != expected or action_snapshot['id'] not in CONTROL_ACTION_TYPES:
        raise ValueError('fixed internal control action snapshot required')
    if (any(type(action_snapshot[k]) is not str or not action_snapshot[k].strip() for k in ('id','name','objectType'))
            or any(type(action_snapshot[k]) is not list for k in ('parameters','requiredMarkings','submissionCriteria'))):
        raise ValueError('canonical action snapshot required')
    # Reject non-JSON material before using the shared AIP canonical hash.
    json.dumps(action_snapshot, allow_nan=False)
    json.dumps(payload, allow_nan=False)
    stable={k:v for k,v in action_snapshot.items() if k!='revisionHash'}
    if action_snapshot['revisionHash'] != canonical_hash(stable):
        raise ValueError('current action snapshot hash differs')
    model=_Activation if action_snapshot['id']=='ecommerce_growth_cutover' else _Rollback
    checked=model.model_validate(payload).model_dump(mode='json',by_alias=True)
    if checked != payload:
        raise ValueError('canonical control payload required')
    return canonical_hash(dict(schemaVersion='aos.runtime-cutover-action-binding/v1',
        tenant=dict(orgId=scope.org_id,projectId=scope.project_id),actionType=action_snapshot,payload=checked))
