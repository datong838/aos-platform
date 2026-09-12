"""Atomic schedule claim boundary shared with first approval binding."""
from contextlib import contextmanager

from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, RuntimeRevisionConflict
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
from aos_api.extension_runtime.storage_ports import require_runtime_role
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner, ScheduleControlBinding
from aos_api.tenant_scope import TenantScope


@contextmanager
def _connection(scope):
    if type(scope) is not TenantScope:
        raise TypeError('exact tenant required')
    tenant = dict(org_id=scope.org_id, project_id=scope.project_id)
    with consumer_connection(runtime_worker_connection, tenant) as conn:
        require_runtime_role(conn, **tenant, protected_tables=('public.pipeline_schedule_control_binding',))
        yield conn


def read_schedule_binding(scope, schedule_id):
    with _connection(scope) as conn:
        return PipelineScheduleControlOwner.read_latest(conn, scope=scope, schedule_id=schedule_id)


@contextmanager
def schedule_claim_connection(scope, *, schedule_id, binding=None):
    if binding is not None:
        if type(binding) is not ScheduleControlBinding:
            raise TypeError('exact schedule binding required')
        if binding.scope != scope or binding.schedule_id != schedule_id:
            raise PermissionError('schedule claim binding differs')
    with _connection(scope) as conn:
        row = conn.execute('''SELECT pipeline_id, enabled, ingest FROM meta_schedule
            WHERE org_id=%s AND project_id=%s AND id=%s FOR UPDATE''', (*scope.key, schedule_id)).fetchone()
        if row is None:
            raise LookupError('schedule unavailable')
        ingest = row['ingest'] or {}
        if (row['enabled'] is not True or type(ingest) is not dict
                or ingest.get('kind') != 'pipeline-live-v1' or ingest.get('pipelineId') != row['pipeline_id']):
            raise RuntimeConflict('schedule is not enabled and live-bound')
        latest = PipelineScheduleControlOwner.read_latest(conn, scope=scope, schedule_id=schedule_id)
        if latest != binding or (binding is not None and row['pipeline_id'] != binding.pipeline_id):
            raise RuntimeRevisionConflict('schedule control changed before claim')
        # First binding uses this same schedule row lock and refuses an active
        # or unconfirmed old Run. Keep the lock until the claim commits.
        yield conn
