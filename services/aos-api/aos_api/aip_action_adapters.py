"""Explicit adapter registry for the AIP Action execution boundary."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from aos_api.aip_adapter_contracts import AdapterCapabilityRevision, ImmutableExactRevisionRef

if TYPE_CHECKING:
    from aos_api.aip_adapter_conformance import AdapterConformanceReport


@dataclass(frozen=True)
class AdapterOutcome:
    status: str
    provider_request_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class ActionAdapter(Protocol):
    def execute(self, *, payload: dict[str, Any], idempotency_key: str) -> AdapterOutcome: ...

    def reconcile(self, *, provider_request_id: str, request_fingerprint: str) -> AdapterOutcome: ...


class ActionAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ActionAdapter] = {}
        self._conformant_adapters: dict[
            tuple[str, int, str], tuple[AdapterCapabilityRevision, ActionAdapter]
        ] = {}

    def register(self, name: str, adapter: ActionAdapter) -> None:
        key = name.strip()
        if not key:
            raise ValueError("adapter name is required")
        self._adapters[key] = adapter

    def unregister(self, name: str) -> None:
        self._adapters.pop(name, None)

    def get(self, name: str) -> ActionAdapter | None:
        return self._adapters.get(name)

    def register_conformant(
        self,
        revision: AdapterCapabilityRevision,
        adapter: ActionAdapter,
        report: "AdapterConformanceReport",
    ) -> None:
        """Register an exact, suite-GREEN revision without claiming publication."""
        if not report.green:
            raise ValueError("adapter conformance report must be GREEN")
        if report.adapter_revision_ref != revision.exact_ref():
            raise ValueError("adapter conformance report revision drift")
        key = (revision.adapter_id, revision.revision, revision.content_hash)
        existing = self._conformant_adapters.get(key)
        if existing is not None and existing[1] is not adapter:
            raise ValueError("exact adapter revision is already registered")
        self._conformant_adapters[key] = (revision, adapter)

    def get_conformant(
        self, ref: ImmutableExactRevisionRef
    ) -> tuple[AdapterCapabilityRevision, ActionAdapter] | None:
        if ref.resource_type != "AdapterCapabilityRevision":
            return None
        return self._conformant_adapters.get((ref.resource_id, ref.revision, ref.content_hash))

    def unregister_conformant(self, ref: ImmutableExactRevisionRef) -> None:
        if ref.resource_type == "AdapterCapabilityRevision":
            self._conformant_adapters.pop((ref.resource_id, ref.revision, ref.content_hash), None)

    def get_conformant_revision(
        self, ref: ImmutableExactRevisionRef
    ) -> AdapterCapabilityRevision | None:
        item = self.get_conformant(ref)
        return item[0] if item else None


ACTION_ADAPTERS = ActionAdapterRegistry()
