"""Host-owned ports used by the ecommerce growth package."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Mapping, Protocol

from aos_extension_sdk import DispatchRef


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class TenantRef:
    org_id: str
    project_id: str

    def __post_init__(self) -> None:
        if not self.org_id.strip() or not self.project_id.strip():
            raise ValueError("tenant identity is required")


@dataclass(frozen=True, slots=True)
class ExactRef:
    resource_type: str
    resource_id: str
    revision: int
    content_hash: str
    receipt_id: str | None = None

    def __post_init__(self) -> None:
        if (
            type(self.resource_type) is not str
            or type(self.resource_id) is not str
            or type(self.content_hash) is not str
            or (self.receipt_id is not None and type(self.receipt_id) is not str)
        ):
            raise ValueError("exact reference fields must use strict types")
        if not 1 <= len(self.resource_type.strip()) <= 120 or not 1 <= len(self.resource_id.strip()) <= 240:
            raise ValueError("exact reference identity is required")
        if type(self.revision) is not int or self.revision <= 0 or not _SHA256.fullmatch(self.content_hash):
            raise ValueError("exact reference revision and hash are required")
        if self.receipt_id is not None and not 1 <= len(self.receipt_id.strip()) <= 240:
            raise ValueError("receipt identity cannot be blank")


class GrowthWritePort(Protocol):
    """The host revalidates DispatchRef in the same transaction as every write."""

    def commit(
        self,
        *,
        dispatch_ref: DispatchRef,
        command: Mapping[str, Any],
        occurred_at: datetime,
    ) -> Mapping[str, Any]: ...


class GrowthReadPort(Protocol):
    def read_exact(self, *, tenant: TenantRef, ref: ExactRef) -> Mapping[str, Any]: ...


class GrowthAnalysisSourcePort(Protocol):
    """Tenant-bound host reader for authorized analysis source material."""

    def read(
        self,
        *,
        task_id: str,
        actor: str,
        request: Mapping[str, Any],
        markings: tuple[str, ...],
        now: datetime,
        max_source_age_seconds: int,
        max_bytes: int,
    ) -> Mapping[str, Any]: ...


class GrowthDataPort(Protocol):
    """Public Data authority port; the host derives tenant from DispatchRef."""

    def commit(
        self,
        *,
        dispatch_ref: DispatchRef,
        command: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


class GrowthRuntimePort(Protocol):
    """Canonical AIP runtime port; host revalidates DispatchRef on every commit."""

    def commit(
        self,
        *,
        dispatch_ref: DispatchRef,
        command: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


class GrowthReviewPort(Protocol):
    """Review/Handoff host port with DB-clock expiry and receipt-first replay.

    The host first reads the idempotency Receipt.  On first write it obtains
    ``decidedAt`` from its authoritative transaction clock and rejects an
    expired Handoff; replay returns the original Receipt and decision time.
    """

    def commit(
        self,
        *,
        dispatch_ref: DispatchRef,
        command: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


class GrowthCapabilityPort(Protocol):
    """Host capability broker: receipt-first budget hold, then Provider call."""

    def commit(
        self,
        *,
        dispatch_ref: DispatchRef,
        command: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


class GrowthContentReviewPort(Protocol):
    """Host-owned exact Artifact review authority; never publishes externally."""

    def commit(
        self,
        *,
        dispatch_ref: DispatchRef,
        command: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


class GrowthFeedbackPort(Protocol):
    """Transaction-bound host sink for deterministic post-review feedback."""

    def enqueue(
        self,
        *,
        review_receipt: Mapping[str, Any],
        feedback_plan: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


__all__ = [
    "ExactRef",
    "GrowthAnalysisSourcePort",
    "GrowthCapabilityPort",
    "GrowthContentReviewPort",
    "GrowthFeedbackPort",
    "GrowthDataPort",
    "GrowthReadPort",
    "GrowthReviewPort",
    "GrowthRuntimePort",
    "GrowthWritePort",
    "TenantRef",
]
