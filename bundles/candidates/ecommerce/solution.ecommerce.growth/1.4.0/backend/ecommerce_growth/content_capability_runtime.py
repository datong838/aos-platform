"""N7 exact capability, budget and readable Artifact orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aos_extension_sdk import DispatchRef, commit_with_dispatch

from .aip_business_investigation_compiler import canonical_command_hash
from .content_artifact_review import ReadableContentArtifact
from .ecommerce_business_investigation_review_command import (
    exact_ref_from_payload,
    exact_ref_payload,
)
from .sdk_ports import ExactRef, GrowthCapabilityPort


CONTENT_GENERATE_OPERATION = "ecommerce_growth_content_generate"
_AUTHORITY_TYPES = (
    ("handoff_ref", "HandoffReceipt"),
    ("task_ref", "Task"),
    ("brief_ref", "TaskBriefRevision"),
    ("growth_plan_ref", "GrowthPlanRevision"),
    ("agent_instance_ref", "AgentInstanceRevision"),
    ("responsibility_plan_ref", "ResponsibilityPlanRevision"),
    ("capability_ref", "CapabilityRevision"),
    ("model_route_ref", "ModelRouteRevision"),
    ("budget_ref", "BudgetRevision"),
    ("pricing_ref", "ModelPriceSnapshotRevision"),
    ("approval_ref", "ActionApprovalEvent"),
    ("capacity_reservation_ref", "CapacityReservation"),
)
_RECEIPT_FIELDS = frozenset(
    {
        "receiptRef",
        "requestHash",
        "state",
        "authorityRefs",
        "sourceArtifactRefs",
        "budgetReservationRef",
        "budgetState",
        "providerRequestReceiptRef",
        "providerReceiptRef",
        "usageReceiptRefs",
        "artifact",
        "currency",
        "upperBoundFen",
        "actualFen",
        "retryDirective",
        "replayed",
        "sideEffects",
    }
)
_SIDE_EFFECT_FIELDS = frozenset(
    {
        "providerInvocationCount",
        "approvalCreatedCount",
        "taskRunCreatedCount",
        "externalPublicationCount",
        "externalBusinessMutationCount",
    }
)


@dataclass(frozen=True, slots=True)
class ContentCapabilityRequest:
    handoff_ref: ExactRef
    task_ref: ExactRef
    brief_ref: ExactRef
    growth_plan_ref: ExactRef
    source_artifact_refs: tuple[ExactRef, ...]
    fact_source_refs: tuple[ExactRef, ...]
    agent_instance_ref: ExactRef
    responsibility_plan_ref: ExactRef
    capability_ref: ExactRef
    model_route_ref: ExactRef
    budget_ref: ExactRef
    pricing_ref: ExactRef
    approval_ref: ExactRef
    capacity_reservation_ref: ExactRef
    currency: str
    upper_bound_fen: int
    max_input_tokens: int
    max_output_tokens: int
    idempotency_key: str

    def __post_init__(self) -> None:
        for name, kind in _AUTHORITY_TYPES:
            if getattr(self, name).resource_type != kind:
                raise ValueError(f"{name} must reference {kind}")
        if (
            type(self.source_artifact_refs) is not tuple
            or len(self.source_artifact_refs) != 4
            or len(set(self.source_artifact_refs)) != 4
            or any(ref.resource_type != "ArtifactRevision" for ref in self.source_artifact_refs)
        ):
            raise ValueError("content capability requires four unique source Artifacts")
        if (
            type(self.fact_source_refs) is not tuple
            or not 1 <= len(self.fact_source_refs) <= 200
            or len(set(self.fact_source_refs)) != len(self.fact_source_refs)
            or any(
                ref.resource_type
                not in {
                    "EvidenceBundleRevision",
                    "DatasetRevision",
                    "DataFulfillmentReceipt",
                }
                for ref in self.fact_source_refs
            )
        ):
            raise ValueError("content capability requires a bounded exact fact-source closure")
        if self.currency != "CNY":
            raise ValueError("content capability first chain only supports CNY")
        if type(self.upper_bound_fen) is not int or not 1 <= self.upper_bound_fen <= 100_000_000:
            raise ValueError("content capability requires a positive bounded risk amount")
        if (
            type(self.max_input_tokens) is not int
            or not 1 <= self.max_input_tokens <= 1_000_000
            or type(self.max_output_tokens) is not int
            or not 1 <= self.max_output_tokens <= 1_000_000
        ):
            raise ValueError("content capability token bounds are required")
        if type(self.idempotency_key) is not str or not 1 <= len(self.idempotency_key.strip()) <= 200:
            raise ValueError("content capability idempotency key is required and bounded")

    def authority_refs(self) -> dict[str, dict[str, object]]:
        return {
            name.removesuffix("_ref"): exact_ref_payload(getattr(self, name))
            for name, _kind in _AUTHORITY_TYPES
        }

    def command_payload(self) -> dict[str, object]:
        return {
            "operation": "content.generate",
            "authorityRefs": self.authority_refs(),
            "sourceArtifactRefs": [exact_ref_payload(ref) for ref in self.source_artifact_refs],
            "factSourceRefs": [exact_ref_payload(ref) for ref in self.fact_source_refs],
            "currency": self.currency,
            "upperBoundFen": self.upper_bound_fen,
            "maxInputTokens": self.max_input_tokens,
            "maxOutputTokens": self.max_output_tokens,
            "idempotencyKey": self.idempotency_key,
        }


def _parse_authority_refs(value: Any) -> dict[str, ExactRef]:
    expected_names = {name.removesuffix("_ref") for name, _kind in _AUTHORITY_TYPES}
    if type(value) is not dict or set(value) != expected_names:
        raise ValueError("capability Receipt authorityRefs drifted")
    kinds = {name.removesuffix("_ref"): kind for name, kind in _AUTHORITY_TYPES}
    return {name: exact_ref_from_payload(item, {kinds[name]}) for name, item in value.items()}


def _parse_ref_list(value: Any, *, kinds: set[str], name: str, allow_empty: bool) -> tuple[ExactRef, ...]:
    if type(value) is not list or (not allow_empty and not value):
        raise ValueError(f"capability Receipt {name} shape drifted")
    result = tuple(exact_ref_from_payload(item, kinds) for item in value)
    if len(result) != len(set(result)):
        raise ValueError(f"capability Receipt {name} contains duplicates")
    return result


@dataclass(frozen=True, slots=True)
class ContentCapabilityReceipt:
    receipt_ref: ExactRef
    request_hash: str
    state: str
    authority_refs: dict[str, ExactRef]
    source_artifact_refs: tuple[ExactRef, ...]
    budget_reservation_ref: ExactRef
    budget_state: str
    provider_request_receipt_ref: ExactRef | None
    provider_receipt_ref: ExactRef | None
    usage_receipt_refs: tuple[ExactRef, ...]
    artifact: ReadableContentArtifact | None
    currency: str
    upper_bound_fen: int
    actual_fen: int | None
    retry_directive: str
    replayed: bool
    provider_invocation_count: int

    @classmethod
    def from_payload(
        cls, value: Any, *, request: ContentCapabilityRequest, request_hash: str
    ) -> "ContentCapabilityReceipt":
        if type(value) is not dict or set(value) != _RECEIPT_FIELDS:
            raise ValueError("capability Receipt fields drifted")
        effects = value["sideEffects"]
        if type(effects) is not dict or set(effects) != _SIDE_EFFECT_FIELDS:
            raise ValueError("capability Receipt sideEffects shape drifted")
        if any(type(effects[field]) is not int or effects[field] < 0 for field in effects):
            raise ValueError("capability Receipt sideEffects values drifted")
        if any(
            effects[field] != 0
            for field in (
                "approvalCreatedCount",
                "taskRunCreatedCount",
                "externalPublicationCount",
                "externalBusinessMutationCount",
            )
        ):
            raise ValueError("capability Receipt external side-effect boundary drifted")
        if value["requestHash"] != request_hash or type(value["replayed"]) is not bool:
            raise ValueError("capability Receipt identity drifted")
        authority_refs = _parse_authority_refs(value["authorityRefs"])
        source_refs = _parse_ref_list(
            value["sourceArtifactRefs"],
            kinds={"ArtifactRevision"},
            name="sourceArtifactRefs",
            allow_empty=False,
        )
        receipt = cls(
            receipt_ref=exact_ref_from_payload(
                value["receiptRef"], {"CapabilityInvocationRevision"}
            ),
            request_hash=request_hash,
            state=value["state"],
            authority_refs=authority_refs,
            source_artifact_refs=source_refs,
            budget_reservation_ref=exact_ref_from_payload(
                value["budgetReservationRef"], {"BudgetReservationRevision"}
            ),
            budget_state=value["budgetState"],
            provider_request_receipt_ref=exact_ref_from_payload(
                value["providerRequestReceiptRef"], {"CapabilityProviderRequestReceipt"}, required=False
            ),
            provider_receipt_ref=exact_ref_from_payload(
                value["providerReceiptRef"], {"CapabilityProviderReceipt"}, required=False
            ),
            usage_receipt_refs=_parse_ref_list(
                value["usageReceiptRefs"],
                kinds={"UsageReceipt"},
                name="usageReceiptRefs",
                allow_empty=True,
            ),
            artifact=None
            if value["artifact"] is None
            else ReadableContentArtifact.from_payload(value["artifact"]),
            currency=value["currency"],
            upper_bound_fen=value["upperBoundFen"],
            actual_fen=value["actualFen"],
            retry_directive=value["retryDirective"],
            replayed=value["replayed"],
            provider_invocation_count=effects["providerInvocationCount"],
        )
        receipt._validate(request)
        return receipt

    def _validate(self, request: ContentCapabilityRequest) -> None:
        if (
            self.authority_refs
            != {name: ref for name, ref in ((key.removesuffix("_ref"), getattr(request, key)) for key, _ in _AUTHORITY_TYPES)}
            or self.source_artifact_refs != request.source_artifact_refs
            or self.currency != request.currency
            or type(self.upper_bound_fen) is not int
            or self.upper_bound_fen != request.upper_bound_fen
            or (self.actual_fen is not None and type(self.actual_fen) is not int)
        ):
            raise ValueError("capability Receipt exact request lineage drifted")
        if self.state == "COMPLETED":
            if (
                self.budget_state != "SETTLED"
                or self.provider_request_receipt_ref is None
                or self.provider_receipt_ref is None
                or not self.usage_receipt_refs
                or self.artifact is None
                or self.artifact.task_ref != request.task_ref
                or self.artifact.brief_ref != request.brief_ref
                or self.artifact.growth_plan_ref != request.growth_plan_ref
                or self.artifact.source_artifact_refs != request.source_artifact_refs
                or self.artifact.fact_source_refs != request.fact_source_refs
                or type(self.actual_fen) is not int
                or not 0 <= self.actual_fen <= request.upper_bound_fen
                or self.retry_directive != "NONE"
                or self.provider_invocation_count != 1
            ):
                raise ValueError("COMPLETED capability Receipt is incomplete or over budget")
        elif self.state == "FAILED_NO_EFFECT":
            pre_submit_failure = (
                self.provider_request_receipt_ref is None
                and self.provider_receipt_ref is None
                and self.retry_directive == "RETRYABLE_NO_EFFECT"
                and self.provider_invocation_count == 0
            )
            submitted_failure = (
                self.provider_request_receipt_ref is not None
                and self.provider_receipt_ref is not None
                and self.retry_directive == "NONE"
                and self.provider_invocation_count == 1
            )
            if (
                self.budget_state != "RELEASED"
                or not (pre_submit_failure or submitted_failure)
                or self.usage_receipt_refs
                or self.artifact is not None
                or self.actual_fen is not None
            ):
                raise ValueError("FAILED_NO_EFFECT capability Receipt shape drifted")
        elif self.state == "UNKNOWN":
            if (
                self.budget_state != "UNKNOWN"
                or self.provider_request_receipt_ref is None
                or self.provider_receipt_ref is not None
                or self.usage_receipt_refs
                or self.artifact is not None
                or self.actual_fen is not None
                or self.retry_directive != "RECONCILE_ONLY"
                or self.provider_invocation_count != 1
            ):
                raise ValueError("UNKNOWN capability Receipt must retain budget and reconcile")
        else:
            raise ValueError("unsupported capability Receipt state")


def execute_content_capability(
    port: GrowthCapabilityPort,
    *,
    dispatch_ref: DispatchRef,
    request: ContentCapabilityRequest,
) -> ContentCapabilityReceipt:
    if dispatch_ref.operation_id != CONTENT_GENERATE_OPERATION or dispatch_ref.handler_kind != "extension":
        raise PermissionError("dispatch does not authorize content capability")
    command = request.command_payload()
    request_hash = canonical_command_hash(command)
    result = commit_with_dispatch(port, dispatch_ref, {**command, "requestHash": request_hash})
    return ContentCapabilityReceipt.from_payload(result, request=request, request_hash=request_hash)


__all__ = [
    "CONTENT_GENERATE_OPERATION",
    "ContentCapabilityReceipt",
    "ContentCapabilityRequest",
    "execute_content_capability",
]
