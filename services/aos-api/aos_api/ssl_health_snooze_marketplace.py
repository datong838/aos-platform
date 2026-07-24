"""W2-BK · SSL / Health Snooze / Context Panel / Marketplace 引擎组（#10 #11 #12 #13）.

本模块提供 W2+ 低优先级批次的 4 个内存态引擎：
    - SslCertificateEngine        #10 Data Connection Agent SSL 证书
    - HealthSnoozeEngine          #11 Data Health 通知打盹（Snoozing）
    - HealthContextPanelEngine    #12 Data Health 上下文面板
    - HealthMarketplaceEngine     #13 Data Health Marketplace 集成

所有引擎均线程安全（threading.Lock），容量上限 200，FIFO 按时间戳淘汰。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────────
# 公共工具
# ────────────────────────────────────────────────────────────────

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


class SslHealthSnoozeError(Exception):
    """SSL / Health Snooze / Context / Marketplace 引擎统一错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def error_payload(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


# ════════════════════ #10 SSL Certificates ════════════════════

class SslCertificate(BaseModel):
    id: str = Field(default_factory=lambda: _uid("cert"))
    agent_id: str
    common_name: str
    issuer: str = ""
    serial_number: str = ""
    fingerprint: str = ""
    valid_from: float = 0
    valid_until: float = 0
    status: str = "active"  # active / expired / revoked
    auto_renew: bool = False
    created_at: float = Field(default_factory=_now_ts)


class SslCertificateEngine:
    """#10 Data Connection Agent SSL 证书引擎。"""

    _MAX_CERTS = 200

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._certs: dict[str, SslCertificate] = {}

    def register_cert(
        self,
        agent_id: str,
        common_name: str,
        valid_from: float = 0,
        valid_until: float = 0,
        issuer: str = "",
        serial_number: str = "",
        fingerprint: str = "",
        auto_renew: bool = False,
    ) -> SslCertificate:
        cert = SslCertificate(
            agent_id=agent_id,
            common_name=common_name,
            issuer=issuer,
            serial_number=serial_number,
            fingerprint=fingerprint,
            valid_from=valid_from,
            valid_until=valid_until,
            auto_renew=auto_renew,
        )
        with self._lock:
            if len(self._certs) >= self._MAX_CERTS:
                oldest_id = min(
                    self._certs, key=lambda cid: self._certs[cid].created_at
                )
                del self._certs[oldest_id]
            self._certs[cert.id] = cert
        return cert

    def get_cert(self, cert_id: str) -> SslCertificate:
        with self._lock:
            cert = self._certs.get(cert_id)
        if cert is None:
            raise SslHealthSnoozeError("NOT_FOUND", f"cert {cert_id} not found")
        return cert

    def list_certs(
        self, agent_id: str | None = None, status: str | None = None
    ) -> list[SslCertificate]:
        with self._lock:
            results = list(self._certs.values())
        if agent_id is not None:
            results = [c for c in results if c.agent_id == agent_id]
        if status is not None:
            results = [c for c in results if c.status == status]
        return sorted(results, key=lambda c: c.created_at)

    def update_cert(self, cert_id: str, updates: dict[str, Any]) -> SslCertificate:
        with self._lock:
            cert = self._certs.get(cert_id)
            if cert is None:
                raise SslHealthSnoozeError("NOT_FOUND", f"cert {cert_id} not found")
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(cert).model_fields
            }
            updated = cert.model_copy(update=applicable)
            self._certs[cert_id] = updated
        return updated

    def revoke_cert(self, cert_id: str) -> SslCertificate:
        with self._lock:
            cert = self._certs.get(cert_id)
            if cert is None:
                raise SslHealthSnoozeError("NOT_FOUND", f"cert {cert_id} not found")
            updated = cert.model_copy(update={"status": "revoked"})
            self._certs[cert_id] = updated
        return updated

    def check_expiry(self, cert_id: str) -> dict[str, Any]:
        with self._lock:
            cert = self._certs.get(cert_id)
        if cert is None:
            raise SslHealthSnoozeError("NOT_FOUND", f"cert {cert_id} not found")
        now = _now_ts()
        days_remaining = int((cert.valid_until - now) / 86400)
        return {
            "cert_id": cert_id,
            "days_remaining": days_remaining,
            "is_expired": days_remaining < 0,
            "is_expiring_soon": days_remaining < 30,
        }

    def renew_cert(self, cert_id: str, new_valid_until: float) -> SslCertificate:
        with self._lock:
            cert = self._certs.get(cert_id)
            if cert is None:
                raise SslHealthSnoozeError("NOT_FOUND", f"cert {cert_id} not found")
            updated = cert.model_copy(
                update={"valid_until": new_valid_until, "status": "active"}
            )
            self._certs[cert_id] = updated
        return updated

    def delete_cert(self, cert_id: str) -> bool:
        with self._lock:
            return self._certs.pop(cert_id, None) is not None


# ════════════════════ #11 Health Snooze ════════════════════

class SnoozeRecord(BaseModel):
    id: str = Field(default_factory=lambda: _uid("snooze"))
    check_id: str
    snoozed_by: str
    reason: str
    snoozed_until: float
    created_at: float = Field(default_factory=_now_ts)
    duration_seconds: int = 0


class SnoozeHistoryEntry(BaseModel):
    id: str
    check_id: str
    action: str  # snoozed / unsnoozed / expired
    timestamp: float
    by_user: str
    reason: str = ""


class HealthSnoozeEngine:
    """#11 Data Health 通知打盹引擎。"""

    _MAX_SNOOZES = 200
    _MAX_HISTORY = 200

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snoozes: dict[str, SnoozeRecord] = {}
        self._history: list[SnoozeHistoryEntry] = []

    def _add_history(
        self, check_id: str, action: str, by_user: str, reason: str = ""
    ) -> None:
        entry = SnoozeHistoryEntry(
            id=_uid("snooze-hist"),
            check_id=check_id,
            action=action,
            timestamp=_now_ts(),
            by_user=by_user,
            reason=reason,
        )
        self._history.append(entry)
        if len(self._history) > self._MAX_HISTORY:
            self._history.pop(0)

    def _evict_snoozes(self) -> None:
        if len(self._snoozes) >= self._MAX_SNOOZES:
            oldest_id = min(
                self._snoozes, key=lambda sid: self._snoozes[sid].created_at
            )
            del self._snoozes[oldest_id]

    def snooze(
        self,
        check_id: str,
        snoozed_by: str,
        duration_seconds: int,
        reason: str = "",
    ) -> SnoozeRecord:
        now = _now_ts()
        record = SnoozeRecord(
            check_id=check_id,
            snoozed_by=snoozed_by,
            reason=reason,
            snoozed_until=now + duration_seconds,
            duration_seconds=duration_seconds,
        )
        with self._lock:
            self._evict_snoozes()
            self._snoozes[record.id] = record
            self._add_history(check_id, "snoozed", snoozed_by, reason)
        return record

    def batch_snooze(
        self,
        check_ids: list[str],
        snoozed_by: str,
        duration_seconds: int,
        reason: str = "",
    ) -> list[SnoozeRecord]:
        records: list[SnoozeRecord] = []
        with self._lock:
            for check_id in check_ids:
                now = _now_ts()
                record = SnoozeRecord(
                    check_id=check_id,
                    snoozed_by=snoozed_by,
                    reason=reason,
                    snoozed_until=now + duration_seconds,
                    duration_seconds=duration_seconds,
                )
                self._evict_snoozes()
                self._snoozes[record.id] = record
                self._add_history(check_id, "snoozed", snoozed_by, reason)
                records.append(record)
        return records

    def unsnooze(self, check_id: str, by_user: str) -> bool:
        now = _now_ts()
        with self._lock:
            active = [
                r
                for r in self._snoozes.values()
                if r.check_id == check_id and r.snoozed_until > now
            ]
            if not active:
                return False
            target = max(active, key=lambda r: r.created_at)
            del self._snoozes[target.id]
            self._add_history(check_id, "unsnoozed", by_user, target.reason)
        return True

    def get_active_snooze(self, check_id: str) -> SnoozeRecord | None:
        now = _now_ts()
        with self._lock:
            active = [
                r
                for r in self._snoozes.values()
                if r.check_id == check_id and r.snoozed_until > now
            ]
        if not active:
            return None
        return max(active, key=lambda r: r.created_at)

    def list_snoozes(
        self, check_id: str | None = None, include_expired: bool = False
    ) -> list[SnoozeRecord]:
        now = _now_ts()
        with self._lock:
            results = list(self._snoozes.values())
        if check_id is not None:
            results = [r for r in results if r.check_id == check_id]
        if not include_expired:
            results = [r for r in results if r.snoozed_until > now]
        return sorted(results, key=lambda r: r.created_at)

    def list_history(self, check_id: str | None = None) -> list[SnoozeHistoryEntry]:
        with self._lock:
            results = list(self._history)
        if check_id is not None:
            results = [h for h in results if h.check_id == check_id]
        return sorted(results, key=lambda h: h.timestamp)

    def cleanup_expired(self) -> int:
        now = _now_ts()
        count = 0
        with self._lock:
            expired = [r for r in self._snoozes.values() if r.snoozed_until <= now]
            for r in expired:
                del self._snoozes[r.id]
                self._add_history(r.check_id, "expired", r.snoozed_by, r.reason)
                count += 1
        return count

    def delete_snooze(self, snooze_id: str) -> bool:
        with self._lock:
            return self._snoozes.pop(snooze_id, None) is not None


# ════════════════════ #12 Health Context Panel ════════════════════

class ContextEntry(BaseModel):
    id: str = Field(default_factory=lambda: _uid("ctx"))
    check_id: str
    entry_type: str  # comment / issue / plan / source
    content: str
    author: str
    created_at: float = Field(default_factory=_now_ts)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthContextPanelEngine:
    """#12 Data Health 上下文面板引擎。"""

    _MAX_ENTRIES = 200
    _VALID_ENTRY_TYPES = {"comment", "issue", "plan", "source"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, ContextEntry] = {}

    def add_entry(
        self,
        check_id: str,
        entry_type: str,
        content: str,
        author: str,
        metadata: dict[str, Any] | None = None,
    ) -> ContextEntry:
        if entry_type not in self._VALID_ENTRY_TYPES:
            raise SslHealthSnoozeError(
                "INVALID_ENTRY_TYPE",
                f"entry_type must be one of {sorted(self._VALID_ENTRY_TYPES)}",
            )
        entry = ContextEntry(
            check_id=check_id,
            entry_type=entry_type,
            content=content,
            author=author,
            metadata=metadata or {},
        )
        with self._lock:
            if len(self._entries) >= self._MAX_ENTRIES:
                oldest_id = min(
                    self._entries, key=lambda eid: self._entries[eid].created_at
                )
                del self._entries[oldest_id]
            self._entries[entry.id] = entry
        return entry

    def get_entry(self, entry_id: str) -> ContextEntry:
        with self._lock:
            entry = self._entries.get(entry_id)
        if entry is None:
            raise SslHealthSnoozeError("NOT_FOUND", f"entry {entry_id} not found")
        return entry

    def list_entries(
        self, check_id: str | None = None, entry_type: str | None = None
    ) -> list[ContextEntry]:
        with self._lock:
            results = list(self._entries.values())
        if check_id is not None:
            results = [e for e in results if e.check_id == check_id]
        if entry_type is not None:
            results = [e for e in results if e.entry_type == entry_type]
        return sorted(results, key=lambda e: e.created_at)

    def update_entry(
        self,
        entry_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ContextEntry:
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is None:
                raise SslHealthSnoozeError("NOT_FOUND", f"entry {entry_id} not found")
            updates: dict[str, Any] = {}
            if content is not None:
                updates["content"] = content
            if metadata is not None:
                updates["metadata"] = metadata
            updated = entry.model_copy(update=updates) if updates else entry
            self._entries[entry_id] = updated
        return updated

    def delete_entry(self, entry_id: str) -> bool:
        with self._lock:
            return self._entries.pop(entry_id, None) is not None

    def get_context_summary(self, check_id: str) -> dict[str, Any]:
        with self._lock:
            entries = [e for e in self._entries.values() if e.check_id == check_id]
        by_type: dict[str, int] = {t: 0 for t in self._VALID_ENTRY_TYPES}
        latest_at = 0.0
        for e in entries:
            by_type[e.entry_type] = by_type.get(e.entry_type, 0) + 1
            if e.created_at > latest_at:
                latest_at = e.created_at
        return {
            "check_id": check_id,
            "total_entries": len(entries),
            "by_type": by_type,
            "latest_entry_at": latest_at if latest_at else None,
        }


# ════════════════════ #13 Health Marketplace ════════════════════

class HealthCheckProduct(BaseModel):
    id: str = Field(default_factory=lambda: _uid("hcp"))
    check_id: str
    product_id: str
    product_name: str
    check_name: str
    check_description: str = ""
    severity_level: str  # info / warning / critical
    enabled: bool = True
    integrated_at: float = Field(default_factory=_now_ts)


class HealthMarketplaceEngine:
    """#13 Data Health Marketplace 集成引擎。"""

    _MAX_PRODUCTS = 200
    _VALID_SEVERITY = {"info", "warning", "critical"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._products: dict[str, HealthCheckProduct] = {}

    def integrate_check(
        self,
        check_id: str,
        product_id: str,
        product_name: str,
        check_name: str,
        check_description: str = "",
        severity_level: str = "info",
    ) -> HealthCheckProduct:
        if severity_level not in self._VALID_SEVERITY:
            raise SslHealthSnoozeError(
                "INVALID_SEVERITY",
                f"severity_level must be one of {sorted(self._VALID_SEVERITY)}",
            )
        product = HealthCheckProduct(
            check_id=check_id,
            product_id=product_id,
            product_name=product_name,
            check_name=check_name,
            check_description=check_description,
            severity_level=severity_level,
        )
        with self._lock:
            if len(self._products) >= self._MAX_PRODUCTS:
                oldest_id = min(
                    self._products,
                    key=lambda pid: self._products[pid].integrated_at,
                )
                del self._products[oldest_id]
            self._products[product_id] = product
        return product

    def get_product(self, product_id: str) -> HealthCheckProduct:
        with self._lock:
            product = self._products.get(product_id)
        if product is None:
            raise SslHealthSnoozeError("NOT_FOUND", f"product {product_id} not found")
        return product

    def list_products(
        self,
        product_id: str | None = None,
        check_id: str | None = None,
        severity_level: str | None = None,
    ) -> list[HealthCheckProduct]:
        with self._lock:
            results = list(self._products.values())
        if product_id is not None:
            results = [p for p in results if p.product_id == product_id]
        if check_id is not None:
            results = [p for p in results if p.check_id == check_id]
        if severity_level is not None:
            results = [p for p in results if p.severity_level == severity_level]
        return sorted(results, key=lambda p: p.integrated_at)

    def update_product(
        self, product_id: str, updates: dict[str, Any]
    ) -> HealthCheckProduct:
        with self._lock:
            product = self._products.get(product_id)
            if product is None:
                raise SslHealthSnoozeError(
                    "NOT_FOUND", f"product {product_id} not found"
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k not in ("id", "product_id") and k in type(product).model_fields
            }
            updated = product.model_copy(update=applicable)
            self._products[product_id] = updated
        return updated

    def enable_product(self, product_id: str) -> HealthCheckProduct:
        with self._lock:
            product = self._products.get(product_id)
            if product is None:
                raise SslHealthSnoozeError(
                    "NOT_FOUND", f"product {product_id} not found"
                )
            updated = product.model_copy(update={"enabled": True})
            self._products[product_id] = updated
        return updated

    def disable_product(self, product_id: str) -> HealthCheckProduct:
        with self._lock:
            product = self._products.get(product_id)
            if product is None:
                raise SslHealthSnoozeError(
                    "NOT_FOUND", f"product {product_id} not found"
                )
            updated = product.model_copy(update={"enabled": False})
            self._products[product_id] = updated
        return updated

    def delete_product(self, product_id: str) -> bool:
        with self._lock:
            return self._products.pop(product_id, None) is not None


# ────────────────────────────────────────────────────────────────
# 单例 getter（双重检查锁）
# ────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_ssl_engine: SslCertificateEngine | None = None
_snooze_engine: HealthSnoozeEngine | None = None
_context_engine: HealthContextPanelEngine | None = None
_health_mp_engine: HealthMarketplaceEngine | None = None


def get_ssl_certificate_engine() -> SslCertificateEngine:
    global _ssl_engine
    if _ssl_engine is None:
        with _lock:
            if _ssl_engine is None:
                _ssl_engine = SslCertificateEngine()
    return _ssl_engine


def get_health_snooze_engine() -> HealthSnoozeEngine:
    global _snooze_engine
    if _snooze_engine is None:
        with _lock:
            if _snooze_engine is None:
                _snooze_engine = HealthSnoozeEngine()
    return _snooze_engine


def get_health_context_panel_engine() -> HealthContextPanelEngine:
    global _context_engine
    if _context_engine is None:
        with _lock:
            if _context_engine is None:
                _context_engine = HealthContextPanelEngine()
    return _context_engine


def get_health_marketplace_engine() -> HealthMarketplaceEngine:
    global _health_mp_engine
    if _health_mp_engine is None:
        with _lock:
            if _health_mp_engine is None:
                _health_mp_engine = HealthMarketplaceEngine()
    return _health_mp_engine
