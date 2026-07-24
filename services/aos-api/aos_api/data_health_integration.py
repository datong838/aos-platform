"""W2-AM · Data Health Integration 引擎（#139 #140 #141）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime

from pydantic import BaseModel

_MAX_HEALTH_ISSUES = 200
_MAX_DATASET_HEALTH_TABS = 200
_MAX_LINEAGE_COLORS = 200
_MAX_LINEAGE_CONFIGS = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class HealthIssuesIntegrationError(Exception):
    """Issues 集成错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DatasetHealthTabError(Exception):
    """数据集健康 Tab 错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LineageHealthColoringError(Exception):
    """沿袭健康着色错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════ #139 Health Issues Integration ════════════════════

class HealthIssue(BaseModel):
    issue_id: str = ""
    dataset_rid: str
    check_id: str
    check_name: str
    severity: str
    title: str
    description: str
    status: str = "open"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    resolved_at: datetime | None = None
    created_by_check: bool = False
    linked_check_runs: list[str] = []


_VALID_ISSUE_SEVERITIES = {"critical", "warning", "info"}
_VALID_ISSUE_STATUSES = {"open", "in_progress", "resolved", "closed"}


class HealthIssuesIntegrationEngine:
    """Issues 集成引擎（检查失败自动创建 Issue，检查通过自动解决）."""

    _instance: HealthIssuesIntegrationEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._issues: dict[str, HealthIssue] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> HealthIssuesIntegrationEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def create_issue(self, dataset_rid: str, check_id: str, check_name: str,
                     severity: str, title: str, description: str) -> HealthIssue:
        if not dataset_rid or not dataset_rid.strip():
            raise HealthIssuesIntegrationError("MISSING_DATASET", "dataset_rid is required")
        if not check_id or not check_id.strip():
            raise HealthIssuesIntegrationError("MISSING_CHECK", "check_id is required")
        if severity not in _VALID_ISSUE_SEVERITIES:
            raise HealthIssuesIntegrationError(
                "INVALID_SEVERITY", f"severity must be one of {_VALID_ISSUE_SEVERITIES}")

        now = _utcnow()
        iid = f"hsi-{uuid.uuid4().hex[:8]}"
        issue = HealthIssue(
            issue_id=iid,
            dataset_rid=dataset_rid,
            check_id=check_id,
            check_name=check_name,
            severity=severity,
            title=title,
            description=description,
            status="open",
            created_at=now,
            updated_at=now,
            resolved_at=None,
            created_by_check=False,
            linked_check_runs=[],
        )

        with self._lock:
            if len(self._issues) >= _MAX_HEALTH_ISSUES:
                oldest = min(self._issues.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._issues[oldest.issue_id]
            self._issues[iid] = issue
        return issue

    def get_issue(self, issue_id: str) -> HealthIssue:
        with self._lock:
            issue = self._issues.get(issue_id)
        if issue is None:
            raise HealthIssuesIntegrationError("NOT_FOUND", f"issue {issue_id} not found")
        return issue

    def list_issues(self, dataset_rid: str | None = None, status: str | None = None,
                    severity: str | None = None, limit: int = 50) -> list[HealthIssue]:
        if status and status not in _VALID_ISSUE_STATUSES:
            raise HealthIssuesIntegrationError(
                "INVALID_STATUS", f"status must be one of {_VALID_ISSUE_STATUSES}")
        if severity and severity not in _VALID_ISSUE_SEVERITIES:
            raise HealthIssuesIntegrationError(
                "INVALID_SEVERITY", f"severity must be one of {_VALID_ISSUE_SEVERITIES}")

        with self._lock:
            results = list(self._issues.values())
        if dataset_rid:
            results = [i for i in results if i.dataset_rid == dataset_rid]
        if status:
            results = [i for i in results if i.status == status]
        if severity:
            results = [i for i in results if i.severity == severity]
        results = sorted(results, key=lambda i: i.created_at or datetime.min, reverse=True)
        return results[:limit]

    def update_issue(self, issue_id: str, updates: dict) -> HealthIssue:
        if "status" in updates and updates["status"] not in _VALID_ISSUE_STATUSES:
            raise HealthIssuesIntegrationError(
                "INVALID_STATUS", f"status must be one of {_VALID_ISSUE_STATUSES}")
        if "severity" in updates and updates["severity"] not in _VALID_ISSUE_SEVERITIES:
            raise HealthIssuesIntegrationError(
                "INVALID_SEVERITY", f"severity must be one of {_VALID_ISSUE_SEVERITIES}")
        with self._lock:
            issue = self._issues.get(issue_id)
            if issue is None:
                raise HealthIssuesIntegrationError("NOT_FOUND", f"issue {issue_id} not found")
            data = issue.model_dump()
            data.update(updates)
            data["updated_at"] = _utcnow()
            updated = HealthIssue(**data)
            self._issues[issue_id] = updated
        return updated

    def resolve_issue(self, issue_id: str) -> HealthIssue:
        with self._lock:
            issue = self._issues.get(issue_id)
            if issue is None:
                raise HealthIssuesIntegrationError("NOT_FOUND", f"issue {issue_id} not found")
            now = _utcnow()
            updated = issue.model_copy(update={
                "status": "resolved",
                "resolved_at": now,
                "updated_at": now,
            })
            self._issues[issue_id] = updated
        return updated

    def close_issue(self, issue_id: str) -> HealthIssue:
        with self._lock:
            issue = self._issues.get(issue_id)
            if issue is None:
                raise HealthIssuesIntegrationError("NOT_FOUND", f"issue {issue_id} not found")
            now = _utcnow()
            updated = issue.model_copy(update={
                "status": "closed",
                "updated_at": now,
            })
            self._issues[issue_id] = updated
        return updated

    def auto_create_from_check(self, dataset_rid: str, check_id: str, check_name: str,
                               severity: str, failure_message: str) -> HealthIssue:
        if not dataset_rid or not dataset_rid.strip():
            raise HealthIssuesIntegrationError("MISSING_DATASET", "dataset_rid is required")
        if not check_id or not check_id.strip():
            raise HealthIssuesIntegrationError("MISSING_CHECK", "check_id is required")
        if severity not in _VALID_ISSUE_SEVERITIES:
            raise HealthIssuesIntegrationError(
                "INVALID_SEVERITY", f"severity must be one of {_VALID_ISSUE_SEVERITIES}")

        title = f"[{severity.upper()}] {check_name} failed on {dataset_rid}"
        description = failure_message or f"Check {check_name} failed for dataset {dataset_rid}."

        now = _utcnow()
        iid = f"hsi-{uuid.uuid4().hex[:8]}"
        issue = HealthIssue(
            issue_id=iid,
            dataset_rid=dataset_rid,
            check_id=check_id,
            check_name=check_name,
            severity=severity,
            title=title,
            description=description,
            status="open",
            created_at=now,
            updated_at=now,
            resolved_at=None,
            created_by_check=True,
            linked_check_runs=[],
        )

        with self._lock:
            if len(self._issues) >= _MAX_HEALTH_ISSUES:
                oldest = min(self._issues.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._issues[oldest.issue_id]
            self._issues[iid] = issue
        return issue

    def auto_resolve_from_check(self, dataset_rid: str, check_id: str) -> HealthIssue | None:
        if not dataset_rid or not dataset_rid.strip():
            raise HealthIssuesIntegrationError("MISSING_DATASET", "dataset_rid is required")
        if not check_id or not check_id.strip():
            raise HealthIssuesIntegrationError("MISSING_CHECK", "check_id is required")

        with self._lock:
            candidates = [i for i in self._issues.values()
                          if i.dataset_rid == dataset_rid
                          and i.check_id == check_id
                          and i.status in ("open", "in_progress")]
            if not candidates:
                return None
            target = sorted(candidates,
                            key=lambda i: i.created_at or datetime.min,
                            reverse=True)[0]
            now = _utcnow()
            updated = target.model_copy(update={
                "status": "resolved",
                "resolved_at": now,
                "updated_at": now,
            })
            self._issues[target.issue_id] = updated
        return updated

    def link_check_run(self, issue_id: str, check_run_id: str) -> HealthIssue:
        with self._lock:
            issue = self._issues.get(issue_id)
            if issue is None:
                raise HealthIssuesIntegrationError("NOT_FOUND", f"issue {issue_id} not found")
            new_runs = list(issue.linked_check_runs)
            if check_run_id not in new_runs:
                new_runs.append(check_run_id)
            updated = issue.model_copy(update={
                "linked_check_runs": new_runs,
                "updated_at": _utcnow(),
            })
            self._issues[issue_id] = updated
        return updated


_health_issues_integration_engine: HealthIssuesIntegrationEngine | None = None
_health_issues_integration_engine_lock = threading.Lock()


def get_health_issues_integration_engine() -> HealthIssuesIntegrationEngine:
    global _health_issues_integration_engine
    if _health_issues_integration_engine is None:
        with _health_issues_integration_engine_lock:
            if _health_issues_integration_engine is None:
                _health_issues_integration_engine = HealthIssuesIntegrationEngine.get_instance()
    return _health_issues_integration_engine


# ════════════════════ #140 Dataset Health Tab ════════════════════

class DatasetHealthTab(BaseModel):
    tab_id: str = ""
    dataset_rid: str
    overall_status: str = "unknown"
    checks_summary: dict = {"total": 0, "passed": 0, "failed": 0, "warning": 0}
    last_check_at: datetime | None = None
    recommendations: list[str] = []
    trends: list[dict] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_TAB_STATUSES = {"healthy", "warning", "critical", "unknown"}


class DatasetHealthTabEngine:
    """数据集健康 Tab 引擎（数据集预览中的健康 Tab）."""

    _instance: DatasetHealthTabEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._tabs: dict[str, DatasetHealthTab] = {}
        self._dataset_index: dict[str, str] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> DatasetHealthTabEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, dataset_rid: str) -> DatasetHealthTab:
        if not dataset_rid or not dataset_rid.strip():
            raise DatasetHealthTabError("MISSING_DATASET", "dataset_rid is required")
        with self._lock:
            existing_id = self._dataset_index.get(dataset_rid)
            if existing_id and existing_id in self._tabs:
                return self._tabs[existing_id]

            now = _utcnow()
            tid = f"dht-{uuid.uuid4().hex[:8]}"
            tab = DatasetHealthTab(
                tab_id=tid,
                dataset_rid=dataset_rid,
                overall_status="unknown",
                checks_summary={"total": 0, "passed": 0, "failed": 0, "warning": 0},
                last_check_at=None,
                recommendations=[],
                trends=[],
                created_at=now,
                updated_at=now,
            )
            if len(self._tabs) >= _MAX_DATASET_HEALTH_TABS:
                oldest = min(self._tabs.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._tabs[oldest.tab_id]
                self._dataset_index.pop(oldest.dataset_rid, None)
            self._tabs[tid] = tab
            self._dataset_index[dataset_rid] = tid
        return tab

    def get(self, tab_id: str) -> DatasetHealthTab:
        with self._lock:
            tab = self._tabs.get(tab_id)
        if tab is None:
            raise DatasetHealthTabError("NOT_FOUND", f"tab {tab_id} not found")
        return tab

    def get_by_dataset(self, dataset_rid: str) -> DatasetHealthTab:
        if not dataset_rid or not dataset_rid.strip():
            raise DatasetHealthTabError("MISSING_DATASET", "dataset_rid is required")
        with self._lock:
            tid = self._dataset_index.get(dataset_rid)
            tab = self._tabs.get(tid) if tid else None
        if tab is None:
            raise DatasetHealthTabError(
                "NOT_FOUND", f"health tab for dataset {dataset_rid} not found")
        return tab

    def list(self, dataset_rid: str | None = None) -> list[DatasetHealthTab]:
        with self._lock:
            results = list(self._tabs.values())
        if dataset_rid:
            results = [t for t in results if t.dataset_rid == dataset_rid]
        return sorted(results, key=lambda t: t.created_at or datetime.min, reverse=True)

    def update_status(self, dataset_rid: str, overall_status: str,
                      checks_summary: dict) -> DatasetHealthTab:
        if not dataset_rid or not dataset_rid.strip():
            raise DatasetHealthTabError("MISSING_DATASET", "dataset_rid is required")
        if overall_status not in _VALID_TAB_STATUSES:
            raise DatasetHealthTabError(
                "INVALID_STATUS", f"overall_status must be one of {_VALID_TAB_STATUSES}")
        with self._lock:
            tid = self._dataset_index.get(dataset_rid)
            tab = self._tabs.get(tid) if tid else None
            if tab is None:
                raise DatasetHealthTabError(
                    "NOT_FOUND", f"health tab for dataset {dataset_rid} not found")
            now = _utcnow()
            updated = tab.model_copy(update={
                "overall_status": overall_status,
                "checks_summary": checks_summary,
                "last_check_at": now,
                "updated_at": now,
            })
            self._tabs[tid] = updated
        return updated

    def add_recommendation(self, dataset_rid: str, recommendation: str) -> DatasetHealthTab:
        if not dataset_rid or not dataset_rid.strip():
            raise DatasetHealthTabError("MISSING_DATASET", "dataset_rid is required")
        with self._lock:
            tid = self._dataset_index.get(dataset_rid)
            tab = self._tabs.get(tid) if tid else None
            if tab is None:
                raise DatasetHealthTabError(
                    "NOT_FOUND", f"health tab for dataset {dataset_rid} not found")
            new_recs = list(tab.recommendations)
            if recommendation not in new_recs:
                new_recs.append(recommendation)
            updated = tab.model_copy(update={
                "recommendations": new_recs,
                "updated_at": _utcnow(),
            })
            self._tabs[tid] = updated
        return updated

    def add_trend(self, dataset_rid: str, date_str: str,
                  status: str, pass_rate: float) -> DatasetHealthTab:
        if not dataset_rid or not dataset_rid.strip():
            raise DatasetHealthTabError("MISSING_DATASET", "dataset_rid is required")
        if status not in _VALID_TAB_STATUSES:
            raise DatasetHealthTabError(
                "INVALID_STATUS", f"status must be one of {_VALID_TAB_STATUSES}")
        with self._lock:
            tid = self._dataset_index.get(dataset_rid)
            tab = self._tabs.get(tid) if tid else None
            if tab is None:
                raise DatasetHealthTabError(
                    "NOT_FOUND", f"health tab for dataset {dataset_rid} not found")
            new_trends = list(tab.trends)
            new_trends.append({"date": date_str, "status": status, "pass_rate": pass_rate})
            updated = tab.model_copy(update={
                "trends": new_trends,
                "updated_at": _utcnow(),
            })
            self._tabs[tid] = updated
        return updated

    def get_overall_health(self, dataset_rid: str) -> dict:
        if not dataset_rid or not dataset_rid.strip():
            raise DatasetHealthTabError("MISSING_DATASET", "dataset_rid is required")
        with self._lock:
            tid = self._dataset_index.get(dataset_rid)
            tab = self._tabs.get(tid) if tid else None
        if tab is None:
            raise DatasetHealthTabError(
                "NOT_FOUND", f"health tab for dataset {dataset_rid} not found")
        return {
            "overall_status": tab.overall_status,
            "checks_summary": tab.checks_summary,
        }

    def delete(self, tab_id: str) -> None:
        with self._lock:
            tab = self._tabs.get(tab_id)
            if tab is None:
                raise DatasetHealthTabError("NOT_FOUND", f"tab {tab_id} not found")
            self._dataset_index.pop(tab.dataset_rid, None)
            del self._tabs[tab_id]


_dataset_health_tab_engine: DatasetHealthTabEngine | None = None
_dataset_health_tab_engine_lock = threading.Lock()


def get_dataset_health_tab_engine() -> DatasetHealthTabEngine:
    global _dataset_health_tab_engine
    if _dataset_health_tab_engine is None:
        with _dataset_health_tab_engine_lock:
            if _dataset_health_tab_engine is None:
                _dataset_health_tab_engine = DatasetHealthTabEngine.get_instance()
    return _dataset_health_tab_engine


# ════════════════════ #141 Lineage Health Coloring ════════════════════

class LineageHealthColor(BaseModel):
    color_id: str = ""
    dataset_rid: str
    health_status: str
    color_code: str
    display_name: str
    tooltip: str
    updated_at: datetime | None = None


class LineageColoringConfig(BaseModel):
    config_id: str = ""
    name: str
    color_scheme: str = "traffic_light"
    status_color_mapping: dict = {}
    default_color: str = "gray"
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_HEALTH_STATUSES = {"healthy", "warning", "critical", "unknown"}
_VALID_COLOR_CODES = {"green", "yellow", "red", "gray"}
_VALID_COLOR_SCHEMES = {"traffic_light", "custom"}

_DEFAULT_TRAFFIC_LIGHT_MAPPING = {
    "healthy": "green",
    "warning": "yellow",
    "critical": "red",
    "unknown": "gray",
}


class LineageHealthColoringEngine:
    """沿袭健康着色引擎（数据沿袭中按健康状态着色）."""

    _instance: LineageHealthColoringEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._colors: dict[str, LineageHealthColor] = {}
        self._configs: dict[str, LineageColoringConfig] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> LineageHealthColoringEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_color(self, dataset_rid: str, health_status: str, color_code: str,
                       display_name: str, tooltip: str) -> LineageHealthColor:
        if not dataset_rid or not dataset_rid.strip():
            raise LineageHealthColoringError("MISSING_DATASET", "dataset_rid is required")
        if health_status not in _VALID_HEALTH_STATUSES:
            raise LineageHealthColoringError(
                "INVALID_HEALTH_STATUS",
                f"health_status must be one of {_VALID_HEALTH_STATUSES}")
        if color_code not in _VALID_COLOR_CODES:
            raise LineageHealthColoringError(
                "INVALID_COLOR_CODE",
                f"color_code must be one of {_VALID_COLOR_CODES}")

        cid = f"lhc-{uuid.uuid4().hex[:8]}"
        color = LineageHealthColor(
            color_id=cid,
            dataset_rid=dataset_rid,
            health_status=health_status,
            color_code=color_code,
            display_name=display_name,
            tooltip=tooltip,
            updated_at=_utcnow(),
        )
        with self._lock:
            if len(self._colors) >= _MAX_LINEAGE_COLORS:
                oldest = min(self._colors.values(),
                             key=lambda x: x.updated_at or datetime.min)
                del self._colors[oldest.dataset_rid]
            self._colors[dataset_rid] = color
        return color

    def get_color(self, dataset_rid: str) -> LineageHealthColor:
        if not dataset_rid or not dataset_rid.strip():
            raise LineageHealthColoringError("MISSING_DATASET", "dataset_rid is required")
        with self._lock:
            color = self._colors.get(dataset_rid)
        if color is None:
            raise LineageHealthColoringError(
                "NOT_FOUND", f"color for dataset {dataset_rid} not found")
        return color

    def list_colors(self, status_filter: str | None = None) -> list[LineageHealthColor]:
        if status_filter and status_filter not in _VALID_HEALTH_STATUSES:
            raise LineageHealthColoringError(
                "INVALID_HEALTH_STATUS",
                f"status_filter must be one of {_VALID_HEALTH_STATUSES}")
        with self._lock:
            results = list(self._colors.values())
        if status_filter:
            results = [c for c in results if c.health_status == status_filter]
        return sorted(results, key=lambda c: c.updated_at or datetime.min, reverse=True)

    def update_color(self, dataset_rid: str, updates: dict) -> LineageHealthColor:
        if not dataset_rid or not dataset_rid.strip():
            raise LineageHealthColoringError("MISSING_DATASET", "dataset_rid is required")
        if "health_status" in updates and updates["health_status"] not in _VALID_HEALTH_STATUSES:
            raise LineageHealthColoringError(
                "INVALID_HEALTH_STATUS",
                f"health_status must be one of {_VALID_HEALTH_STATUSES}")
        if "color_code" in updates and updates["color_code"] not in _VALID_COLOR_CODES:
            raise LineageHealthColoringError(
                "INVALID_COLOR_CODE",
                f"color_code must be one of {_VALID_COLOR_CODES}")
        with self._lock:
            color = self._colors.get(dataset_rid)
            if color is None:
                raise LineageHealthColoringError(
                    "NOT_FOUND", f"color for dataset {dataset_rid} not found")
            data = color.model_dump()
            data.update(updates)
            data["updated_at"] = _utcnow()
            updated = LineageHealthColor(**data)
            self._colors[dataset_rid] = updated
        return updated

    def delete_color(self, dataset_rid: str) -> None:
        if not dataset_rid or not dataset_rid.strip():
            raise LineageHealthColoringError("MISSING_DATASET", "dataset_rid is required")
        with self._lock:
            if dataset_rid not in self._colors:
                raise LineageHealthColoringError(
                    "NOT_FOUND", f"color for dataset {dataset_rid} not found")
            del self._colors[dataset_rid]

    def register_config(self, config: LineageColoringConfig) -> LineageColoringConfig:
        if not config.name or not config.name.strip():
            raise LineageHealthColoringError("MISSING_NAME", "config name is required")
        if config.color_scheme not in _VALID_COLOR_SCHEMES:
            raise LineageHealthColoringError(
                "INVALID_COLOR_SCHEME",
                f"color_scheme must be one of {_VALID_COLOR_SCHEMES}")

        now = _utcnow()
        cid = f"lcc-{uuid.uuid4().hex[:8]}"
        mapping = config.status_color_mapping
        if not mapping:
            mapping = dict(_DEFAULT_TRAFFIC_LIGHT_MAPPING)
        default_color = config.default_color if config.default_color in _VALID_COLOR_CODES else "gray"

        stored = config.model_copy(update={
            "config_id": cid,
            "status_color_mapping": mapping,
            "default_color": default_color,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._configs) >= _MAX_LINEAGE_CONFIGS:
                oldest = min(self._configs.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._configs[oldest.config_id]
            self._configs[cid] = stored
        return stored

    def get_config(self, config_id: str) -> LineageColoringConfig:
        with self._lock:
            config = self._configs.get(config_id)
        if config is None:
            raise LineageHealthColoringError(
                "CONFIG_NOT_FOUND", f"config {config_id} not found")
        return config

    def list_configs(self) -> list[LineageColoringConfig]:
        with self._lock:
            results = list(self._configs.values())
        return sorted(results, key=lambda c: c.created_at or datetime.min, reverse=True)

    def apply_coloring(self, dataset_rids: list[str],
                       config_id: str) -> list[LineageHealthColor]:
        if not config_id or not config_id.strip():
            raise LineageHealthColoringError("CONFIG_NOT_FOUND", "config_id is required")
        with self._lock:
            config = self._configs.get(config_id)
        if config is None:
            raise LineageHealthColoringError(
                "CONFIG_NOT_FOUND", f"config {config_id} not found")

        mapping = config.status_color_mapping or _DEFAULT_TRAFFIC_LIGHT_MAPPING
        default_color = config.default_color if config.default_color in _VALID_COLOR_CODES else "gray"

        results: list[LineageHealthColor] = []
        for rid in dataset_rids:
            if not rid or not rid.strip():
                raise LineageHealthColoringError("MISSING_DATASET", "dataset_rid is required")
            with self._lock:
                existing = self._colors.get(rid)
            health_status = existing.health_status if existing else "unknown"
            color_code = mapping.get(health_status, default_color)
            if color_code not in _VALID_COLOR_CODES:
                color_code = default_color
            display_name = existing.display_name if existing else health_status.capitalize()
            tooltip = f"Config '{config.name}': {health_status} -> {color_code}"

            color = self.register_color(
                dataset_rid=rid,
                health_status=health_status,
                color_code=color_code,
                display_name=display_name,
                tooltip=tooltip,
            )
            results.append(color)
        return results


_lineage_health_coloring_engine: LineageHealthColoringEngine | None = None
_lineage_health_coloring_engine_lock = threading.Lock()


def get_lineage_health_coloring_engine() -> LineageHealthColoringEngine:
    global _lineage_health_coloring_engine
    if _lineage_health_coloring_engine is None:
        with _lineage_health_coloring_engine_lock:
            if _lineage_health_coloring_engine is None:
                _lineage_health_coloring_engine = LineageHealthColoringEngine.get_instance()
    return _lineage_health_coloring_engine
