"""Bounded natural D01 AgentRun issuance through the existing AIP Owner.

Not registered in the Runtime Host until the current origin and full governed
source packet can be supplied by production readers.  No Provider transition.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import Field, model_validator

from aos_api.aip_agent_registry_contracts import CreateAgentRunRequest
from aos_api.aip_contracts import AipContractModel
from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_analyst_portrait_inputs import (
    PortraitMetricSourceRequest, read_portrait_input_packet,
)
from aos_api.ecommerce_growth_runtime_connection import connect_serializable
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.openfga import openfga_api_url
from aos_api.tenant_scope import TenantScope


_SOURCE_KINDS = frozenset({
    'MethodRevision', 'EvalContractRevision', 'MetricDefinitionRevision',
    'QueryResultRevision', 'EvidenceBundleRevision',
})


class D01SourcePacket(AipContractModel):
    method_ref: AnalystExactRef
    eval_ref: AnalystExactRef
    metric_sources: list[PortraitMetricSourceRequest] = Field(min_length=1, max_length=100)
    cutoff_at: datetime
    markings: list[str] = Field(min_length=1, max_length=50)
    max_source_age_seconds: int = Field(strict=True, ge=1, le=31536000)
    max_bytes: int = Field(strict=True, ge=1, le=2_000_000)

    @model_validator(mode='after')
    def _exact_packet(self):
        if (self.method_ref.resource_type != 'MethodRevision'
                or self.eval_ref.resource_type != 'EvalContractRevision'
                or self.cutoff_at.utcoffset() is None
                or len({item.metric_ref.resource_id for item in self.metric_sources})
                    != len(self.metric_sources)
                or any(item.metric_ref.resource_type != 'MetricDefinitionRevision'
                       or item.result_ref.resource_type != 'QueryResultRevision'
                       or item.source_request.bundle_ref.resource_type != 'EvidenceBundleRevision'
                       for item in self.metric_sources)
                or any(type(label) is not str or not label.strip() or label != label.strip()
                       for label in self.markings)):
            raise ValueError('complete exact D01 source packet required')
        return self


def _packet_ref_keys(packet: D01SourcePacket):
    refs = [packet.method_ref, packet.eval_ref,
            *(item.metric_ref for item in packet.metric_sources),
            *(item.result_ref for item in packet.metric_sources),
            *(item.source_request.bundle_ref for item in packet.metric_sources)]
    return {(ref.resource_type, ref.resource_id, str(ref.revision), 'postgresql')
            for ref in refs}


def require_current_d01_sources(scope: TenantScope, request: CreateAgentRunRequest,
                                packet: D01SourcePacket, actor: str,
                                occurred_at: datetime) -> bool:
    with connect_serializable(scope) as conn:
        return require_current_d01_sources_in_transaction(
            HostTransaction(conn), scope, request, packet, actor, occurred_at)


def require_current_d01_sources_in_transaction(
        transaction: HostTransaction, scope: TenantScope,
        request: CreateAgentRunRequest, packet: D01SourcePacket,
        actor: str, occurred_at: datetime) -> bool:
    """Read governed AOS inputs on the caller's tenant transaction; no mall SQL."""
    if (type(transaction) is not HostTransaction or type(scope) is not TenantScope
            or type(request) is not CreateAgentRunRequest
            or type(packet) is not D01SourcePacket or type(actor) is not str
            or not actor or actor != actor.strip()
            or type(occurred_at) is not datetime or occurred_at.utcoffset() is None):
        raise ValueError('exact D01 source read context required')
    packet = D01SourcePacket.model_validate(packet.model_dump(mode='python'))
    declared = {(ref.resource_type, ref.resource_id, ref.revision, ref.authority)
                for ref in request.run.input_refs}
    if declared != _packet_ref_keys(packet) or len(declared) != len(request.run.input_refs):
        raise ValueError('D01 packet differs from declared exact AgentRun inputs')
    if openfga_api_url():
        raise PermissionError('current remote D01 marking adapter required')
    current = transaction.execute(
        "SELECT current_setting('aos.org_id',true) AS org_id, "
        "current_setting('aos.project_id',true) AS project_id"
    ).fetchone()
    if current is None or (current['org_id'], current['project_id']) != scope.key:
        raise PermissionError('borrowed D01 source transaction tenant differs')
    database_now = transaction.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    if (not isinstance(database_now, datetime) or database_now.utcoffset() is None
            or abs((database_now - occurred_at).total_seconds()) > 300
            or packet.cutoff_at > database_now):
        raise ValueError('D01 source clock or cutoff unavailable')
    membership = transaction.execute(
        'SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE',
        (*scope.key, actor),
    ).fetchall()
    bearer = transaction.execute(
        "SELECT object_key FROM authz_tuple WHERE org_id=%s AND project_id=%s "
        "AND user_key=%s AND relation='bearer' AND object_key LIKE %s LIMIT 1001 FOR SHARE",
        (*scope.key, 'user:' + actor, 'marking:%'),
    ).fetchall()
    granted = {row['object_key'][len('marking:'):] for row in bearer
               if row['object_key'].startswith('marking:')}
    if (len(membership) != 1 or len(bearer) > 1000
            or any(not label or label != label.strip() for label in granted)
            or not set(packet.markings).issubset(granted)):
        raise PermissionError('current D01 actor membership or bearer markings unavailable')
    read_portrait_input_packet(
        conn=transaction, scope=scope, task_id=request.run.task_ref.resource_id,
        input_refs=request.run.input_refs, actor=actor,
        method_ref=packet.method_ref, eval_ref=packet.eval_ref,
        metric_sources=packet.metric_sources, cutoff_at=packet.cutoff_at,
        markings=packet.markings, now=database_now,
        max_source_age=timedelta(seconds=packet.max_source_age_seconds),
        max_bytes=packet.max_bytes,
    )
    return True


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
                 require_current_sources=require_current_d01_sources):
        if (not isinstance(tasks, AipTaskStore) and not callable(getattr(tasks, 'timeline', None))
                or not callable(getattr(owner, 'create', None))
                or not callable(require_current_origin)
                or not callable(require_current_sources)):
            raise TypeError('exact D01 task, Owner, origin and source readers required')
        self._tasks, self._owner = tasks, owner
        self._origin = require_current_origin
        self._sources = require_current_sources

    def issue(self, scope: TenantScope, task_run_id: str, request: CreateAgentRunRequest,
              packet: D01SourcePacket, *, actor: str, occurred_at: datetime):
        if (type(scope) is not TenantScope or type(request) is not CreateAgentRunRequest
                or type(packet) is not D01SourcePacket
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
                or identities != _packet_ref_keys(packet)
                or any(ref.authority != 'postgresql' or ref.revision is None for ref in inputs)):
            raise ValueError('complete unique D01 exact source inventory required')
        if self._origin(scope, task_run_id) is not True:
            raise ValueError('current natural origin unavailable')
        if self._sources(scope, request, packet, actor, occurred_at) is not True:
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
