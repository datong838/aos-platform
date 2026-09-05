"""Data-only registration comparison inputs."""

from pydantic import Field

from aos_api.asset_registry.contracts import ContributionClaim, StrictContract
from aos_api.extension_runtime.profiles import MAX_REGISTRATION_ITEMS


class RegistrationDescription(StrictContract):
    contributions: list[ContributionClaim] = Field(max_length=MAX_REGISTRATION_ITEMS)
