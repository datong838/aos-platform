"""Host-owned, read-only discovery of natural analyst stages.

This is deliberately not an AgentRun issuer.  A discovered task still needs
current method, source, route, budget, capacity and approval authority before
any D01/D02/D03 execution can be added.
"""
from __future__ import annotations

import asyncio

from aos_api.ecommerce_growth_runtime_connection import connect_read_only
from aos_api.ecommerce_growth_runtime_adapters import _analysis_command_hash
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.logging_facade import get_logger
from aos_api.tenant_scope import TenantScope

log = get_logger('aos-api.analyst-stage-readiness')

_LIMIT = 100
_SCAN = """SELECT r.response,r.request_hash,r.target_receipt_ref,
    r.installation_id,r.generation,r.execution_epoch,r.dispatch_revision,
    d.handler_kind,d.installation_id AS current_installation,
    d.generation AS current_generation,d.execution_epoch AS current_epoch,
    d.revision AS current_dispatch_revision,d.operation_fence AS dispatch_fence,
    b.desired_state,b.observed_state,b.enabled,b.operation_fence AS runtime_fence,
    t.status AS task_run_status,t.task_id,t.plan_revision_id,
    task.status AS task_status,task.current_plan_revision_id,
    EXISTS(SELECT 1 FROM aip_agent_run agent WHERE agent.org_id=r.org_id
      AND agent.project_id=r.project_id
      AND agent.task_run_id=t.run_id) AS has_agent_run
  FROM ecommerce_growth_runtime_command_receipt r
  LEFT JOIN extension_operation_dispatch_binding d ON d.org_id=r.org_id
    AND d.project_id=r.project_id AND d.operation_id=r.operation_id
  LEFT JOIN extension_runtime_binding b ON b.org_id=r.org_id
    AND b.project_id=r.project_id AND b.installation_id=r.installation_id
    AND b.generation=r.generation
  LEFT JOIN aip_task_run t ON t.org_id=r.org_id AND t.project_id=r.project_id
    AND t.run_id=r.response->'taskRunRef'->>'resourceId'
  LEFT JOIN aip_task task ON task.org_id=t.org_id AND task.project_id=t.project_id
    AND task.task_id=t.task_id
  WHERE r.org_id=%s AND r.project_id=%s
    AND r.operation_id='ecommerce_growth_analysis_advance'
  ORDER BY r.occurred_at DESC,r.idempotency_key LIMIT 101"""


def _classify(row, scope, directory):
    response = row['response']
    if type(response) is not dict:
        return 'reconcile'
    ref = response.get('receiptRef')
    body = {key: value for key, value in response.items() if key != 'receiptRef'}
    if (type(ref) is not dict or ref != row['target_receipt_ref']
            or ref.get('contentHash') != _analysis_command_hash(body)
            or response.get('requestHash') != row['request_hash']):
        return 'reconcile'
    task_ref = response.get('taskRunRef')
    if (type(task_ref) is not dict or task_ref.get('resourceType') != 'TaskRun'
            or type(task_ref.get('resourceId')) is not str
            or not task_ref['resourceId']):
        return 'reconcile'
    if response.get('phase') == 'RECONCILING' or row['has_agent_run']:
        return 'reconcile'
    if (row['handler_kind'] != 'extension' or row['dispatch_fence'] is not False
            or row['current_installation'] != row['installation_id']
            or row['current_generation'] != row['generation']
            or row['current_epoch'] != row['execution_epoch']
            or row['current_dispatch_revision'] != row['dispatch_revision']
            or row['desired_state'] != 'enabled' or row['observed_state'] != 'ready'
            or row['enabled'] is not True or row['runtime_fence'] is not False):
        return 'blocked'
    try:
        directory.resolve(scope=scope, installation_id=row['installation_id'],
                          generation=row['generation'])
    except (LookupError, TypeError, ValueError):
        return 'blocked'
    if (response.get('phase') != 'RUNNING' or response.get('completed') is not False
            or row['task_run_status'] != 'running' or row['task_status'] != 'executing'
            or row['current_plan_revision_id'] != row['plan_revision_id']):
        return 'blocked'
    # This status is never execution permission.  Method/source/approval and
    # Provider budget/capacity must be proved by the later issuing Owner.
    return 'awaiting-authority'


def require_unique_current_analysis_receipt(scope, task_run_id, directory):
    """Discover one live Receipt; this is not original-origin authorization."""
    if (type(scope) is not TenantScope or type(task_run_id) is not str
            or not task_run_id or type(directory) is not LivePreparedJobDirectory):
        raise ValueError('exact analysis receipt lookup required')
    with connect_read_only(scope) as conn:
        rows = conn.execute(_SCAN, scope.key).fetchall()
    if len(rows) > _LIMIT:
        raise ValueError('analysis receipt scan overflow')
    matching = [row for row in rows
                if type(row['response']) is dict
                and type(row['response'].get('taskRunRef')) is dict
                and row['response']['taskRunRef'].get('resourceId') == task_run_id]
    if len(matching) != 1:
        raise ValueError('unique analysis receipt required')
    if _classify(matching[0], scope, directory) != 'awaiting-authority':
        raise ValueError('current analysis receipt unavailable')
    return True


class AnalystStageReadinessWorker:
    def __init__(self, directory, *, connect=connect_read_only):
        if type(directory) is not LivePreparedJobDirectory or not callable(connect):
            raise TypeError('exact live directory and read-only connection required')
        self.directory, self._connect = directory, connect
        self.last_status = dict(scopesChecked=0, blocked=0, reconcile=0,
                                awaitingAuthority=0, overflow=0)

    def scan_scope(self, scope):
        if type(scope) is not TenantScope:
            raise TypeError('exact tenant required')
        with self._connect(scope) as conn:
            rows = conn.execute(_SCAN, scope.key).fetchall()
        if len(rows) > _LIMIT:
            return dict(blocked=0, reconcile=0, awaitingAuthority=0, overflow=1)
        statuses = [_classify(row, scope, self.directory) for row in rows]
        # Multiple historical Receipts for one TaskRun are not proof of a
        # unique original issuance.  No downstream stage may be issued here.
        task_ids = [row['response'].get('taskRunRef', {}).get('resourceId')
                    if type(row['response']) is dict
                    and type(row['response'].get('taskRunRef')) is dict else None
                    for row in rows]
        duplicated = {task_id for task_id in task_ids if task_id is not None
                      and task_ids.count(task_id) > 1}
        statuses = ['reconcile' if task_id in duplicated else status
                    for task_id, status in zip(task_ids, statuses)]
        return dict(blocked=statuses.count('blocked'),
                    reconcile=statuses.count('reconcile'),
                    awaitingAuthority=statuses.count('awaiting-authority'), overflow=0)

    async def tick(self):
        targets = self.directory.current_targets()
        scopes = sorted({scope for scope, _, _ in targets}, key=lambda item: item.key)
        stats = dict(scopesChecked=0, blocked=0, reconcile=0,
                     awaitingAuthority=0, overflow=0)
        for scope in scopes[:4]:
            result = await asyncio.to_thread(self.scan_scope, scope)
            stats['scopesChecked'] += 1
            for key in ('blocked', 'reconcile', 'awaitingAuthority', 'overflow'):
                stats[key] += result[key]
        self.last_status = stats
        return stats

    async def serve(self, stop, *, host_ready):
        while not stop.is_set() and host_ready():
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.last_status = dict(scopesChecked=0, blocked=0, reconcile=1,
                                        awaitingAuthority=0, overflow=0)
                log.exception('analyst_stage_readiness_failed_closed')
            try:
                await asyncio.wait_for(stop.wait(), timeout=15)
            except TimeoutError:
                continue


def build_analyst_stage_readiness_worker(control_plane):
    directory = getattr(control_plane, 'live_job_directory', None)
    return None if directory is None else AnalystStageReadinessWorker(directory)
