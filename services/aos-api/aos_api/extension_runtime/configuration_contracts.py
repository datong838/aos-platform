"""Exact configuration references, never configuration contents or permission."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConfigurationRef(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True, hide_input_in_errors=True,
                              revalidate_instances='always')
    configurationId: str
    revision: int = Field(ge=1)
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
    bindingRevision: int = Field(ge=1)
    configRef: ConfigurationRef

    @field_validator('generation')
    @classmethod
    def canonical_generation(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('canonical deployment generation required')
        return value
