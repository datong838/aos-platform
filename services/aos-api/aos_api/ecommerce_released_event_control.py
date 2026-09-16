"""Disable one event binding after its runtime resources were safely released."""
from dataclasses import dataclass
from uuid import UUID

from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.ecommerce_growth_host_ports import EcommerceGrowthDispatchSnapshot,HostTransaction
from aos_api.ecommerce_product_event_control_contracts import ProductEventControlCommand
from aos_api.ecommerce_product_event_control_host_service import ProductEventControlHostService
from aos_api.ecommerce_product_event_control_qualified_owner import ProductEventControlQualifiedOwner
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class ReleasedEventTarget:
    installation_id:str
    generation:str
    execution_epoch:int
    runtime_revision:int
    cutover_group_id:str
    cutover_group_revision:int

    def __post_init__(self):
        for value in (self.installation_id,self.generation,self.cutover_group_id):
            if str(UUID(value))!=value:raise ValueError('canonical released event identity required')
        if any(type(value) is not int or value<1 for value in
               (self.execution_epoch,self.runtime_revision,self.cutover_group_revision)):
            raise ValueError('positive released event revisions required')


class ReleasedProductEventControlService:
    """Negative-only recovery; it cannot enable a schedule or execute a package."""
    def __init__(self,owner,*,actor,connect_factory):
        if type(owner) is not ProductEventControlQualifiedOwner or not callable(connect_factory):
            raise TypeError('current control Owner and scoped connection required')
        if type(actor) is not str or not actor or actor!=actor.strip() or not actor.isprintable():
            raise ValueError('canonical released control actor required')
        self._owner,self._actor,self._connect=owner,actor,connect_factory

    def disable(self,*,scope,command,target):
        if type(scope) is not TenantScope or type(target) is not ReleasedEventTarget:
            raise TypeError('trusted released event target required')
        checked=ProductEventControlCommand.model_validate(command)
        if checked.intent!='disable' or checked.approval_ref is not None:
            raise ValueError('released recovery only accepts unprivileged disable')
        with self._connect(scope) as conn:
            rows=[dict(row) for row in conn.execute(
                'SELECT * FROM extension_dispatch_lock_group_a0v_028(%s)',
                (UUID(target.cutover_group_id),)).fetchall()]
            expected=set(ECOMMERCE_GROWTH_OPERATIONS)|{'ecommerce_growth_event_control'}
            if (len(rows)!=10 or {row['operation_id'] for row in rows}!=expected
                    or any(row['handler_kind']!='extension'
                        or str(row['installation_id'])!=target.installation_id
                        or str(row['generation'])!=target.generation
                        or row['execution_epoch']!=target.execution_epoch
                        or row['operation_fence'] is not False
                        or str(row['cutover_group_id'])!=target.cutover_group_id
                        or row['cutover_group_revision']!=target.cutover_group_revision for row in rows)):
                raise ValueError('exact released event dispatch group required')
            runtime=conn.execute('''SELECT * FROM extension_runtime_binding WHERE org_id=%s
                AND project_id=%s AND installation_id=%s AND generation=%s FOR UPDATE''',
                (*scope.key,UUID(target.installation_id),UUID(target.generation))).fetchone()
            resources=conn.execute('''SELECT count(*) AS total,
                count(*) FILTER (WHERE cleanup_state='released' AND observed_release) AS released
                FROM extension_runtime_resource_lease WHERE org_id=%s AND project_id=%s
                AND generation=%s''',(*scope.key,UUID(target.generation))).fetchone()
            unresolved=conn.execute('''SELECT
                (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id=%s
                  AND project_id=%s AND installation_id=%s AND generation=%s AND state='running') AS running,
                (SELECT count(*) FROM automation_occurrence WHERE org_id=%s AND project_id=%s
                  AND installation_id=%s AND generation=%s AND status='claimed') AS claimed,
                (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
                  USING(org_id,project_id,occurrence_id) WHERE a.org_id=%s AND a.project_id=%s
                  AND o.installation_id=%s AND o.generation=%s AND a.status='claimed') AS claimed_attempts,
                (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
                  USING(org_id,project_id,occurrence_id) WHERE a.org_id=%s AND a.project_id=%s
                  AND o.installation_id=%s AND o.generation=%s AND a.status='unknown' AND (
                    o.status<>'needs_attention' OR o.trigger_source<>'event'
                    OR o.operation_id<>'ecommerce_growth_analysis_advance'
                    OR o.receipt_ref IS NOT NULL OR a.receipt_ref IS NOT NULL
                    OR a.claim_until>=clock_timestamp()
                    OR EXISTS(SELECT 1 FROM ecommerce_growth_runtime_command_receipt r
                      WHERE r.org_id=o.org_id AND r.project_id=o.project_id
                        AND r.operation_id='ecommerce_growth_analysis_advance'
                        AND r.idempotency_key=a.target_idempotency_key)
                    OR EXISTS(SELECT 1 FROM ecommerce_investigation_run x
                      WHERE x.org_id=o.org_id AND x.project_id=o.project_id
                        AND (x.trigger_key=a.target_idempotency_key OR x.run_id='analysis-'||substr(encode(
                          sha256(convert_to(o.org_id||chr(31)||o.project_id||chr(31)||
                            a.target_idempotency_key,'UTF8')),'hex'),1,32))))) AS unsafe_unknown''',
                (*scope.key,UUID(target.installation_id),UUID(target.generation),*scope.key,
                 UUID(target.installation_id),UUID(target.generation),*scope.key,
                 UUID(target.installation_id),UUID(target.generation),*scope.key,
                 UUID(target.installation_id),UUID(target.generation))).fetchone()
            if (runtime is None or runtime['revision']!=target.runtime_revision
                    or runtime['execution_epoch']<=target.execution_epoch
                    or runtime['enabled'] is not False or runtime['operation_fence'] is not True
                    or runtime['desired_state']!='enabled' or runtime['observed_state']!='unknown'
                    or resources is None or resources['total']!=3 or resources['released']!=3
                    or unresolved is None or any(unresolved[key] for key in
                        ('running','claimed','claimed_attempts','unsafe_unknown'))):
                raise ValueError('exact drained released runtime required')
            event=next(row for row in rows if row['operation_id']=='ecommerce_growth_event_control')
            checked_at=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            dispatch=EcommerceGrowthDispatchSnapshot(operation_id=event['operation_id'],
                dispatch_revision=event['revision'],installation_id=event['installation_id'],
                generation=event['generation'],execution_epoch=event['execution_epoch'],
                cutover_group_id=event['cutover_group_id'],
                cutover_group_revision=event['cutover_group_revision'],
                runtime_revision=runtime['revision'],checked_at=checked_at)
            service=ProductEventControlHostService(self._owner,actor=self._actor)
            tx=HostTransaction(conn);wire=checked.model_dump(by_alias=True,mode='json')
            service.revalidate(transaction=tx,scope=scope,dispatch=dispatch,command=wire)
            receipt=service.execute(transaction=tx,scope=scope,dispatch_ref=dispatch,
                command=wire,checked_at=checked_at,occurred_at=None)
            if service.verify_receipt(transaction=tx,scope=scope,dispatch=dispatch,
                    command=wire,receipt=receipt)!=receipt:
                raise ValueError('released event control receipt readback differs')
            conn.commit()
            return receipt
