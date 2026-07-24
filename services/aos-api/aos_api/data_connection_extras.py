"""W2-AW · Data Connection Extras 引擎（#128 #129 #5）."""
from __future__ import annotations

from typing import Optional

import threading
import uuid
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel

_MAX_CLOUD_IDENTITIES = 200
_MAX_VIRTUAL_TABLES = 200
_MAX_AGENT_METRICS = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


# ════════════════════ #128 Cloud Identity ════════════════════

class CloudIdentityError(Exception):
    """Cloud Identity 错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class CloudIdentity(BaseModel):
    identity_id: str = ""
    name: str
    provider: str = "oidc"  # oidc | azure_ad | aws_iam | gcp
    config: dict = {}
    status: str = "active"  # active | inactive
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


_VALID_CLOUD_PROVIDERS = {"oidc", "azure_ad", "aws_iam", "gcp", "aws"}
_VALID_IDENTITY_STATUSES = {"active", "inactive"}


class CloudIdentityEngine:
    """Cloud Identity OIDC/Cloud Identity 引擎."""

    _instance: Optional[CloudIdentityEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._identities: dict[str, CloudIdentity] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> CloudIdentityEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_identity(self, identity: CloudIdentity) -> CloudIdentity:
        if not identity.name or not identity.name.strip():
            raise CloudIdentityError("MISSING_NAME", "name is required")
        if not identity.provider or not identity.provider.strip():
            raise CloudIdentityError("MISSING_PROVIDER", "provider is required")
        if identity.provider not in _VALID_CLOUD_PROVIDERS:
            raise CloudIdentityError(
                "INVALID_PROVIDER",
                f"provider must be one of {_VALID_CLOUD_PROVIDERS}",
            )
        if identity.status not in _VALID_IDENTITY_STATUSES:
            raise CloudIdentityError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_IDENTITY_STATUSES}",
            )

        now = _utcnow()
        iid = f"ci-{uuid.uuid4().hex[:8]}"
        stored = identity.model_copy(
            update={"identity_id": iid, "created_at": now, "updated_at": now}
        )
        with self._lock:
            if len(self._identities) >= _MAX_CLOUD_IDENTITIES:
                oldest = min(
                    self._identities.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._identities[oldest.identity_id]
            self._identities[iid] = stored
        return stored

    def get_identity(self, identity_id: str) -> CloudIdentity:
        with self._lock:
            identity = self._identities.get(identity_id)
        if identity is None:
            raise CloudIdentityError(
                "NOT_FOUND", f"identity {identity_id} not found"
            )
        return identity

    def list_identities(
        self,
        provider: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[CloudIdentity]:
        with self._lock:
            results = list(self._identities.values())
        if provider:
            results = [i for i in results if i.provider == provider]
        if status:
            results = [i for i in results if i.status == status]
        return sorted(
            results,
            key=lambda i: i.created_at or datetime.min,
            reverse=True,
        )

    def update_identity(
        self, identity_id: str, updates: dict
    ) -> CloudIdentity:
        if "provider" in updates and updates["provider"] not in _VALID_CLOUD_PROVIDERS:
            raise CloudIdentityError(
                "INVALID_PROVIDER",
                f"provider must be one of {_VALID_CLOUD_PROVIDERS}",
            )
        if "status" in updates and updates["status"] not in _VALID_IDENTITY_STATUSES:
            raise CloudIdentityError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_IDENTITY_STATUSES}",
            )

        with self._lock:
            identity = self._identities.get(identity_id)
            if identity is None:
                raise CloudIdentityError(
                    "NOT_FOUND", f"identity {identity_id} not found"
                )
            data = identity.model_dump()
            data.update(updates)
            updated = CloudIdentity(**{**data, "updated_at": _utcnow()})
            self._identities[identity_id] = updated
        return updated

    def delete_identity(self, identity_id: str) -> bool:
        with self._lock:
            if identity_id in self._identities:
                del self._identities[identity_id]
                return True
        return False

    def validate_config(self, provider: str, config: dict) -> dict[str, Any]:
        errors: list[str] = []
        if provider not in _VALID_CLOUD_PROVIDERS:
            errors.append(f"provider must be one of {_VALID_CLOUD_PROVIDERS}")
            return {"ok": False, "errors": errors}

        if provider == "oidc":
            if "issuer_url" not in config or not config["issuer_url"]:
                errors.append("oidc config missing issuer_url")
            if "client_id" not in config or not config["client_id"]:
                errors.append("oidc config missing client_id")
        elif provider == "azure_ad":
            if "tenant_id" not in config or not config["tenant_id"]:
                errors.append("azure_ad config missing tenant_id")
            if "client_id" not in config or not config["client_id"]:
                errors.append("azure_ad config missing client_id")
        elif provider == "aws_iam":
            if "role_arn" not in config or not config["role_arn"]:
                errors.append("aws_iam config missing role_arn")
        elif provider == "gcp":
            if "service_account_key" not in config or not config["service_account_key"]:
                errors.append("gcp config missing service_account_key")

        return {"ok": len(errors) == 0, "errors": errors}


_cloud_identity_engine: Optional[CloudIdentityEngine] = None
_cloud_identity_engine_lock = threading.Lock()


def get_cloud_identity_engine() -> CloudIdentityEngine:
    global _cloud_identity_engine
    if _cloud_identity_engine is None:
        with _cloud_identity_engine_lock:
            if _cloud_identity_engine is None:
                _cloud_identity_engine = CloudIdentityEngine.get_instance()
    return _cloud_identity_engine


# ════════════════════ #129 Virtual Table ════════════════════

class VirtualTableError(Exception):
    """Virtual Table 错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SchemaColumn(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    description: str = ""


class VirtualTable(BaseModel):
    table_id: str = ""
    name: str
    source_connection_id: str = ""
    source_table: str = ""
    schema_columns: list[SchemaColumn] = []
    sync_mode: str = "snapshot"  # snapshot | incremental
    status: str = "active"  # active | inactive
    last_sync_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


_VALID_SYNC_MODES = {"snapshot", "incremental"}
_VALID_VIRTUAL_TABLE_STATUSES = {"active", "inactive"}


class VirtualTableEngine:
    """Data Connection 虚拟表引擎."""

    _instance: Optional[VirtualTableEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._tables: dict[str, VirtualTable] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> VirtualTableEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_table(self, table: VirtualTable) -> VirtualTable:
        if not table.name or not table.name.strip():
            raise VirtualTableError("MISSING_NAME", "name is required")
        if (
            not table.source_connection_id
            or not table.source_connection_id.strip()
        ):
            raise VirtualTableError(
                "MISSING_SOURCE_CONNECTION", "source_connection_id is required"
            )
        if table.sync_mode not in _VALID_SYNC_MODES:
            raise VirtualTableError(
                "INVALID_SYNC_MODE",
                f"sync_mode must be one of {_VALID_SYNC_MODES}",
            )
        if table.status not in _VALID_VIRTUAL_TABLE_STATUSES:
            raise VirtualTableError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_VIRTUAL_TABLE_STATUSES}",
            )

        now = _utcnow()
        tid = f"vt-{uuid.uuid4().hex[:8]}"
        stored = table.model_copy(
            update={"table_id": tid, "created_at": now, "updated_at": now}
        )
        with self._lock:
            if len(self._tables) >= _MAX_VIRTUAL_TABLES:
                oldest = min(
                    self._tables.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._tables[oldest.table_id]
            self._tables[tid] = stored
        return stored

    def get_table(self, table_id: str) -> VirtualTable:
        with self._lock:
            table = self._tables.get(table_id)
        if table is None:
            raise VirtualTableError("NOT_FOUND", f"table {table_id} not found")
        return table

    def list_tables(
        self,
        source_connection_id: Optional[str] = None,
        sync_mode: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[VirtualTable]:
        with self._lock:
            results = list(self._tables.values())
        if source_connection_id:
            results = [
                t for t in results if t.source_connection_id == source_connection_id
            ]
        if sync_mode:
            results = [t for t in results if t.sync_mode == sync_mode]
        if status:
            results = [t for t in results if t.status == status]
        return sorted(
            results,
            key=lambda t: t.created_at or datetime.min,
            reverse=True,
        )

    def update_table(self, table_id: str, updates: dict) -> VirtualTable:
        if "sync_mode" in updates and updates["sync_mode"] not in _VALID_SYNC_MODES:
            raise VirtualTableError(
                "INVALID_SYNC_MODE",
                f"sync_mode must be one of {_VALID_SYNC_MODES}",
            )
        if "status" in updates and updates["status"] not in _VALID_VIRTUAL_TABLE_STATUSES:
            raise VirtualTableError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_VIRTUAL_TABLE_STATUSES}",
            )

        with self._lock:
            table = self._tables.get(table_id)
            if table is None:
                raise VirtualTableError(
                    "NOT_FOUND", f"table {table_id} not found"
                )
            data = table.model_dump()
            data.update(updates)
            updated = VirtualTable(**{**data, "updated_at": _utcnow()})
            self._tables[table_id] = updated
        return updated

    def delete_table(self, table_id: str) -> bool:
        with self._lock:
            if table_id in self._tables:
                del self._tables[table_id]
                return True
        return False

    def sync_table(self, table_id: str) -> VirtualTable:
        with self._lock:
            table = self._tables.get(table_id)
            if table is None:
                raise VirtualTableError(
                    "NOT_FOUND", f"table {table_id} not found"
                )
            updated = table.model_copy(
                update={"last_sync_at": _utcnow(), "updated_at": _utcnow()}
            )
            self._tables[table_id] = updated
        return updated


_virtual_table_engine: Optional[VirtualTableEngine] = None
_virtual_table_engine_lock = threading.Lock()


def get_virtual_table_engine() -> VirtualTableEngine:
    global _virtual_table_engine
    if _virtual_table_engine is None:
        with _virtual_table_engine_lock:
            if _virtual_table_engine is None:
                _virtual_table_engine = VirtualTableEngine.get_instance()
    return _virtual_table_engine


# ════════════════════ #5 Agent Metrics ════════════════════

class AgentMetricsError(Exception):
    """Agent Metrics 错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AgentMetrics(BaseModel):
    metrics_id: str = ""
    agent_id: str
    memory_mb: float = 0.0
    disk_gb: float = 0.0
    cpu_percent: float = 0.0
    queue_depth: int = 0
    uptime_seconds: int = 0
    status: str = "healthy"  # healthy | warning | critical
    collected_at: Optional[datetime] = None
    recorded_at: Optional[datetime] = None  # alias for collected_at
    created_at: Optional[datetime] = None


_VALID_METRICS_STATUSES = {"healthy", "warning", "critical", "ok"}


class AgentMetricsEngine:
    """Data Connection Agent Metrics 引擎."""

    _instance: Optional[AgentMetricsEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._metrics: dict[str, AgentMetrics] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> AgentMetricsEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def record_metrics(self, metrics: AgentMetrics) -> AgentMetrics:
        if not metrics.agent_id or not metrics.agent_id.strip():
            raise AgentMetricsError("MISSING_AGENT", "agent_id is required")
        if metrics.status not in _VALID_METRICS_STATUSES:
            raise AgentMetricsError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_METRICS_STATUSES}",
            )

        now = _utcnow()
        mid = f"am-{uuid.uuid4().hex[:8]}"
        stored = metrics.model_copy(
            update={
                "metrics_id": mid,
                "collected_at": metrics.collected_at or now,
                "created_at": now,
            }
        )
        with self._lock:
            if len(self._metrics) >= _MAX_AGENT_METRICS:
                oldest = min(
                    self._metrics.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._metrics[oldest.metrics_id]
            self._metrics[mid] = stored
        return stored

    def get_metrics(self, metrics_id: str) -> AgentMetrics:
        with self._lock:
            metrics = self._metrics.get(metrics_id)
        if metrics is None:
            raise AgentMetricsError(
                "NOT_FOUND", f"metrics {metrics_id} not found"
            )
        return metrics

    def list_metrics(
        self,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[AgentMetrics]:
        with self._lock:
            results = list(self._metrics.values())
        if agent_id:
            results = [m for m in results if m.agent_id == agent_id]
        if status:
            results = [m for m in results if m.status == status]
        return sorted(
            results,
            key=lambda m: m.created_at or datetime.min,
            reverse=True,
        )

    def list_latest_by_agent(self) -> list[AgentMetrics]:
        with self._lock:
            all_metrics = list(self._metrics.values())
        latest: dict[str, AgentMetrics] = {}
        for m in all_metrics:
            existing = latest.get(m.agent_id)
            if existing is None or (
                (m.created_at or datetime.min)
                > (existing.created_at or datetime.min)
            ):
                latest[m.agent_id] = m
        return sorted(
            latest.values(),
            key=lambda m: m.created_at or datetime.min,
            reverse=True,
        )

    def get_agent_summary(self, agent_id: str) -> dict[str, Any]:
        cutoff = _utcnow() - timedelta(hours=24)
        with self._lock:
            agent_metrics = [
                m
                for m in self._metrics.values()
                if m.agent_id == agent_id and m.created_at and m.created_at >= cutoff
            ]
        if not agent_metrics:
            return {
                "agent_id": agent_id,
                "count": 0,
                "avg_memory_mb": 0.0,
                "avg_disk_gb": 0.0,
                "avg_cpu_percent": 0.0,
                "avg_queue_depth": 0.0,
                "avg_uptime_seconds": 0.0,
            }

        count = len(agent_metrics)
        return {
            "agent_id": agent_id,
            "count": count,
            "avg_memory_mb": sum(m.memory_mb for m in agent_metrics) / count,
            "avg_disk_gb": sum(m.disk_gb for m in agent_metrics) / count,
            "avg_cpu_percent": sum(m.cpu_percent for m in agent_metrics) / count,
            "avg_queue_depth": sum(m.queue_depth for m in agent_metrics) / count,
            "avg_uptime_seconds": sum(m.uptime_seconds for m in agent_metrics)
            / count,
        }

    def prune_old(self, days: int = 30) -> int:
        cutoff = _utcnow() - timedelta(days=days)
        removed = 0
        with self._lock:
            to_remove = [
                mid
                for mid, m in self._metrics.items()
                if m.created_at and m.created_at < cutoff
            ]
            for mid in to_remove:
                del self._metrics[mid]
                removed += 1
        return removed


_agent_metrics_engine: Optional[AgentMetricsEngine] = None
_agent_metrics_engine_lock = threading.Lock()


def get_agent_metrics_engine() -> AgentMetricsEngine:
    global _agent_metrics_engine
    if _agent_metrics_engine is None:
        with _agent_metrics_engine_lock:
            if _agent_metrics_engine is None:
                _agent_metrics_engine = AgentMetricsEngine.get_instance()
    return _agent_metrics_engine
