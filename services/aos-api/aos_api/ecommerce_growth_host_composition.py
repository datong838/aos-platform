"""Fixed trusted-host composition for ecommerce growth operations."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from aos_api.ecommerce_growth_host_ports import (
    ConnectFactory,
    EcommerceGrowthHostBlocked,
    EcommerceGrowthOperationBinding,
    LockedEcommerceGrowthHostPort,
)


EVENT_CONTROL_OPERATION = "ecommerce_growth_event_control"

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
_RUNTIME_HOST_SERVICES = (
    ("ecommerce_growth_investigation_describe", "InvestigationDescribeHostService"),
    ("ecommerce_growth_case_put", "CasePutHostService"),
    ("ecommerce_growth_schedule_put", "SchedulePutHostService"),
    ("ecommerce_growth_schedule_trigger", "ScheduleTriggerHostService"),
    ("ecommerce_growth_data_fulfill", "DataFulfillHostService"),
    ("ecommerce_growth_analysis_advance", "AnalysisAdvanceHostService"),
    ("ecommerce_growth_review_advance", "ReviewAdvanceHostService"),
    ("ecommerce_growth_content_generate", "ContentGenerateHostService"),
    ("ecommerce_growth_content_review", "ContentReviewHostService"),
)
# Host-owned review seal.  Presence of a class or method shape is not proof that
# its production authority lineage is wired.  Add an operation only in the
# implementation commit that closes and verifies that lineage.
RUNTIME_WIRING_PROVEN_OPERATIONS = (
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


_CONTROL_SPEC = _OperationSpec(EVENT_CONTROL_OPERATION,
    ("schedule_policy", "case", "source_selection", "approval", "runtime"), ("receiptRef",))


def _registry_specs(operation_ids):
    if operation_ids == ECOMMERCE_GROWTH_OPERATIONS:
        return _OPERATION_SPECS
    if operation_ids == (*ECOMMERCE_GROWTH_OPERATIONS, EVENT_CONTROL_OPERATION):
        return (*_OPERATION_SPECS, _CONTROL_SPEC)
    raise ValueError("ecommerce growth registry operation order drifted")


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
        specs = _registry_specs(tuple(bindings))
        for spec in specs:
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


def _require_runtime_dependencies() -> None:
    from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
    from aos_api.ecommerce_growth_feedback_port import BoundEcommerceGrowthFeedbackPort
    from aos_api.ecommerce_growth_runtime_store import BoundEcommerceGrowthRuntimeStore

    if not all(
        callable(dependency)
        for dependency in (
            BoundEcommerceGrowthRuntimeStore,
            BoundEcommerceGrowthFeedbackPort,
            AipBudgetReservationStore,
        )
    ):
        raise EcommerceGrowthHostBlocked(_RUNTIME_WIRING_REQUIRED)


def build_runtime_ecommerce_growth_registry() -> EcommerceGrowthHostAdapterRegistry:
    """Build the sealed runtime registry only when all nine host services exist."""

    from aos_api import ecommerce_growth_runtime_adapters as adapters

    _require_runtime_dependencies()
    if tuple(item[0] for item in _RUNTIME_HOST_SERVICES) != ECOMMERCE_GROWTH_OPERATIONS:
        raise EcommerceGrowthHostBlocked(_RUNTIME_WIRING_REQUIRED)
    if RUNTIME_WIRING_PROVEN_OPERATIONS != ECOMMERCE_GROWTH_OPERATIONS:
        raise EcommerceGrowthHostBlocked(_RUNTIME_WIRING_REQUIRED)
    if tuple(adapter.SPEC.operation_id for adapter in adapters.RUNTIME_ADAPTER_TYPES) != ECOMMERCE_GROWTH_OPERATIONS:
        raise EcommerceGrowthHostBlocked(_RUNTIME_WIRING_REQUIRED)
    bindings: dict[str, EcommerceGrowthOperationBinding] = {}
    for adapter_type, (operation_id, class_name) in zip(
        adapters.RUNTIME_ADAPTER_TYPES,
        _RUNTIME_HOST_SERVICES,
        strict=True,
    ):
        service_cls = getattr(adapters, class_name, None)
        if (
            adapter_type.SPEC.operation_id != operation_id
            or not isinstance(service_cls, type)
            or not callable(getattr(service_cls, "revalidate", None))
            or not callable(getattr(service_cls, "execute", None))
            or not callable(getattr(service_cls, "verify_receipt", None))
        ):
            raise EcommerceGrowthHostBlocked(_RUNTIME_WIRING_REQUIRED)
        bindings[operation_id] = adapter_type(service_cls()).binding()
    return EcommerceGrowthHostAdapterRegistry._from_host_factory(_REGISTRY_TOKEN, bindings)


def build_scoped_ecommerce_growth_registry(principal, pipeline_factory) -> EcommerceGrowthHostAdapterRegistry:
    """Add event dispatch using only the authenticated request and server factory."""
    from aos_api.ecommerce_product_event_dispatch import EventAwareSchedulePutHostService, EventControlRequestHostService
    from aos_api.ecommerce_growth_runtime_adapters import SchedulePutAdapter, EventControlAdapter

    service = EventAwareSchedulePutHostService(principal, pipeline_factory)
    baseline = build_runtime_ecommerce_growth_registry()
    bindings = {operation: baseline._binding(operation) for operation in baseline.operation_ids}
    bindings["ecommerce_growth_schedule_put"] = SchedulePutAdapter(service).binding()
    bindings[EVENT_CONTROL_OPERATION] = EventControlAdapter(EventControlRequestHostService(principal, pipeline_factory)).binding()
    return EcommerceGrowthHostAdapterRegistry._from_host_factory(_REGISTRY_TOKEN, bindings)


def select_ecommerce_growth_registry() -> EcommerceGrowthHostAdapterRegistry:
    """Use runtime wiring only after the complete nine-service factory succeeds."""

    try:
        return build_runtime_ecommerce_growth_registry()
    except EcommerceGrowthHostBlocked as exc:
        if str(exc) != _RUNTIME_WIRING_REQUIRED:
            raise
        return build_registration_only_ecommerce_growth_registry()


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
    control_port: LockedEcommerceGrowthHostPort | None = None


def build_ecommerce_growth_host_ports(
    registry: EcommerceGrowthHostAdapterRegistry,
    *,
    connect_factory: ConnectFactory,
) -> EcommerceGrowthHostPorts:
    if type(registry) is not EcommerceGrowthHostAdapterRegistry:
        raise TypeError("ecommerce growth host requires its sealed adapter registry")
    _registry_specs(registry.operation_ids)

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
        control_port=port(EVENT_CONTROL_OPERATION) if EVENT_CONTROL_OPERATION in registry.operation_ids else None,
    )


__all__ = [
    "ECOMMERCE_GROWTH_OPERATIONS",
    "ECOMMERCE_GROWTH_AUTHORITY_KINDS",
    "ECOMMERCE_GROWTH_RECEIPT_KEYS",
    "EcommerceGrowthHostAdapterRegistry",
    "EcommerceGrowthHostPorts",
    "build_registration_only_ecommerce_growth_registry",
    "build_runtime_ecommerce_growth_registry",
    "select_ecommerce_growth_registry",
    "build_ecommerce_growth_host_ports",
]
