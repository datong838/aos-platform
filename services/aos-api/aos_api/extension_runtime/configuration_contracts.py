"""Exact configuration references, never configuration contents or permission."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Literal
from .audit_envelopes import ExactRef


class ConfigurationRef(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True, hide_input_in_errors=True,
                              revalidate_instances='always')
    configurationId: str
    revision: int = Field(ge=1, le=2**63-1)
    hash: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')

    @field_validator('configurationId')
    @classmethod
    def canonical_id(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('canonical configuration identity required')
        return value


class ConfigureTarget(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True, hide_input_in_errors=True,
                              revalidate_instances='always')
    generation: str
    bindingRevision: int = Field(ge=1, le=2**63-1)
    configRef: ConfigurationRef

    @field_validator('generation')
    @classmethod
    def canonical_generation(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('canonical deployment generation required')
        return value


class ConfigurationSourceRef(ExactRef):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True, hide_input_in_errors=True,
                              revalidate_instances='always')
    revision: int = Field(ge=1, le=2**63-1)

    @field_validator('id')
    @classmethod
    def opaque_identity(cls, value):
        if not value.isprintable() or value != value.strip() or '://' in value:
            raise ValueError('opaque source identity required')
        return value


class ConfigurationDocument(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True, hide_input_in_errors=True,
                              revalidate_instances='always')
    schemaVersion: Literal[1] = 1
    roleRefs: tuple[ConfigurationSourceRef,...] = Field(max_length=64)
    dataRefs: tuple[ConfigurationSourceRef,...] = Field(max_length=64)
    budgetRef: ConfigurationSourceRef
    policyRef: ConfigurationSourceRef

    @field_validator('schemaVersion', mode='before')
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int: raise ValueError('integer schema version required')
        return value

    @model_validator(mode='after')
    def bounded(self):
        for refs in (self.roleRefs,self.dataRefs):
            if len({(ref.authority,ref.id) for ref in refs}) != len(refs):
                raise ValueError('duplicate or ambiguous configuration reference')
        if len(self.model_dump_json().encode()) > 65536: raise ValueError('configuration exceeds 64KiB')
        return self
