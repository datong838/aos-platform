"""Principal-scoped configuration service; never creates runs or source calls."""
from contextlib import contextmanager
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
from aos_api.extension_runtime.storage_ports import require_runtime_role
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
from aos_api.pipeline_snapshot_schedule_definition import PipelineSnapshotScheduleDefinitionOwner
from aos_api.tenant_scope import TenantScope


class PipelineSnapshotScheduleService:
    def __init__(self,*,scope,controls,installation_store):
        if type(scope) is not TenantScope:raise TypeError('exact tenant required')
        self.scope=scope
        self._owner=PipelineSnapshotScheduleDefinitionOwner(controls=controls,installation_store=installation_store)

    @contextmanager
    def _connection(self):
        tenant=dict(org_id=self.scope.org_id,project_id=self.scope.project_id)
        with consumer_connection(runtime_worker_connection,tenant) as conn:
            require_runtime_role(conn,**tenant,protected_tables=(
                'public.pipeline_snapshot_schedule_definition_revision',
                'public.pipeline_snapshot_schedule_definition_head',
                'public.pipeline_snapshot_schedule_current_member'))
            yield conn

    def configure(self,*,definition_id,actor,cron,policy_ref,members,expected_ref,idempotency_key):
        if type(members) not in (list,tuple) or len(members)!=12:
            raise ValueError('twelve exact schedule members required')
        with self._connection() as conn:
            bindings=[]
            for member in members:
                if type(member) is not dict or set(member)!={'scheduleId','bindingRef'}:
                    raise ValueError('exact schedule member required')
                current=PipelineScheduleControlOwner.read_latest(conn,scope=self.scope,schedule_id=member['scheduleId'])
                if current is None or current.ref!=PipelineExactRef.model_validate(member['bindingRef']):
                    raise ValueError('requested schedule binding is not current')
                bindings.append(current)
            return self._owner.configure(conn,scope=self.scope,definition_id=definition_id,actor=actor,
                cron=cron,policy_ref=policy_ref,bindings=tuple(bindings),expected_ref=expected_ref,idempotency_key=idempotency_key)

    def transition(self,*,definition_id,actor,intent,expected_ref,idempotency_key):
        with self._connection() as conn:
            return self._owner.transition(conn,scope=self.scope,definition_id=definition_id,actor=actor,
                intent=intent,expected_ref=expected_ref,idempotency_key=idempotency_key)

    def read(self,*,definition_id,actor):
        with self._connection() as conn:
            result=self._owner.read(conn,scope=self.scope,definition_id=definition_id)
            if result is None:raise LookupError('snapshot schedule definition unavailable')
            body=result['body']
            if self._owner._permission(conn,org_id=self.scope.org_id,project_id=self.scope.project_id,
                    installation_id=body['installationId'],generation=body['generation'],actor=actor) is not True:
                raise PermissionError('current installation configuration permission required')
            return self._owner.read(conn,scope=self.scope,definition_id=definition_id)
