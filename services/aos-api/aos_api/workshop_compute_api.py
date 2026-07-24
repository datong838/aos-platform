"""W2-AQ · Workshop 变量 + Compute Module API + app.py 约定（#147 #151 #152）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime

from pydantic import BaseModel

_MAX_WORKSHOP_VARIABLES = 200
_MAX_VARIABLE_EVENTS = 200
_MAX_COMPUTE_JOBS = 200
_MAX_APP_ENTRIES = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


# ════════════════════ #147 Workshop Variable ════════════════════

class WorkshopVariableError(Exception):
    """Workshop 变量错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class WorkshopVariable(BaseModel):
    var_id: str = ""
    name: str
    var_type: str
    definition_type: str
    value: str = ""
    expression: str = ""
    depends_on: list[str] = []
    recompute_strategy: str = "automatic"
    lazy: bool = False
    module_id: str = ""
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class VariableEvent(BaseModel):
    event_id: str = ""
    var_id: str
    event_type: str
    payload: dict = {}
    created_at: datetime | None = None


_VALID_VAR_TYPES = {
    "object_set", "object_set_filter", "string", "numeric", "boolean",
    "date", "timestamp", "array", "struct", "geopoint", "geoshape",
    "time_series_set",
}
_VALID_DEFINITION_TYPES = {
    "static", "function", "object_set_aggregation", "object_property",
    "object_set_definition", "variable_transformation",
}
_VALID_RECOMPUTE_STRATEGIES = {"automatic", "triggered", "on_load"}


class WorkshopVariableEngine:
    """Workshop 变量引擎（#147）."""

    _instance: WorkshopVariableEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._variables: dict[str, WorkshopVariable] = {}
        self._events: list[VariableEvent] = []
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> WorkshopVariableEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, variable: WorkshopVariable) -> WorkshopVariable:
        if not variable.name or not variable.name.strip():
            raise WorkshopVariableError("MISSING_NAME", "name is required")
        if variable.var_type not in _VALID_VAR_TYPES:
            raise WorkshopVariableError(
                "INVALID_VAR_TYPE", f"var_type must be one of {_VALID_VAR_TYPES}")
        if variable.definition_type not in _VALID_DEFINITION_TYPES:
            raise WorkshopVariableError(
                "INVALID_DEFINITION_TYPE",
                f"definition_type must be one of {_VALID_DEFINITION_TYPES}")
        if variable.recompute_strategy not in _VALID_RECOMPUTE_STRATEGIES:
            raise WorkshopVariableError(
                "INVALID_RECOMPUTE_STRATEGY",
                f"recompute_strategy must be one of {_VALID_RECOMPUTE_STRATEGIES}")

        now = _utcnow()
        vid = f"var-{uuid.uuid4().hex[:8]}"
        stored = variable.model_copy(update={
            "var_id": vid,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if variable.definition_type == "variable_transformation":
                for dep_id in variable.depends_on:
                    if dep_id not in self._variables:
                        raise WorkshopVariableError(
                            "DEPENDENCY_NOT_FOUND",
                            f"dependency {dep_id} not found")
            if len(self._variables) >= _MAX_WORKSHOP_VARIABLES:
                oldest = min(self._variables.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._variables[oldest.var_id]
            self._variables[vid] = stored
        return stored

    def get(self, var_id: str) -> WorkshopVariable:
        with self._lock:
            variable = self._variables.get(var_id)
        if variable is None:
            raise WorkshopVariableError("NOT_FOUND", f"variable {var_id} not found")
        return variable

    def list(self, var_type: str | None = None,
             definition_type: str | None = None,
             module_id: str | None = None) -> list[WorkshopVariable]:
        with self._lock:
            results = list(self._variables.values())
        if var_type:
            results = [v for v in results if v.var_type == var_type]
        if definition_type:
            results = [v for v in results if v.definition_type == definition_type]
        if module_id:
            results = [v for v in results if v.module_id == module_id]
        return sorted(results, key=lambda v: v.created_at or datetime.min, reverse=True)

    def update(self, var_id: str, fields: dict) -> WorkshopVariable:
        with self._lock:
            variable = self._variables.get(var_id)
            if variable is None:
                raise WorkshopVariableError("NOT_FOUND", f"variable {var_id} not found")
            if "var_type" in fields and fields["var_type"] not in _VALID_VAR_TYPES:
                raise WorkshopVariableError(
                    "INVALID_VAR_TYPE", f"var_type must be one of {_VALID_VAR_TYPES}")
            if "definition_type" in fields and fields["definition_type"] not in _VALID_DEFINITION_TYPES:
                raise WorkshopVariableError(
                    "INVALID_DEFINITION_TYPE",
                    f"definition_type must be one of {_VALID_DEFINITION_TYPES}")
            if "recompute_strategy" in fields and fields["recompute_strategy"] not in _VALID_RECOMPUTE_STRATEGIES:
                raise WorkshopVariableError(
                    "INVALID_RECOMPUTE_STRATEGY",
                    f"recompute_strategy must be one of {_VALID_RECOMPUTE_STRATEGIES}")
            data = variable.model_dump()
            data.update(fields)
            data["updated_at"] = _utcnow()
            updated = WorkshopVariable(**data)
            self._variables[var_id] = updated
        return updated

    def delete(self, var_id: str) -> None:
        with self._lock:
            if var_id not in self._variables:
                raise WorkshopVariableError("NOT_FOUND", f"variable {var_id} not found")
            del self._variables[var_id]
            for other_id, other in self._variables.items():
                if var_id in other.depends_on:
                    self._variables[other_id] = other.model_copy(
                        update={"depends_on": [d for d in other.depends_on if d != var_id]})

    def evaluate(self, var_id: str) -> dict:
        with self._lock:
            variable = self._variables.get(var_id)
            if variable is None:
                raise WorkshopVariableError("NOT_FOUND", f"variable {var_id} not found")

            if variable.definition_type == "static":
                return {"value": variable.value}
            if variable.definition_type == "function":
                return {"value": f"func_result_{variable.var_id}"}
            if variable.definition_type == "variable_transformation":
                resolved: dict[str, str] = {}
                visited: set[str] = set()
                queue: list[str] = list(variable.depends_on)
                while queue:
                    dep_id = queue.pop(0)
                    if dep_id in visited:
                        raise WorkshopVariableError(
                            "CIRCULAR_DEPENDENCY",
                            f"circular dependency detected at {dep_id}")
                    visited.add(dep_id)
                    dep_var = self._variables.get(dep_id)
                    if dep_var is None:
                        continue
                    if dep_var.definition_type == "static":
                        resolved[dep_id] = dep_var.value
                    elif dep_var.definition_type == "function":
                        resolved[dep_id] = f"func_result_{dep_var.var_id}"
                    else:
                        resolved[dep_id] = dep_var.value
                    for sub_dep in dep_var.depends_on:
                        queue.append(sub_dep)
                resolved_value = f"transform_{variable.var_id}"
                return {"value": resolved_value, "resolved": resolved}
            return {"value": variable.value}

    def _resolve_deps_locked(self, var_id: str) -> list[str]:
        """Assumes lock held. Returns all upstream dependency var_ids."""
        variable = self._variables.get(var_id)
        if variable is None:
            return []
        visited: set[str] = set()
        result: list[str] = []
        queue: list[str] = list(variable.depends_on)
        while queue:
            dep_id = queue.pop(0)
            if dep_id in visited:
                continue
            visited.add(dep_id)
            result.append(dep_id)
            dep_var = self._variables.get(dep_id)
            if dep_var:
                for sub_dep in dep_var.depends_on:
                    queue.append(sub_dep)
        return result

    def resolve_dependencies(self, var_id: str) -> list[str]:
        with self._lock:
            variable = self._variables.get(var_id)
            if variable is None:
                raise WorkshopVariableError("NOT_FOUND", f"variable {var_id} not found")
            return self._resolve_deps_locked(var_id)

    def get_lineage(self, var_id: str) -> dict:
        with self._lock:
            variable = self._variables.get(var_id)
            if variable is None:
                raise WorkshopVariableError("NOT_FOUND", f"variable {var_id} not found")
            upstream = self._resolve_deps_locked(var_id)
            downstream = [v.var_id for v in self._variables.values()
                          if var_id in v.depends_on]
            return {"upstream": upstream, "downstream": downstream}

    def record_event(self, var_id: str, event_type: str,
                     payload: dict) -> VariableEvent:
        with self._lock:
            variable = self._variables.get(var_id)
            if variable is None:
                raise WorkshopVariableError("NOT_FOUND", f"variable {var_id} not found")
            now = _utcnow()
            event = VariableEvent(
                event_id=f"ve-{uuid.uuid4().hex[:8]}",
                var_id=var_id,
                event_type=event_type,
                payload=payload,
                created_at=now,
            )
            if len(self._events) >= _MAX_VARIABLE_EVENTS:
                oldest = min(self._events,
                             key=lambda x: x.created_at or datetime.min)
                self._events.remove(oldest)
            self._events.append(event)
        return event

    def list_events(self, var_id: str | None = None) -> list[VariableEvent]:
        with self._lock:
            results = list(self._events)
        if var_id:
            results = [e for e in results if e.var_id == var_id]
        return sorted(results, key=lambda e: e.created_at or datetime.min, reverse=True)


_workshop_variable_engine: WorkshopVariableEngine | None = None
_workshop_variable_engine_lock = threading.Lock()


def get_workshop_variable_engine() -> WorkshopVariableEngine:
    global _workshop_variable_engine
    if _workshop_variable_engine is None:
        with _workshop_variable_engine_lock:
            if _workshop_variable_engine is None:
                _workshop_variable_engine = WorkshopVariableEngine.get_instance()
    return _workshop_variable_engine


# ════════════════════ #151 Compute Job Polling ════════════════════

class ComputeJobError(Exception):
    """Compute Job 轮询错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ComputeJob(BaseModel):
    job_id: str = ""
    module_id: str
    function_name: str
    payload: dict = {}
    status: str = "queued"
    result: dict = {}
    error: str = ""
    polling_token: str = ""
    poll_count: int = 0
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_polled_at: datetime | None = None
    timeout_seconds: int = 30


_VALID_JOB_STATUSES = {"queued", "running", "succeeded", "failed", "timeout"}
_DEFAULT_TIMEOUT_SECONDS = 30


class ComputeJobPollingEngine:
    """Compute Job 轮询引擎（#151）."""

    _instance: ComputeJobPollingEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._jobs: dict[str, ComputeJob] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ComputeJobPollingEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def submit(self, module_id: str, function_name: str,
               payload: dict | None = None) -> ComputeJob:
        if not module_id or not module_id.strip():
            raise ComputeJobError("MISSING_MODULE", "module_id is required")
        if not function_name or not function_name.strip():
            raise ComputeJobError("MISSING_FUNCTION", "function_name is required")
        now = _utcnow()
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        polling_token = f"pt-{uuid.uuid4().hex[:8]}"
        stored = ComputeJob(
            job_id=job_id,
            module_id=module_id,
            function_name=function_name,
            payload=payload or {},
            status="queued",
            result={},
            error="",
            polling_token=polling_token,
            poll_count=0,
            created_at=now,
            started_at=None,
            finished_at=None,
            last_polled_at=None,
            timeout_seconds=_DEFAULT_TIMEOUT_SECONDS,
        )
        with self._lock:
            if len(self._jobs) >= _MAX_COMPUTE_JOBS:
                oldest = min(self._jobs.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._jobs[oldest.job_id]
            self._jobs[job_id] = stored
        return stored

    def get(self, job_id: str) -> ComputeJob:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise ComputeJobError("NOT_FOUND", f"job {job_id} not found")
        return job

    def list(self, module_id: str | None = None,
             status: str | None = None) -> list[ComputeJob]:
        with self._lock:
            results = list(self._jobs.values())
        if module_id:
            results = [j for j in results if j.module_id == module_id]
        if status:
            results = [j for j in results if j.status == status]
        return sorted(results, key=lambda j: j.created_at or datetime.min, reverse=True)

    def poll(self, job_id: str, polling_token: str) -> ComputeJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise ComputeJobError("NOT_FOUND", f"job {job_id} not found")
            if job.polling_token != polling_token:
                raise ComputeJobError("INVALID_TOKEN", "polling token mismatch")
            now = _utcnow()
            updates: dict = {
                "poll_count": job.poll_count + 1,
                "last_polled_at": now,
            }
            if job.status == "queued":
                updates["status"] = "running"
                updates["started_at"] = now
            elif job.status == "running":
                updates["status"] = "succeeded"
                updates["finished_at"] = now
                updates["result"] = {"ok": True, "output": f"result_{job_id}"}
            updated = job.model_copy(update=updates)
            self._jobs[job_id] = updated
        return updated

    def get_result(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise ComputeJobError("NOT_FOUND", f"job {job_id} not found")
        if job.status == "succeeded":
            return job.result
        raise ComputeJobError(
            "JOB_NOT_COMPLETED", f"job {job_id} not completed (status={job.status})")

    def cancel(self, job_id: str) -> ComputeJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise ComputeJobError("NOT_FOUND", f"job {job_id} not found")
            if job.status not in ("queued", "running"):
                raise ComputeJobError(
                    "ALREADY_TERMINAL",
                    f"job {job_id} already in terminal state {job.status}")
            now = _utcnow()
            updated = job.model_copy(update={
                "status": "failed",
                "error": "cancelled",
                "finished_at": now,
            })
            self._jobs[job_id] = updated
        return updated

    def check_timeouts(self) -> list[ComputeJob]:
        timed_out: list[ComputeJob] = []
        now = _utcnow()
        with self._lock:
            for job_id, job in self._jobs.items():
                if job.status == "running" and job.started_at is not None:
                    elapsed = (now - job.started_at).total_seconds()
                    if elapsed > job.timeout_seconds:
                        updated = job.model_copy(update={
                            "status": "timeout",
                            "finished_at": now,
                        })
                        self._jobs[job_id] = updated
                        timed_out.append(updated)
        return timed_out


_compute_job_polling_engine: ComputeJobPollingEngine | None = None
_compute_job_polling_engine_lock = threading.Lock()


def get_compute_job_polling_engine() -> ComputeJobPollingEngine:
    global _compute_job_polling_engine
    if _compute_job_polling_engine is None:
        with _compute_job_polling_engine_lock:
            if _compute_job_polling_engine is None:
                _compute_job_polling_engine = ComputeJobPollingEngine.get_instance()
    return _compute_job_polling_engine


# ════════════════════ #152 App Entry Convention ════════════════════

class AppEntryError(Exception):
    """App Entry 约定错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AppEntry(BaseModel):
    entry_id: str = ""
    module_id: str
    function_name: str
    endpoint_path: str = ""
    relative_imports: list[str] = []
    json_serializable: bool = True
    signature_params: list[str] = []
    return_type: str = ""
    status: str = "valid"
    validation_errors: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_RETURN_TYPES = {"dict", "list", "str", "int", "float", "bool", "None", ""}


class AppEntryConventionEngine:
    """App Entry 约定引擎（#152）."""

    _instance: AppEntryConventionEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._entries: dict[str, AppEntry] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> AppEntryConventionEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _validate(self, entry: AppEntry) -> tuple[list[str], str]:
        errors: list[str] = []
        for imp in entry.relative_imports:
            if not imp.startswith("."):
                errors.append(f"non-relative import: {imp}")
        if entry.return_type and entry.return_type not in _VALID_RETURN_TYPES:
            errors.append(f"non-json-serializable return type: {entry.return_type}")
        status = "valid" if not errors else "invalid"
        return errors, status

    def register(self, entry: AppEntry) -> AppEntry:
        if not entry.module_id or not entry.module_id.strip():
            raise AppEntryError("MISSING_MODULE", "module_id is required")
        if not entry.function_name or not entry.function_name.strip():
            raise AppEntryError("MISSING_FUNCTION", "function_name is required")

        endpoint_path = "/" + entry.function_name.replace("_", "/")
        errors, status = self._validate(entry)
        json_serializable = not any(
            "non-json-serializable" in e for e in errors)

        now = _utcnow()
        eid = f"entry-{uuid.uuid4().hex[:8]}"
        stored = entry.model_copy(update={
            "entry_id": eid,
            "endpoint_path": endpoint_path,
            "validation_errors": errors,
            "status": status,
            "json_serializable": json_serializable,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._entries) >= _MAX_APP_ENTRIES:
                oldest = min(self._entries.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._entries[oldest.entry_id]
            self._entries[eid] = stored
        return stored

    def get(self, entry_id: str) -> AppEntry:
        with self._lock:
            entry = self._entries.get(entry_id)
        if entry is None:
            raise AppEntryError("NOT_FOUND", f"entry {entry_id} not found")
        return entry

    def list(self, module_id: str | None = None,
             status: str | None = None) -> list[AppEntry]:
        with self._lock:
            results = list(self._entries.values())
        if module_id:
            results = [e for e in results if e.module_id == module_id]
        if status:
            results = [e for e in results if e.status == status]
        return sorted(results, key=lambda e: e.created_at or datetime.min, reverse=True)

    def validate(self, entry_id: str) -> AppEntry:
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is None:
                raise AppEntryError("NOT_FOUND", f"entry {entry_id} not found")
            errors, status = self._validate(entry)
            json_serializable = not any(
                "non-json-serializable" in e for e in errors)
            updated = entry.model_copy(update={
                "validation_errors": errors,
                "status": status,
                "json_serializable": json_serializable,
                "updated_at": _utcnow(),
            })
            self._entries[entry_id] = updated
        return updated

    def list_invalid(self) -> list[AppEntry]:
        with self._lock:
            results = [e for e in self._entries.values() if e.status == "invalid"]
        return sorted(results, key=lambda e: e.created_at or datetime.min, reverse=True)

    def update(self, entry_id: str, fields: dict) -> AppEntry:
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is None:
                raise AppEntryError("NOT_FOUND", f"entry {entry_id} not found")
            data = entry.model_dump()
            data.update(fields)
            temp = AppEntry(**data)
            errors, status = self._validate(temp)
            data["json_serializable"] = not any(
                "non-json-serializable" in e for e in errors)
            data["validation_errors"] = errors
            data["status"] = status
            data["updated_at"] = _utcnow()
            updated = AppEntry(**data)
            self._entries[entry_id] = updated
        return updated

    def delete(self, entry_id: str) -> None:
        with self._lock:
            if entry_id not in self._entries:
                raise AppEntryError("NOT_FOUND", f"entry {entry_id} not found")
            del self._entries[entry_id]

    def get_endpoint(self, entry_id: str) -> str:
        with self._lock:
            entry = self._entries.get(entry_id)
        if entry is None:
            raise AppEntryError("NOT_FOUND", f"entry {entry_id} not found")
        return entry.endpoint_path


_app_entry_convention_engine: AppEntryConventionEngine | None = None
_app_entry_convention_engine_lock = threading.Lock()


def get_app_entry_convention_engine() -> AppEntryConventionEngine:
    global _app_entry_convention_engine
    if _app_entry_convention_engine is None:
        with _app_entry_convention_engine_lock:
            if _app_entry_convention_engine is None:
                _app_entry_convention_engine = AppEntryConventionEngine.get_instance()
    return _app_entry_convention_engine
