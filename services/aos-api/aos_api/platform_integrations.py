"""W2-AV · Platform Integrations 引擎（#142 / #159 / #160）.

- #142 HealthAppEngine：Data Health 应用入口
- #159 FunctionIntegrationEngine：Functions/Workshop/Slate 集成
- #160 FerryPackageEngine：Ferry 增量包
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

_MAX_HEALTH_APP_ENTRIES = 200
_MAX_FUNCTION_INTEGRATIONS = 200
_MAX_FERRY_PACKAGES = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


# ════════════════════ #142 HealthAppEngine ════════════════════

class PlatformIntegrationError(Exception):
    """Platform Integrations 统一错误基类."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class HealthAppError(PlatformIntegrationError):
    """Health App 错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message)


class HealthAppEntry(BaseModel):
    entry_id: str = ""
    app_name: str
    icon: str = ""
    path: str
    category: str = "data_health"  # data_health | monitoring | governance
    permissions: list[str] = []
    status: str = "active"  # active | inactive
    order_index: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_HEALTH_APP_CATEGORIES = {"data_health", "monitoring", "governance"}
_VALID_HEALTH_APP_STATUSES = {"active", "inactive"}


class HealthAppEngine:
    """Data Health 应用入口引擎（#142）."""

    _instance: HealthAppEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._entries: dict[str, HealthAppEntry] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> HealthAppEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_entry(self, entry: HealthAppEntry) -> HealthAppEntry:
        if not entry.app_name or not entry.app_name.strip():
            raise HealthAppError("MISSING_APP_NAME", "app_name is required")
        if not entry.path or not entry.path.strip():
            raise HealthAppError("MISSING_PATH", "path is required")
        if entry.category not in _VALID_HEALTH_APP_CATEGORIES:
            raise HealthAppError(
                "INVALID_CATEGORY",
                f"category must be one of {_VALID_HEALTH_APP_CATEGORIES}",
            )
        if entry.status not in _VALID_HEALTH_APP_STATUSES:
            raise HealthAppError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_HEALTH_APP_STATUSES}",
            )

        now = _utcnow()
        eid = f"ha-{uuid.uuid4().hex[:8]}"
        stored = entry.model_copy(update={
            "entry_id": eid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._entries) >= _MAX_HEALTH_APP_ENTRIES:
                oldest = min(
                    self._entries.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._entries[oldest.entry_id]
            self._entries[eid] = stored
        return stored

    def get_entry(self, entry_id: str) -> HealthAppEntry:
        with self._lock:
            entry = self._entries.get(entry_id)
        if entry is None:
            raise HealthAppError("NOT_FOUND", f"entry {entry_id} not found")
        return entry

    def list_entries(
        self,
        category: str | None = None,
        status: str | None = None,
    ) -> list[HealthAppEntry]:
        with self._lock:
            results = list(self._entries.values())
        if category:
            results = [e for e in results if e.category == category]
        if status:
            results = [e for e in results if e.status == status]
        return sorted(
            results, key=lambda e: e.created_at or datetime.min, reverse=True
        )

    def update_entry(self, entry_id: str, fields: dict[str, Any]) -> HealthAppEntry:
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is None:
                raise HealthAppError("NOT_FOUND", f"entry {entry_id} not found")
            data = entry.model_dump()
            data.update(fields)
            if (
                "category" in data
                and data["category"] not in _VALID_HEALTH_APP_CATEGORIES
            ):
                raise HealthAppError(
                    "INVALID_CATEGORY",
                    f"category must be one of {_VALID_HEALTH_APP_CATEGORIES}",
                )
            if (
                "status" in data
                and data["status"] not in _VALID_HEALTH_APP_STATUSES
            ):
                raise HealthAppError(
                    "INVALID_STATUS",
                    f"status must be one of {_VALID_HEALTH_APP_STATUSES}",
                )
            data["updated_at"] = _utcnow()
            updated = HealthAppEntry(**data)
            self._entries[entry_id] = updated
        return updated

    def delete_entry(self, entry_id: str) -> bool:
        with self._lock:
            if entry_id not in self._entries:
                return False
            del self._entries[entry_id]
            return True

    def reorder_entries(self, orders: dict[str, int]) -> list[HealthAppEntry]:
        with self._lock:
            for entry_id, idx in orders.items():
                if entry_id in self._entries:
                    self._entries[entry_id].order_index = idx
            results = list(self._entries.values())
        return sorted(results, key=lambda e: e.order_index)

    def get_sidebar_items(self) -> list[HealthAppEntry]:
        with self._lock:
            results = [e for e in self._entries.values() if e.status == "active"]
        return sorted(results, key=lambda e: e.order_index)


# ════════════════════ #159 FunctionIntegrationEngine ════════════════════

class FunctionIntegrationError(PlatformIntegrationError):
    """Function 集成错误."""


class FunctionIntegration(BaseModel):
    integration_id: str = ""
    module_id: str
    function_id: str
    backend_type: str = "python"  # python | typescript | container
    trigger_type: str = "direct"  # workshop | slate | direct
    trigger_config: dict = {}
    endpoint_url: str = ""
    status: str = "active"  # active | inactive
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_BACKEND_TYPES = {"python", "typescript", "container"}
_VALID_TRIGGER_TYPES = {"workshop", "slate", "direct"}
_VALID_FUNCTION_STATUSES = {"active", "inactive"}


class FunctionIntegrationEngine:
    """Functions/Workshop/Slate 集成引擎（#159）."""

    _instance: FunctionIntegrationEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._integrations: dict[str, FunctionIntegration] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> FunctionIntegrationEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_integration(
        self, integration: FunctionIntegration
    ) -> FunctionIntegration:
        if not integration.module_id or not integration.module_id.strip():
            raise FunctionIntegrationError("MISSING_MODULE", "module_id is required")
        if not integration.function_id or not integration.function_id.strip():
            raise FunctionIntegrationError(
                "MISSING_FUNCTION", "function_id is required"
            )
        if (
            not integration.backend_type
            or not integration.backend_type.strip()
        ):
            raise FunctionIntegrationError(
                "MISSING_BACKEND_TYPE", "backend_type is required"
            )
        if integration.backend_type not in _VALID_BACKEND_TYPES:
            raise FunctionIntegrationError(
                "INVALID_BACKEND_TYPE",
                f"backend_type must be one of {_VALID_BACKEND_TYPES}",
            )
        if integration.trigger_type not in _VALID_TRIGGER_TYPES:
            raise FunctionIntegrationError(
                "INVALID_TRIGGER_TYPE",
                f"trigger_type must be one of {_VALID_TRIGGER_TYPES}",
            )
        if integration.status not in _VALID_FUNCTION_STATUSES:
            raise FunctionIntegrationError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_FUNCTION_STATUSES}",
            )

        now = _utcnow()
        iid = f"fi-{uuid.uuid4().hex[:8]}"
        stored = integration.model_copy(update={
            "integration_id": iid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._integrations) >= _MAX_FUNCTION_INTEGRATIONS:
                oldest = min(
                    self._integrations.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._integrations[oldest.integration_id]
            self._integrations[iid] = stored
        return stored

    def get_integration(self, integration_id: str) -> FunctionIntegration:
        with self._lock:
            integration = self._integrations.get(integration_id)
        if integration is None:
            raise FunctionIntegrationError(
                "NOT_FOUND", f"integration {integration_id} not found"
            )
        return integration

    def list_integrations(
        self,
        module_id: str | None = None,
        backend_type: str | None = None,
        trigger_type: str | None = None,
        status: str | None = None,
    ) -> list[FunctionIntegration]:
        with self._lock:
            results = list(self._integrations.values())
        if module_id:
            results = [i for i in results if i.module_id == module_id]
        if backend_type:
            results = [i for i in results if i.backend_type == backend_type]
        if trigger_type:
            results = [i for i in results if i.trigger_type == trigger_type]
        if status:
            results = [i for i in results if i.status == status]
        return sorted(
            results, key=lambda i: i.created_at or datetime.min, reverse=True
        )

    def update_integration(
        self, integration_id: str, fields: dict[str, Any]
    ) -> FunctionIntegration:
        with self._lock:
            integration = self._integrations.get(integration_id)
            if integration is None:
                raise FunctionIntegrationError(
                    "NOT_FOUND", f"integration {integration_id} not found"
                )
            data = integration.model_dump()
            data.update(fields)
            if (
                "backend_type" in data
                and data["backend_type"] not in _VALID_BACKEND_TYPES
            ):
                raise FunctionIntegrationError(
                    "INVALID_BACKEND_TYPE",
                    f"backend_type must be one of {_VALID_BACKEND_TYPES}",
                )
            if (
                "trigger_type" in data
                and data["trigger_type"] not in _VALID_TRIGGER_TYPES
            ):
                raise FunctionIntegrationError(
                    "INVALID_TRIGGER_TYPE",
                    f"trigger_type must be one of {_VALID_TRIGGER_TYPES}",
                )
            if (
                "status" in data
                and data["status"] not in _VALID_FUNCTION_STATUSES
            ):
                raise FunctionIntegrationError(
                    "INVALID_STATUS",
                    f"status must be one of {_VALID_FUNCTION_STATUSES}",
                )
            data["updated_at"] = _utcnow()
            updated = FunctionIntegration(**data)
            self._integrations[integration_id] = updated
        return updated

    def delete_integration(self, integration_id: str) -> bool:
        with self._lock:
            if integration_id not in self._integrations:
                return False
            del self._integrations[integration_id]
            return True

    def invoke(
        self, integration_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        with self._lock:
            integration = self._integrations.get(integration_id)
        if integration is None:
            raise FunctionIntegrationError(
                "NOT_FOUND", f"integration {integration_id} not found"
            )
        return {
            "integration_id": integration.integration_id,
            "module_id": integration.module_id,
            "function_id": integration.function_id,
            "backend_type": integration.backend_type,
            "trigger_type": integration.trigger_type,
            "result": payload or {},
            "invoked_at": _utcnow().isoformat(),
        }

    def list_by_function(self, function_id: str) -> list[FunctionIntegration]:
        with self._lock:
            results = [
                i
                for i in self._integrations.values()
                if i.function_id == function_id
            ]
        return sorted(
            results, key=lambda i: i.created_at or datetime.min, reverse=True
        )


# ════════════════════ #160 FerryPackageEngine ════════════════════

class FerryPackageError(PlatformIntegrationError):
    """Ferry 包错误."""


class FerryPackage(BaseModel):
    package_id: str = ""
    source_dataset_rid: str
    target_dataset_rid: str
    package_type: str = "incremental"  # incremental | full
    change_count: int = 0
    status: str = "pending"  # pending | packaging | ready | failed
    size_bytes: int = 0
    checksum: str = ""
    created_at: datetime | None = None
    completed_at: datetime | None = None


_VALID_PACKAGE_TYPES = {"incremental", "full"}
_VALID_PACKAGE_STATUSES = {"pending", "packaging", "ready", "failed", "applied"}


class FerryPackageEngine:
    """Ferry 增量包引擎（#160）."""

    _instance: FerryPackageEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._packages: dict[str, FerryPackage] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> FerryPackageEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def create_package(self, package: FerryPackage) -> FerryPackage:
        if (
            not package.source_dataset_rid
            or not package.source_dataset_rid.strip()
        ):
            raise FerryPackageError(
                "MISSING_SOURCE", "source_dataset_rid is required"
            )
        if (
            not package.target_dataset_rid
            or not package.target_dataset_rid.strip()
        ):
            raise FerryPackageError(
                "MISSING_TARGET", "target_dataset_rid is required"
            )
        if package.package_type not in _VALID_PACKAGE_TYPES:
            raise FerryPackageError(
                "INVALID_PACKAGE_TYPE",
                f"package_type must be one of {_VALID_PACKAGE_TYPES}",
            )
        if package.status not in _VALID_PACKAGE_STATUSES:
            raise FerryPackageError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_PACKAGE_STATUSES}",
            )

        now = _utcnow()
        pid = f"fp-{uuid.uuid4().hex[:8]}"
        stored = package.model_copy(update={
            "package_id": pid,
            "created_at": now,
        })
        with self._lock:
            if len(self._packages) >= _MAX_FERRY_PACKAGES:
                oldest = min(
                    self._packages.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._packages[oldest.package_id]
            self._packages[pid] = stored
        return stored

    def get_package(self, package_id: str) -> FerryPackage:
        with self._lock:
            package = self._packages.get(package_id)
        if package is None:
            raise FerryPackageError(
                "NOT_FOUND", f"package {package_id} not found"
            )
        return package

    def list_packages(
        self,
        source_dataset_rid: str | None = None,
        target_dataset_rid: str | None = None,
        package_type: str | None = None,
        status: str | None = None,
    ) -> list[FerryPackage]:
        with self._lock:
            results = list(self._packages.values())
        if source_dataset_rid:
            results = [
                p for p in results if p.source_dataset_rid == source_dataset_rid
            ]
        if target_dataset_rid:
            results = [
                p for p in results if p.target_dataset_rid == target_dataset_rid
            ]
        if package_type:
            results = [p for p in results if p.package_type == package_type]
        if status:
            results = [p for p in results if p.status == status]
        return sorted(
            results, key=lambda p: p.created_at or datetime.min, reverse=True
        )

    def update_package(
        self, package_id: str, fields: dict[str, Any]
    ) -> FerryPackage:
        with self._lock:
            package = self._packages.get(package_id)
            if package is None:
                raise FerryPackageError(
                    "NOT_FOUND", f"package {package_id} not found"
                )
            data = package.model_dump()
            data.update(fields)
            if (
                "package_type" in data
                and data["package_type"] not in _VALID_PACKAGE_TYPES
            ):
                raise FerryPackageError(
                    "INVALID_PACKAGE_TYPE",
                    f"package_type must be one of {_VALID_PACKAGE_TYPES}",
                )
            if (
                "status" in data
                and data["status"] not in _VALID_PACKAGE_STATUSES
            ):
                raise FerryPackageError(
                    "INVALID_STATUS",
                    f"status must be one of {_VALID_PACKAGE_STATUSES}",
                )
            data["updated_at"] = _utcnow()
            updated = FerryPackage(**data)
            self._packages[package_id] = updated
        return updated

    def delete_package(self, package_id: str) -> bool:
        with self._lock:
            if package_id not in self._packages:
                return False
            del self._packages[package_id]
            return True

    def build_package(self, package_id: str) -> FerryPackage:
        with self._lock:
            package = self._packages.get(package_id)
            if package is None:
                raise FerryPackageError(
                    "NOT_FOUND", f"package {package_id} not found"
                )
            if package.status != "pending":
                raise FerryPackageError(
                    "INVALID_STATUS",
                    f"current status {package.status} cannot build",
                )
            change_count = max(
                1, len(package.source_dataset_rid) + len(package.target_dataset_rid)
            )
            size_bytes = change_count * 1024
            checksum = f"sha256:{uuid.uuid4().hex}"
            updated = package.model_copy(update={
                "status": "ready",
                "change_count": change_count,
                "size_bytes": size_bytes,
                "checksum": checksum,
                "completed_at": _utcnow(),
            })
            self._packages[package_id] = updated
        return updated

    def fail_package(self, package_id: str) -> FerryPackage:
        with self._lock:
            package = self._packages.get(package_id)
            if package is None:
                raise FerryPackageError(
                    "NOT_FOUND", f"package {package_id} not found"
                )
            if package.status != "packaging":
                raise FerryPackageError(
                    "INVALID_STATUS",
                    f"current status {package.status} cannot fail",
                )
            updated = package.model_copy(update={
                "status": "failed",
                "completed_at": _utcnow(),
            })
            self._packages[package_id] = updated
        return updated

    def apply_package(self, package_id: str) -> dict[str, Any]:
        with self._lock:
            package = self._packages.get(package_id)
            if package is None:
                raise FerryPackageError(
                    "NOT_FOUND", f"package {package_id} not found"
                )
            if package.status != "ready":
                raise FerryPackageError(
                    "INVALID_STATUS",
                    f"current status {package.status} cannot apply",
                )
            updated = package.model_copy(update={
                "status": "applied",
                "completed_at": _utcnow(),
            })
            self._packages[package_id] = updated
        return {
            "package_id": package.package_id,
            "source_dataset_rid": package.source_dataset_rid,
            "target_dataset_rid": package.target_dataset_rid,
            "applied": True,
            "applied_at": _utcnow().isoformat(),
        }


# ════════════════════ 单例 getter ════════════════════

_health_app_engine: HealthAppEngine | None = None
_function_integration_engine: FunctionIntegrationEngine | None = None
_ferry_package_engine: FerryPackageEngine | None = None
_engine_lock = threading.Lock()


def get_health_app_engine() -> HealthAppEngine:
    global _health_app_engine
    if _health_app_engine is None:
        with _engine_lock:
            if _health_app_engine is None:
                _health_app_engine = HealthAppEngine.get_instance()
    return _health_app_engine


def get_function_integration_engine() -> FunctionIntegrationEngine:
    global _function_integration_engine
    if _function_integration_engine is None:
        with _engine_lock:
            if _function_integration_engine is None:
                _function_integration_engine = FunctionIntegrationEngine.get_instance()
    return _function_integration_engine


def get_ferry_package_engine() -> FerryPackageEngine:
    global _ferry_package_engine
    if _ferry_package_engine is None:
        with _engine_lock:
            if _ferry_package_engine is None:
                _ferry_package_engine = FerryPackageEngine.get_instance()
    return _ferry_package_engine
