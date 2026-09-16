"""Saved-input approval and readback, deliberately no execution endpoint."""
from typing import Annotated
from fastapi import APIRouter,Depends,Request
from pydantic import AwareDatetime,BaseModel,ConfigDict,Field,model_validator
from starlette.concurrency import run_in_threadpool
from aos_api.auth import Principal,require_principal
from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.asset_registry.control_policy import validate_idempotency_key
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.errors import ApiError
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict,RuntimeRevisionConflict
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_runtime_control_owner import _ref_identity
from aos_api.pipeline_snapshot_schedule_claim import _group_id
from aos_api.routers.asset_control_headers import require_idempotency_key
from aos_api.tenant_scope import TenantScope

router=APIRouter(prefix='/snapshot-recoveries')
PrincipalDependency=Annotated[Principal,Depends(require_principal)]


class SnapshotRecoveryRequest(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid',hide_input_in_errors=True)
    expected_definition_ref:PipelineExactRef=Field(alias='expectedDefinitionRef')
    expected_recovery_ref:PipelineExactRef|None=Field(alias='expectedRecoveryRef')
    input_manifest_hash:str=Field(alias='inputManifestHash',pattern='^sha256:[0-9a-f]{64}$')
    not_before:AwareDatetime=Field(alias='notBefore')
    expires_at:AwareDatetime=Field(alias='expiresAt')

    @model_validator(mode='after')
    def exact(self):
        _ref_identity(self.expected_definition_ref,'SnapshotScheduleDefinitionRevision','snapshot-schedule-')
        if self.expected_recovery_ref is not None:
            _ref_identity(self.expected_recovery_ref,'SnapshotGroupRecoveryRevision','snapshot-recovery-')
        if not 0<(self.expires_at-self.not_before).total_seconds()<=86400:
            raise ValueError('bounded recovery window required')
        return self


def _operate(request,principal,group_id,intent,body=None,receipt_key=None):
    try:
        group_id=_group_id(group_id)
        key=require_idempotency_key(request) if intent=='renew' else None
        if receipt_key is not None:validate_idempotency_key(receipt_key)
        if body is not None and body.expected_recovery_ref is not None and body.expected_recovery_ref.resource_id!='snapshot-recovery-'+group_id:
            raise ValueError('recovery predecessor group differs')
        plane=getattr(request.app.state,'extension_runtime_control_plane',None)
        factory=getattr(plane,'pipeline_control_factory',None)
        if factory is None:raise ApiError(code='SNAPSHOT_RECOVERY_UNAVAILABLE',message='原任务恢复服务当前不可用。',status_code=503)
        service=factory.build_snapshot_schedule(TenantScope(principal.org_id,principal.project_id),source_controls=intent!='receipt')
        common=dict(group_id=group_id,actor=principal.subject)
        if intent=='context':return service.read_recovery_context(**common)
        if intent=='receipt':return service.read_recovery_receipt(**common,idempotency_key=receipt_key)
        return service.renew_saved_group(**common,expected_definition_ref=body.expected_definition_ref,
            expected_recovery_ref=body.expected_recovery_ref,input_manifest_hash=body.input_manifest_hash,
            not_before=body.not_before,expires_at=body.expires_at,idempotency_key=key)
    except ApiError:raise
    except AssetRegistryError as exc:
        raise ApiError(code=exc.code.value,message='当前安装权限或状态不满足恢复要求。',status_code=exc.http_status) from exc
    except RuntimeRevisionConflict as exc:
        raise ApiError(code='SNAPSHOT_RECOVERY_REVISION_CONFLICT',message='版本已变化，请刷新核对原任务。',status_code=412) from exc
    except (RuntimeConflict,IngressJournalConflict) as exc:
        raise ApiError(code='SNAPSHOT_RECOVERY_CONFLICT',message='原输入、执行状态或当前权限不满足恢复条件。',status_code=409) from exc
    except PermissionError as exc:
        raise ApiError(code='SNAPSHOT_RECOVERY_ACCESS_DENIED',message='当前身份无权办理原任务恢复。',status_code=403) from exc
    except LookupError as exc:
        raise ApiError(code='SNAPSHOT_RECOVERY_NOT_FOUND',message='未找到当前租户可见的原任务或回执。',status_code=404) from exc
    except ValueError as exc:
        raise ApiError(code='SNAPSHOT_RECOVERY_INVALID',message='恢复窗口或精确引用无效，请刷新核对。',status_code=422) from exc
    except Exception as exc:
        raise ApiError(code='SNAPSHOT_RECOVERY_OUTCOME_UNCONFIRMED',message='暂未确认审批结果；请保留原幂等键查询回执，勿重新创建。',status_code=503) from exc


@router.get('/{group_id}/receipts/{idempotency_key}')
async def receipt(group_id:str,idempotency_key:str,request:Request,principal:PrincipalDependency):
    return await run_in_threadpool(_operate,request,principal,group_id,'receipt',receipt_key=idempotency_key)


@router.get('/{group_id}')
async def context(group_id:str,request:Request,principal:PrincipalDependency):
    return await run_in_threadpool(_operate,request,principal,group_id,'context')


@router.post('/{group_id}/renew')
async def renew(group_id:str,request:Request,principal:PrincipalDependency):
    from aos_api.routers.pipeline_controls import _request_body
    body=await _request_body(request,SnapshotRecoveryRequest)
    return await run_in_threadpool(_operate,request,principal,group_id,'renew',body=body)
