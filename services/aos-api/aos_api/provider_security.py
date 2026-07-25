"""Provider Security Engine — 222plan Phase A.

供应商安全策略引擎：内容过滤/QPS限制/IP白名单/审计/数据驻留。

对应 222 文档第 23 章 Tab 3 安全策略。
"""
from __future__ import annotations

import threading
from typing import Any

from pydantic import BaseModel, Field

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.provider_security")

_KV_KEY = "model_provider_security"


class ProviderSecurity(BaseModel):
    provider_id: str
    content_filter: bool = True       # 调用前对 prompt 做 PII 脱敏 + 敏感词过滤
    max_tokens: int = 4096            # 防止单次调用成本失控
    qps_limit: int = 100              # 每秒最大请求数
    ip_allowlist: list[str] = Field(default_factory=list)  # CIDR 格式
    audit_log: bool = True            # 记录所有 prompt + response
    data_residency: str = "provider"  # provider / local_cache / no_cache


_DEFAULT_SECURITY: dict[str, Any] = {
    "content_filter": True,
    "max_tokens": 4096,
    "qps_limit": 100,
    "ip_allowlist": [],
    "audit_log": True,
    "data_residency": "provider",
}


class ProviderSecurityEngine:
    """Singleton + threading.Lock. Persisted to aip_kv_store."""

    _instance: ProviderSecurityEngine | None = None
    _lock = threading.Lock()

    def __new__(cls) -> ProviderSecurityEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    self = super().__new__(cls)
                    self._store: dict[str, ProviderSecurity] = {}
                    self._load()
                    cls._instance = self
        return cls._instance

    def _load(self) -> None:
        from aos_api.aip_kv_store import get_payload

        raw = get_payload(_KV_KEY)
        if not raw or not isinstance(raw, dict):
            return
        by_id = raw.get("byProvider") or {}
        for pid, item in by_id.items():
            if isinstance(item, dict):
                try:
                    self._store[pid] = ProviderSecurity(**item)
                except Exception:
                    pass
        log.info("security_load providers=%d", len(self._store))

    def _save(self) -> None:
        from aos_api.aip_kv_store import put_payload

        data = {
            "byProvider": {pid: s.model_dump() for pid, s in self._store.items()}
        }
        put_payload(_KV_KEY, data)

    def get_security(self, provider_id: str) -> ProviderSecurity:
        """Get security policy, creating default if not exists."""
        if provider_id not in self._store:
            self._store[provider_id] = ProviderSecurity(
                provider_id=provider_id, **_DEFAULT_SECURITY
            )
            self._save()
        return self._store[provider_id]

    def update_security(
        self, provider_id: str, **updates: Any
    ) -> ProviderSecurity:
        """Update security policy fields."""
        sec = self.get_security(provider_id)  # Ensures exists
        for k, v in updates.items():
            if hasattr(sec, k) and v is not None:
                setattr(sec, k, v)
        self._store[provider_id] = sec
        self._save()
        log.info("security_update provider=%s", provider_id)
        return sec


_engine: ProviderSecurityEngine | None = None
_engine_lock = threading.Lock()


def get_security_engine() -> ProviderSecurityEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = ProviderSecurityEngine()
    return _engine
