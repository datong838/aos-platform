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
        if not 1 <= len(self.resource_type.strip()) <= 120 or not 1 <= len(self.resource_id.strip()) <= 240:
            raise ValueError("exact reference identity is required")
        if self.revision <= 0 or not _SHA256.fullmatch(self.content_hash):
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


class GrowthDataPort(Protocol):
    """Public Data authority port; the host derives tenant from DispatchRef."""

    def commit(
        self,
        *,
        dispatch_ref: DispatchRef,
        command: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


__all__ = ["ExactRef", "GrowthDataPort", "GrowthReadPort", "GrowthWritePort", "TenantRef"]
