"""Phase 3 · AIP Capabilities & Registry 引擎.

Agent 注册表 + 能力列表（含配置更新）。
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()


class Capability(BaseModel):
    id: str = Field(default_factory=lambda: "aip-cap-" + uuid.uuid4().hex[:8])
    name: str = ""
    category: str = ""  # data | build | governance | ai | ops | security
    description: str = ""
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0.0"
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class RegistryEntry(BaseModel):
    id: str = Field(default_factory=lambda: "aip-reg-" + uuid.uuid4().hex[:8])
    agent_id: str = ""
    agent_name: str = ""
    capabilities: list[str] = Field(default_factory=list)  # capability ids
    scope: str = "org"  # org | project | personal
    status: str = "registered"  # registered | pending | revoked
    registered_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class CapabilitiesEngine:
    """AIP Capabilities & Registry 引擎。"""

    _instance: "CapabilitiesEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "CapabilitiesEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._capabilities: dict[str, Capability] = {}
                    cls._instance._registry: dict[str, RegistryEntry] = {}
        return cls._instance

    # ── Capabilities ──
    def create_capability(self, name: str, **kwargs: Any) -> Capability:
        with _LOCK:
            cap = Capability(name=name, **kwargs)
            self._capabilities[cap.id] = cap
            return cap

    def get_capability(self, cap_id: str) -> Capability | None:
        return self._capabilities.get(cap_id)

    def list_capabilities(self, category: str | None = None, enabled: bool | None = None) -> list[Capability]:
        items = list(self._capabilities.values())
        if category:
            items = [c for c in items if c.category == category]
        if enabled is not None:
            items = [c for c in items if c.enabled == enabled]
        return items

    def update_capability(self, cap_id: str, **kwargs: Any) -> Capability:
        with _LOCK:
            cap = self._capabilities.get(cap_id)
            if cap is None:
                raise KeyError(f"Capability {cap_id} not found")
            for k, v in kwargs.items():
                if hasattr(cap, k):
                    setattr(cap, k, v)
            cap.updated_at = time.time()
            return cap

    def delete_capability(self, cap_id: str) -> bool:
        with _LOCK:
            return self._capabilities.pop(cap_id, None) is not None

    # ── Registry ──
    def register(self, agent_id: str, agent_name: str, capabilities: list[str], **kwargs: Any) -> RegistryEntry:
        with _LOCK:
            entry = RegistryEntry(agent_id=agent_id, agent_name=agent_name, capabilities=capabilities, **kwargs)
            self._registry[entry.id] = entry
            return entry

    def get_registry_entry(self, entry_id: str) -> RegistryEntry | None:
        return self._registry.get(entry_id)

    def list_registry(self, status: str | None = None, scope: str | None = None) -> list[RegistryEntry]:
        items = list(self._registry.values())
        if status:
            items = [e for e in items if e.status == status]
        if scope:
            items = [e for e in items if e.scope == scope]
        return items

    def update_registry(self, entry_id: str, **kwargs: Any) -> RegistryEntry:
        with _LOCK:
            entry = self._registry.get(entry_id)
            if entry is None:
                raise KeyError(f"Registry entry {entry_id} not found")
            for k, v in kwargs.items():
                if hasattr(entry, k):
                    setattr(entry, k, v)
            entry.updated_at = time.time()
            return entry

    def delete_registry(self, entry_id: str) -> bool:
        with _LOCK:
            return self._registry.pop(entry_id, None) is not None

    # ── Stats ──
    def registry_stats(self) -> dict[str, Any]:
        items = list(self._registry.values())
        caps = list(self._capabilities.values())
        by_scope: dict[str, int] = {}
        for e in items:
            by_scope[e.scope] = by_scope.get(e.scope, 0) + 1
        return {
            "total_agents": len(items),
            "total_capabilities": len(caps),
            "by_scope": by_scope,
            "enabled_capabilities": sum(1 for c in caps if c.enabled),
        }

    def reset(self) -> None:
        with _LOCK:
            self._capabilities.clear()
            self._registry.clear()


def get_engine() -> CapabilitiesEngine:
    return CapabilitiesEngine()
