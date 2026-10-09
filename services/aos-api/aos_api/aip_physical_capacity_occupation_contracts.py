"""Nonexecuting native physical guard facts; never an allocation permit."""
from datetime import datetime
from typing import Literal
from pydantic import Field,field_validator
from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
from aos_api.aip_model_eval_execution_contracts import _ModelExecutionContract


class PhysicalAccountGuardPreparation(_ModelExecutionContract):
    source_ref: FormalExactRef
    physical_account_id: str = Field(pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    version: int = Field(strict=True,gt=0)
    xid: str = Field(pattern=r'^[1-9][0-9]*$')
    pid: int = Field(strict=True,gt=0)
    checked_at: datetime
    execution_allowed: Literal[False]

    @field_validator('execution_allowed',mode='before')
    @classmethod
    def _false(cls,value):
        if type(value) is not bool or value is not False:
            raise ValueError('native nonexecuting guard required')
        return value


# Descriptive preparation only; these DTOs never establish runtime authority.
from typing import Annotated
from pydantic import model_validator
from aos_api.aip_model_runtime_store import canonical_hash

_OccupationUUID = Annotated[str, Field(strict=True, pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')]
_OccupationHash = Annotated[str, Field(strict=True, pattern=r'^sha256:[0-9a-f]{64}$')]


class _OccupationTenant(_ModelExecutionContract):
    org_id: Literal['org-org']
    project_id: Literal['dev-project']


class _OccupationOrigin(_ModelExecutionContract):
    call_id: _OccupationUUID
    tenant: _OccupationTenant
    caller_login: Literal['aos_provider_capacity_occupation']
    caller_xid: str = Field(strict=True, pattern=r'^[1-9][0-9]*$')
    caller_pid: int = Field(strict=True, gt=0)
    counts_as_inflight: Literal[False]

    @field_validator('counts_as_inflight', mode='before')
    @classmethod
    def _not_inflight(cls, value):
        if type(value) is not bool or value is not False:
            raise ValueError('exact nonexecuting occupation preparation required')
        return value


class PhysicalOccupationRootPreparation(_OccupationOrigin):
    schema_version: Literal['aos.actual-call-occupation-preparation/v1']
    plan_id: _OccupationUUID
    intent_id: _OccupationUUID
    case_id: str = Field(strict=True, min_length=1)
    purpose: Literal['target']
    parent_hold: _OccupationUUID
    physical_account_id: _OccupationUUID
    token_upper_bound: int = Field(strict=True, gt=0)
    prepared_call_hash: _OccupationHash
    initial_state: Literal['prepared_only']
    execution_allowed: Literal[False]

    @field_validator('execution_allowed', mode='before')
    @classmethod
    def _nonexecuting(cls, value):
        return PhysicalAccountGuardPreparation._false(value)


class PhysicalOccupationInitialEvent(_OccupationOrigin):
    schema_version: Literal['aos.actual-call-occupation-initial-event/v1']
    occupation_hash: _OccupationHash
    event_seq: Literal[1]
    previous_event_hash: None
    state: Literal['prepared_only']

    @field_validator('event_seq', mode='before')
    @classmethod
    def _first_event(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError('exact first occupation event required')
        return value


class PhysicalOccupationPreparation(_ModelExecutionContract):
    """Parse exact native preparation facts; never an admission permit."""
    call_id: _OccupationUUID
    immutable: PhysicalOccupationRootPreparation
    occupation_hash: _OccupationHash
    initial_event: PhysicalOccupationInitialEvent
    event_hash: _OccupationHash
    counts_as_inflight: Literal[False]
    execution_allowed: Literal[False]

    @field_validator('counts_as_inflight', 'execution_allowed', mode='before')
    @classmethod
    def _nonexecuting(cls, value):
        return PhysicalAccountGuardPreparation._false(value)

    @model_validator(mode='after')
    def _exact_native_binding(self):
        root, event = self.immutable, self.initial_event
        if (self.call_id != root.call_id or self.call_id != event.call_id
                or self.occupation_hash != event.occupation_hash
                or root.tenant != event.tenant
                or (root.caller_login, root.caller_xid, root.caller_pid) !=
                   (event.caller_login, event.caller_xid, event.caller_pid)):
            raise ValueError('exact occupation root/event origin binding required')
        for body, expected in ((root, self.occupation_hash), (event, self.event_hash)):
            actual = 'sha256:' + canonical_hash(body.model_dump(mode='json', by_alias=True))
            if actual != expected:
                raise ValueError('original native occupation content hash required')
        return self


from aos_api.aip_model_eval_execution_contracts import ModelEvalTargetJudgeSharedRiskManifest


class SharedParentRiskDescriptionBody(_ModelExecutionContract):
    """Complete persisted description; presented executor references are untrusted."""
    schema_version: Literal['aos.shared-parent-risk-description-preparation/v1']
    plan_id: _OccupationUUID
    tenant: _OccupationTenant
    original_risk_hash: _OccupationHash
    manifest: ModelEvalTargetJudgeSharedRiskManifest
    manifest_hash: Annotated[str, Field(strict=True, pattern=r'^[0-9a-f]{64}$')]
    caller_login: Literal['aos_provider_capacity_occupation']
    caller_xid: str = Field(strict=True, pattern=r'^[1-9][0-9]*$')
    caller_pid: int = Field(strict=True, gt=0)
    state: Literal['prepared_description_only']
    executors_authenticated: Literal[False]
    execution_allowed: Literal[False]

    @field_validator('executors_authenticated', 'execution_allowed', mode='before')
    @classmethod
    def _nonexecuting(cls, value):
        return PhysicalAccountGuardPreparation._false(value)

    @model_validator(mode='after')
    def _whole_manifest(self):
        if (self.plan_id != self.manifest.execution_id
                or self.tenant.model_dump() != self.manifest.tenant.model_dump()
                or self.manifest_hash != canonical_hash(self.manifest.model_dump(mode='json', by_alias=True))):
            raise ValueError('complete canonical shared-risk description required')
        return self


class SharedParentRiskDescriptionPreparation(_ModelExecutionContract):
    plan_id: _OccupationUUID
    immutable: SharedParentRiskDescriptionBody
    content_hash: _OccupationHash
    execution_allowed: Literal[False]

    @field_validator('execution_allowed', mode='before')
    @classmethod
    def _nonexecuting(cls, value):
        return PhysicalAccountGuardPreparation._false(value)

    @model_validator(mode='after')
    def _native_body(self):
        if (self.plan_id != self.immutable.plan_id or self.content_hash !=
                'sha256:' + canonical_hash(self.immutable.model_dump(mode='json', by_alias=True))):
            raise ValueError('exact native shared-risk description hash required')
        return self
