"""Explicit adapter registry for the AIP Action execution boundary."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


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

    def register(self, name: str, adapter: ActionAdapter) -> None:
        key = name.strip()
        if not key:
            raise ValueError("adapter name is required")
        self._adapters[key] = adapter

    def unregister(self, name: str) -> None:
        self._adapters.pop(name, None)

    def get(self, name: str) -> ActionAdapter | None:
        return self._adapters.get(name)


ACTION_ADAPTERS = ActionAdapterRegistry()
