"""Conservative control targets do not require usable runtime configuration."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DisableTarget(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid',frozen=True,
        hide_input_in_errors=True,revalidate_instances='always')
    generation: str
    bindingRevision: int=Field(ge=1,le=2**63-1)

    @field_validator('generation')
    @classmethod
    def canonical_generation(cls,value):
        if str(UUID(value))!=value:
            raise ValueError('canonical deployment generation required')
        return value
