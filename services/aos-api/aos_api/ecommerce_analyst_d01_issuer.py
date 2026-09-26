"""Bounded natural D01 AgentRun issuance through the existing AIP Owner.

Not registered in the Runtime Host until the current origin and full governed
source packet can be supplied by production readers.  No Provider transition.
"""
from __future__ import annotations

from datetime import datetime

from aos_api.aip_agent_registry_contracts import CreateAgentRunRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.tenant_scope import TenantScope


_SOURCE_KINDS = frozenset({
    'MethodRevision', 'EvalContractRevision', 'MetricDefinitionRevision',
    'QueryResultRevision', 'EvidenceBundleRevision',
})


def d01_agent_run_id(scope: TenantScope, task_run_id: str, plan_id: str) -> str:
    if type(scope) is not TenantScope or not task_run_id or not plan_id:
        raise ValueError('exact D01 identity required')
    return 'd01-agent-' + canonical_hash({
        'tenant': scope.key, 'taskRunId': task_run_id,
        'planRevisionId': plan_id, 'stepKey': 'portrait',
    })[:40]


def _value(item):
    return getattr(item, 'value', item)


class NaturalD01Issuer:
    def __init__(self, tasks, owner, *, require_current_origin,
                 require_current_sources):
        if (not isinstance(tasks, AipTaskStore) and not callable(getattr(tasks, 'timeline', None))
                or not callable(getattr(owner, 'create', None))
                or not callable(require_current_origin)
                or not callable(require_current_sources)):
            raise TypeError('exact D01 task, Owner, origin and source readers required')
        self._tasks, self._owner = tasks, owner
        self._origin = require_current_origin
        self._sources = require_current_sources

    def issue(self, scope: TenantScope, task_run_id: str, request: CreateAgentRunRequest,
              *, actor: str, occurred_at: datetime):
        if (type(scope) is not TenantScope or type(request) is not CreateAgentRunRequest
                or not task_run_id or type(actor) is not str or not actor.strip()
                or not isinstance(occurred_at, datetime) or occurred_at.utcoffset() is None):
            raise ValueError('exact D01 issue context required')
        timeline = self._tasks.timeline(scope, task_run_id)
        run, task, plan = timeline.run, timeline.task, timeline.plan
        stages = tuple(item.step_key for item in plan.steps)
        if (run.id != task_run_id or run.task_id != task.id
                or run.plan_revision_id != plan.id or plan.task_id != task.id
                or _value(run.status) != 'running'
                or _value(task.status) != 'executing'
                or _value(plan.approval_status) != 'approved'
                or stages != ('portrait', 'diagnosis', 'solution-design')
                or any(item.applicability != 'applicable' for item in plan.steps)
                or timeline.steps):
            raise ValueError('current approved D01 task lineage required')
        refs = request.run
        expected_id = d01_agent_run_id(scope, task_run_id, plan.id)
        if (request.agent_run_id != expected_id
                or request.task_run_ref.resource_type != 'TaskRun'
                or (request.task_run_ref.resource_id, request.task_run_ref.revision)
                    != (run.id, str(run.version))
                or refs.task_ref.resource_type != 'Task'
                or (refs.task_ref.resource_id, refs.task_ref.revision)
                    != (task.id, str(task.version))
                or refs.plan_ref.resource_type != 'PlanRevision'
                or (refs.plan_ref.resource_id, refs.plan_ref.revision)
                    != (plan.id, str(plan.revision))
                or refs.skill.asset_type != 'SkillTemplate'
                or refs.skill.asset_id != 'ecommerce.skill.D01'
                or refs.agent_instance.asset_type != 'AgentInstance'
                or refs.policy.asset_type != 'RuntimePolicyRevision'):
            raise ValueError('D01 exact Owner request drifted')
        assignees = [ref for ref in plan.steps[0].assignee_refs
                     if ref.resource_type == 'AgentInstance']
        if (len(assignees) != 1 or assignees[0].authority != 'aip-assignee-directory'
                or (assignees[0].resource_id, assignees[0].revision)
                    != (refs.agent_instance.asset_id, str(refs.agent_instance.revision))):
            raise ValueError('D01 assignee differs from approved plan')
        inputs = refs.input_refs
        identities = {(ref.resource_type, ref.resource_id, ref.revision, ref.authority)
                      for ref in inputs}
        if (len(identities) != len(inputs) or not _SOURCE_KINDS.issubset(
                {ref.resource_type for ref in inputs})
                or any(ref.authority != 'postgresql' or ref.revision is None for ref in inputs)):
            raise ValueError('complete unique D01 exact source inventory required')
        if self._origin(scope, task_run_id) is not True:
            raise ValueError('current natural origin unavailable')
        if self._sources(scope, request, actor, occurred_at) is not True:
            raise ValueError('current governed D01 source packet unavailable')
        if self._origin(scope, task_run_id) is not True:
            raise ValueError('natural origin changed during D01 preflight')
        key = 'natural-d01:' + expected_id
        # The canonical Owner checks its original Receipt under a stable key.
        # Unknown commit outcomes propagate; never mint a replacement identity.
        agent_run, receipt = self._owner.create(
            scope, request, idempotency_key=key, actor=actor, occurred_at=occurred_at)
        if (agent_run.agent_run_id != expected_id
                or _value(agent_run.status) not in {'queued', 'running', 'paused', 'succeeded'}
                or receipt.operation != 'agent_run.create'
                or receipt.idempotency_key != key
                or receipt.result_ref.resource_type != 'AgentRun'
                or receipt.result_ref.resource_id != expected_id):
            raise ValueError('D01 Owner readback differs; reconcile original key')
        return agent_run, receipt
