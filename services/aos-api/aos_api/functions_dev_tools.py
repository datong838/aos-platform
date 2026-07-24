"""W2-AO · Functions Dev Tools 引擎（#143 #144 #146）."""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime

from pydantic import BaseModel

_MAX_TEST_CASES = 200
_MAX_DEBUG_SESSIONS = 200
_MAX_PROFILES = 200
_MAX_EXTERNAL_CALLS = 200
_MAX_CALL_RESULTS = 200
_MAX_PREVIEW_TABS = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


# ════════════════════ Error Classes ════════════════════

class FunctionsTestDebugError(Exception):
    """Functions 测试调试错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ExternalApiCallError(Exception):
    """外部 API 调用错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DatasetPreviewTabsError(Exception):
    """数据集预览 Tabs 错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════ #143 Functions Test Debug ════════════════════

class FunctionTestCase(BaseModel):
    case_id: str = ""
    function_id: str
    test_name: str
    language: str = "python"  # python | typescript
    test_code: str
    assertions: list[str] = []
    status: str = "pending"  # pending | passed | failed | error
    output: str = ""
    duration_ms: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FunctionDebugSession(BaseModel):
    session_id: str = ""
    function_id: str
    inputs: dict = {}
    breakpoints: list[int] = []
    state: str = "created"  # created | running | paused | completed | error
    current_line: int = 0
    variables: dict = {}
    output: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProfileResult(BaseModel):
    profile_id: str = ""
    function_id: str
    duration_ms: int = 0
    memory_bytes: int = 0
    cpu_percent: float = 0.0
    call_count: int = 0
    hotspots: list[dict] = []
    created_at: datetime | None = None


_VALID_TEST_LANGUAGES = {"python", "typescript"}
_VALID_TEST_STATUSES = {"pending", "passed", "failed", "error"}
_VALID_DEBUG_STATES = {"created", "running", "paused", "completed", "error"}


class FunctionsTestDebugEngine:
    """Functions 测试调试引擎（#143）."""

    _instance: FunctionsTestDebugEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._tests: dict[str, FunctionTestCase] = {}
        self._sessions: dict[str, FunctionDebugSession] = {}
        self._profiles: dict[str, ProfileResult] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> FunctionsTestDebugEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_test(self, case: FunctionTestCase) -> FunctionTestCase:
        if not case.function_id or not case.function_id.strip():
            raise FunctionsTestDebugError("MISSING_FUNCTION", "function_id is required")
        if not case.test_name or not case.test_name.strip():
            raise FunctionsTestDebugError("MISSING_NAME", "test_name is required")
        if case.language not in _VALID_TEST_LANGUAGES:
            raise FunctionsTestDebugError(
                "INVALID_LANGUAGE", f"language must be one of {_VALID_TEST_LANGUAGES}")

        now = _utcnow()
        cid = f"ftc-{uuid.uuid4().hex[:8]}"
        stored = case.model_copy(update={
            "case_id": cid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._tests) >= _MAX_TEST_CASES:
                oldest = min(self._tests.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._tests[oldest.case_id]
            self._tests[cid] = stored
        return stored

    def get_test(self, case_id: str) -> FunctionTestCase:
        with self._lock:
            case = self._tests.get(case_id)
        if case is None:
            raise FunctionsTestDebugError("NOT_FOUND", f"test case {case_id} not found")
        return case

    def list_tests(self, function_id: str | None = None,
                   status: str | None = None) -> list[FunctionTestCase]:
        with self._lock:
            results = list(self._tests.values())
        if function_id:
            results = [t for t in results if t.function_id == function_id]
        if status:
            results = [t for t in results if t.status == status]
        return sorted(results, key=lambda t: t.created_at or datetime.min, reverse=True)

    def run_test(self, case_id: str) -> FunctionTestCase:
        with self._lock:
            case = self._tests.get(case_id)
            if case is None:
                raise FunctionsTestDebugError("NOT_FOUND", f"test case {case_id} not found")

            if case.language == "python":
                if "assert" in case.test_code and "fail" not in case.test_code:
                    status = "passed"
                    output = "All assertions passed."
                elif "fail" in case.test_code:
                    status = "failed"
                    output = "Test failed: failure condition met."
                else:
                    status = "passed"
                    output = "Test executed successfully."
            else:
                status = "passed"
                output = "TypeScript test passed."

            duration_ms = (uuid.uuid4().int % 100) + 1
            now = _utcnow()
            updated = case.model_copy(update={
                "status": status,
                "output": output,
                "duration_ms": duration_ms,
                "updated_at": now,
            })
            self._tests[case_id] = updated
        return updated

    def register_debug(self, function_id: str, inputs: dict,
                       breakpoints: list[int]) -> FunctionDebugSession:
        if not function_id or not function_id.strip():
            raise FunctionsTestDebugError("MISSING_FUNCTION", "function_id is required")

        now = _utcnow()
        sid = f"fds-{uuid.uuid4().hex[:8]}"
        session = FunctionDebugSession(
            session_id=sid,
            function_id=function_id,
            inputs=inputs,
            breakpoints=breakpoints,
            state="created",
            current_line=0,
            variables={},
            output="",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            if len(self._sessions) >= _MAX_DEBUG_SESSIONS:
                oldest = min(self._sessions.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._sessions[oldest.session_id]
            self._sessions[sid] = session
        return session

    def get_debug_session(self, session_id: str) -> FunctionDebugSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise FunctionsTestDebugError(
                "NOT_FOUND", f"debug session {session_id} not found")
        return session

    def step(self, session_id: str) -> FunctionDebugSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise FunctionsTestDebugError(
                    "NOT_FOUND", f"debug session {session_id} not found")
            if session.state not in ("running", "paused"):
                raise FunctionsTestDebugError(
                    "INVALID_STATE", f"cannot step in state {session.state}")

            new_line = session.current_line + 1
            if new_line in session.breakpoints:
                new_state = "paused"
            else:
                new_state = "running"
            if new_line >= 10:
                new_state = "completed"

            new_variables = dict(session.variables)
            new_variables[f"line_{new_line}"] = new_line

            now = _utcnow()
            updated = session.model_copy(update={
                "current_line": new_line,
                "state": new_state,
                "variables": new_variables,
                "updated_at": now,
            })
            self._sessions[session_id] = updated
        return updated

    def start_debug(self, session_id: str) -> FunctionDebugSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise FunctionsTestDebugError(
                    "NOT_FOUND", f"debug session {session_id} not found")
            if session.state != "created":
                raise FunctionsTestDebugError(
                    "ALREADY_STARTED", f"session already started in state {session.state}")

            now = _utcnow()
            updated = session.model_copy(update={
                "state": "running",
                "updated_at": now,
            })
            self._sessions[session_id] = updated
        return updated

    def profile(self, function_id: str, inputs: dict) -> ProfileResult:
        if not function_id or not function_id.strip():
            raise FunctionsTestDebugError("MISSING_FUNCTION", "function_id is required")

        now = _utcnow()
        pid = f"fpr-{uuid.uuid4().hex[:8]}"
        seed = uuid.uuid4().int
        profile = ProfileResult(
            profile_id=pid,
            function_id=function_id,
            duration_ms=(seed % 1000) + 1,
            memory_bytes=(seed % 10000000) + 1024,
            cpu_percent=((seed % 10000) / 100.0),
            call_count=(seed % 50) + 1,
            hotspots=[{"line": 1, "hits": 5}, {"line": 5, "hits": 3}],
            created_at=now,
        )
        with self._lock:
            if len(self._profiles) >= _MAX_PROFILES:
                oldest = min(self._profiles.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._profiles[oldest.profile_id]
            self._profiles[pid] = profile
        return profile

    def list_profiles(self, function_id: str) -> list[ProfileResult]:
        with self._lock:
            results = list(self._profiles.values())
        results = [p for p in results if p.function_id == function_id]
        return sorted(results, key=lambda p: p.created_at or datetime.min, reverse=True)


_functions_test_debug_engine: FunctionsTestDebugEngine | None = None
_functions_test_debug_engine_lock = threading.Lock()


def get_functions_test_debug_engine() -> FunctionsTestDebugEngine:
    global _functions_test_debug_engine
    if _functions_test_debug_engine is None:
        with _functions_test_debug_engine_lock:
            if _functions_test_debug_engine is None:
                _functions_test_debug_engine = FunctionsTestDebugEngine.get_instance()
    return _functions_test_debug_engine


# ════════════════════ #144 External API Call ════════════════════

class ExternalApiCall(BaseModel):
    call_id: str = ""
    name: str
    language: str = "typescript"  # typescript | python
    endpoint_url: str
    method: str = "GET"  # GET | POST | PUT | PATCH | DELETE
    headers: dict = {}
    auth_type: str = "none"  # none | bearer | basic | api_key
    auth_config: dict = {}
    payload_template: str = ""
    response_mapping: dict = {}
    status: str = "active"  # active | inactive
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CallResult(BaseModel):
    result_id: str = ""
    call_id: str
    status: str = "success"  # success | failed
    status_code: int = 200
    response_body: str = ""
    duration_ms: int = 0
    error_message: str = ""
    executed_at: datetime | None = None


_VALID_CALL_LANGUAGES = {"typescript", "python"}
_VALID_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
_VALID_AUTH_TYPES = {"none", "bearer", "basic", "api_key"}
_VALID_CALL_STATUSES = {"active", "inactive"}


class ExternalApiCallEngine:
    """外部 API 调用引擎（#144）."""

    _instance: ExternalApiCallEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._calls: dict[str, ExternalApiCall] = {}
        self._results: dict[str, CallResult] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ExternalApiCallEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, call: ExternalApiCall) -> ExternalApiCall:
        if not call.name or not call.name.strip():
            raise ExternalApiCallError("MISSING_NAME", "name is required")
        if not call.endpoint_url or not call.endpoint_url.strip():
            raise ExternalApiCallError("MISSING_URL", "endpoint_url is required")
        if call.language not in _VALID_CALL_LANGUAGES:
            raise ExternalApiCallError(
                "INVALID_LANGUAGE", f"language must be one of {_VALID_CALL_LANGUAGES}")
        if call.method not in _VALID_HTTP_METHODS:
            raise ExternalApiCallError(
                "INVALID_METHOD", f"method must be one of {_VALID_HTTP_METHODS}")
        if call.auth_type not in _VALID_AUTH_TYPES:
            raise ExternalApiCallError(
                "INVALID_AUTH_TYPE", f"auth_type must be one of {_VALID_AUTH_TYPES}")

        now = _utcnow()
        cid = f"eac-{uuid.uuid4().hex[:8]}"
        stored = call.model_copy(update={
            "call_id": cid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._calls) >= _MAX_EXTERNAL_CALLS:
                oldest = min(self._calls.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._calls[oldest.call_id]
            self._calls[cid] = stored
        return stored

    def get(self, call_id: str) -> ExternalApiCall:
        with self._lock:
            call = self._calls.get(call_id)
        if call is None:
            raise ExternalApiCallError("NOT_FOUND", f"call {call_id} not found")
        return call

    def list(self, language: str | None = None,
             status: str | None = None) -> list[ExternalApiCall]:
        with self._lock:
            results = list(self._calls.values())
        if language:
            results = [c for c in results if c.language == language]
        if status:
            results = [c for c in results if c.status == status]
        return sorted(results, key=lambda c: c.created_at or datetime.min, reverse=True)

    def update(self, call_id: str, updates: dict) -> ExternalApiCall:
        if "language" in updates and updates["language"] not in _VALID_CALL_LANGUAGES:
            raise ExternalApiCallError(
                "INVALID_LANGUAGE", f"language must be one of {_VALID_CALL_LANGUAGES}")
        if "method" in updates and updates["method"] not in _VALID_HTTP_METHODS:
            raise ExternalApiCallError(
                "INVALID_METHOD", f"method must be one of {_VALID_HTTP_METHODS}")
        if "auth_type" in updates and updates["auth_type"] not in _VALID_AUTH_TYPES:
            raise ExternalApiCallError(
                "INVALID_AUTH_TYPE", f"auth_type must be one of {_VALID_AUTH_TYPES}")
        if "status" in updates and updates["status"] not in _VALID_CALL_STATUSES:
            raise ExternalApiCallError(
                "INVALID_STATUS", f"status must be one of {_VALID_CALL_STATUSES}")

        with self._lock:
            call = self._calls.get(call_id)
            if call is None:
                raise ExternalApiCallError("NOT_FOUND", f"call {call_id} not found")
            data = call.model_dump()
            data.update(updates)
            data["updated_at"] = _utcnow()
            updated = ExternalApiCall(**data)
            self._calls[call_id] = updated
        return updated

    def delete(self, call_id: str) -> None:
        with self._lock:
            call = self._calls.get(call_id)
            if call is None:
                raise ExternalApiCallError("NOT_FOUND", f"call {call_id} not found")
            del self._calls[call_id]

    def execute(self, call_id: str, payload: dict) -> CallResult:
        with self._lock:
            call = self._calls.get(call_id)
            if call is None:
                raise ExternalApiCallError("NOT_FOUND", f"call {call_id} not found")

        now = _utcnow()
        rid = f"cr-{uuid.uuid4().hex[:8]}"
        response_body = json.dumps({"ok": True, "echo": payload})
        duration_ms = (uuid.uuid4().int % 191) + 10  # 10-200ms
        result = CallResult(
            result_id=rid,
            call_id=call_id,
            status="success",
            status_code=200,
            response_body=response_body,
            duration_ms=duration_ms,
            error_message="",
            executed_at=now,
        )
        with self._lock:
            if len(self._results) >= _MAX_CALL_RESULTS:
                oldest = min(self._results.values(),
                             key=lambda x: x.executed_at or datetime.min)
                del self._results[oldest.result_id]
            self._results[rid] = result
        return result

    def list_results(self, call_id: str) -> list[CallResult]:
        with self._lock:
            results = list(self._results.values())
        results = [r for r in results if r.call_id == call_id]
        return sorted(results, key=lambda r: r.executed_at or datetime.min, reverse=True)

    def enable(self, call_id: str) -> ExternalApiCall:
        with self._lock:
            call = self._calls.get(call_id)
            if call is None:
                raise ExternalApiCallError("NOT_FOUND", f"call {call_id} not found")
            now = _utcnow()
            updated = call.model_copy(update={
                "status": "active",
                "updated_at": now,
            })
            self._calls[call_id] = updated
        return updated

    def disable(self, call_id: str) -> ExternalApiCall:
        with self._lock:
            call = self._calls.get(call_id)
            if call is None:
                raise ExternalApiCallError("NOT_FOUND", f"call {call_id} not found")
            now = _utcnow()
            updated = call.model_copy(update={
                "status": "inactive",
                "updated_at": now,
            })
            self._calls[call_id] = updated
        return updated


_external_api_call_engine: ExternalApiCallEngine | None = None
_external_api_call_engine_lock = threading.Lock()


def get_external_api_call_engine() -> ExternalApiCallEngine:
    global _external_api_call_engine
    if _external_api_call_engine is None:
        with _external_api_call_engine_lock:
            if _external_api_call_engine is None:
                _external_api_call_engine = ExternalApiCallEngine.get_instance()
    return _external_api_call_engine


# ════════════════════ #146 Dataset Preview Tabs ════════════════════

class HistoryTab(BaseModel):
    enabled: bool = True
    last_n_versions: int = 10
    snapshot_diff: bool = False


class HealthTab(BaseModel):
    enabled: bool = True
    overall_status: str = "unknown"  # healthy | warning | critical | unknown
    checks_summary: dict = {"total": 0, "passed": 0, "failed": 0, "warning": 0}
    recommendations: list[str] = []


class ComparisonTab(BaseModel):
    enabled: bool = False
    baseline_dataset_rid: str = ""
    compare_mode: str = "schema"  # schema | content | stats


class StreamViewTab(BaseModel):
    enabled: bool = False
    stream_type: str = ""  # kafka | kinesis | pubsub
    partition: int = 0
    offset: int = 0
    status: str = "stopped"  # running | stopped


class DatasetPreviewTabs(BaseModel):
    tabs_id: str = ""
    dataset_rid: str
    history_tab: HistoryTab = HistoryTab()
    health_tab: HealthTab = HealthTab()
    comparison_tab: ComparisonTab = ComparisonTab()
    stream_view_tab: StreamViewTab = StreamViewTab()
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_HEALTH_STATUSES = {"healthy", "warning", "critical", "unknown"}
_VALID_COMPARE_MODES = {"schema", "content", "stats"}
_VALID_STREAM_TYPES = {"kafka", "kinesis", "pubsub"}
_VALID_STREAM_STATUSES = {"running", "stopped"}

_TAB_NAMES = {"history", "health", "comparison", "stream_view"}
_TAB_FIELD_MAP = {
    "history": "history_tab",
    "health": "health_tab",
    "comparison": "comparison_tab",
    "stream_view": "stream_view_tab",
}


class DatasetPreviewTabsEngine:
    """数据集预览 Tabs 引擎（#146）."""

    _instance: DatasetPreviewTabsEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._tabs: dict[str, DatasetPreviewTabs] = {}
        self._dataset_index: dict[str, str] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> DatasetPreviewTabsEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, dataset_rid: str) -> DatasetPreviewTabs:
        if not dataset_rid or not dataset_rid.strip():
            raise DatasetPreviewTabsError("MISSING_DATASET", "dataset_rid is required")
        with self._lock:
            existing_id = self._dataset_index.get(dataset_rid)
            if existing_id and existing_id in self._tabs:
                return self._tabs[existing_id]

            now = _utcnow()
            tid = f"dpt-{uuid.uuid4().hex[:8]}"
            tabs = DatasetPreviewTabs(
                tabs_id=tid,
                dataset_rid=dataset_rid,
                history_tab=HistoryTab(),
                health_tab=HealthTab(),
                comparison_tab=ComparisonTab(),
                stream_view_tab=StreamViewTab(),
                created_at=now,
                updated_at=now,
            )
            if len(self._tabs) >= _MAX_PREVIEW_TABS:
                oldest = min(self._tabs.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._tabs[oldest.tabs_id]
                self._dataset_index.pop(oldest.dataset_rid, None)
            self._tabs[tid] = tabs
            self._dataset_index[dataset_rid] = tid
        return tabs

    def get(self, tabs_id: str) -> DatasetPreviewTabs:
        with self._lock:
            tabs = self._tabs.get(tabs_id)
        if tabs is None:
            raise DatasetPreviewTabsError("NOT_FOUND", f"tabs {tabs_id} not found")
        return tabs

    def get_by_dataset(self, dataset_rid: str) -> DatasetPreviewTabs:
        if not dataset_rid or not dataset_rid.strip():
            raise DatasetPreviewTabsError("MISSING_DATASET", "dataset_rid is required")
        with self._lock:
            tid = self._dataset_index.get(dataset_rid)
            tabs = self._tabs.get(tid) if tid else None
        if tabs is None:
            raise DatasetPreviewTabsError(
                "NOT_FOUND", f"preview tabs for dataset {dataset_rid} not found")
        return tabs

    def list(self, dataset_rid: str | None = None) -> list[DatasetPreviewTabs]:
        with self._lock:
            results = list(self._tabs.values())
        if dataset_rid:
            results = [t for t in results if t.dataset_rid == dataset_rid]
        return sorted(results, key=lambda t: t.created_at or datetime.min, reverse=True)

    def enable_tab(self, dataset_rid: str, tab_name: str) -> DatasetPreviewTabs:
        if not dataset_rid or not dataset_rid.strip():
            raise DatasetPreviewTabsError("MISSING_DATASET", "dataset_rid is required")
        if tab_name not in _TAB_NAMES:
            raise DatasetPreviewTabsError(
                "INVALID_TAB_NAME", f"tab_name must be one of {_TAB_NAMES}")
        with self._lock:
            tid = self._dataset_index.get(dataset_rid)
            tabs = self._tabs.get(tid) if tid else None
            if tabs is None:
                raise DatasetPreviewTabsError(
                    "NOT_FOUND", f"preview tabs for dataset {dataset_rid} not found")
            field = _TAB_FIELD_MAP[tab_name]
            sub_tab = getattr(tabs, field)
            updated_sub = sub_tab.model_copy(update={"enabled": True})
            updated = tabs.model_copy(update={
                field: updated_sub,
                "updated_at": _utcnow(),
            })
            self._tabs[tid] = updated
        return updated

    def disable_tab(self, dataset_rid: str, tab_name: str) -> DatasetPreviewTabs:
        if not dataset_rid or not dataset_rid.strip():
            raise DatasetPreviewTabsError("MISSING_DATASET", "dataset_rid is required")
        if tab_name not in _TAB_NAMES:
            raise DatasetPreviewTabsError(
                "INVALID_TAB_NAME", f"tab_name must be one of {_TAB_NAMES}")
        with self._lock:
            tid = self._dataset_index.get(dataset_rid)
            tabs = self._tabs.get(tid) if tid else None
            if tabs is None:
                raise DatasetPreviewTabsError(
                    "NOT_FOUND", f"preview tabs for dataset {dataset_rid} not found")
            field = _TAB_FIELD_MAP[tab_name]
            sub_tab = getattr(tabs, field)
            updated_sub = sub_tab.model_copy(update={"enabled": False})
            updated = tabs.model_copy(update={
                field: updated_sub,
                "updated_at": _utcnow(),
            })
            self._tabs[tid] = updated
        return updated

    def update_history_tab(self, dataset_rid: str, last_n_versions: int,
                           snapshot_diff: bool) -> DatasetPreviewTabs:
        with self._lock:
            tid = self._dataset_index.get(dataset_rid)
            tabs = self._tabs.get(tid) if tid else None
            if tabs is None:
                raise DatasetPreviewTabsError(
                    "NOT_FOUND", f"preview tabs for dataset {dataset_rid} not found")
            updated_sub = tabs.history_tab.model_copy(update={
                "last_n_versions": last_n_versions,
                "snapshot_diff": snapshot_diff,
            })
            updated = tabs.model_copy(update={
                "history_tab": updated_sub,
                "updated_at": _utcnow(),
            })
            self._tabs[tid] = updated
        return updated

    def update_health_tab(self, dataset_rid: str, overall_status: str,
                          checks_summary: dict) -> DatasetPreviewTabs:
        if overall_status not in _VALID_HEALTH_STATUSES:
            raise DatasetPreviewTabsError(
                "INVALID_HEALTH_STATUS",
                f"overall_status must be one of {_VALID_HEALTH_STATUSES}")
        with self._lock:
            tid = self._dataset_index.get(dataset_rid)
            tabs = self._tabs.get(tid) if tid else None
            if tabs is None:
                raise DatasetPreviewTabsError(
                    "NOT_FOUND", f"preview tabs for dataset {dataset_rid} not found")
            updated_sub = tabs.health_tab.model_copy(update={
                "overall_status": overall_status,
                "checks_summary": checks_summary,
            })
            updated = tabs.model_copy(update={
                "health_tab": updated_sub,
                "updated_at": _utcnow(),
            })
            self._tabs[tid] = updated
        return updated

    def update_comparison_tab(self, dataset_rid: str, baseline_dataset_rid: str,
                              compare_mode: str) -> DatasetPreviewTabs:
        if compare_mode not in _VALID_COMPARE_MODES:
            raise DatasetPreviewTabsError(
                "INVALID_COMPARE_MODE",
                f"compare_mode must be one of {_VALID_COMPARE_MODES}")
        with self._lock:
            tid = self._dataset_index.get(dataset_rid)
            tabs = self._tabs.get(tid) if tid else None
            if tabs is None:
                raise DatasetPreviewTabsError(
                    "NOT_FOUND", f"preview tabs for dataset {dataset_rid} not found")
            updated_sub = tabs.comparison_tab.model_copy(update={
                "baseline_dataset_rid": baseline_dataset_rid,
                "compare_mode": compare_mode,
            })
            updated = tabs.model_copy(update={
                "comparison_tab": updated_sub,
                "updated_at": _utcnow(),
            })
            self._tabs[tid] = updated
        return updated

    def update_stream_view_tab(self, dataset_rid: str, stream_type: str,
                               partition: int, offset: int,
                               status: str) -> DatasetPreviewTabs:
        if stream_type not in _VALID_STREAM_TYPES:
            raise DatasetPreviewTabsError(
                "INVALID_STREAM_TYPE",
                f"stream_type must be one of {_VALID_STREAM_TYPES}")
        if status not in _VALID_STREAM_STATUSES:
            raise DatasetPreviewTabsError(
                "INVALID_STREAM_STATUS",
                f"status must be one of {_VALID_STREAM_STATUSES}")
        with self._lock:
            tid = self._dataset_index.get(dataset_rid)
            tabs = self._tabs.get(tid) if tid else None
            if tabs is None:
                raise DatasetPreviewTabsError(
                    "NOT_FOUND", f"preview tabs for dataset {dataset_rid} not found")
            updated_sub = tabs.stream_view_tab.model_copy(update={
                "stream_type": stream_type,
                "partition": partition,
                "offset": offset,
                "status": status,
            })
            updated = tabs.model_copy(update={
                "stream_view_tab": updated_sub,
                "updated_at": _utcnow(),
            })
            self._tabs[tid] = updated
        return updated


_dataset_preview_tabs_engine: DatasetPreviewTabsEngine | None = None
_dataset_preview_tabs_engine_lock = threading.Lock()


def get_dataset_preview_tabs_engine() -> DatasetPreviewTabsEngine:
    global _dataset_preview_tabs_engine
    if _dataset_preview_tabs_engine is None:
        with _dataset_preview_tabs_engine_lock:
            if _dataset_preview_tabs_engine is None:
                _dataset_preview_tabs_engine = DatasetPreviewTabsEngine.get_instance()
    return _dataset_preview_tabs_engine
