"""Discover existing successor materials; never register, disable or allocate."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator
from psycopg.types.json import Jsonb

from aos_api.aip_contracts import TenantContext
from aos_api.asset_registry.control_policy import validate_idempotency_key
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.ecommerce_growth_lifecycle import (
    EcommerceGrowthDisableDependent, EcommerceGrowthLifecycleBlocked, _snapshot,
)
from aos_api.ecommerce_growth_successor_registration import (
    SuccessorDispatchRegistrationRequest, require_successor_snapshot,
)


class SuccessorPreparationOption(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True)
    label: Literal['接续原安装的经营任务'] = '接续原安装的经营任务'
    command: SuccessorDispatchRegistrationRequest


class SuccessorPreparation(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True)
    schemaVersion: Literal['aos.ecommerce.successor-preparation/v1'] = 'aos.ecommerce.successor-preparation/v1'
    tenant: TenantContext
    installationId: str
    ready: bool
    reasons: tuple[str, ...]
    options: tuple[SuccessorPreparationOption, ...]
    executable: Literal[False] = False

    @model_validator(mode='after')
    def coherent(self):
        if self.ready != bool(self.options) or (self.ready and self.reasons):
            raise ValueError('preparation state differs from materials')
        return self


def prepare_successor_registration(owner, *, scope, installation_id, idempotency_key, actor):
    owner._identity(scope, actor)
    if type(installation_id) is not str or str(UUID(installation_id)) != installation_id:
        raise ValueError('canonical preparation installation required')
    key = validate_idempotency_key(idempotency_key)

    def answer(reasons=(), command=None):
        return SuccessorPreparation(tenant=TenantContext(orgId=scope.org_id, projectId=scope.project_id),
            installationId=installation_id, ready=command is not None, reasons=tuple(reasons),
            options=() if command is None else (SuccessorPreparationOption(command=command),))

    with owner._transaction(scope) as conn:
        owner._require_current_transaction(conn, scope)
        locked = owner._authorize_receipt_access(conn, scope, installation_id, actor)
        record = locked.record
        binding = conn.execute('''SELECT generation,revision,execution_epoch,config_ref,
            enabled,operation_fence,desired_state,observed_state
            FROM public.extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s''',
            (*scope.key, installation_id)).fetchone()
        rows = conn.execute('''SELECT * FROM public.extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND operation_id=ANY(%s) ORDER BY operation_id''',
            (*scope.key, list(ECOMMERCE_GROWTH_OPERATIONS))).fetchall()
        snapshot = [_snapshot(dict(row)) for row in rows]
        reasons = []
        if record.state != 'active' or binding is None or binding['config_ref'] is None:
            reasons.append('新安装尚未完成运行配置')
        if binding is None or not (binding['enabled'] is True and binding['operation_fence'] is False
                and binding['desired_state'] == 'enabled' and binding['observed_state'] == 'ready'):
            reasons.append('新安装尚未准备好承接经营任务')
        if (len(snapshot) != len(ECOMMERCE_GROWTH_OPERATIONS)
                or any(row['handlerKind'] != 'legacy' or row['operationFence'] is not True for row in snapshot)):
            reasons.append('原经营入口尚未正式停用')
        if reasons:
            return answer(reasons)

        group = snapshot[0]['cutoverGroupId']
        candidates = conn.execute('''SELECT l.runtime_operation_id,l.fenced_group_revision,
                c.target_installation_id,c.target_generation
            FROM public.extension_dispatch_lifecycle_operation l
            JOIN public.extension_dispatch_cutover_operation c
              ON c.org_id=l.org_id AND c.project_id=l.project_id
             AND c.cutover_operation_id=l.activation_operation_id
            JOIN public.extension_runtime_operation r
              ON r.org_id=l.org_id AND r.project_id=l.project_id AND r.operation_id=l.runtime_operation_id
            JOIN public.extension_runtime_binding b
              ON b.org_id=c.org_id AND b.project_id=c.project_id
             AND b.installation_id=c.target_installation_id AND b.generation=c.target_generation
            WHERE l.org_id=%s AND l.project_id=%s AND l.cutover_group_id=%s
              AND l.status='detached' AND l.legacy_snapshot=%s
              AND c.kind='activate' AND c.status='resumed' AND c.target_installation_id<>%s
              AND r.installation_id=c.target_installation_id
              AND r.kind='disable' AND r.status='succeeded' AND r.phase='succeeded'
              AND NOT b.enabled AND b.operation_fence
              AND b.desired_state='disabled' AND b.observed_state='unknown'
            ORDER BY l.updated_at DESC,l.runtime_operation_id LIMIT 2''',
            (*scope.key, group, Jsonb(snapshot), installation_id)).fetchall()
        if len(candidates) != 1:
            return answer(['原安装尚无匹配的正式退出记录' if not candidates else '退出记录需要复核，暂不可接续'])
        candidate = dict(candidates[0])
        owner._authorize_receipt_access(conn, scope, str(candidate['target_installation_id']), actor)
        lifecycle = EcommerceGrowthDisableDependent()
        row = lifecycle._load_receipt(conn, scope, candidate['runtime_operation_id'], 'detach')
        if row is None:
            raise ValueError('preparation detach receipt unavailable')
        detached = lifecycle._receipt(scope, row, replayed=True)
        if detached.phase != 'detach' or detached.status != 'detached' or list(detached.dispatch_snapshot) != snapshot:
            raise ValueError('preparation detach snapshot differs')
        try:
            lifecycle._assert_recovery_drained(conn, scope, candidate)
        except EcommerceGrowthLifecycleBlocked:
            return answer(['原安装仍有待核对的任务，暂不可接续'])
        remaining = conn.execute('''SELECT
            EXISTS(SELECT 1 FROM public.extension_dispatch_claim_gate
                WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s) AS claim_pending,
            EXISTS(SELECT 1 FROM public.extension_runtime_resource_lease l
                JOIN public.extension_runtime_operation o USING(org_id,project_id,operation_id)
                WHERE o.org_id=%s AND o.project_id=%s AND o.installation_id=%s
                  AND l.generation=%s AND (l.cleanup_state<>'released' OR NOT l.observed_release)) AS resources_pending''',
            (*scope.key, group, *scope.key, candidate['target_installation_id'], candidate['target_generation'])).fetchone()
        if remaining is None or any(remaining.values()):
            return answer(['原安装仍有待释放的任务或资源，暂不可接续'])

        command = SuccessorDispatchRegistrationRequest.model_validate(dict(
            schemaVersion='aos.ecommerce.successor-dispatch-registration/v1',
            registration=dict(schemaVersion='aos.ecommerce.first-dispatch-registration/v1',
                installationRef=dict(installationId=installation_id, revision=record.current.revision,
                    lockHash=record.current.lock_hash, overlayRevision=record.current.overlay_revision),
                generation=str(binding['generation']), bindingRevision=binding['revision'],
                executionEpoch=binding['execution_epoch'], configRef=binding['config_ref'], groupId=group, idempotencyKey=key),
            expectedGroupRevision=candidate['fenced_group_revision']+1,
            predecessorDetachReceiptRef=dict(resourceType='DispatchDisableDetachReceipt',
                resourceId=str(detached.receipt_id), revision=1, contentHash=detached.content_hash)))
        require_successor_snapshot(snapshot, command)
        owner.validate_current_authority_in_transaction(conn, scope=scope, request=command.registration, actor=actor)
        return answer(command=command)
