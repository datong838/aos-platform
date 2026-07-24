"""W2-AP · Compute Module 路由（#148 #149 #150）."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.compute_module import (
    ComputeModule,
    ComputeResourceError,
    ComputeSchedulerError,
    Replica,
    ResourceQuota,
    ScalePolicy,
    ComputeScalerError,
    get_compute_resource_engine,
    get_compute_scaler_engine,
    get_compute_scheduler_engine,
)
from aos_api.errors import ApiError

router = APIRouter(prefix="/compute-module", tags=["Compute Module"])


def _map_scheduler_err(e: ComputeSchedulerError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少 name"),
        "MISSING_IMAGE": (400, "缺少 image"),
        "INVALID_TRANSITION": (400, "非法状态转换"),
        "NOT_RUNNING": (400, "模块未运行"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_scaler_err(e: ComputeScalerError) -> HTTPException:
    mapping = {
        "MISSING_MODULE": (400, "缺少 module_id"),
        "INVALID_MIN_REPLICAS": (400, "min_replicas 无效"),
        "INVALID_MAX_REPLICAS": (400, "max_replicas 无效"),
        "INVALID_TARGET_CONCURRENCY": (400, "target_concurrency 无效"),
        "INVALID_THRESHOLD": (400, "扩缩阈值无效"),
        "INVALID_COUNT": (400, "count 无效"),
        "INVALID_STATUS": (400, "状态无效"),
        "POLICY_INACTIVE": (400, "策略未激活"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_resource_err(e: ComputeResourceError) -> HTTPException:
    mapping = {
        "MISSING_MODULE": (400, "缺少 module_id"),
        "INVALID_CPU_REQUEST": (400, "cpu_request 无效"),
        "INVALID_CPU_LIMIT": (400, "cpu_limit 无效"),
        "INVALID_MEMORY_REQUEST": (400, "memory_request_mb 无效"),
        "INVALID_MEMORY_LIMIT": (400, "memory_limit_mb 无效"),
        "INVALID_GPU_COUNT": (400, "gpu_count 无效"),
        "INVALID_GPU_TYPE": (400, "gpu_type 无效"),
        "INVALID_STORAGE": (400, "ephemeral_storage_gb 无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


# ════════════════════ #148 Compute Scheduler ════════════════════

@router.post("/modules", response_model=ComputeModule)
def register_module(body: ComputeModule, _=require_principal):
    try:
        return get_compute_scheduler_engine().register(body)
    except ComputeSchedulerError as e:
        raise _map_scheduler_err(e) from e


@router.get("/modules/{module_id}", response_model=ComputeModule)
def get_module(module_id: str, _=require_principal):
    try:
        return get_compute_scheduler_engine().get(module_id)
    except ComputeSchedulerError as e:
        raise _map_scheduler_err(e) from e


@router.get("/modules", response_model=list[ComputeModule])
def list_modules(
    status: str | None = Query(None),
    _=require_principal,
):
    return get_compute_scheduler_engine().list(status=status)


@router.post("/modules/{module_id}/start", response_model=ComputeModule)
def start_module(module_id: str, _=require_principal):
    try:
        return get_compute_scheduler_engine().start(module_id)
    except ComputeSchedulerError as e:
        raise _map_scheduler_err(e) from e


@router.post("/modules/{module_id}/stop", response_model=ComputeModule)
def stop_module(module_id: str, _=require_principal):
    try:
        return get_compute_scheduler_engine().stop(module_id)
    except ComputeSchedulerError as e:
        raise _map_scheduler_err(e) from e


@router.post("/modules/{module_id}/restart", response_model=ComputeModule)
def restart_module(module_id: str, _=require_principal):
    try:
        return get_compute_scheduler_engine().restart(module_id)
    except ComputeSchedulerError as e:
        raise _map_scheduler_err(e) from e


@router.post("/modules/{module_id}/heartbeat", response_model=ComputeModule)
def heartbeat_module(module_id: str, _=require_principal):
    try:
        return get_compute_scheduler_engine().heartbeat(module_id)
    except ComputeSchedulerError as e:
        raise _map_scheduler_err(e) from e


@router.delete("/modules/{module_id}")
def remove_module(module_id: str, _=require_principal):
    try:
        get_compute_scheduler_engine().remove(module_id)
        return {"deleted": True}
    except ComputeSchedulerError as e:
        raise _map_scheduler_err(e) from e


# ════════════════════ #149 Compute Scaler ════════════════════

@router.post("/scale-policies", response_model=ScalePolicy)
def register_scale_policy(body: ScalePolicy, _=require_principal):
    try:
        return get_compute_scaler_engine().register_policy(body)
    except ComputeScalerError as e:
        raise _map_scaler_err(e) from e


@router.get("/scale-policies/{policy_id}", response_model=ScalePolicy)
def get_scale_policy(policy_id: str, _=require_principal):
    try:
        return get_compute_scaler_engine().get_policy(policy_id)
    except ComputeScalerError as e:
        raise _map_scaler_err(e) from e


@router.get("/scale-policies", response_model=list[ScalePolicy])
def list_scale_policies(
    module_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_compute_scaler_engine().list_policies(
        module_id=module_id, status=status)


@router.put("/scale-policies/{policy_id}", response_model=ScalePolicy)
def update_scale_policy(policy_id: str, updates: dict, _=require_principal):
    try:
        return get_compute_scaler_engine().update_policy(policy_id, updates)
    except ComputeScalerError as e:
        raise _map_scaler_err(e) from e


@router.delete("/scale-policies/{policy_id}")
def delete_scale_policy(policy_id: str, _=require_principal):
    try:
        get_compute_scaler_engine().delete_policy(policy_id)
        return {"deleted": True}
    except ComputeScalerError as e:
        raise _map_scaler_err(e) from e


class EvaluateBody(BaseModel):
    current_concurrency: int


@router.post("/scale-policies/{policy_id}/evaluate")
def evaluate_scale(policy_id: str, body: EvaluateBody, _=require_principal):
    try:
        return get_compute_scaler_engine().evaluate_scale(
            policy_id, body.current_concurrency)
    except ComputeScalerError as e:
        raise _map_scaler_err(e) from e


class ScaleBody(BaseModel):
    count: int = 1


@router.post("/scale-policies/{policy_id}/scale-up", response_model=list[Replica])
def scale_up(policy_id: str, body: ScaleBody, _=require_principal):
    try:
        return get_compute_scaler_engine().scale_up(policy_id, body.count)
    except ComputeScalerError as e:
        raise _map_scaler_err(e) from e


@router.post("/scale-policies/{policy_id}/scale-down", response_model=list[Replica])
def scale_down(policy_id: str, body: ScaleBody, _=require_principal):
    try:
        return get_compute_scaler_engine().scale_down(policy_id, body.count)
    except ComputeScalerError as e:
        raise _map_scaler_err(e) from e


@router.get("/replicas", response_model=list[Replica])
def list_replicas(
    module_id: str = Query(...),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_compute_scaler_engine().list_replicas(
        module_id=module_id, status=status)


@router.post("/replicas/{replica_id}/unhealthy", response_model=Replica)
def mark_replica_unhealthy(replica_id: str, _=require_principal):
    try:
        return get_compute_scaler_engine().mark_replica_unhealthy(replica_id)
    except ComputeScalerError as e:
        raise _map_scaler_err(e) from e


# ════════════════════ #150 Compute Resource ════════════════════
# 注意：字面量路由 /quotas/module/{module_id} 须注册在参数路由 /quotas/{quota_id}
# 之前，否则 GET /quotas/module/... 会被 {quota_id} 误匹配。

@router.post("/quotas", response_model=ResourceQuota)
def register_quota(body: ResourceQuota, _=require_principal):
    try:
        return get_compute_resource_engine().register(body)
    except ComputeResourceError as e:
        raise _map_resource_err(e) from e


@router.get("/quotas/module/{module_id}", response_model=ResourceQuota)
def get_quota_by_module(module_id: str, _=require_principal):
    try:
        return get_compute_resource_engine().get_by_module(module_id)
    except ComputeResourceError as e:
        raise _map_resource_err(e) from e


@router.get("/quotas/{quota_id}", response_model=ResourceQuota)
def get_quota(quota_id: str, _=require_principal):
    try:
        return get_compute_resource_engine().get(quota_id)
    except ComputeResourceError as e:
        raise _map_resource_err(e) from e


@router.get("/quotas", response_model=list[ResourceQuota])
def list_quotas(
    module_id: str | None = Query(None),
    _=require_principal,
):
    return get_compute_resource_engine().list(module_id=module_id)


@router.put("/quotas/{quota_id}", response_model=ResourceQuota)
def update_quota(quota_id: str, updates: dict, _=require_principal):
    try:
        return get_compute_resource_engine().update(quota_id, updates)
    except ComputeResourceError as e:
        raise _map_resource_err(e) from e


@router.delete("/quotas/{quota_id}")
def delete_quota(quota_id: str, _=require_principal):
    try:
        get_compute_resource_engine().delete(quota_id)
        return {"deleted": True}
    except ComputeResourceError as e:
        raise _map_resource_err(e) from e


class CompareBody(BaseModel):
    requested_cpu: float
    requested_memory_mb: int


@router.post("/quotas/module/{module_id}/compare")
def compare_quota(module_id: str, body: CompareBody, _=require_principal):
    try:
        return get_compute_resource_engine().compare_quota(
            module_id, body.requested_cpu, body.requested_memory_mb)
    except ComputeResourceError as e:
        raise _map_resource_err(e) from e
