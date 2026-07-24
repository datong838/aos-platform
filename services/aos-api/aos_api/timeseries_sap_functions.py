"""W2-AS · 时间序列 + SAP 集成 + pb-functions 函数库（#164 #165 #166）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime

from pydantic import BaseModel

_MAX_TS_OBJECTS = 200
_MAX_SENSORS = 200
_MAX_TS_POINTS = 200
_MAX_SAP_CONNECTIONS = 200
_MAX_SAP_IMPORT_JOBS = 200
_MAX_PB_FUNCTIONS = 200
_MAX_PB_CATEGORIES = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class TimeSeriesError(Exception):
    """时间序列引擎错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SapIntegrationError(Exception):
    """SAP 集成引擎错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PbFunctionsError(Exception):
    """pb-functions 引擎错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════ #164 TimeSeries ════════════════════

class TimeSeriesObject(BaseModel):
    ts_id: str = ""
    name: str
    object_type: str = "TSP"
    description: str = ""
    sync_index_status: str = "pending"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Sensor(BaseModel):
    sensor_id: str = ""
    name: str
    ts_object_id: str
    data_type: str = "numeric"
    unit: str = ""
    frequency_seconds: int = 60
    status: str = "active"
    created_at: datetime | None = None


class TimeSeriesPoint(BaseModel):
    point_id: str = ""
    sensor_id: str
    timestamp: datetime | None = None
    value: float = 0.0
    created_at: datetime | None = None


_VALID_TS_OBJECT_TYPES = {"TSP", "sensor"}
_VALID_SENSOR_DATA_TYPES = {"numeric", "boolean", "string"}
_VALID_SENSOR_STATUSES = {"active", "inactive"}


class TimeSeriesEngine:
    """时间序列引擎（TS Object / Sensor / 数据点）."""

    _instance: TimeSeriesEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._objects: dict[str, TimeSeriesObject] = {}
        self._sensors: dict[str, Sensor] = {}
        self._points: list[TimeSeriesPoint] = []
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> TimeSeriesEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── TS Object ──

    def register_object(self, obj: TimeSeriesObject) -> TimeSeriesObject:
        if not obj.name or not obj.name.strip():
            raise TimeSeriesError("MISSING_NAME", "name is required")
        if obj.object_type not in _VALID_TS_OBJECT_TYPES:
            raise TimeSeriesError(
                "INVALID_OBJECT_TYPE",
                f"object_type must be one of {_VALID_TS_OBJECT_TYPES}")

        now = _utcnow()
        ts_id = f"ts-{uuid.uuid4().hex[:8]}"
        stored = obj.model_copy(update={
            "ts_id": ts_id,
            "sync_index_status": "pending",
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._objects) >= _MAX_TS_OBJECTS:
                oldest = min(self._objects.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._objects[oldest.ts_id]
            self._objects[ts_id] = stored
        return stored

    def get_object(self, ts_id: str) -> TimeSeriesObject:
        with self._lock:
            obj = self._objects.get(ts_id)
        if obj is None:
            raise TimeSeriesError("NOT_FOUND", f"ts-object {ts_id} not found")
        return obj

    def list_objects(self, object_type: str | None = None) -> list[TimeSeriesObject]:
        with self._lock:
            results = list(self._objects.values())
        if object_type:
            results = [o for o in results if o.object_type == object_type]
        return sorted(results, key=lambda o: o.created_at or datetime.min, reverse=True)

    def update_object(self, ts_id: str, fields: dict) -> TimeSeriesObject:
        with self._lock:
            obj = self._objects.get(ts_id)
            if obj is None:
                raise TimeSeriesError("NOT_FOUND", f"ts-object {ts_id} not found")
            data = obj.model_dump()
            data.update(fields)
            data["updated_at"] = _utcnow()
            updated = TimeSeriesObject(**data)
            self._objects[ts_id] = updated
        return updated

    def delete_object(self, ts_id: str) -> None:
        with self._lock:
            if ts_id not in self._objects:
                raise TimeSeriesError("NOT_FOUND", f"ts-object {ts_id} not found")
            del self._objects[ts_id]

    def build_sync_index(self, ts_id: str) -> TimeSeriesObject:
        with self._lock:
            obj = self._objects.get(ts_id)
            if obj is None:
                raise TimeSeriesError("NOT_FOUND", f"ts-object {ts_id} not found")
            updated = obj.model_copy(update={
                "sync_index_status": "built",
                "updated_at": _utcnow(),
            })
            self._objects[ts_id] = updated
        return updated

    # ── Sensor ──

    def register_sensor(self, sensor: Sensor) -> Sensor:
        if not sensor.name or not sensor.name.strip():
            raise TimeSeriesError("MISSING_NAME", "name is required")
        if not sensor.ts_object_id or not sensor.ts_object_id.strip():
            raise TimeSeriesError("MISSING_TS_OBJECT", "ts_object_id is required")
        if sensor.data_type not in _VALID_SENSOR_DATA_TYPES:
            raise TimeSeriesError(
                "INVALID_DATA_TYPE",
                f"data_type must be one of {_VALID_SENSOR_DATA_TYPES}")
        if sensor.status not in _VALID_SENSOR_STATUSES:
            raise TimeSeriesError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_SENSOR_STATUSES}")

        now = _utcnow()
        sensor_id = f"sensor-{uuid.uuid4().hex[:8]}"
        stored = sensor.model_copy(update={
            "sensor_id": sensor_id,
            "created_at": now,
        })
        with self._lock:
            if len(self._sensors) >= _MAX_SENSORS:
                oldest = min(self._sensors.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._sensors[oldest.sensor_id]
            self._sensors[sensor_id] = stored
        return stored

    def get_sensor(self, sensor_id: str) -> Sensor:
        with self._lock:
            sensor = self._sensors.get(sensor_id)
        if sensor is None:
            raise TimeSeriesError("NOT_FOUND", f"sensor {sensor_id} not found")
        return sensor

    def list_sensors(self, ts_object_id: str | None = None,
                     status: str | None = None) -> list[Sensor]:
        with self._lock:
            results = list(self._sensors.values())
        if ts_object_id:
            results = [s for s in results if s.ts_object_id == ts_object_id]
        if status:
            results = [s for s in results if s.status == status]
        return sorted(results, key=lambda s: s.created_at or datetime.min, reverse=True)

    def update_sensor(self, sensor_id: str, fields: dict) -> Sensor:
        with self._lock:
            sensor = self._sensors.get(sensor_id)
            if sensor is None:
                raise TimeSeriesError("NOT_FOUND", f"sensor {sensor_id} not found")
            data = sensor.model_dump()
            data.update(fields)
            updated = Sensor(**data)
            self._sensors[sensor_id] = updated
        return updated

    def delete_sensor(self, sensor_id: str) -> None:
        with self._lock:
            if sensor_id not in self._sensors:
                raise TimeSeriesError("NOT_FOUND", f"sensor {sensor_id} not found")
            del self._sensors[sensor_id]

    # ── 数据点 ──

    def ingest_points(self, sensor_id: str,
                      points: list[float]) -> list[TimeSeriesPoint]:
        with self._lock:
            sensor = self._sensors.get(sensor_id)
        if sensor is None:
            raise TimeSeriesError("NOT_FOUND", f"sensor {sensor_id} not found")

        now = _utcnow()
        created: list[TimeSeriesPoint] = []
        with self._lock:
            for value in points:
                point_id = f"pt-{uuid.uuid4().hex[:8]}"
                point = TimeSeriesPoint(
                    point_id=point_id,
                    sensor_id=sensor_id,
                    timestamp=now,
                    value=value,
                    created_at=now,
                )
                if len(self._points) >= _MAX_TS_POINTS:
                    oldest = min(self._points,
                                 key=lambda x: x.created_at or datetime.min)
                    self._points.remove(oldest)
                self._points.append(point)
                created.append(point)
        return created

    def list_points(self, sensor_id: str, limit: int = 100) -> list[TimeSeriesPoint]:
        with self._lock:
            sensor = self._sensors.get(sensor_id)
        if sensor is None:
            raise TimeSeriesError("NOT_FOUND", f"sensor {sensor_id} not found")
        with self._lock:
            results = [p for p in self._points if p.sensor_id == sensor_id]
        results = sorted(results, key=lambda p: p.timestamp or datetime.min, reverse=True)
        return results[:limit]

    def get_latest_point(self, sensor_id: str) -> TimeSeriesPoint | None:
        with self._lock:
            sensor = self._sensors.get(sensor_id)
        if sensor is None:
            raise TimeSeriesError("NOT_FOUND", f"sensor {sensor_id} not found")
        with self._lock:
            results = [p for p in self._points if p.sensor_id == sensor_id]
        if not results:
            return None
        return max(results, key=lambda p: p.timestamp or datetime.min)


_time_series_engine: TimeSeriesEngine | None = None
_time_series_engine_lock = threading.Lock()


def get_time_series_engine() -> TimeSeriesEngine:
    global _time_series_engine
    if _time_series_engine is None:
        with _time_series_engine_lock:
            if _time_series_engine is None:
                _time_series_engine = TimeSeriesEngine.get_instance()
    return _time_series_engine


# ════════════════════ #165 SAP Integration ════════════════════

class SapConnection(BaseModel):
    conn_id: str = ""
    name: str
    system_type: str = "S4HANA"
    host: str
    port: int = 8000
    client: str = "100"
    auth_type: str = "basic"
    username: str = ""
    status: str = "disconnected"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SapImportJob(BaseModel):
    job_id: str = ""
    conn_id: str
    object_type: str = "table"
    source_object: str
    target_dataset: str = ""
    status: str = "pending"
    total_rows: int = 0
    imported_rows: int = 0
    error: str = ""
    created_at: datetime | None = None
    finished_at: datetime | None = None


_VALID_SAP_SYSTEM_TYPES = {"S4HANA", "ECC", "BW", "SLT"}
_VALID_SAP_AUTH_TYPES = {"basic", "certificate", "snc"}
_VALID_SAP_OBJECT_TYPES = {"table", "bapi", "cds", "info_provider", "bex_query", "extractor"}
_VALID_SAP_JOB_STATUSES = {"pending", "running", "completed", "failed"}


class SapIntegrationEngine:
    """SAP 集成引擎（连接 / 导入作业）."""

    _instance: SapIntegrationEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._connections: dict[str, SapConnection] = {}
        self._jobs: dict[str, SapImportJob] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> SapIntegrationEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── 连接 ──

    def register_connection(self, conn: SapConnection) -> SapConnection:
        if not conn.name or not conn.name.strip():
            raise SapIntegrationError("MISSING_NAME", "name is required")
        if not conn.host or not conn.host.strip():
            raise SapIntegrationError("MISSING_HOST", "host is required")
        if conn.system_type not in _VALID_SAP_SYSTEM_TYPES:
            raise SapIntegrationError(
                "INVALID_SYSTEM_TYPE",
                f"system_type must be one of {_VALID_SAP_SYSTEM_TYPES}")
        if conn.auth_type not in _VALID_SAP_AUTH_TYPES:
            raise SapIntegrationError(
                "INVALID_AUTH_TYPE",
                f"auth_type must be one of {_VALID_SAP_AUTH_TYPES}")

        now = _utcnow()
        conn_id = f"sap-{uuid.uuid4().hex[:8]}"
        stored = conn.model_copy(update={
            "conn_id": conn_id,
            "status": "disconnected",
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._connections) >= _MAX_SAP_CONNECTIONS:
                oldest = min(self._connections.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._connections[oldest.conn_id]
            self._connections[conn_id] = stored
        return stored

    def get_connection(self, conn_id: str) -> SapConnection:
        with self._lock:
            conn = self._connections.get(conn_id)
        if conn is None:
            raise SapIntegrationError("NOT_FOUND", f"sap-connection {conn_id} not found")
        return conn

    def list_connections(self, system_type: str | None = None,
                         status: str | None = None) -> list[SapConnection]:
        with self._lock:
            results = list(self._connections.values())
        if system_type:
            results = [c for c in results if c.system_type == system_type]
        if status:
            results = [c for c in results if c.status == status]
        return sorted(results, key=lambda c: c.created_at or datetime.min, reverse=True)

    def update_connection(self, conn_id: str, fields: dict) -> SapConnection:
        with self._lock:
            conn = self._connections.get(conn_id)
            if conn is None:
                raise SapIntegrationError("NOT_FOUND", f"sap-connection {conn_id} not found")
            data = conn.model_dump()
            data.update(fields)
            data["updated_at"] = _utcnow()
            updated = SapConnection(**data)
            self._connections[conn_id] = updated
        return updated

    def delete_connection(self, conn_id: str) -> None:
        with self._lock:
            if conn_id not in self._connections:
                raise SapIntegrationError("NOT_FOUND", f"sap-connection {conn_id} not found")
            del self._connections[conn_id]

    def test_connection(self, conn_id: str) -> SapConnection:
        with self._lock:
            conn = self._connections.get(conn_id)
            if conn is None:
                raise SapIntegrationError("NOT_FOUND", f"sap-connection {conn_id} not found")
            updated = conn.model_copy(update={
                "status": "connected",
                "updated_at": _utcnow(),
            })
            self._connections[conn_id] = updated
        return updated

    # ── 导入作业 ──

    def create_import_job(self, job: SapImportJob) -> SapImportJob:
        if not job.conn_id or not job.conn_id.strip():
            raise SapIntegrationError("MISSING_CONNECTION", "conn_id is required")
        if job.object_type not in _VALID_SAP_OBJECT_TYPES:
            raise SapIntegrationError(
                "INVALID_OBJECT_TYPE",
                f"object_type must be one of {_VALID_SAP_OBJECT_TYPES}")
        if not job.source_object or not job.source_object.strip():
            raise SapIntegrationError("MISSING_SOURCE_OBJECT", "source_object is required")

        now = _utcnow()
        job_id = f"sapjob-{uuid.uuid4().hex[:8]}"
        stored = job.model_copy(update={
            "job_id": job_id,
            "status": "pending",
            "created_at": now,
        })
        with self._lock:
            if len(self._jobs) >= _MAX_SAP_IMPORT_JOBS:
                oldest = min(self._jobs.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._jobs[oldest.job_id]
            self._jobs[job_id] = stored
        return stored

    def get_import_job(self, job_id: str) -> SapImportJob:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise SapIntegrationError("NOT_FOUND", f"sap-import-job {job_id} not found")
        return job

    def list_import_jobs(self, conn_id: str | None = None,
                         status: str | None = None) -> list[SapImportJob]:
        with self._lock:
            results = list(self._jobs.values())
        if conn_id:
            results = [j for j in results if j.conn_id == conn_id]
        if status:
            results = [j for j in results if j.status == status]
        return sorted(results, key=lambda j: j.created_at or datetime.min, reverse=True)

    def run_import_job(self, job_id: str) -> SapImportJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise SapIntegrationError("NOT_FOUND", f"sap-import-job {job_id} not found")
            now = _utcnow()
            # 模拟 running -> completed
            updated = job.model_copy(update={
                "status": "completed",
                "total_rows": 100,
                "imported_rows": 100,
                "finished_at": now,
            })
            self._jobs[job_id] = updated
        return updated

    def cancel_import_job(self, job_id: str) -> SapImportJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise SapIntegrationError("NOT_FOUND", f"sap-import-job {job_id} not found")
            if job.status not in ("pending", "running"):
                raise SapIntegrationError(
                    "INVALID_TRANSITION",
                    f"cannot cancel job in status {job.status}")
            now = _utcnow()
            updated = job.model_copy(update={
                "status": "failed",
                "error": "cancelled",
                "finished_at": now,
            })
            self._jobs[job_id] = updated
        return updated


_sap_integration_engine: SapIntegrationEngine | None = None
_sap_integration_engine_lock = threading.Lock()


def get_sap_integration_engine() -> SapIntegrationEngine:
    global _sap_integration_engine
    if _sap_integration_engine is None:
        with _sap_integration_engine_lock:
            if _sap_integration_engine is None:
                _sap_integration_engine = SapIntegrationEngine.get_instance()
    return _sap_integration_engine


# ════════════════════ #166 pb-functions ════════════════════

class PbFunction(BaseModel):
    func_id: str = ""
    name: str
    category: str = "expression"
    signature: str = ""
    description: str = ""
    return_type: str = "any"
    version: str = "1.0.0"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PbFunctionCategory(BaseModel):
    category_id: str = ""
    name: str
    description: str = ""
    function_count: int = 0
    created_at: datetime | None = None


_VALID_PB_CATEGORIES = {"expression", "transform", "ai"}


class PbFunctionsEngine:
    """pb-functions 函数库引擎（函数 / 分类）."""

    _instance: PbFunctionsEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._functions: dict[str, PbFunction] = {}
        self._categories: dict[str, PbFunctionCategory] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> PbFunctionsEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── 函数 ──

    def register_function(self, func: PbFunction) -> PbFunction:
        if not func.name or not func.name.strip():
            raise PbFunctionsError("MISSING_NAME", "name is required")
        if func.category not in _VALID_PB_CATEGORIES:
            raise PbFunctionsError(
                "INVALID_CATEGORY",
                f"category must be one of {_VALID_PB_CATEGORIES}")

        now = _utcnow()
        func_id = f"pbf-{uuid.uuid4().hex[:8]}"
        stored = func.model_copy(update={
            "func_id": func_id,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._functions) >= _MAX_PB_FUNCTIONS:
                oldest = min(self._functions.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._functions[oldest.func_id]
            self._functions[func_id] = stored
            # 更新对应 category 的 function_count
            for cat in self._categories.values():
                if cat.name == stored.category:
                    self._categories[cat.category_id] = cat.model_copy(
                        update={"function_count": cat.function_count + 1})
                    break
        return stored

    def get_function(self, func_id: str) -> PbFunction:
        with self._lock:
            func = self._functions.get(func_id)
        if func is None:
            raise PbFunctionsError("NOT_FOUND", f"pb-function {func_id} not found")
        return func

    def list_functions(self, category: str | None = None) -> list[PbFunction]:
        with self._lock:
            results = list(self._functions.values())
        if category:
            results = [f for f in results if f.category == category]
        return sorted(results, key=lambda f: f.created_at or datetime.min, reverse=True)

    def search_functions(self, keyword: str) -> list[PbFunction]:
        with self._lock:
            results = [f for f in self._functions.values()
                       if keyword in f.name or keyword in f.description]
        return sorted(results, key=lambda f: f.created_at or datetime.min, reverse=True)

    def update_function(self, func_id: str, fields: dict) -> PbFunction:
        with self._lock:
            func = self._functions.get(func_id)
            if func is None:
                raise PbFunctionsError("NOT_FOUND", f"pb-function {func_id} not found")
            data = func.model_dump()
            data.update(fields)
            data["updated_at"] = _utcnow()
            updated = PbFunction(**data)
            self._functions[func_id] = updated
        return updated

    def delete_function(self, func_id: str) -> None:
        with self._lock:
            func = self._functions.get(func_id)
            if func is None:
                raise PbFunctionsError("NOT_FOUND", f"pb-function {func_id} not found")
            # 更新对应 category 的 function_count
            for cat in self._categories.values():
                if cat.name == func.category:
                    self._categories[cat.category_id] = cat.model_copy(
                        update={"function_count": max(cat.function_count - 1, 0)})
                    break
            del self._functions[func_id]

    # ── 分类 ──

    def register_category(self, category: PbFunctionCategory) -> PbFunctionCategory:
        if not category.name or not category.name.strip():
            raise PbFunctionsError("MISSING_NAME", "name is required")

        now = _utcnow()
        category_id = f"pbcat-{uuid.uuid4().hex[:8]}"
        stored = category.model_copy(update={
            "category_id": category_id,
            "created_at": now,
        })
        with self._lock:
            if len(self._categories) >= _MAX_PB_CATEGORIES:
                oldest = min(self._categories.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._categories[oldest.category_id]
            self._categories[category_id] = stored
        return stored

    def get_category(self, category_id: str) -> PbFunctionCategory:
        with self._lock:
            category = self._categories.get(category_id)
        if category is None:
            raise PbFunctionsError("NOT_FOUND", f"pb-category {category_id} not found")
        return category

    def list_categories(self) -> list[PbFunctionCategory]:
        with self._lock:
            results = list(self._categories.values())
        return sorted(results, key=lambda c: c.created_at or datetime.min, reverse=True)

    def delete_category(self, category_id: str) -> None:
        with self._lock:
            if category_id not in self._categories:
                raise PbFunctionsError("NOT_FOUND", f"pb-category {category_id} not found")
            del self._categories[category_id]


_pb_functions_engine: PbFunctionsEngine | None = None
_pb_functions_engine_lock = threading.Lock()


def get_pb_functions_engine() -> PbFunctionsEngine:
    global _pb_functions_engine
    if _pb_functions_engine is None:
        with _pb_functions_engine_lock:
            if _pb_functions_engine is None:
                _pb_functions_engine = PbFunctionsEngine.get_instance()
    return _pb_functions_engine
