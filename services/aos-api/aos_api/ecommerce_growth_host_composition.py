"""Fixed trusted-host composition for ecommerce growth operations."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from aos_api.ecommerce_growth_host_ports import (
    ConnectFactory,
    EcommerceGrowthOperationBinding,
    LockedEcommerceGrowthHostPort,
)


ECOMMERCE_GROWTH_OPERATIONS = (
    "ecommerce_growth_investigation_describe",
    "ecommerce_growth_case_put",
    "ecommerce_growth_schedule_put",
    "ecommerce_growth_schedule_trigger",
    "ecommerce_growth_data_fulfill",
    "ecommerce_growth_analysis_advance",
    "ecommerce_growth_review_advance",
    "ecommerce_growth_content_generate",
    "ecommerce_growth_content_review",
)

ECOMMERCE_GROWTH_AUTHORITY_KINDS = {
    "ecommerce_growth_investigation_describe": ("channel", "business_entity", "source_readiness"),
    "ecommerce_growth_case_put": ("profile", "channel", "business_entity", "task_brief"),
    "ecommerce_growth_schedule_put": ("case", "schedule_policy", "approval"),
    "ecommerce_growth_schedule_trigger": ("schedule_policy", "occurrence", "execution_epoch"),
    "ecommerce_growth_data_fulfill": (
        "case", "run", "checkpoint", "channel", "business_entity", "data_requirement",
        "source_readiness", "mapping", "facts", "evidence",
    ),
    "ecommerce_growth_analysis_advance": (
        "occurrence", "case", "profile", "run", "plan", "task_run", "checkpoint",
        "data_requirement", "fulfillment", "facts", "evidence",
    ),
    "ecommerce_growth_review_advance": (
        "occurrence", "case", "run", "analysis_receipt", "plan", "growth_plan",
        "review_issue", "eval_report", "artifacts", "responsibility",
    ),
    "ecommerce_growth_content_generate": (
        "task", "task_brief", "growth_plan", "artifacts", "fact_sources", "responsibility",
        "capability", "model_route", "pricing", "approval", "budget", "capacity",
    ),
    "ecommerce_growth_content_review": (
        "artifact", "task", "task_brief", "review_issue", "reviewer_authority",
    ),
}

ECOMMERCE_GROWTH_RECEIPT_KEYS = {
    "ecommerce_growth_investigation_describe": ("receiptRef",),
    "ecommerce_growth_case_put": ("receiptRef",),
    "ecommerce_growth_schedule_put": ("receiptRef",),
    "ecommerce_growth_schedule_trigger": ("occurrenceRef",),
    "ecommerce_growth_data_fulfill": ("requirementRef", "fulfillmentRef"),
    "ecommerce_growth_analysis_advance": ("receiptRef",),
    "ecommerce_growth_review_advance": ("receiptRef",),
    "ecommerce_growth_content_generate": ("receiptRef",),
    "ecommerce_growth_content_review": ("receiptRef",),
}

_REGISTRY_TOKEN: Final[object] = object()
_RUNTIME_WIRING_REQUIRED = "AR2_7D_RUNTIME_WIRING_REQUIRED"


@dataclass(frozen=True, slots=True)
class _OperationSpec:
    operation_id: str
    authority_kinds: tuple[str, ...]
    receipt_keys: tuple[str, ...]


_OPERATION_SPECS = tuple(
    _OperationSpec(
        operation_id=operation_id,
        authority_kinds=ECOMMERCE_GROWTH_AUTHORITY_KINDS[operation_id],
        receipt_keys=ECOMMERCE_GROWTH_RECEIPT_KEYS[operation_id],
    )
    for operation_id in ECOMMERCE_GROWTH_OPERATIONS
)


class EcommerceGrowthHostAdapterRegistry:
    """Sealed host-owned registry; callers cannot inject executable callbacks."""

    __slots__ = ("__bindings", "__token")

    def __init__(self, *_args, **_kwargs) -> None:
        raise TypeError("use an AOS host registry factory")

    @classmethod
    def _from_host_factory(
        cls,
        token: object,
        bindings: dict[str, EcommerceGrowthOperationBinding],
    ) -> "EcommerceGrowthHostAdapterRegistry":
        if token is not _REGISTRY_TOKEN:
            raise TypeError("registry construction is host-internal")
        expected = tuple(spec.operation_id for spec in _OPERATION_SPECS)
        if tuple(bindings) != expected:
            raise ValueError("ecommerce growth registry operation order drifted")
        for spec in _OPERATION_SPECS:
            binding = bindings[spec.operation_id]
            if (
                binding.operation_id != spec.operation_id
                or binding.authority_kinds != spec.authority_kinds
                or binding.receipt_keys != spec.receipt_keys
            ):
                raise ValueError("ecommerce growth registry contract drifted")
        value = object.__new__(cls)
        value.__bindings = MappingProxyType(dict(bindings))
        value.__token = token
        return value

    def _binding(self, operation_id: str) -> EcommerceGrowthOperationBinding:
        if self.__token is not _REGISTRY_TOKEN:
            raise TypeError("untrusted ecommerce growth registry")
        return self.__bindings[operation_id]

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(self.__bindings)


def _runtime_wiring_required(**_kwargs):
    from aos_api.ecommerce_growth_host_ports import EcommerceGrowthHostBlocked

    raise EcommerceGrowthHostBlocked(_RUNTIME_WIRING_REQUIRED)


def build_registration_only_ecommerce_growth_registry() -> EcommerceGrowthHostAdapterRegistry:
    """Build the only production registry allowed before AR2-7D wiring."""

    bindings = {
        spec.operation_id: EcommerceGrowthOperationBinding(
            operation_id=spec.operation_id,
            receipt_keys=spec.receipt_keys,
            authority_kinds=spec.authority_kinds,
            revalidate=_runtime_wiring_required,
            execute=_runtime_wiring_required,
            verify_receipt=_runtime_wiring_required,
        )
        for spec in _OPERATION_SPECS
    }
    return EcommerceGrowthHostAdapterRegistry._from_host_factory(_REGISTRY_TOKEN, bindings)


@dataclass(frozen=True, slots=True)
class EcommerceGrowthHostPorts:
    describe_port: LockedEcommerceGrowthHostPort
    write_port: LockedEcommerceGrowthHostPort
    occurrence_port: LockedEcommerceGrowthHostPort
    data_port: LockedEcommerceGrowthHostPort
    runtime_port: LockedEcommerceGrowthHostPort
    review_port: LockedEcommerceGrowthHostPort
    capability_port: LockedEcommerceGrowthHostPort
    content_review_port: LockedEcommerceGrowthHostPort


def build_ecommerce_growth_host_ports(
    registry: EcommerceGrowthHostAdapterRegistry,
    *,
    connect_factory: ConnectFactory,
) -> EcommerceGrowthHostPorts:
    if type(registry) is not EcommerceGrowthHostAdapterRegistry:
        raise TypeError("ecommerce growth host requires its sealed adapter registry")
    if registry.operation_ids != ECOMMERCE_GROWTH_OPERATIONS:
        raise ValueError("ecommerce growth host registry drifted")

    def port(*operation_ids: str) -> LockedEcommerceGrowthHostPort:
        return LockedEcommerceGrowthHostPort(
            {operation_id: registry._binding(operation_id) for operation_id in operation_ids},
            connect_factory=connect_factory,
        )

    return EcommerceGrowthHostPorts(
        describe_port=port("ecommerce_growth_investigation_describe"),
        write_port=port("ecommerce_growth_case_put", "ecommerce_growth_schedule_put"),
        occurrence_port=port("ecommerce_growth_schedule_trigger"),
        data_port=port("ecommerce_growth_data_fulfill"),
        runtime_port=port("ecommerce_growth_analysis_advance"),
        review_port=port("ecommerce_growth_review_advance"),
        capability_port=port("ecommerce_growth_content_generate"),
        content_review_port=port("ecommerce_growth_content_review"),
    )


__all__ = [
    "ECOMMERCE_GROWTH_OPERATIONS",
    "ECOMMERCE_GROWTH_AUTHORITY_KINDS",
    "ECOMMERCE_GROWTH_RECEIPT_KEYS",
    "EcommerceGrowthHostAdapterRegistry",
    "EcommerceGrowthHostPorts",
    "build_registration_only_ecommerce_growth_registry",
    "build_ecommerce_growth_host_ports",
]
