"""Deterministic, read-only Provider Health production audit entrypoint."""
from __future__ import annotations

from dataclasses import dataclass

from aos_api.aip_provider_health_activation_audit import (
    ProviderHealthActivationAudit,
    audit_provider_health_activation,
)
from aos_api.aip_provider_health_activation_authority_readers import (
    ExactActionAuthoritySelection,
    ExactBindingSelection,
    build_exact_action_authority_owner_reader,
    build_exact_binding_owner_reader,
)
from aos_api.aip_provider_health_activation_change_packet import CANONICAL_TENANT
from aos_api.aip_provider_health_activation_owner_adapters import (
    build_production_activation_fact_readers,
)


@dataclass(frozen=True, slots=True)
class ProviderHealthProductionAuditRequest:
    """Explicit immutable refs required to assemble the production audit."""

    tenant: str
    expected_deployed_revision: str
    expected_action_type_revision_hash: str
    action: ExactActionAuthoritySelection
    bindings: ExactBindingSelection

    def __post_init__(self) -> None:
        if not self.expected_deployed_revision.strip():
            raise ValueError("expected_deployed_revision must be non-empty")
        normalized = self.expected_action_type_revision_hash.strip().lower()
        if normalized != self.action.action_type_revision_hash:
            raise ValueError(
                "expected_action_type_revision_hash must match Action selection"
            )
        object.__setattr__(self, "expected_action_type_revision_hash", normalized)


def run_provider_health_production_audit(
    request: ProviderHealthProductionAuditRequest,
) -> ProviderHealthActivationAudit:
    """Compose exact authority readers and audit cached owner facts once.

    This entrypoint deliberately registers no API route and owns no mutation,
    refresh, Provider invocation, Secret resolution, or execution callback.
    """
    if request.tenant != CANONICAL_TENANT:
        raise ValueError("Provider Health production audit tenant is not canonical")

    authority_reader = build_exact_action_authority_owner_reader(request.action)
    binding_reader = build_exact_binding_owner_reader(request.bindings)
    bundle = build_production_activation_fact_readers(
        expected_deployed_revision=request.expected_deployed_revision,
        expected_action_type_revision_hash=(
            request.expected_action_type_revision_hash
        ),
        authority_reader=authority_reader,
        binding_reader=binding_reader,
    )
    return audit_provider_health_activation(
        tenant=request.tenant,
        evaluated_at=bundle.collected_at,
        readers=bundle.readers,
    )


__all__ = [
    "ProviderHealthProductionAuditRequest",
    "run_provider_health_production_audit",
]
