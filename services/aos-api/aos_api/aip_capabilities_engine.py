"""Phase 3 · AIP Capabilities & Registry 引擎.

Agent 注册表 + 能力列表（含配置更新）。
模式：Singleton + Pydantic + threading.Lock。
W4-B5：插件默认种子、upsert、连通测试（进程内模拟）。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()

# 与 CapabilityPage 已接入卡 id 对齐（幂等种子）
PLUGIN_DEFAULTS: list[dict[str, Any]] = [
    {
        "id": "video-job",
        "name": "短视频生成",
        "category": "ai",
        "description": "C1 Job · GPU · → MediaSet",
        "config": {
            "kind": "job",
            "endpoint": "https://cap.internal/video/v1",
            "concurrency": 4,
            "secretRef": "vault://aip/capabilities/short-video#token",
            "webhook": "https://aos-api/v1/aip/capabilities/cb/video",
        },
    },
    {
        "id": "live-script",
        "name": "直播稿引擎",
        "category": "ai",
        "description": "C0 sync / 可升 C1 · → LiveScript",
        "config": {
            "kind": "script",
            "mode": "sync",
            "timeoutSec": 15,
            "outputObjectType": "LiveScript",
            "endpoint": "https://cap.internal/script/v1",
        },
    },
    {
        "id": "avatar-commerce",
        "name": "电商可交互数字人",
        "category": "ai",
        "description": "C2 Session · AV 外置 · AvatarSession",
        "config": {
            "kind": "session",
            "gateway": "wss://avatar.internal/session",
            "sessionObject": "AvatarSession",
            "avExternal": True,
            "draftGate": True,
            "endpoint": "wss://avatar.internal/session",
        },
    },
    {
        "id": "avatar-edu",
        "name": "教育可交互数字人",
        "category": "ai",
        "description": "C2 Session · 课纲 Wiki · CourseSession",
        "enabled": False,
        "config": {
            "kind": "session",
            "gateway": "wss://avatar.internal/edu",
            "sessionObject": "CourseSession",
            "avExternal": True,
            "draftGate": True,
            "endpoint": "wss://avatar.internal/edu",
        },
    },
    {
        "id": "http-adapter",
        "name": "HTTP Adapter",
        "category": "ai",
        "description": "自定义重包契约",
        "config": {
            "kind": "http",
            "baseUrl": "https://pkg.example/api",
            "manifest": "capability://org/custom-pkg@1.0",
            "endpoint": "https://pkg.example/api",
        },
    },
]


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

    def ensure_plugin_defaults(self) -> int:
        """幂等写入插件页固定 id；已存在则跳过。返回新写入条数。"""
        created = 0
        with _LOCK:
            for row in PLUGIN_DEFAULTS:
                cap_id = str(row["id"])
                if cap_id in self._capabilities:
                    continue
                fields = {k: v for k, v in row.items() if k != "id"}
                self._capabilities[cap_id] = Capability(id=cap_id, **fields)
                created += 1
        return created

    def upsert_capability(self, cap_id: str, **kwargs: Any) -> Capability:
        """存在则更新；否则以给定 id 创建。"""
        allowed = set(Capability.model_fields.keys()) - {"id"}
        clean = {k: v for k, v in kwargs.items() if k in allowed}
        with _LOCK:
            cap = self._capabilities.get(cap_id)
            if cap is None:
                cap = Capability(id=cap_id, **clean)
                self._capabilities[cap_id] = cap
                return cap
            for k, v in clean.items():
                setattr(cap, k, v)
            cap.updated_at = time.time()
            return cap

    def test_connectivity(
        self,
        cap_id: str | None = None,
        endpoint: str | None = None,
    ) -> dict[str, Any]:
        """进程内连通模拟：不外呼；有 endpoint / 已登记能力则 healthy。"""
        self.ensure_plugin_defaults()
        started = time.time()
        cap: Capability | None = None
        if cap_id:
            cap = self.get_capability(cap_id)
            if cap is None:
                # 首次测连通：按 id upsert 占位，避免 UI 固定 id 404
                cap = self.upsert_capability(
                    cap_id,
                    name=cap_id,
                    category="ai",
                    config={"endpoint": endpoint or f"mock://{cap_id}"},
                )
        resolved_endpoint = endpoint
        if not resolved_endpoint and cap is not None:
            cfg = cap.config or {}
            resolved_endpoint = str(
                cfg.get("endpoint") or cfg.get("baseUrl") or cfg.get("gateway") or ""
            ) or None
        if not resolved_endpoint:
            resolved_endpoint = f"mock://local/{cap_id or 'anon'}"
        latency_ms = max(1, int((time.time() - started) * 1000) + 12)
        enabled = True if cap is None else bool(cap.enabled)
        ok = enabled and bool(resolved_endpoint)
        return {
            "ok": ok,
            "status": "healthy" if ok else "unhealthy",
            "latencyMs": latency_ms,
            "endpoint": resolved_endpoint,
            "capabilityId": cap.id if cap else cap_id,
            "message": "connectivity ok" if ok else "capability disabled or missing endpoint",
        }

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
