"""Installed snapshot schedule configuration; no execution endpoints."""
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool
from aos_api.auth import Principal,require_principal
from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.asset_registry.control_policy import validate_idempotency_key
from aos_api.errors import ApiError
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict,RuntimeRevisionConflict
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_runtime_control_owner import _ref_identity
from aos_api.pipeline_snapshot_schedule_definition import _cron
from aos_api.pipeline_source_claim_owner import _text
from aos_api.routers.asset_control_headers import require_idempotency_key
from aos_api.tenant_scope import TenantScope

router=APIRouter(prefix='/snapshot-schedules')
PrincipalDependency=Annotated[Principal,Depends(require_principal)]


def _worker_status(request,principal,definition_id):
    app=request.app.state
    worker=getattr(app,'snapshot_group_worker',None)
    state=getattr(app,'snapshot_group_worker_status','UNAVAILABLE')
    if worker is None:
        return dict(state=state if state in {'DISABLED','FAILED_CLOSED','STOPPED','NOT_SELECTED'} else 'UNAVAILABLE',
            available=False,active=False,errorCode=None)
    if worker.scope!=TenantScope(principal.org_id,principal.project_id):
        return dict(state='UNAVAILABLE',available=False,active=False,errorCode=None)
    task=getattr(app,'snapshot_group_worker_task',None)
    host=getattr(app,'extension_runtime_host_task',None)
    topology=getattr(app,'snapshot_group_worker_topology','cohosted')
    dependency_live=(topology=='independent' or
        (topology=='cohosted' and host is not None and not host.done()))
    live=task is not None and not task.done() and dependency_live
    actual=getattr(worker,'status','UNAVAILABLE')
    if state=='FAILED_CLOSED':actual=state
    elif not live and actual in {'RUNNING','IDLE'}:actual='UNAVAILABLE'
    if actual not in {'RUNNING','IDLE','STOPPING','STOPPED','FAILED_CLOSED','UNAVAILABLE'}:actual='UNAVAILABLE'
    available=live and actual in {'RUNNING','IDLE'}
    code=getattr(worker,'last_error',None)
    if code not in {'SNAPSHOT_TICK_UNCONFIRMED'}:code=None
    return dict(state=actual,available=available,
        active=available and getattr(worker,'active_definition_id',None)==definition_id,errorCode=code)


class SnapshotScheduleMember(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid',hide_input_in_errors=True)
    schedule_id:str=Field(alias='scheduleId',min_length=1,max_length=200)
    binding_ref:PipelineExactRef=Field(alias='bindingRef')

    @model_validator(mode='after')
    def exact(self):
        _text(self.schedule_id,200)
        _ref_identity(self.binding_ref,'PipelineScheduleControlBinding','schedule-control-')
        return self


class SnapshotScheduleConfigureRequest(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid',hide_input_in_errors=True)
    cron:str=Field(max_length=120)
    policy_ref:PipelineExactRef=Field(alias='policyRef')
    members:list[SnapshotScheduleMember]=Field(min_length=12,max_length=12)
    expected_ref:PipelineExactRef|None=Field(default=None,alias='expectedRef')

    @model_validator(mode='after')
    def exact(self):
        _cron(self.cron)
        if len({m.schedule_id for m in self.members})!=12:raise ValueError('duplicate schedule member')
        if self.policy_ref.resource_type!='SnapshotRelationshipPolicy':raise ValueError('exact relationship policy required')
        if self.expected_ref is not None:
            _ref_identity(self.expected_ref,'SnapshotScheduleDefinitionRevision','snapshot-schedule-')
        return self


class SnapshotScheduleTransitionRequest(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid',hide_input_in_errors=True)
    expected_ref:PipelineExactRef=Field(alias='expectedRef')

    @model_validator(mode='after')
    def exact(self):
        _ref_identity(self.expected_ref,'SnapshotScheduleDefinitionRevision','snapshot-schedule-')
        return self


def _operate(request,principal,definition_id,body,intent,receipt_key=None,after=None,limit=50,installation_id=None,generation=None):
    try:
        if intent not in {'list','options'} and str(UUID(definition_id))!=definition_id:raise ValueError('canonical definition id required')
        if after is not None and str(UUID(after))!=after:raise ValueError('canonical page cursor required')
        if intent=='options':
            if str(UUID(installation_id))!=installation_id or str(UUID(generation))!=generation:
                raise ValueError('canonical installation and generation required')
        if receipt_key is not None:validate_idempotency_key(receipt_key)
        key=None if intent in {'read','receipt','list','options','runtime'} else require_idempotency_key(request)
        if body is not None and body.expected_ref is not None and body.expected_ref.resource_id!='snapshot-schedule-'+definition_id:
            raise ValueError('definition predecessor differs')
        plane=getattr(request.app.state,'extension_runtime_control_plane',None)
        factory=getattr(plane,'pipeline_control_factory',None)
        if factory is None:
            raise ApiError(code='SNAPSHOT_SCHEDULE_UNAVAILABLE',message='数据组配置服务当前不可用。',status_code=503)
        service=factory.build_snapshot_schedule(TenantScope(principal.org_id,principal.project_id),
            source_controls=intent in {'configure','enable','options','runtime'})
        if intent=='options':return service.options(actor=principal.subject,installation_id=installation_id,generation=generation)
        if intent=='list':return service.list(actor=principal.subject,after=after,limit=limit)
        common=dict(definition_id=definition_id,actor=principal.subject)
        if intent=='runtime':return dict(service.read_runtime_status(**common),worker=_worker_status(request,principal,definition_id))
        if intent=='receipt':return service.read_receipt(**common,idempotency_key=receipt_key)
        if intent=='read':return service.read(**common)
        common.update(expected_ref=body.expected_ref,idempotency_key=key)
        if intent=='configure':
            return service.configure(**common,cron=body.cron,policy_ref=body.policy_ref,
                members=[m.model_dump(mode='json',by_alias=True,exclude_none=True) for m in body.members])
        return service.transition(**common,intent=intent)
    except ApiError:raise
    except AssetRegistryError as exc:
        raise ApiError(code=exc.code.value,message='当前安装配置权限或状态不满足要求。',status_code=exc.http_status) from exc
    except RuntimeRevisionConflict as exc:
        raise ApiError(code='SNAPSHOT_SCHEDULE_REVISION_CONFLICT',message='配置版本已变化，请刷新核对。',status_code=412) from exc
    except RuntimeConflict as exc:
        raise ApiError(code='SNAPSHOT_SCHEDULE_CONFLICT',message='当前状态不允许此操作。',status_code=409) from exc
    except PermissionError as exc:
        raise ApiError(code='SNAPSHOT_SCHEDULE_ACCESS_DENIED',message='当前身份无权执行此操作。',status_code=403) from exc
    except LookupError as exc:
        raise ApiError(code='SNAPSHOT_SCHEDULE_NOT_FOUND',message='未找到当前租户可见的数据组配置。',status_code=404) from exc
    except ValueError as exc:
        raise ApiError(code='SNAPSHOT_SCHEDULE_INVALID',message='配置范围或精确引用无效，请刷新核对。',status_code=422) from exc
    except Exception as exc:
        raise ApiError(code='SNAPSHOT_SCHEDULE_OUTCOME_UNCONFIRMED',message='暂未确认操作结果；请保留原幂等键核对，勿重复创建。',status_code=503) from exc


@router.get('/options')
async def options(request:Request,principal:PrincipalDependency,
                  installation_id:str=Query(alias='installationId'),generation:str=Query()):
    return await run_in_threadpool(_operate,request,principal,None,None,'options',
        installation_id=installation_id,generation=generation)


@router.get('/definitions')
async def list_configurations(request:Request,principal:PrincipalDependency,after:str|None=None,
                              limit:int=Query(default=50,ge=1,le=50)):
    return await run_in_threadpool(_operate,request,principal,None,None,'list',after=after,limit=limit)


@router.get('/{definition_id}/receipts/{idempotency_key}')
async def receipt(definition_id:str,idempotency_key:str,request:Request,principal:PrincipalDependency):
    return await run_in_threadpool(_operate,request,principal,definition_id,None,'receipt',receipt_key=idempotency_key)


@router.get('/{definition_id}')
async def read(definition_id:str,request:Request,principal:PrincipalDependency):
    return await run_in_threadpool(_operate,request,principal,definition_id,None,'read')


@router.get('/{definition_id}/runtime')
async def runtime_status(definition_id:str,request:Request,principal:PrincipalDependency):
    return await run_in_threadpool(_operate,request,principal,definition_id,None,'runtime')


@router.put('/{definition_id}')
async def configure(definition_id:str,request:Request,principal:PrincipalDependency):
    from aos_api.routers.pipeline_controls import _request_body
    body=await _request_body(request,SnapshotScheduleConfigureRequest)
    return await run_in_threadpool(_operate,request,principal,definition_id,body,'configure')


@router.post('/{definition_id}/{intent}')
async def transition(definition_id:str,intent:Literal['enable','disable','retire'],request:Request,principal:PrincipalDependency):
    from aos_api.routers.pipeline_controls import _request_body
    body=await _request_body(request,SnapshotScheduleTransitionRequest)
    return await run_in_threadpool(_operate,request,principal,definition_id,body,intent)
