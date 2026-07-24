"""W2-AZ · Pipeline Builder Extra 路由（#18 #19 #20）."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from aos_api.auth import require_principal
from aos_api.errors import ApiError
from aos_api.pipeline_builder_extra import (
    DataExpectation,
    PipelineBranch,
    PipelineBranchError,
    PipelineConfig,
    PipelineDataExpectationError,
    PipelineManagementError,
    get_branch_engine,
    get_expectation_engine,
    get_management_engine,
)

router = APIRouter(prefix="/pipeline-builder-extra", tags=["Pipeline Builder Extra"])


# ════════════════════ Error Mapping ════════════════════

def _map_branch_err(err: PipelineBranchError) -> ApiError:
    mapping = {
        "MISSING_PIPELINE": (400, "缺少 pipeline_id"),
        "MISSING_NAME": (400, "缺少 name"),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "分支不存在"),
    }
    status, msg = mapping.get(err.code, (400, err.message))
    return ApiError(code=err.code, message=msg, status_code=status)


def _map_management_err(err: PipelineManagementError) -> ApiError:
    mapping = {
        "MISSING_PIPELINE": (400, "缺少 pipeline_id"),
        "NOT_FOUND": (404, "配置不存在"),
    }
    status, msg = mapping.get(err.code, (400, err.message))
    return ApiError(code=err.code, message=msg, status_code=status)


def _map_expectation_err(err: PipelineDataExpectationError) -> ApiError:
    mapping = {
        "MISSING_PIPELINE": (400, "缺少 pipeline_id"),
        "MISSING_NAME": (400, "缺少 name"),
        "INVALID_EXPECTATION_TYPE": (400, "期望类型无效"),
        "INVALID_SEVERITY": (400, "严重级别无效"),
        "NOT_FOUND": (404, "数据期望不存在"),
    }
    status, msg = mapping.get(err.code, (400, err.message))
    return ApiError(code=err.code, message=msg, status_code=status)


# ════════════════════ #18 Pipeline Branch Endpoints ════════════════════

class CreateBranchRequest(BaseModel):
    pipeline_id: str
    name: str
    base_branch_id: Optional[str] = None
    protection_enabled: bool = False


class MergeBranchRequest(BaseModel):
    target_branch_id: str


@router.post("/branches", response_model=PipelineBranch)
def create_branch(req: CreateBranchRequest, _=require_principal):
    try:
        return get_branch_engine().create_branch(
            pipeline_id=req.pipeline_id,
            name=req.name,
            base_branch_id=req.base_branch_id,
            protection_enabled=req.protection_enabled,
        )
    except PipelineBranchError as err:
        raise _map_branch_err(err) from err


@router.get("/branches", response_model=list[PipelineBranch])
def list_branches(
    pipeline_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    _=require_principal,
):
    return get_branch_engine().list_branches(pipeline_id=pipeline_id, status=status)


@router.get("/branches/{branch_id}", response_model=PipelineBranch)
def get_branch(branch_id: str, _=require_principal):
    try:
        return get_branch_engine().get_branch(branch_id)
    except PipelineBranchError as err:
        raise _map_branch_err(err) from err


@router.put("/branches/{branch_id}", response_model=PipelineBranch)
def update_branch(
    branch_id: str,
    name: Optional[str] = Query(None),
    protection_enabled: Optional[bool] = Query(None),
    _=require_principal,
):
    try:
        return get_branch_engine().update_branch(
            branch_id=branch_id,
            name=name,
            protection_enabled=protection_enabled,
        )
    except PipelineBranchError as err:
        raise _map_branch_err(err) from err


@router.delete("/branches/{branch_id}")
def delete_branch(branch_id: str, _=require_principal):
    deleted = get_branch_engine().delete_branch(branch_id)
    if not deleted:
        raise ApiError(code="NOT_FOUND", message="分支不存在", status_code=404)
    return {"deleted": branch_id}


@router.post("/branches/{branch_id}/approve", response_model=PipelineBranch)
def approve_branch(branch_id: str, _=require_principal):
    try:
        return get_branch_engine().approve_branch(branch_id)
    except PipelineBranchError as err:
        raise _map_branch_err(err) from err


@router.post("/branches/{branch_id}/merge", response_model=PipelineBranch)
def merge_branch(branch_id: str, req: MergeBranchRequest, _=require_principal):
    try:
        return get_branch_engine().merge_branch(
            branch_id=branch_id,
            target_branch_id=req.target_branch_id,
        )
    except PipelineBranchError as err:
        raise _map_branch_err(err) from err


@router.post("/branches/{branch_id}/revert", response_model=PipelineBranch)
def revert_branch(branch_id: str, _=require_principal):
    try:
        return get_branch_engine().revert_branch(branch_id)
    except PipelineBranchError as err:
        raise _map_branch_err(err) from err


# ════════════════════ #19 Pipeline Management Endpoints ════════════════════

class CreateConfigRequest(BaseModel):
    pipeline_id: str
    checkpoints: Optional[dict] = None
    color_groups: Optional[dict] = None
    custom_functions: Optional[dict] = None
    folders: Optional[dict] = None
    sampling_config: Optional[dict] = None
    task_groups: Optional[dict] = None
    parameters: Optional[dict] = None


@router.post("/configs", response_model=PipelineConfig)
def create_config(req: CreateConfigRequest, _=require_principal):
    try:
        return get_management_engine().create_config(
            pipeline_id=req.pipeline_id,
            checkpoints=req.checkpoints,
            color_groups=req.color_groups,
            custom_functions=req.custom_functions,
            folders=req.folders,
            sampling_config=req.sampling_config,
            task_groups=req.task_groups,
            parameters=req.parameters,
        )
    except PipelineManagementError as err:
        raise _map_management_err(err) from err


@router.get("/configs", response_model=list[PipelineConfig])
def list_configs(
    pipeline_id: Optional[str] = Query(None),
    _=require_principal,
):
    return get_management_engine().list_configs(pipeline_id=pipeline_id)


@router.get("/configs/by-pipeline/{pipeline_id}", response_model=PipelineConfig)
def get_config_by_pipeline(pipeline_id: str, _=require_principal):
    try:
        return get_management_engine().get_config_by_pipeline(pipeline_id)
    except PipelineManagementError as err:
        raise _map_management_err(err) from err


@router.get("/configs/{config_id}", response_model=PipelineConfig)
def get_config(config_id: str, _=require_principal):
    try:
        return get_management_engine().get_config(config_id)
    except PipelineManagementError as err:
        raise _map_management_err(err) from err


@router.put("/configs/{config_id}", response_model=PipelineConfig)
def update_config(config_id: str, updates: dict, _=require_principal):
    try:
        return get_management_engine().update_config(config_id, **updates)
    except PipelineManagementError as err:
        raise _map_management_err(err) from err


@router.delete("/configs/{config_id}")
def delete_config(config_id: str, _=require_principal):
    deleted = get_management_engine().delete_config(config_id)
    if not deleted:
        raise ApiError(code="NOT_FOUND", message="配置不存在", status_code=404)
    return {"deleted": config_id}


# ════════════════════ #20 Pipeline Data Expectation Endpoints ════════════════════

class CreateExpectationRequest(BaseModel):
    pipeline_id: str
    name: str
    expectation_type: str
    config: Optional[dict] = None
    severity: str = "warning"
    enabled: bool = True


class UpdateExpectationRequest(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    severity: Optional[str] = None
    enabled: Optional[bool] = None


@router.post("/expectations", response_model=DataExpectation)
def create_expectation(req: CreateExpectationRequest, _=require_principal):
    try:
        return get_expectation_engine().create_expectation(
            pipeline_id=req.pipeline_id,
            name=req.name,
            expectation_type=req.expectation_type,
            config=req.config,
            severity=req.severity,
            enabled=req.enabled,
        )
    except PipelineDataExpectationError as err:
        raise _map_expectation_err(err) from err


@router.get("/expectations", response_model=list[DataExpectation])
def list_expectations(
    pipeline_id: Optional[str] = Query(None),
    expectation_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    _=require_principal,
):
    return get_expectation_engine().list_expectations(
        pipeline_id=pipeline_id,
        expectation_type=expectation_type,
        severity=severity,
        enabled=enabled,
    )


@router.get("/expectations/{expectation_id}", response_model=DataExpectation)
def get_expectation(expectation_id: str, _=require_principal):
    try:
        return get_expectation_engine().get_expectation(expectation_id)
    except PipelineDataExpectationError as err:
        raise _map_expectation_err(err) from err


@router.put("/expectations/{expectation_id}", response_model=DataExpectation)
def update_expectation(
    expectation_id: str,
    name: Optional[str] = Query(None),
    config: Optional[dict] = None,
    severity: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    _=require_principal,
):
    try:
        return get_expectation_engine().update_expectation(
            expectation_id=expectation_id,
            name=name,
            config=config,
            severity=severity,
            enabled=enabled,
        )
    except PipelineDataExpectationError as err:
        raise _map_expectation_err(err) from err


@router.delete("/expectations/{expectation_id}")
def delete_expectation(expectation_id: str, _=require_principal):
    deleted = get_expectation_engine().delete_expectation(expectation_id)
    if not deleted:
        raise ApiError(code="NOT_FOUND", message="数据期望不存在", status_code=404)
    return {"deleted": expectation_id}


@router.post("/expectations/{expectation_id}/run", response_model=DataExpectation)
def run_expectation(expectation_id: str, _=require_principal):
    try:
        return get_expectation_engine().run_expectation(expectation_id)
    except PipelineDataExpectationError as err:
        raise _map_expectation_err(err) from err


@router.post("/expectations/run-all/{pipeline_id}", response_model=list[DataExpectation])
def run_all_expectations(pipeline_id: str, _=require_principal):
    return get_expectation_engine().run_all_expectations(pipeline_id)