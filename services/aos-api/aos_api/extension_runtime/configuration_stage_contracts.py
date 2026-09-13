"""Untrusted configuration staging input; neither principal nor execution permit."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .configuration_contracts import ConfigurationRef, ConfigurationSourceRef


class ConfigurationStageTarget(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True,
                              hide_input_in_errors=True, revalidate_instances='always')
    installationId: str
    installationEtag: int = Field(ge=1, le=2**63-1)
    generation: str
    bindingRevision: int = Field(ge=1, le=2**63-1)

    @field_validator('installationId', 'generation')
    @classmethod
    def canonical_identity(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('canonical installation and generation required')
        return value


class ConfigurationStageRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True,
                              hide_input_in_errors=True, revalidate_instances='always')
    schemaVersion: Literal['aos.runtime-configuration-stage/v1']
    action: Literal['stage-configuration']
    target: ConfigurationStageTarget
    roleRefs: tuple[ConfigurationSourceRef, ...] = Field(min_length=1, max_length=64)
    policyRef: ConfigurationSourceRef
    previousRef: ConfigurationRef | None = None

    @field_validator('roleRefs', mode='before')
    @classmethod
    def json_reference_array(cls, value):
        # FastAPI decodes JSON before strict model validation; preserve the
        # immutable internal tuple without coercing values inside the array.
        return tuple(value) if type(value) is list else value

    @model_validator(mode='after')
    def exact_sources(self):
        if (any(ref.authority != 'aip.responsibility_plan_revision' for ref in self.roleRefs)
                or self.policyRef.authority != 'aip.runtime_policy_revision'):
            raise ValueError('current AIP responsibility and runtime policy references required')
        if len({ref.id for ref in self.roleRefs}) != len(self.roleRefs):
            raise ValueError('duplicate responsibility identity')
        if len(self.model_dump_json().encode('utf-8')) > 65536:
            raise ValueError('configuration staging request exceeds 64KiB')
        return self
