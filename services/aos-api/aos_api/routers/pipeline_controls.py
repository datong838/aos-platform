"""Principal-bound pipeline approvals; execution remains with the current Owner."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Security
from fastapi.security import HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool

from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, RuntimeRevisionConflict
from aos_api.pipeline_runtime_control_contracts import (
    PipelineExactRef, PipelineRuntimeControlDraft, PipelineSourceSelectionDraft,
)
from aos_api.routers.asset_control_headers import require_idempotency_key
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix='/v1/pipelines', tags=['pipeline-control'],
                   dependencies=[Security(HTTPBearer(auto_error=False))])
PrincipalDependency = Annotated[Principal, Depends(require_principal)]


class SelectionApprovalRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', hide_input_in_errors=True)
    draft: PipelineSourceSelectionDraft
    previous_ref: PipelineExactRef | None = Field(default=None, alias='previousRef')

    @model_validator(mode='after')
    def exact_predecessor(self):
        if self.previous_ref is not None:
            ref = self.previous_ref
            kind, prefix = ('PipelineRuntimeControlRevision', 'pipeline-control-') if isinstance(self, ControlApprovalRequest) else ('SourceSelectionRevision', 'source-selection-')
            identity = ref.resource_id.removeprefix(prefix)
            if ref.resource_type != kind or type(ref.revision) is not int or ref.resource_id != prefix + str(UUID(identity)):
                raise ValueError('exact approval predecessor required')
        return self


class ControlApprovalRequest(SelectionApprovalRequest):
    draft: PipelineRuntimeControlDraft


class ScheduleBindingRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', hide_input_in_errors=True)
    schedule_id: str = Field(alias='scheduleId',min_length=1,max_length=200)
    control_ref: PipelineExactRef = Field(alias='controlRef')
    previous_ref: PipelineExactRef | None = Field(default=None,alias='previousRef')

    @model_validator(mode='after')
    def exact_binding(self):
        from aos_api.pipeline_runtime_control_owner import _ref_identity
        from aos_api.pipeline_source_claim_owner import _text
        _text(self.schedule_id,200)
        _ref_identity(self.control_ref,'PipelineRuntimeControlRevision','pipeline-control-')
        if self.previous_ref is not None:
            _ref_identity(self.previous_ref,'PipelineScheduleControlBinding','schedule-control-')
        return self


def _approve(request, principal, pipeline_id, body, selection):
    from aos_api.pipeline_source_claim_owner import _text
    try:
        key = require_idempotency_key(request)
        _text(pipeline_id,200)
        binding = isinstance(body,ScheduleBindingRequest)
        draft = None if binding else body.draft
        scope = TenantScope(principal.org_id, principal.project_id)
        if not binding and scope.key != (draft.org_id, draft.project_id):
            raise PermissionError('request scope differs')
        if not binding and draft.pipeline_id != pipeline_id:
            raise ValueError('request pipeline differs')
        plane = getattr(request.app.state, 'extension_runtime_control_plane', None)
        factory = getattr(plane, 'pipeline_control_factory', None)
        if factory is None:
            raise ApiError(code='PIPELINE_CONTROL_UNAVAILABLE', message='管道控制服务当前不可用。', status_code=503)
        service = factory.build(scope)
        if binding:
            return service.bind_schedule(pipeline_id=pipeline_id,schedule_id=body.schedule_id,
                control_ref=body.control_ref,actor=principal.subject,idempotency_key=key,previous_ref=body.previous_ref)
        operation = service.approve_selection if selection else service.approve_control
        return operation(draft=draft, actor=principal.subject, idempotency_key=key, previous_ref=body.previous_ref)
    except ApiError:
        raise
    except AssetRegistryError as exc:
        raise ApiError(code=exc.code.value, message='管道审批条件未满足，请刷新核对。', status_code=exc.http_status) from exc
    except RuntimeRevisionConflict as exc:
        raise ApiError(code='PIPELINE_CONTROL_REVISION_CONFLICT', message='审批版本已变化，请刷新核对。', status_code=412) from exc
    except RuntimeConflict as exc:
        raise ApiError(code='PIPELINE_CONTROL_CONFLICT', message='当前状态或幂等请求冲突。', status_code=409) from exc
    except PermissionError as exc:
        raise ApiError(code='PIPELINE_CONTROL_ACCESS_DENIED', message='当前身份或配置不允许此审批。', status_code=403) from exc
    except LookupError as exc:
        raise ApiError(code='PIPELINE_CONTROL_NOT_FOUND', message='未找到当前租户可见的审批资源。', status_code=404) from exc
    except ValueError as exc:
        raise ApiError(code='PIPELINE_CONTROL_INVALID', message='审批范围或引用无效，请刷新核对。', status_code=422) from exc
    except Exception as exc:
        # A commit may already have happened. Never retry or create another key here.
        raise ApiError(code='PIPELINE_CONTROL_OUTCOME_UNCONFIRMED', message='暂未确认审批结果；请保留原幂等键核对，勿创建重复请求。', status_code=503) from exc


async def _request_body(request, model):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 65536:
            raise ApiError(code='PIPELINE_CONTROL_INVALID', message='审批请求过大。', status_code=413)
    try:
        # Strict JSON mode accepts ISO timestamps without coercing numeric fields.
        return model.model_validate_json(bytes(raw))
    except ValueError as exc:
        raise ApiError(code='PIPELINE_CONTROL_INVALID', message='审批请求格式无效。', status_code=422) from exc


@router.post('/{pipeline_id}/source-selection-approvals', response_model=PipelineExactRef)
async def approve_selection(pipeline_id: str, request: Request, principal: PrincipalDependency):
    body = await _request_body(request, SelectionApprovalRequest)
    return await run_in_threadpool(_approve, request, principal, pipeline_id, body, True)


@router.post('/{pipeline_id}/runtime-control-approvals', response_model=PipelineExactRef)
async def approve_control(pipeline_id: str, request: Request, principal: PrincipalDependency):
    body = await _request_body(request, ControlApprovalRequest)
    return await run_in_threadpool(_approve, request, principal, pipeline_id, body, False)


@router.post('/{pipeline_id}/schedule-control-bindings', response_model=PipelineExactRef)
async def bind_schedule_control(pipeline_id: str, request: Request, principal: PrincipalDependency):
    body = await _request_body(request, ScheduleBindingRequest)
    return await run_in_threadpool(_approve, request, principal, pipeline_id, body, False)


from aos_api.routers.pipeline_snapshot_schedules import router as snapshot_schedule_router
router.include_router(snapshot_schedule_router)
from aos_api.routers.pipeline_snapshot_recoveries import router as snapshot_recovery_router
router.include_router(snapshot_recovery_router)
