"""W2-AS · TimeSeries SAP Functions 路由（#164 #165 #166）."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.timeseries_sap_functions import (
    PbFunction,
    PbFunctionCategory,
    PbFunctionsError,
    SapConnection,
    SapImportJob,
    SapIntegrationError,
    Sensor,
    TimeSeriesError,
    TimeSeriesObject,
    TimeSeriesPoint,
    get_pb_functions_engine,
    get_sap_integration_engine,
    get_time_series_engine,
)

router = APIRouter(prefix="/timeseries-sap-functions", tags=["TimeSeries Sap Functions"])


def _map_ts_err(e: TimeSeriesError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少 name"),
        "MISSING_TS_OBJECT": (400, "缺少 ts_object_id"),
        "INVALID_OBJECT_TYPE": (400, "object_type 无效"),
        "INVALID_DATA_TYPE": (400, "data_type 无效"),
        "INVALID_STATUS": (400, "status 无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_sap_err(e: SapIntegrationError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少 name"),
        "MISSING_HOST": (400, "缺少 host"),
        "MISSING_CONNECTION": (400, "缺少 conn_id"),
        "MISSING_SOURCE_OBJECT": (400, "缺少 source_object"),
        "INVALID_SYSTEM_TYPE": (400, "system_type 无效"),
        "INVALID_AUTH_TYPE": (400, "auth_type 无效"),
        "INVALID_OBJECT_TYPE": (400, "object_type 无效"),
        "INVALID_TRANSITION": (400, "非法状态转换"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_pbf_err(e: PbFunctionsError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少 name"),
        "INVALID_CATEGORY": (400, "category 无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


# ════════════════════ #164 TimeSeries ════════════════════
# ── TS Object ──

@router.post("/ts-objects", response_model=TimeSeriesObject)
def register_ts_object(
    body: TimeSeriesObject,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_time_series_engine().register_object(body)
    except TimeSeriesError as e:
        raise _map_ts_err(e) from e


@router.get("/ts-objects", response_model=list[TimeSeriesObject])
def list_ts_objects(
    object_type: str | None = Query(None),
    principal: Principal = Depends(require_principal),
):
    return get_time_series_engine().list_objects(object_type=object_type)


@router.get("/ts-objects/{ts_id}", response_model=TimeSeriesObject)
def get_ts_object(
    ts_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_time_series_engine().get_object(ts_id)
    except TimeSeriesError as e:
        raise _map_ts_err(e) from e


@router.put("/ts-objects/{ts_id}", response_model=TimeSeriesObject)
def update_ts_object(
    ts_id: str,
    fields: dict,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_time_series_engine().update_object(ts_id, fields)
    except TimeSeriesError as e:
        raise _map_ts_err(e) from e


@router.delete("/ts-objects/{ts_id}")
def delete_ts_object(
    ts_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_time_series_engine().delete_object(ts_id)
        return {"deleted": True}
    except TimeSeriesError as e:
        raise _map_ts_err(e) from e


@router.post("/ts-objects/{ts_id}/build-index", response_model=TimeSeriesObject)
def build_sync_index(
    ts_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_time_series_engine().build_sync_index(ts_id)
    except TimeSeriesError as e:
        raise _map_ts_err(e) from e


# ── Sensor ──

@router.post("/sensors", response_model=Sensor)
def register_sensor(
    body: Sensor,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_time_series_engine().register_sensor(body)
    except TimeSeriesError as e:
        raise _map_ts_err(e) from e


@router.get("/sensors", response_model=list[Sensor])
def list_sensors(
    ts_object_id: str | None = Query(None),
    status: str | None = Query(None),
    principal: Principal = Depends(require_principal),
):
    return get_time_series_engine().list_sensors(
        ts_object_id=ts_object_id, status=status)


@router.get("/sensors/{sensor_id}", response_model=Sensor)
def get_sensor(
    sensor_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_time_series_engine().get_sensor(sensor_id)
    except TimeSeriesError as e:
        raise _map_ts_err(e) from e


@router.put("/sensors/{sensor_id}", response_model=Sensor)
def update_sensor(
    sensor_id: str,
    fields: dict,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_time_series_engine().update_sensor(sensor_id, fields)
    except TimeSeriesError as e:
        raise _map_ts_err(e) from e


@router.delete("/sensors/{sensor_id}")
def delete_sensor(
    sensor_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_time_series_engine().delete_sensor(sensor_id)
        return {"deleted": True}
    except TimeSeriesError as e:
        raise _map_ts_err(e) from e


# ── 数据点（注意：静态路径 /points/latest 须注册在 /points 之前）──

class IngestPointsBody(BaseModel):
    points: list[float]


@router.post("/sensors/{sensor_id}/ingest", response_model=list[TimeSeriesPoint])
def ingest_points(
    sensor_id: str,
    body: IngestPointsBody,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_time_series_engine().ingest_points(sensor_id, body.points)
    except TimeSeriesError as e:
        raise _map_ts_err(e) from e


@router.get("/sensors/{sensor_id}/points/latest", response_model=Optional[TimeSeriesPoint])
def get_latest_point(
    sensor_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_time_series_engine().get_latest_point(sensor_id)
    except TimeSeriesError as e:
        raise _map_ts_err(e) from e


@router.get("/sensors/{sensor_id}/points", response_model=list[TimeSeriesPoint])
def list_points(
    sensor_id: str,
    limit: int = Query(100),
    principal: Principal = Depends(require_principal),
):
    try:
        return get_time_series_engine().list_points(sensor_id, limit=limit)
    except TimeSeriesError as e:
        raise _map_ts_err(e) from e


# ════════════════════ #165 SAP Integration ════════════════════
# ── 连接 ──

@router.post("/sap-connections", response_model=SapConnection)
def register_sap_connection(
    body: SapConnection,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_sap_integration_engine().register_connection(body)
    except SapIntegrationError as e:
        raise _map_sap_err(e) from e


@router.get("/sap-connections", response_model=list[SapConnection])
def list_sap_connections(
    system_type: str | None = Query(None),
    status: str | None = Query(None),
    principal: Principal = Depends(require_principal),
):
    return get_sap_integration_engine().list_connections(
        system_type=system_type, status=status)


@router.get("/sap-connections/{conn_id}", response_model=SapConnection)
def get_sap_connection(
    conn_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_sap_integration_engine().get_connection(conn_id)
    except SapIntegrationError as e:
        raise _map_sap_err(e) from e


@router.put("/sap-connections/{conn_id}", response_model=SapConnection)
def update_sap_connection(
    conn_id: str,
    fields: dict,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_sap_integration_engine().update_connection(conn_id, fields)
    except SapIntegrationError as e:
        raise _map_sap_err(e) from e


@router.delete("/sap-connections/{conn_id}")
def delete_sap_connection(
    conn_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_sap_integration_engine().delete_connection(conn_id)
        return {"deleted": True}
    except SapIntegrationError as e:
        raise _map_sap_err(e) from e


@router.post("/sap-connections/{conn_id}/test", response_model=SapConnection)
def test_sap_connection(
    conn_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_sap_integration_engine().test_connection(conn_id)
    except SapIntegrationError as e:
        raise _map_sap_err(e) from e


# ── 导入作业 ──

@router.post("/sap-import-jobs", response_model=SapImportJob)
def create_sap_import_job(
    body: SapImportJob,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_sap_integration_engine().create_import_job(body)
    except SapIntegrationError as e:
        raise _map_sap_err(e) from e


@router.get("/sap-import-jobs", response_model=list[SapImportJob])
def list_sap_import_jobs(
    conn_id: str | None = Query(None),
    status: str | None = Query(None),
    principal: Principal = Depends(require_principal),
):
    return get_sap_integration_engine().list_import_jobs(
        conn_id=conn_id, status=status)


@router.post("/sap-import-jobs/{job_id}/run", response_model=SapImportJob)
def run_sap_import_job(
    job_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_sap_integration_engine().run_import_job(job_id)
    except SapIntegrationError as e:
        raise _map_sap_err(e) from e


@router.post("/sap-import-jobs/{job_id}/cancel", response_model=SapImportJob)
def cancel_sap_import_job(
    job_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_sap_integration_engine().cancel_import_job(job_id)
    except SapIntegrationError as e:
        raise _map_sap_err(e) from e


# ════════════════════ #166 pb-functions ════════════════════
# ── 函数（注意：静态路径 /pb-functions/search 须注册在 /pb-functions/{func_id} 之前）──

@router.post("/pb-functions", response_model=PbFunction)
def register_pb_function(
    body: PbFunction,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_pb_functions_engine().register_function(body)
    except PbFunctionsError as e:
        raise _map_pbf_err(e) from e


@router.get("/pb-functions", response_model=list[PbFunction])
def list_pb_functions(
    category: str | None = Query(None),
    principal: Principal = Depends(require_principal),
):
    return get_pb_functions_engine().list_functions(category=category)


@router.get("/pb-functions/search", response_model=list[PbFunction])
def search_pb_functions(
    keyword: str = Query(...),
    principal: Principal = Depends(require_principal),
):
    return get_pb_functions_engine().search_functions(keyword)


@router.get("/pb-functions/{func_id}", response_model=PbFunction)
def get_pb_function(
    func_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_pb_functions_engine().get_function(func_id)
    except PbFunctionsError as e:
        raise _map_pbf_err(e) from e


@router.put("/pb-functions/{func_id}", response_model=PbFunction)
def update_pb_function(
    func_id: str,
    fields: dict,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_pb_functions_engine().update_function(func_id, fields)
    except PbFunctionsError as e:
        raise _map_pbf_err(e) from e


@router.delete("/pb-functions/{func_id}")
def delete_pb_function(
    func_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_pb_functions_engine().delete_function(func_id)
        return {"deleted": True}
    except PbFunctionsError as e:
        raise _map_pbf_err(e) from e


# ── 分类 ──

@router.post("/pb-categories", response_model=PbFunctionCategory)
def register_pb_category(
    body: PbFunctionCategory,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_pb_functions_engine().register_category(body)
    except PbFunctionsError as e:
        raise _map_pbf_err(e) from e


@router.get("/pb-categories", response_model=list[PbFunctionCategory])
def list_pb_categories(
    principal: Principal = Depends(require_principal),
):
    return get_pb_functions_engine().list_categories()


@router.get("/pb-categories/{category_id}", response_model=PbFunctionCategory)
def get_pb_category(
    category_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_pb_functions_engine().get_category(category_id)
    except PbFunctionsError as e:
        raise _map_pbf_err(e) from e


@router.delete("/pb-categories/{category_id}")
def delete_pb_category(
    category_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_pb_functions_engine().delete_category(category_id)
        return {"deleted": True}
    except PbFunctionsError as e:
        raise _map_pbf_err(e) from e
