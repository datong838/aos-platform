"""W2-AR · Data Integration 框架 + Pipeline 维护 + Ontology Interface 扩展（#161 #162 #163）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime

from pydantic import BaseModel

_MAX_INTEGRATION_FRAMEWORKS = 200
_MAX_PIPELINE_HEALTH_CHECKS = 200
_MAX_DATA_EXPECTATIONS = 200
_MAX_STABILITY_SUGGESTIONS = 200
_MAX_INTERFACE_LINK_TYPES = 200
_MAX_MARKETPLACE_LISTINGS = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class DataIntegrationError(Exception):
    """Data Integration 框架错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PipelineMaintenanceError(Exception):
    """Pipeline 维护错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class InterfaceExtensionError(Exception):
    """Ontology Interface 扩展错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════ #161 Data Integration Framework ════════════════════

class IntegrationFramework(BaseModel):
    framework_id: str = ""
    name: str
    description: str = ""
    connection_id: str = ""
    transform_id: str = ""
    management_config: dict = {}
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DataIntegrationFrameworkEngine:
    """Data Integration 框架引擎（注册/链接 connection/transform/汇总）."""

    _instance: DataIntegrationFrameworkEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._frameworks: dict[str, IntegrationFramework] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> DataIntegrationFrameworkEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, framework: IntegrationFramework) -> IntegrationFramework:
        if not framework.name or not framework.name.strip():
            raise DataIntegrationError("MISSING_NAME", "name is required")
        now = _utcnow()
        fid = f"fw-{uuid.uuid4().hex[:8]}"
        stored = framework.model_copy(update={
            "framework_id": fid,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._frameworks) >= _MAX_INTEGRATION_FRAMEWORKS:
                oldest = min(self._frameworks.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._frameworks[oldest.framework_id]
            self._frameworks[fid] = stored
        return stored

    def get(self, framework_id: str) -> IntegrationFramework:
        with self._lock:
            framework = self._frameworks.get(framework_id)
        if framework is None:
            raise DataIntegrationError("NOT_FOUND", f"framework {framework_id} not found")
        return framework

    def list(self, status: str | None = None) -> list[IntegrationFramework]:
        with self._lock:
            results = list(self._frameworks.values())
        if status:
            results = [f for f in results if f.status == status]
        return sorted(results, key=lambda f: f.created_at or datetime.min, reverse=True)

    def update(self, framework_id: str, fields: dict) -> IntegrationFramework:
        with self._lock:
            framework = self._frameworks.get(framework_id)
            if framework is None:
                raise DataIntegrationError("NOT_FOUND", f"framework {framework_id} not found")
            data = framework.model_dump()
            data.update(fields)
            data["updated_at"] = _utcnow()
            updated = IntegrationFramework(**data)
            self._frameworks[framework_id] = updated
        return updated

    def delete(self, framework_id: str) -> None:
        with self._lock:
            if framework_id not in self._frameworks:
                raise DataIntegrationError("NOT_FOUND", f"framework {framework_id} not found")
            del self._frameworks[framework_id]

    def link_connection(self, framework_id: str, connection_id: str) -> IntegrationFramework:
        with self._lock:
            framework = self._frameworks.get(framework_id)
            if framework is None:
                raise DataIntegrationError("NOT_FOUND", f"framework {framework_id} not found")
            updated = framework.model_copy(update={
                "connection_id": connection_id,
                "updated_at": _utcnow(),
            })
            self._frameworks[framework_id] = updated
        return updated

    def link_transform(self, framework_id: str, transform_id: str) -> IntegrationFramework:
        with self._lock:
            framework = self._frameworks.get(framework_id)
            if framework is None:
                raise DataIntegrationError("NOT_FOUND", f"framework {framework_id} not found")
            updated = framework.model_copy(update={
                "transform_id": transform_id,
                "updated_at": _utcnow(),
            })
            self._frameworks[framework_id] = updated
        return updated

    def get_summary(self, framework_id: str) -> dict:
        with self._lock:
            framework = self._frameworks.get(framework_id)
        if framework is None:
            raise DataIntegrationError("NOT_FOUND", f"framework {framework_id} not found")
        has_connection = bool(framework.connection_id)
        has_transform = bool(framework.transform_id)
        has_management = bool(framework.management_config)
        if has_connection and has_transform and has_management:
            completeness = "full"
        elif has_connection or has_transform or has_management:
            completeness = "partial"
        else:
            completeness = "empty"
        return {
            "framework_id": framework.framework_id,
            "name": framework.name,
            "has_connection": has_connection,
            "has_transform": has_transform,
            "has_management": has_management,
            "completeness": completeness,
        }


_data_integration_framework_engine: DataIntegrationFrameworkEngine | None = None
_data_integration_framework_engine_lock = threading.Lock()


def get_data_integration_framework_engine() -> DataIntegrationFrameworkEngine:
    global _data_integration_framework_engine
    if _data_integration_framework_engine is None:
        with _data_integration_framework_engine_lock:
            if _data_integration_framework_engine is None:
                _data_integration_framework_engine = DataIntegrationFrameworkEngine.get_instance()
    return _data_integration_framework_engine


# ════════════════════ #162 Pipeline Maintenance ════════════════════

class PipelineHealthCheck(BaseModel):
    check_id: str = ""
    pipeline_id: str
    check_type: str
    status: str = "pass"  # pass | fail | warning
    severity: str = "info"  # info | warning | critical
    message: str = ""
    last_run_at: datetime | None = None
    created_at: datetime | None = None


class DataExpectation(BaseModel):
    expectation_id: str = ""
    pipeline_id: str
    delivery_cycle: str = ""
    build_frequency: str = ""
    data_expiry_threshold_hours: int = 24
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StabilitySuggestion(BaseModel):
    suggestion_id: str = ""
    pipeline_id: str
    suggestion_type: str
    priority: str = "medium"  # low | medium | high
    description: str = ""
    created_at: datetime | None = None


_VALID_CHECK_STATUSES = {"pass", "fail", "warning"}
_VALID_SEVERITIES = {"info", "warning", "critical"}
_VALID_PRIORITIES = {"low", "medium", "high"}


class PipelineMaintenanceEngine:
    """Pipeline 维护引擎（健康检查 + 数据期望 + 稳定性建议）."""

    _instance: PipelineMaintenanceEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._checks: dict[str, PipelineHealthCheck] = {}
        self._expectations: dict[str, DataExpectation] = {}
        self._suggestions: dict[str, StabilitySuggestion] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> PipelineMaintenanceEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── 健康检查 ──

    def register_check(self, check: PipelineHealthCheck) -> PipelineHealthCheck:
        if not check.pipeline_id or not check.pipeline_id.strip():
            raise PipelineMaintenanceError("MISSING_PIPELINE", "pipeline_id is required")
        if not check.check_type or not check.check_type.strip():
            raise PipelineMaintenanceError("MISSING_CHECK_TYPE", "check_type is required")
        if check.status not in _VALID_CHECK_STATUSES:
            raise PipelineMaintenanceError(
                "INVALID_STATUS", f"status must be one of {_VALID_CHECK_STATUSES}")
        if check.severity not in _VALID_SEVERITIES:
            raise PipelineMaintenanceError(
                "INVALID_SEVERITY", f"severity must be one of {_VALID_SEVERITIES}")
        now = _utcnow()
        cid = f"phc-{uuid.uuid4().hex[:8]}"
        stored = check.model_copy(update={
            "check_id": cid,
            "last_run_at": now,
            "created_at": now,
        })
        with self._lock:
            if len(self._checks) >= _MAX_PIPELINE_HEALTH_CHECKS:
                oldest = min(self._checks.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._checks[oldest.check_id]
            self._checks[cid] = stored
        return stored

    def get_check(self, check_id: str) -> PipelineHealthCheck:
        with self._lock:
            check = self._checks.get(check_id)
        if check is None:
            raise PipelineMaintenanceError("NOT_FOUND", f"check {check_id} not found")
        return check

    def list_checks(self, pipeline_id: str | None = None,
                    status: str | None = None) -> list[PipelineHealthCheck]:
        with self._lock:
            results = list(self._checks.values())
        if pipeline_id:
            results = [c for c in results if c.pipeline_id == pipeline_id]
        if status:
            results = [c for c in results if c.status == status]
        return sorted(results, key=lambda c: c.created_at or datetime.min, reverse=True)

    def update_check(self, check_id: str, fields: dict) -> PipelineHealthCheck:
        if "status" in fields and fields["status"] not in _VALID_CHECK_STATUSES:
            raise PipelineMaintenanceError(
                "INVALID_STATUS", f"status must be one of {_VALID_CHECK_STATUSES}")
        if "severity" in fields and fields["severity"] not in _VALID_SEVERITIES:
            raise PipelineMaintenanceError(
                "INVALID_SEVERITY", f"severity must be one of {_VALID_SEVERITIES}")
        with self._lock:
            check = self._checks.get(check_id)
            if check is None:
                raise PipelineMaintenanceError("NOT_FOUND", f"check {check_id} not found")
            data = check.model_dump()
            data.update(fields)
            data["last_run_at"] = _utcnow()
            updated = PipelineHealthCheck(**data)
            self._checks[check_id] = updated
        return updated

    def delete_check(self, check_id: str) -> None:
        with self._lock:
            if check_id not in self._checks:
                raise PipelineMaintenanceError("NOT_FOUND", f"check {check_id} not found")
            del self._checks[check_id]

    def list_failing_checks(self, pipeline_id: str | None = None) -> list[PipelineHealthCheck]:
        with self._lock:
            results = [c for c in self._checks.values()
                       if c.status in ("fail", "warning")]
        if pipeline_id:
            results = [c for c in results if c.pipeline_id == pipeline_id]
        return sorted(results, key=lambda c: c.created_at or datetime.min, reverse=True)

    # ── 数据期望 ──

    def register_expectation(self, expectation: DataExpectation) -> DataExpectation:
        if not expectation.pipeline_id or not expectation.pipeline_id.strip():
            raise PipelineMaintenanceError("MISSING_PIPELINE", "pipeline_id is required")
        now = _utcnow()
        eid = f"de-{uuid.uuid4().hex[:8]}"
        stored = expectation.model_copy(update={
            "expectation_id": eid,
            "created_at": now,
        })
        with self._lock:
            if len(self._expectations) >= _MAX_DATA_EXPECTATIONS:
                oldest = min(self._expectations.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._expectations[oldest.expectation_id]
            self._expectations[eid] = stored
        return stored

    def get_expectation(self, expectation_id: str) -> DataExpectation:
        with self._lock:
            expectation = self._expectations.get(expectation_id)
        if expectation is None:
            raise PipelineMaintenanceError(
                "NOT_FOUND", f"expectation {expectation_id} not found")
        return expectation

    def list_expectations(self, pipeline_id: str | None = None) -> list[DataExpectation]:
        with self._lock:
            results = list(self._expectations.values())
        if pipeline_id:
            results = [e for e in results if e.pipeline_id == pipeline_id]
        return sorted(results, key=lambda e: e.created_at or datetime.min, reverse=True)

    def update_expectation(self, expectation_id: str, fields: dict) -> DataExpectation:
        with self._lock:
            expectation = self._expectations.get(expectation_id)
            if expectation is None:
                raise PipelineMaintenanceError(
                    "NOT_FOUND", f"expectation {expectation_id} not found")
            data = expectation.model_dump()
            data.update(fields)
            data["updated_at"] = _utcnow()
            updated = DataExpectation(**data)
            self._expectations[expectation_id] = updated
        return updated

    def delete_expectation(self, expectation_id: str) -> None:
        with self._lock:
            if expectation_id not in self._expectations:
                raise PipelineMaintenanceError(
                    "NOT_FOUND", f"expectation {expectation_id} not found")
            del self._expectations[expectation_id]

    # ── 稳定性建议 ──

    def register_suggestion(self, suggestion: StabilitySuggestion) -> StabilitySuggestion:
        if not suggestion.pipeline_id or not suggestion.pipeline_id.strip():
            raise PipelineMaintenanceError("MISSING_PIPELINE", "pipeline_id is required")
        if not suggestion.suggestion_type or not suggestion.suggestion_type.strip():
            raise PipelineMaintenanceError("MISSING_SUGGESTION_TYPE", "suggestion_type is required")
        if suggestion.priority not in _VALID_PRIORITIES:
            raise PipelineMaintenanceError(
                "INVALID_PRIORITY", f"priority must be one of {_VALID_PRIORITIES}")
        now = _utcnow()
        sid = f"ss-{uuid.uuid4().hex[:8]}"
        stored = suggestion.model_copy(update={
            "suggestion_id": sid,
            "created_at": now,
        })
        with self._lock:
            if len(self._suggestions) >= _MAX_STABILITY_SUGGESTIONS:
                oldest = min(self._suggestions.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._suggestions[oldest.suggestion_id]
            self._suggestions[sid] = stored
        return stored

    def get_suggestion(self, suggestion_id: str) -> StabilitySuggestion:
        with self._lock:
            suggestion = self._suggestions.get(suggestion_id)
        if suggestion is None:
            raise PipelineMaintenanceError(
                "NOT_FOUND", f"suggestion {suggestion_id} not found")
        return suggestion

    def list_suggestions(self, pipeline_id: str | None = None,
                         priority: str | None = None) -> list[StabilitySuggestion]:
        with self._lock:
            results = list(self._suggestions.values())
        if pipeline_id:
            results = [s for s in results if s.pipeline_id == pipeline_id]
        if priority:
            results = [s for s in results if s.priority == priority]
        return sorted(results, key=lambda s: s.created_at or datetime.min, reverse=True)

    def delete_suggestion(self, suggestion_id: str) -> None:
        with self._lock:
            if suggestion_id not in self._suggestions:
                raise PipelineMaintenanceError(
                    "NOT_FOUND", f"suggestion {suggestion_id} not found")
            del self._suggestions[suggestion_id]

    # ── 综合 ──

    def monitor_pipeline(self, pipeline_id: str) -> dict:
        with self._lock:
            checks = [c for c in self._checks.values() if c.pipeline_id == pipeline_id]
            has_expectation = any(
                e.pipeline_id == pipeline_id for e in self._expectations.values())
            suggestions_count = sum(
                1 for s in self._suggestions.values() if s.pipeline_id == pipeline_id)
        failing = [c for c in checks if c.status in ("fail", "warning")]
        has_fail = any(c.status == "fail" for c in checks)
        has_warning = any(c.status == "warning" for c in checks)
        if has_fail:
            health_status = "critical"
        elif has_warning:
            health_status = "degraded"
        else:
            health_status = "healthy"
        return {
            "pipeline_id": pipeline_id,
            "total_checks": len(checks),
            "failing_checks": len(failing),
            "has_expectation": has_expectation,
            "suggestions_count": suggestions_count,
            "health_status": health_status,
        }


_pipeline_maintenance_engine: PipelineMaintenanceEngine | None = None
_pipeline_maintenance_engine_lock = threading.Lock()


def get_pipeline_maintenance_engine() -> PipelineMaintenanceEngine:
    global _pipeline_maintenance_engine
    if _pipeline_maintenance_engine is None:
        with _pipeline_maintenance_engine_lock:
            if _pipeline_maintenance_engine is None:
                _pipeline_maintenance_engine = PipelineMaintenanceEngine.get_instance()
    return _pipeline_maintenance_engine


# ════════════════════ #163 Ontology Interface Extension ════════════════════

class InterfaceLinkType(BaseModel):
    link_type_id: str = ""
    name: str
    source_interface_id: str
    target_interface_id: str
    cardinality: str = "many_to_many"  # one_to_one | one_to_many | many_to_many
    description: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InterfaceMarketplaceListing(BaseModel):
    listing_id: str = ""
    interface_id: str
    title: str
    description: str = ""
    version: str = "1.0.0"
    publisher: str = ""
    status: str = "draft"  # draft | published | imported
    published_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_CARDINALITIES = {"one_to_one", "one_to_many", "many_to_many"}
_VALID_LISTING_STATUSES = {"draft", "published", "imported"}


class OntologyInterfaceExtensionEngine:
    """Ontology Interface 扩展引擎（接口链接类型 + Marketplace）."""

    _instance: OntologyInterfaceExtensionEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._link_types: dict[str, InterfaceLinkType] = {}
        self._listings: dict[str, InterfaceMarketplaceListing] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> OntologyInterfaceExtensionEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── 接口链接类型 ──

    def register_link_type(self, link_type: InterfaceLinkType) -> InterfaceLinkType:
        if not link_type.name or not link_type.name.strip():
            raise InterfaceExtensionError("MISSING_NAME", "name is required")
        if not link_type.source_interface_id or not link_type.source_interface_id.strip():
            raise InterfaceExtensionError("MISSING_SOURCE_INTERFACE", "source_interface_id is required")
        if not link_type.target_interface_id or not link_type.target_interface_id.strip():
            raise InterfaceExtensionError("MISSING_TARGET_INTERFACE", "target_interface_id is required")
        if link_type.cardinality not in _VALID_CARDINALITIES:
            raise InterfaceExtensionError(
                "INVALID_CARDINALITY", f"cardinality must be one of {_VALID_CARDINALITIES}")
        now = _utcnow()
        lid = f"ilt-{uuid.uuid4().hex[:8]}"
        stored = link_type.model_copy(update={
            "link_type_id": lid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._link_types) >= _MAX_INTERFACE_LINK_TYPES:
                oldest = min(self._link_types.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._link_types[oldest.link_type_id]
            self._link_types[lid] = stored
        return stored

    def get_link_type(self, link_type_id: str) -> InterfaceLinkType:
        with self._lock:
            link_type = self._link_types.get(link_type_id)
        if link_type is None:
            raise InterfaceExtensionError(
                "NOT_FOUND", f"link_type {link_type_id} not found")
        return link_type

    def list_link_types(self, source_interface_id: str | None = None) -> list[InterfaceLinkType]:
        with self._lock:
            results = list(self._link_types.values())
        if source_interface_id:
            results = [lt for lt in results if lt.source_interface_id == source_interface_id]
        return sorted(results, key=lambda lt: lt.created_at or datetime.min, reverse=True)

    def update_link_type(self, link_type_id: str, fields: dict) -> InterfaceLinkType:
        if "cardinality" in fields and fields["cardinality"] not in _VALID_CARDINALITIES:
            raise InterfaceExtensionError(
                "INVALID_CARDINALITY", f"cardinality must be one of {_VALID_CARDINALITIES}")
        with self._lock:
            link_type = self._link_types.get(link_type_id)
            if link_type is None:
                raise InterfaceExtensionError(
                    "NOT_FOUND", f"link_type {link_type_id} not found")
            data = link_type.model_dump()
            data.update(fields)
            data["updated_at"] = _utcnow()
            updated = InterfaceLinkType(**data)
            self._link_types[link_type_id] = updated
        return updated

    def delete_link_type(self, link_type_id: str) -> None:
        with self._lock:
            if link_type_id not in self._link_types:
                raise InterfaceExtensionError(
                    "NOT_FOUND", f"link_type {link_type_id} not found")
            del self._link_types[link_type_id]

    # ── Marketplace ──

    def register_listing(self, listing: InterfaceMarketplaceListing) -> InterfaceMarketplaceListing:
        if not listing.interface_id or not listing.interface_id.strip():
            raise InterfaceExtensionError("MISSING_INTERFACE", "interface_id is required")
        if not listing.title or not listing.title.strip():
            raise InterfaceExtensionError("MISSING_TITLE", "title is required")
        if listing.status not in _VALID_LISTING_STATUSES:
            raise InterfaceExtensionError(
                "INVALID_STATUS", f"status must be one of {_VALID_LISTING_STATUSES}")
        now = _utcnow()
        lid = f"iml-{uuid.uuid4().hex[:8]}"
        stored = listing.model_copy(update={
            "listing_id": lid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._listings) >= _MAX_MARKETPLACE_LISTINGS:
                oldest = min(self._listings.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._listings[oldest.listing_id]
            self._listings[lid] = stored
        return stored

    def get_listing(self, listing_id: str) -> InterfaceMarketplaceListing:
        with self._lock:
            listing = self._listings.get(listing_id)
        if listing is None:
            raise InterfaceExtensionError(
                "NOT_FOUND", f"listing {listing_id} not found")
        return listing

    def list_listings(self, status: str | None = None) -> list[InterfaceMarketplaceListing]:
        with self._lock:
            results = list(self._listings.values())
        if status:
            results = [l for l in results if l.status == status]
        return sorted(results, key=lambda l: l.created_at or datetime.min, reverse=True)

    def publish_to_marketplace(self, listing_id: str) -> InterfaceMarketplaceListing:
        now = _utcnow()
        with self._lock:
            listing = self._listings.get(listing_id)
            if listing is None:
                raise InterfaceExtensionError(
                    "NOT_FOUND", f"listing {listing_id} not found")
            updated = listing.model_copy(update={
                "status": "published",
                "published_at": now,
                "updated_at": now,
            })
            self._listings[listing_id] = updated
        return updated

    def import_from_marketplace(self, interface_id: str, title: str,
                                description: str = "", version: str = "1.0.0",
                                publisher: str = "") -> InterfaceMarketplaceListing:
        if not interface_id or not interface_id.strip():
            raise InterfaceExtensionError("MISSING_INTERFACE", "interface_id is required")
        if not title or not title.strip():
            raise InterfaceExtensionError("MISSING_TITLE", "title is required")
        now = _utcnow()
        lid = f"iml-{uuid.uuid4().hex[:8]}"
        stored = InterfaceMarketplaceListing(
            listing_id=lid,
            interface_id=interface_id,
            title=title,
            description=description,
            version=version,
            publisher=publisher,
            status="imported",
            published_at=None,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            if len(self._listings) >= _MAX_MARKETPLACE_LISTINGS:
                oldest = min(self._listings.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._listings[oldest.listing_id]
            self._listings[lid] = stored
        return stored

    def update_listing(self, listing_id: str, fields: dict) -> InterfaceMarketplaceListing:
        if "status" in fields and fields["status"] not in _VALID_LISTING_STATUSES:
            raise InterfaceExtensionError(
                "INVALID_STATUS", f"status must be one of {_VALID_LISTING_STATUSES}")
        with self._lock:
            listing = self._listings.get(listing_id)
            if listing is None:
                raise InterfaceExtensionError(
                    "NOT_FOUND", f"listing {listing_id} not found")
            data = listing.model_dump()
            data.update(fields)
            data["updated_at"] = _utcnow()
            updated = InterfaceMarketplaceListing(**data)
            self._listings[listing_id] = updated
        return updated

    def delete_listing(self, listing_id: str) -> None:
        with self._lock:
            if listing_id not in self._listings:
                raise InterfaceExtensionError(
                    "NOT_FOUND", f"listing {listing_id} not found")
            del self._listings[listing_id]


_ontology_interface_extension_engine: OntologyInterfaceExtensionEngine | None = None
_ontology_interface_extension_engine_lock = threading.Lock()


def get_ontology_interface_extension_engine() -> OntologyInterfaceExtensionEngine:
    global _ontology_interface_extension_engine
    if _ontology_interface_extension_engine is None:
        with _ontology_interface_extension_engine_lock:
            if _ontology_interface_extension_engine is None:
                _ontology_interface_extension_engine = OntologyInterfaceExtensionEngine.get_instance()
    return _ontology_interface_extension_engine
