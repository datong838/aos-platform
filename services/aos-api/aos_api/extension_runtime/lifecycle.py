"""Pure subordinate runtime rules; never advance the Installation authority."""
from pydantic import BaseModel, ConfigDict, Field


class AdmissionFacts(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    installation_active: bool
    installation_revision: int = Field(ge=1)
    binding_installation_revision: int = Field(ge=1)
    binding_ready: bool
    enabled: bool
    operation_fence: bool
    execution_epoch: int = Field(ge=1)
    request_epoch: int = Field(ge=1)
    permissions_valid: bool
    budget_valid: bool
    policy_valid: bool


def effective_ready(facts: AdmissionFacts) -> bool:
    """Read under the installation/binding transaction lock, never persist as authority."""
    return all((facts.installation_active,
                facts.installation_revision == facts.binding_installation_revision,
                facts.binding_ready, facts.enabled, not facts.operation_fence,
                facts.execution_epoch == facts.request_epoch,
                facts.permissions_valid, facts.budget_valid, facts.policy_valid))


_PATHS = {
    "runtime-apply": ("accepted", "validating", "preparing", "registered", "committing", "succeeded"),
    "runtime-verify": ("accepted", "validating", "committing", "succeeded"),
    "configure": ("accepted", "validating", "fencing", "committing", "succeeded"),
    "enable": ("accepted", "validating", "committing", "succeeded"),
    "disable": ("accepted", "fencing", "draining", "committing", "succeeded"),
    "abort_prepare": ("accepted", "fencing", "draining", "resources_released", "committing", "cancelled"),
    "uninstall-execute": ("accepted", "validating", "fencing", "draining", "obligations_resolved",
                          "resources_released", "committing", "succeeded"),
}


def next_phase(kind: str, current: str, requested: str) -> str:
    """Only the next successful checkpoint. Failures retain their phase for reconciliation.

    Reinstall is a new Installation, not a mutation of the old terminal operation.
    Approval/status/revision checks remain mandatory in the transactional store.
    """
    path = _PATHS.get(kind, ())
    if current not in path or path.index(current) + 1 >= len(path) or path[path.index(current) + 1] != requested:
        raise ValueError("runtime phase transition requires its preceding checkpoint")
    return requested
