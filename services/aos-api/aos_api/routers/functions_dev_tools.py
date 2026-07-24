"""W2-AO · Functions Dev Tools 路由（#143 #144 #146）."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.errors import ApiError
from aos_api.functions_dev_tools import (
    CallResult,
    DatasetPreviewTabs,
    DatasetPreviewTabsError,
    ExternalApiCall,
    ExternalApiCallError,
    FunctionDebugSession,
    FunctionTestCase,
    FunctionsTestDebugError,
    ProfileResult,
    get_dataset_preview_tabs_engine,
    get_external_api_call_engine,
    get_functions_test_debug_engine,
)

router = APIRouter(prefix="/functions-dev-tools", tags=["Functions Dev Tools"])


def _map_test_debug_err(e: FunctionsTestDebugError) -> HTTPException:
    mapping = {
        "MISSING_FUNCTION": (400, "缺少 function_id"),
        "MISSING_NAME": (400, "缺少 test_name"),
        "INVALID_LANGUAGE": (400, "语言无效"),
        "INVALID_STATE": (400, "状态无效"),
        "ALREADY_STARTED": (400, "调试会话已启动"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_external_call_err(e: ExternalApiCallError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少 name"),
        "MISSING_URL": (400, "缺少 endpoint_url"),
        "INVALID_LANGUAGE": (400, "语言无效"),
        "INVALID_METHOD": (400, "HTTP 方法无效"),
        "INVALID_AUTH_TYPE": (400, "认证类型无效"),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_preview_tabs_err(e: DatasetPreviewTabsError) -> HTTPException:
    mapping = {
        "MISSING_DATASET": (400, "缺少 dataset_rid"),
        "INVALID_TAB_NAME": (400, "Tab 名称无效"),
        "INVALID_HEALTH_STATUS": (400, "健康状态无效"),
        "INVALID_COMPARE_MODE": (400, "对比模式无效"),
        "INVALID_STREAM_TYPE": (400, "流类型无效"),
        "INVALID_STREAM_STATUS": (400, "流状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


# ════════════════════ #143 Functions Test Debug ════════════════════

class RegisterTestBody(BaseModel):
    function_id: str
    test_name: str
    language: str = "python"
    test_code: str
    assertions: list[str] = []


@router.post("/tests", response_model=FunctionTestCase)
def register_test(body: RegisterTestBody, _=require_principal):
    try:
        case = FunctionTestCase(
            function_id=body.function_id,
            test_name=body.test_name,
            language=body.language,
            test_code=body.test_code,
            assertions=body.assertions,
        )
        return get_functions_test_debug_engine().register_test(case)
    except FunctionsTestDebugError as e:
        raise _map_test_debug_err(e) from e


@router.get("/tests/{case_id}", response_model=FunctionTestCase)
def get_test(case_id: str, _=require_principal):
    try:
        return get_functions_test_debug_engine().get_test(case_id)
    except FunctionsTestDebugError as e:
        raise _map_test_debug_err(e) from e


@router.get("/tests", response_model=list[FunctionTestCase])
def list_tests(
    function_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_functions_test_debug_engine().list_tests(
        function_id=function_id, status=status,
    )


@router.post("/tests/{case_id}/run", response_model=FunctionTestCase)
def run_test(case_id: str, _=require_principal):
    try:
        return get_functions_test_debug_engine().run_test(case_id)
    except FunctionsTestDebugError as e:
        raise _map_test_debug_err(e) from e


class RegisterDebugBody(BaseModel):
    function_id: str
    inputs: dict = {}
    breakpoints: list[int] = []


@router.post("/debug-sessions", response_model=FunctionDebugSession)
def register_debug(body: RegisterDebugBody, _=require_principal):
    try:
        return get_functions_test_debug_engine().register_debug(
            function_id=body.function_id,
            inputs=body.inputs,
            breakpoints=body.breakpoints,
        )
    except FunctionsTestDebugError as e:
        raise _map_test_debug_err(e) from e


@router.get("/debug-sessions/{session_id}", response_model=FunctionDebugSession)
def get_debug_session(session_id: str, _=require_principal):
    try:
        return get_functions_test_debug_engine().get_debug_session(session_id)
    except FunctionsTestDebugError as e:
        raise _map_test_debug_err(e) from e


@router.post("/debug-sessions/{session_id}/start", response_model=FunctionDebugSession)
def start_debug(session_id: str, _=require_principal):
    try:
        return get_functions_test_debug_engine().start_debug(session_id)
    except FunctionsTestDebugError as e:
        raise _map_test_debug_err(e) from e


@router.post("/debug-sessions/{session_id}/step", response_model=FunctionDebugSession)
def step_debug(session_id: str, _=require_principal):
    try:
        return get_functions_test_debug_engine().step(session_id)
    except FunctionsTestDebugError as e:
        raise _map_test_debug_err(e) from e


class ProfileBody(BaseModel):
    function_id: str
    inputs: dict = {}


@router.post("/profiles", response_model=ProfileResult)
def create_profile(body: ProfileBody, _=require_principal):
    try:
        return get_functions_test_debug_engine().profile(
            function_id=body.function_id,
            inputs=body.inputs,
        )
    except FunctionsTestDebugError as e:
        raise _map_test_debug_err(e) from e


@router.get("/profiles", response_model=list[ProfileResult])
def list_profiles(
    function_id: str = Query(...),
    _=require_principal,
):
    return get_functions_test_debug_engine().list_profiles(function_id)


# ════════════════════ #144 External API Call ════════════════════

@router.post("/external-calls", response_model=ExternalApiCall)
def register_call(call: ExternalApiCall, _=require_principal):
    try:
        return get_external_api_call_engine().register(call)
    except ExternalApiCallError as e:
        raise _map_external_call_err(e) from e


@router.get("/external-calls/{call_id}", response_model=ExternalApiCall)
def get_call(call_id: str, _=require_principal):
    try:
        return get_external_api_call_engine().get(call_id)
    except ExternalApiCallError as e:
        raise _map_external_call_err(e) from e


@router.get("/external-calls", response_model=list[ExternalApiCall])
def list_calls(
    language: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_external_api_call_engine().list(language=language, status=status)


@router.put("/external-calls/{call_id}", response_model=ExternalApiCall)
def update_call(call_id: str, updates: dict, _=require_principal):
    try:
        return get_external_api_call_engine().update(call_id, updates)
    except ExternalApiCallError as e:
        raise _map_external_call_err(e) from e


@router.delete("/external-calls/{call_id}")
def delete_call(call_id: str, _=require_principal):
    try:
        get_external_api_call_engine().delete(call_id)
        return {"deleted": True}
    except ExternalApiCallError as e:
        raise _map_external_call_err(e) from e


class ExecuteBody(BaseModel):
    payload: dict = {}


@router.post("/external-calls/{call_id}/execute", response_model=CallResult)
def execute_call(call_id: str, body: ExecuteBody, _=require_principal):
    try:
        return get_external_api_call_engine().execute(call_id, body.payload)
    except ExternalApiCallError as e:
        raise _map_external_call_err(e) from e


@router.get("/external-calls/{call_id}/results", response_model=list[CallResult])
def list_call_results(call_id: str, _=require_principal):
    return get_external_api_call_engine().list_results(call_id)


@router.post("/external-calls/{call_id}/enable", response_model=ExternalApiCall)
def enable_call(call_id: str, _=require_principal):
    try:
        return get_external_api_call_engine().enable(call_id)
    except ExternalApiCallError as e:
        raise _map_external_call_err(e) from e


@router.post("/external-calls/{call_id}/disable", response_model=ExternalApiCall)
def disable_call(call_id: str, _=require_principal):
    try:
        return get_external_api_call_engine().disable(call_id)
    except ExternalApiCallError as e:
        raise _map_external_call_err(e) from e


# ════════════════════ #146 Dataset Preview Tabs ════════════════════

class RegisterTabsBody(BaseModel):
    dataset_rid: str


@router.post("/preview-tabs", response_model=DatasetPreviewTabs)
def register_tabs(body: RegisterTabsBody, _=require_principal):
    try:
        return get_dataset_preview_tabs_engine().register(body.dataset_rid)
    except DatasetPreviewTabsError as e:
        raise _map_preview_tabs_err(e) from e


@router.get("/preview-tabs/{tabs_id}", response_model=DatasetPreviewTabs)
def get_tabs(tabs_id: str, _=require_principal):
    try:
        return get_dataset_preview_tabs_engine().get(tabs_id)
    except DatasetPreviewTabsError as e:
        raise _map_preview_tabs_err(e) from e


@router.get("/preview-tabs/dataset/{dataset_rid}", response_model=DatasetPreviewTabs)
def get_tabs_by_dataset(dataset_rid: str, _=require_principal):
    try:
        return get_dataset_preview_tabs_engine().get_by_dataset(dataset_rid)
    except DatasetPreviewTabsError as e:
        raise _map_preview_tabs_err(e) from e


@router.get("/preview-tabs", response_model=list[DatasetPreviewTabs])
def list_tabs(
    dataset_rid: str | None = Query(None),
    _=require_principal,
):
    return get_dataset_preview_tabs_engine().list(dataset_rid=dataset_rid)


@router.post(
    "/preview-tabs/dataset/{dataset_rid}/enable/{tab_name}",
    response_model=DatasetPreviewTabs,
)
def enable_tab(dataset_rid: str, tab_name: str, _=require_principal):
    try:
        return get_dataset_preview_tabs_engine().enable_tab(dataset_rid, tab_name)
    except DatasetPreviewTabsError as e:
        raise _map_preview_tabs_err(e) from e


@router.post(
    "/preview-tabs/dataset/{dataset_rid}/disable/{tab_name}",
    response_model=DatasetPreviewTabs,
)
def disable_tab(dataset_rid: str, tab_name: str, _=require_principal):
    try:
        return get_dataset_preview_tabs_engine().disable_tab(dataset_rid, tab_name)
    except DatasetPreviewTabsError as e:
        raise _map_preview_tabs_err(e) from e


class UpdateHistoryBody(BaseModel):
    last_n_versions: int
    snapshot_diff: bool


@router.post(
    "/preview-tabs/dataset/{dataset_rid}/history",
    response_model=DatasetPreviewTabs,
)
def update_history_tab(
    dataset_rid: str, body: UpdateHistoryBody, _=require_principal,
):
    try:
        return get_dataset_preview_tabs_engine().update_history_tab(
            dataset_rid=dataset_rid,
            last_n_versions=body.last_n_versions,
            snapshot_diff=body.snapshot_diff,
        )
    except DatasetPreviewTabsError as e:
        raise _map_preview_tabs_err(e) from e


class UpdateHealthBody(BaseModel):
    overall_status: str
    checks_summary: dict


@router.post(
    "/preview-tabs/dataset/{dataset_rid}/health",
    response_model=DatasetPreviewTabs,
)
def update_health_tab(
    dataset_rid: str, body: UpdateHealthBody, _=require_principal,
):
    try:
        return get_dataset_preview_tabs_engine().update_health_tab(
            dataset_rid=dataset_rid,
            overall_status=body.overall_status,
            checks_summary=body.checks_summary,
        )
    except DatasetPreviewTabsError as e:
        raise _map_preview_tabs_err(e) from e


class UpdateComparisonBody(BaseModel):
    baseline_dataset_rid: str
    compare_mode: str


@router.post(
    "/preview-tabs/dataset/{dataset_rid}/comparison",
    response_model=DatasetPreviewTabs,
)
def update_comparison_tab(
    dataset_rid: str, body: UpdateComparisonBody, _=require_principal,
):
    try:
        return get_dataset_preview_tabs_engine().update_comparison_tab(
            dataset_rid=dataset_rid,
            baseline_dataset_rid=body.baseline_dataset_rid,
            compare_mode=body.compare_mode,
        )
    except DatasetPreviewTabsError as e:
        raise _map_preview_tabs_err(e) from e


class UpdateStreamViewBody(BaseModel):
    stream_type: str
    partition: int
    offset: int
    status: str


@router.post(
    "/preview-tabs/dataset/{dataset_rid}/stream-view",
    response_model=DatasetPreviewTabs,
)
def update_stream_view_tab(
    dataset_rid: str, body: UpdateStreamViewBody, _=require_principal,
):
    try:
        return get_dataset_preview_tabs_engine().update_stream_view_tab(
            dataset_rid=dataset_rid,
            stream_type=body.stream_type,
            partition=body.partition,
            offset=body.offset,
            status=body.status,
        )
    except DatasetPreviewTabsError as e:
        raise _map_preview_tabs_err(e) from e
