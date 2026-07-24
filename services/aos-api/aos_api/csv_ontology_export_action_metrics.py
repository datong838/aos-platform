"""W2-BI · CSV / Ontology 导出 / 用量 / Action 指标（W2+ 低优先级 #1 #2 #3 #4）.

- #1 CsvParsingEngine：Dataset Preview CSV 解析引擎（基于 stdlib csv，不依赖 pandas）
- #2 OntologyExchangeEngine：Ontology JSON 导出/导入
- #3 OntologyUsageEngine：Ontology 计算/占用量跟踪
- #4 ActionMetricsEngine：Action 操作指标
"""
from __future__ import annotations

import csv
import io
import threading
import time
import uuid
from typing import Any, Callable

from pydantic import BaseModel, Field


# ════════════════════ 公共辅助 ════════════════════

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


class ExchangeMetricsError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_DEFAULT_NA_TOKENS: set[str] = {"", "NaN", "nan", "NULL", "null", "NA", "None", "N/A"}
_INT_TYPES = {"int", "int64", "integer", "long"}
_FLOAT_TYPES = {"float", "float64", "double", "number"}


def _cast_value(value: Any, type_str: str) -> Any:
    if type_str in _INT_TYPES:
        return int(value)
    if type_str in _FLOAT_TYPES:
        return float(value)
    if type_str == "str":
        return str(value)
    if type_str == "bool":
        return str(value).strip().lower() in ("true", "1", "yes", "y")
    return value


# ════════════════════ #1 Dataset Preview CSV 解析引擎 ════════════════════

class CsvParseConfig(BaseModel):
    delimiter: str = ","
    quotechar: str = '"'
    escapechar: str = ""
    doublequote: bool = True
    skipinitialspace: bool = False
    lineterminator: str = "\r\n"
    encoding: str = "utf-8"
    skiprows: int = 0
    max_rows: int = 1000
    na_values: list[str] = Field(default_factory=list)
    keep_default_na: bool = True
    dtype: dict[str, str] = Field(default_factory=dict)


class CsvParseResult(BaseModel):
    id: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    headers: list[str] = Field(default_factory=list)
    row_count: int
    parser_type: str
    config_used: CsvParseConfig
    warnings: list[str] = Field(default_factory=list)
    created_at: float


_VALID_PARSER_TYPES = {"csv_reader", "dict_reader", "pandas", "text_dataframe"}


class CsvParsingEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._results: dict[str, CsvParseResult] = {}

    _MAX_RESULTS = 200

    def parse(
        self,
        content: str,
        config: CsvParseConfig | None = None,
        parser_type: str = "dict_reader",
    ) -> CsvParseResult:
        if parser_type not in _VALID_PARSER_TYPES:
            raise ExchangeMetricsError(
                "INVALID_PARSER_TYPE",
                f"parser_type must be one of {sorted(_VALID_PARSER_TYPES)}",
            )
        cfg = config if config is not None else CsvParseConfig()
        warnings: list[str] = []

        # 编码归一化：尝试按指定编码重新解码以校验/规整。
        text = content
        if cfg.encoding and cfg.encoding.lower() not in ("utf-8", "utf8"):
            try:
                text = content.encode("utf-8", errors="replace").decode(
                    cfg.encoding, errors="replace"
                )
            except LookupError:
                warnings.append(f"unsupported encoding '{cfg.encoding}', falling back to utf-8")
                text = content

        # 统一换行符，避免 \r\n 解析出尾部 \r。
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")

        reader_kwargs: dict[str, Any] = {
            "delimiter": cfg.delimiter,
            "quotechar": cfg.quotechar,
            "doublequote": cfg.doublequote,
            "skipinitialspace": cfg.skipinitialspace,
            "lineterminator": cfg.lineterminator,
        }
        if cfg.escapechar:
            reader_kwargs["escapechar"] = cfg.escapechar

        na_set: set[str] = set(cfg.na_values)
        if cfg.keep_default_na:
            na_set |= _DEFAULT_NA_TOKENS

        rows: list[dict[str, Any]] = []
        headers: list[str] = []

        if parser_type == "csv_reader":
            reader = csv.reader(io.StringIO(normalized), **reader_kwargs)
            all_rows = list(reader)
            if cfg.skiprows > 0:
                all_rows = all_rows[cfg.skiprows:]
            if all_rows:
                max_cols = max(len(r) for r in all_rows)
                headers = [str(i) for i in range(max_cols)]
            data_rows = all_rows
            if cfg.max_rows and cfg.max_rows > 0:
                data_rows = data_rows[: cfg.max_rows]
            for r in data_rows:
                row_dict: dict[str, Any] = {}
                for i, val in enumerate(r):
                    key = str(i)
                    row_dict[key] = None if val in na_set else val
                rows.append(row_dict)
        else:
            # dict_reader / pandas / text_dataframe 共用 DictReader 语义。
            reader = csv.DictReader(io.StringIO(normalized), **reader_kwargs)
            all_rows = list(reader)
            headers = list(reader.fieldnames or [])
            if cfg.skiprows > 0:
                all_rows = all_rows[cfg.skiprows:]
            data_rows = all_rows
            if cfg.max_rows and cfg.max_rows > 0:
                data_rows = data_rows[: cfg.max_rows]
            for r in data_rows:
                row_dict: dict[str, Any] = {}
                for key in headers:
                    val = r.get(key, None)
                    if val is None or val in na_set:
                        row_dict[key] = None
                    else:
                        row_dict[key] = val
                rows.append(row_dict)

        # dtype 类型转换。
        if cfg.dtype:
            for col, type_str in cfg.dtype.items():
                if col not in headers:
                    continue
                failed = False
                for row in rows:
                    if col in row and row[col] is not None:
                        try:
                            row[col] = _cast_value(row[col], type_str)
                        except (ValueError, TypeError):
                            failed = True
                if failed:
                    warnings.append(f"could not cast column '{col}' to {type_str}")

        result = CsvParseResult(
            id=_uid("csv"),
            rows=rows,
            headers=headers,
            row_count=len(rows),
            parser_type=parser_type,
            config_used=cfg,
            warnings=warnings,
            created_at=_now_ts(),
        )
        with self._lock:
            self._results[result.id] = result
            if len(self._results) > self._MAX_RESULTS:
                oldest = min(self._results.values(), key=lambda r: r.created_at)
                self._results.pop(oldest.id, None)
        return result

    def get_result(self, result_id: str) -> CsvParseResult:
        with self._lock:
            r = self._results.get(result_id)
            if not r:
                raise ExchangeMetricsError("NOT_FOUND", f"csv result {result_id} not found")
            return r.model_copy(deep=True)

    def list_results(self, parser_type: str | None = None) -> list[CsvParseResult]:
        with self._lock:
            result = list(self._results.values())
        if parser_type:
            result = [r for r in result if r.parser_type == parser_type]
        return [r.model_copy(deep=True) for r in result]

    def delete_result(self, result_id: str) -> bool:
        with self._lock:
            if result_id in self._results:
                del self._results[result_id]
                return True
            return False


# ════════════════════ #2 Ontology JSON 导出/导入 ════════════════════

class OntologyExportPackage(BaseModel):
    id: str
    source_ontology_id: str
    version: str = "1.0"
    object_types: list[dict[str, Any]] = Field(default_factory=list)
    link_types: list[dict[str, Any]] = Field(default_factory=list)
    properties: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float


class OntologyImportResult(BaseModel):
    id: str
    target_ontology_id: str
    imported_object_types: int
    imported_link_types: int
    imported_properties: int
    skipped: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: float


class OntologyExchangeEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._exports: dict[str, OntologyExportPackage] = {}
        self._imports: dict[str, OntologyImportResult] = {}

    _MAX_RECORDS = 200

    def export_ontology(
        self,
        source_ontology_id: str,
        object_types: list[dict] | None = None,
        link_types: list[dict] | None = None,
        properties: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> OntologyExportPackage:
        if not source_ontology_id:
            raise ExchangeMetricsError("MISSING_ONTOLOGY_ID", "source_ontology_id is required")
        package = OntologyExportPackage(
            id=_uid("oexp"),
            source_ontology_id=source_ontology_id,
            object_types=list(object_types) if object_types else [],
            link_types=list(link_types) if link_types else [],
            properties=list(properties) if properties else [],
            metadata=dict(metadata) if metadata else {},
            created_at=_now_ts(),
        )
        with self._lock:
            self._exports[package.id] = package
            if len(self._exports) > self._MAX_RECORDS:
                oldest = min(self._exports.values(), key=lambda p: p.created_at)
                self._exports.pop(oldest.id, None)
        return package

    def get_export(self, export_id: str) -> OntologyExportPackage:
        with self._lock:
            p = self._exports.get(export_id)
            if not p:
                raise ExchangeMetricsError("NOT_FOUND", f"export {export_id} not found")
            return p.model_copy(deep=True)

    def list_exports(self, source_ontology_id: str | None = None) -> list[OntologyExportPackage]:
        with self._lock:
            result = list(self._exports.values())
        if source_ontology_id:
            result = [p for p in result if p.source_ontology_id == source_ontology_id]
        return [p.model_copy(deep=True) for p in result]

    def delete_export(self, export_id: str) -> bool:
        with self._lock:
            if export_id in self._exports:
                del self._exports[export_id]
                return True
            return False

    def import_ontology(
        self,
        export_package: OntologyExportPackage,
        target_ontology_id: str,
        overwrite: bool = False,
    ) -> OntologyImportResult:
        if not target_ontology_id:
            raise ExchangeMetricsError("MISSING_ONTOLOGY_ID", "target_ontology_id is required")
        warnings: list[str] = []
        if not overwrite:
            warnings.append("overwrite=False; conflicting items would be skipped on a real target")
        result = OntologyImportResult(
            id=_uid("oimp"),
            target_ontology_id=target_ontology_id,
            imported_object_types=len(export_package.object_types),
            imported_link_types=len(export_package.link_types),
            imported_properties=len(export_package.properties),
            skipped=[],
            warnings=warnings,
            created_at=_now_ts(),
        )
        with self._lock:
            self._imports[result.id] = result
            if len(self._imports) > self._MAX_RECORDS:
                oldest = min(self._imports.values(), key=lambda r: r.created_at)
                self._imports.pop(oldest.id, None)
        return result

    def get_import(self, import_id: str) -> OntologyImportResult:
        with self._lock:
            r = self._imports.get(import_id)
            if not r:
                raise ExchangeMetricsError("NOT_FOUND", f"import {import_id} not found")
            return r.model_copy(deep=True)

    def list_imports(self, target_ontology_id: str | None = None) -> list[OntologyImportResult]:
        with self._lock:
            result = list(self._imports.values())
        if target_ontology_id:
            result = [r for r in result if r.target_ontology_id == target_ontology_id]
        return [r.model_copy(deep=True) for r in result]

    def delete_import(self, import_id: str) -> bool:
        with self._lock:
            if import_id in self._imports:
                del self._imports[import_id]
                return True
            return False


# ════════════════════ #3 Ontology 计算/占用量跟踪 ════════════════════

class UsageRecord(BaseModel):
    id: str
    ontology_id: str
    resource_type: str
    amount: float
    recorded_at: float
    description: str = ""


class UsageSummary(BaseModel):
    ontology_id: str
    total_compute_vcpu_seconds: float = 0
    total_compute_gpu_t4_seconds: float = 0
    total_compute_gpu_v100_seconds: float = 0
    total_compute_gpu_a10g_seconds: float = 0
    total_storage_v1_gb: float = 0
    total_storage_v2_gb: float = 0
    gb_month_v1: float = 0
    gb_month_v2: float = 0
    record_count: int = 0
    last_recorded_at: float = 0


_VALID_RESOURCE_TYPES = {
    "compute_seconds_vcpu",
    "compute_seconds_gpu_t4",
    "compute_seconds_gpu_v100",
    "compute_seconds_gpu_a10g",
    "storage_v1_gb",
    "storage_v2_gb",
}


class OntologyUsageEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, UsageRecord] = {}

    _MAX_RECORDS = 200

    def record_usage(
        self,
        ontology_id: str,
        resource_type: str,
        amount: float,
        description: str = "",
    ) -> UsageRecord:
        if not ontology_id:
            raise ExchangeMetricsError("MISSING_ONTOLOGY_ID", "ontology_id is required")
        if resource_type not in _VALID_RESOURCE_TYPES:
            raise ExchangeMetricsError(
                "INVALID_RESOURCE_TYPE",
                f"resource_type must be one of {sorted(_VALID_RESOURCE_TYPES)}",
            )
        record = UsageRecord(
            id=_uid("use"),
            ontology_id=ontology_id,
            resource_type=resource_type,
            amount=amount,
            recorded_at=_now_ts(),
            description=description,
        )
        with self._lock:
            self._records[record.id] = record
            if len(self._records) > self._MAX_RECORDS:
                oldest = min(self._records.values(), key=lambda r: r.recorded_at)
                self._records.pop(oldest.id, None)
        return record

    def get_usage(self, usage_id: str) -> UsageRecord:
        with self._lock:
            r = self._records.get(usage_id)
            if not r:
                raise ExchangeMetricsError("NOT_FOUND", f"usage {usage_id} not found")
            return r.model_copy(deep=True)

    def list_usage(
        self,
        ontology_id: str | None = None,
        resource_type: str | None = None,
    ) -> list[UsageRecord]:
        with self._lock:
            result = list(self._records.values())
        if ontology_id:
            result = [r for r in result if r.ontology_id == ontology_id]
        if resource_type:
            result = [r for r in result if r.resource_type == resource_type]
        return [r.model_copy(deep=True) for r in result]

    def get_summary(self, ontology_id: str) -> UsageSummary:
        summary = UsageSummary(ontology_id=ontology_id)
        with self._lock:
            records = [r for r in self._records.values() if r.ontology_id == ontology_id]
        if not records:
            return summary
        vcpu = t4 = v100 = a10g = 0.0
        v1 = v2 = 0.0
        last_at = 0.0
        for r in records:
            if r.resource_type == "compute_seconds_vcpu":
                vcpu += r.amount
            elif r.resource_type == "compute_seconds_gpu_t4":
                t4 += r.amount
            elif r.resource_type == "compute_seconds_gpu_v100":
                v100 += r.amount
            elif r.resource_type == "compute_seconds_gpu_a10g":
                a10g += r.amount
            elif r.resource_type == "storage_v1_gb":
                v1 += r.amount
            elif r.resource_type == "storage_v2_gb":
                v2 += r.amount
            if r.recorded_at > last_at:
                last_at = r.recorded_at
        days_in_month = 30
        summary.total_compute_vcpu_seconds = vcpu
        summary.total_compute_gpu_t4_seconds = t4
        summary.total_compute_gpu_v100_seconds = v100
        summary.total_compute_gpu_a10g_seconds = a10g
        summary.total_storage_v1_gb = v1
        summary.total_storage_v2_gb = v2
        summary.gb_month_v1 = v1 * (days_in_month / 30)
        summary.gb_month_v2 = v2 * (days_in_month / 30)
        summary.record_count = len(records)
        summary.last_recorded_at = last_at
        return summary

    def delete_usage(self, usage_id: str) -> bool:
        with self._lock:
            if usage_id in self._records:
                del self._records[usage_id]
                return True
            return False


# ════════════════════ #4 Action 操作指标 ════════════════════

class ActionMetric(BaseModel):
    id: str
    action_id: str
    status: str
    duration_ms: float = 0
    recorded_at: float
    error_code: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionMetricSummary(BaseModel):
    action_id: str
    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    failure_rate: float = 0.0
    avg_duration_ms: float = 0.0
    last_30_days: int = 0
    last_recorded_at: float = 0


_VALID_STATUSES = {"success", "failure", "timeout"}

_DAY_SECONDS = 86400


class ActionMetricsEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics: dict[str, ActionMetric] = {}

    _MAX_METRICS = 200

    def record_metric(
        self,
        action_id: str,
        status: str,
        duration_ms: float = 0,
        error_code: str = "",
        metadata: dict | None = None,
    ) -> ActionMetric:
        if not action_id:
            raise ExchangeMetricsError("MISSING_ACTION_ID", "action_id is required")
        if status not in _VALID_STATUSES:
            raise ExchangeMetricsError(
                "INVALID_STATUS",
                f"status must be one of {sorted(_VALID_STATUSES)}",
            )
        metric = ActionMetric(
            id=_uid("am"),
            action_id=action_id,
            status=status,
            duration_ms=duration_ms,
            recorded_at=_now_ts(),
            error_code=error_code,
            metadata=dict(metadata) if metadata else {},
        )
        with self._lock:
            self._metrics[metric.id] = metric
            if len(self._metrics) > self._MAX_METRICS:
                oldest = min(self._metrics.values(), key=lambda m: m.recorded_at)
                self._metrics.pop(oldest.id, None)
        return metric

    def get_metric(self, metric_id: str) -> ActionMetric:
        with self._lock:
            m = self._metrics.get(metric_id)
            if not m:
                raise ExchangeMetricsError("NOT_FOUND", f"metric {metric_id} not found")
            return m.model_copy(deep=True)

    def list_metrics(
        self,
        action_id: str | None = None,
        status: str | None = None,
        days: int = 30,
    ) -> list[ActionMetric]:
        now = _now_ts()
        cutoff = now - days * _DAY_SECONDS
        with self._lock:
            result = [m.model_copy(deep=True) for m in self._metrics.values()]
        if action_id:
            result = [m for m in result if m.action_id == action_id]
        if status:
            result = [m for m in result if m.status == status]
        result = [m for m in result if m.recorded_at >= cutoff]
        result.sort(key=lambda m: m.recorded_at, reverse=True)
        return result

    def get_summary(self, action_id: str, days: int = 30) -> ActionMetricSummary:
        now = _now_ts()
        cutoff = now - days * _DAY_SECONDS
        cutoff_30 = now - 30 * _DAY_SECONDS
        with self._lock:
            records = [m for m in self._metrics.values() if m.action_id == action_id]
        window = [m for m in records if m.recorded_at >= cutoff]
        summary = ActionMetricSummary(action_id=action_id)
        summary.last_30_days = sum(1 for m in records if m.recorded_at >= cutoff_30)
        if not window:
            return summary
        success = failure = timeout = 0
        total_duration = 0.0
        last_at = 0.0
        for m in window:
            if m.status == "success":
                success += 1
            elif m.status == "failure":
                failure += 1
            elif m.status == "timeout":
                timeout += 1
            total_duration += m.duration_ms
            if m.recorded_at > last_at:
                last_at = m.recorded_at
        total = len(window)
        summary.total_calls = total
        summary.success_count = success
        summary.failure_count = failure
        summary.timeout_count = timeout
        summary.failure_rate = round((failure + timeout) / total, 4) if total else 0.0
        summary.avg_duration_ms = round(total_duration / total, 2) if total else 0.0
        summary.last_recorded_at = last_at
        return summary

    def get_dashboard(self, days: int = 30) -> list[ActionMetricSummary]:
        with self._lock:
            action_ids = sorted({m.action_id for m in self._metrics.values()})
        return [self.get_summary(aid, days=days) for aid in action_ids]

    def delete_metric(self, metric_id: str) -> bool:
        with self._lock:
            if metric_id in self._metrics:
                del self._metrics[metric_id]
                return True
            return False


# ════════════════════ 单例 getter（双重检查锁） ════════════════════

_lock = threading.Lock()
_csv_engine: CsvParsingEngine | None = None
_exchange_engine: OntologyExchangeEngine | None = None
_usage_engine: OntologyUsageEngine | None = None
_action_metrics_engine: ActionMetricsEngine | None = None


def get_csv_parsing_engine() -> CsvParsingEngine:
    global _csv_engine
    if _csv_engine is None:
        with _lock:
            if _csv_engine is None:
                _csv_engine = CsvParsingEngine()
    return _csv_engine


def get_ontology_exchange_engine() -> OntologyExchangeEngine:
    global _exchange_engine
    if _exchange_engine is None:
        with _lock:
            if _exchange_engine is None:
                _exchange_engine = OntologyExchangeEngine()
    return _exchange_engine


def get_ontology_usage_engine() -> OntologyUsageEngine:
    global _usage_engine
    if _usage_engine is None:
        with _lock:
            if _usage_engine is None:
                _usage_engine = OntologyUsageEngine()
    return _usage_engine


def get_action_metrics_engine() -> ActionMetricsEngine:
    global _action_metrics_engine
    if _action_metrics_engine is None:
        with _lock:
            if _action_metrics_engine is None:
                _action_metrics_engine = ActionMetricsEngine()
    return _action_metrics_engine
