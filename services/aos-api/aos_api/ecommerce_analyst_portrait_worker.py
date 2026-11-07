"""Trusted D01 worker over canonical scheduling and governed generation.

No public route, AgentRun provisioning, automatic approval or model selection.
Callers provide scoped factories that open independent per-call connections.
"""
from datetime import timedelta
from contextlib import ExitStack

from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
from aos_api.aip_task_models import RunControlResult
from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked, _canonical_hash
from aos_api.aip_taor_loop import CanonicalTaorRunner
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
from aos_api.ecommerce_analyst_portrait_service import PortraitGenerationService
from aos_api.ecommerce_analyst_portrait_inputs import read_portrait_inputs
from aos_api.public_contracts import TaskStatus


def portrait_stage_attempt_id(scope, timeline) -> str:
    return "portrait-taor-" + canonical_hash({
        "tenant": scope.key, "taskRunId": timeline.run.id,
        "planRevisionId": timeline.plan.id, "planContentHash": timeline.plan.content_hash,
        "stepKey": "portrait",
    })[:40]


def require_portrait_stage_lineage(scope, timeline, agent_run, command) -> None:
    plan, task, run = timeline.plan, timeline.task, timeline.run
    plan_payload = {"steps": [x.model_dump(mode="json", by_alias=True) for x in plan.steps],
                    "dependencies": plan.dependencies, "risk": plan.risk}
    request = agent_run.request
    if (
        run.status.value != "running" or task.status is not TaskStatus.EXECUTING
        or plan.approval_status != "approved" or plan.content_hash != _canonical_hash(plan_payload)
        or plan.task_id != task.id or run.task_id != task.id or run.plan_revision_id != plan.id
        or [x.step_key for x in plan.steps] != ["portrait", "diagnosis", "solution-design"]
        or any(x.applicability != "applicable" for x in plan.steps)
        or (agent_run.tenant.org_id, agent_run.tenant.project_id) != scope.key
        or agent_run.task_id != task.id or agent_run.task_run_id != run.id
        or request.task_ref.resource_type != "Task" or request.task_ref.resource_id != task.id
        or request.plan_ref.resource_type != "PlanRevision" or request.plan_ref.resource_id != plan.id
        or request.plan_ref.revision != str(plan.revision)
        or request.skill.asset_type != "SkillTemplate" or request.skill.asset_id != "ecommerce.skill.D01"
        or command.attempt_id != portrait_stage_attempt_id(scope, timeline) or command.attempt_no != 1
    ):
        raise AipTaskTransitionBlocked("D01 task, plan, agent run or stable attempt lineage mismatch")
    completed = [x["step_key"] for x in timeline.steps if x.get("status") == "succeeded"]
    if completed:
        raise AipTaskTransitionBlocked("D01 requires no completed predecessor stages")
    assignees = [ref for ref in plan.steps[0].assignee_refs
                 if ref.resource_type == "AgentInstance" and ref.resource_id == agent_run.instance_id]
    instance = request.agent_instance
    if (len(assignees) != 1 or assignees[0].authority != "aip-assignee-directory"
            or (assignees[0].resource_id, assignees[0].revision) != (agent_run.instance_id, str(agent_run.instance_version))
            or instance.asset_type != "AgentInstance"
            or (instance.asset_id, instance.revision) != (agent_run.instance_id, agent_run.instance_version)):
        raise AipTaskTransitionBlocked("D01 agent instance does not match the approved stage assignee")


class PortraitTaorWorker:
    def __init__(self, connect_factory, executor):
        self._generation = PortraitGenerationService(connect_factory, executor)
        self._connect = connect_factory
        self._tasks = AipTaskStore(connect_factory=connect_factory)
        self._runs = AipAgentRunService(connect_factory)
        self._analyst = EcommerceAnalystAuthorityStore(connect_factory)
        self._attempts = AipAgentRunExecutionService(connect_factory)

    def _lineage(self, scope, task_run_id, agent_run_id, command):
        timeline = self._tasks.timeline(scope, task_run_id)
        agent_run = self._runs.get(scope, agent_run_id)
        if timeline.run.id != task_run_id or agent_run.agent_run_id != agent_run_id:
            raise AipTaskTransitionBlocked("D01 requested runtime identity mismatch")
        require_portrait_stage_lineage(scope, timeline, agent_run, command)
        return timeline

    def run(self, scope, task_run_id, agent_run_id, command, *, actor, worker_id,
            markings, clock, max_source_age: timedelta, max_bytes: int, lease_seconds=30) -> RunControlResult:
        return self._run(scope, task_run_id, agent_run_id, command, actor=actor,
            worker_id=worker_id, markings=markings, clock=clock,
            max_source_age=max_source_age, max_bytes=max_bytes, lease_seconds=lease_seconds)

    def run_with_formal_source(
            self, scope, task_run_id, agent_run_id, command, *, source_service,
            parent_request, source_ref, installation_id, installation_revision,
            installation_etag, **execution) -> RunControlResult:
        """Original TAOR with explicit per-invocation formal Source authority."""
        from aos_api.aip_formal_source_disclosure import FormalSourceDisclosureService
        from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
        from aos_api.aip_production_contracts import ResolveEvidenceDisclosureRequest
        if type(source_service) is not FormalSourceDisclosureService:
            raise TypeError('original formal Source service required')
        formal_source = dict(source_service=source_service,
            parent_request=ResolveEvidenceDisclosureRequest.model_validate(parent_request.model_dump()),
            source_ref=FormalExactRef.model_validate(source_ref.model_dump()),
            installation_id=installation_id, installation_revision=installation_revision,
            installation_etag=installation_etag)
        return self._run(scope, task_run_id, agent_run_id, command,
                         formal_source=formal_source, **execution)

    def _run(self, scope, task_run_id, agent_run_id, command, *, actor, worker_id,
             markings, clock, max_source_age: timedelta, max_bytes: int,
             lease_seconds=30, formal_source=None) -> RunControlResult:
        if not callable(clock) or not actor.strip() or not worker_id.strip():
            raise ValueError("D01 worker requires clock, actor and worker identity")
        command = command.model_copy(deep=True)
        timeline = self._lineage(scope, task_run_id, agent_run_id, command)
        adapter = _PortraitAdapter(self, scope, task_run_id, agent_run_id, command,
                                    actor, list(markings), clock, max_source_age, max_bytes, timeline.plan.content_hash,
                                    formal_source=formal_source)
        return CanonicalTaorRunner(self._tasks).run(scope, task_run_id, actor=actor, worker_id=worker_id,
            adapter=adapter, lease_seconds=lease_seconds, renew_step_lease=True, stop_after_step="portrait")


class _PortraitAdapter:
    def __init__(self, worker, scope, task_run_id, agent_run_id, command, actor, markings, clock, max_source_age, max_bytes, plan_hash, *, formal_source=None):
        self.worker, self.scope = worker, scope
        self.task_run_id, self.agent_run_id, self.command = task_run_id, agent_run_id, command
        self.actor, self.markings, self.clock = actor, markings, clock
        self.max_source_age, self.plan_hash, self.max_bytes = max_source_age, plan_hash, max_bytes
        self.formal_source = formal_source

    def think(self, step, context):
        try:
            if step["stepKey"] != "portrait" or context["runRef"] != self.task_run_id or context["planContentHash"] != self.plan_hash:
                raise ValueError("stage context drifted")
            run = self.worker._runs.get(self.scope, self.agent_run_id)
            with ExitStack() as stack:
                source_store = None
                if self.formal_source is None:
                    conn = stack.enter_context(self.worker._connect(self.scope))
                else:
                    source_args = {key: value for key, value in self.formal_source.items()
                                   if key not in {'source_service', 'parent_request'}}
                    conn, source_store = stack.enter_context(
                        self.formal_source['source_service'].source_transaction(
                            self.scope, self.actor, self.formal_source['parent_request'], **source_args))
                read_portrait_inputs(conn=conn, scope=self.scope, method_ref=self.command.method_ref, eval_ref=self.command.eval_ref,
                    metric_sources=self.command.metric_sources, cutoff_at=self.command.cutoff_at, run=run, actor=self.actor, markings=self.markings,
                    now=self.clock(), max_source_age=self.max_source_age, max_bytes=self.max_bytes,
                    **({'source_store': source_store} if source_store is not None else {}))
            return {"attemptId": self.command.attempt_id, "generationCommandHash": canonical_hash(self.command.model_dump(mode="json", by_alias=True))}
        except Exception:
            raise AipTaskTransitionBlocked("D01 predecessor evidence or current portrait inputs are not usable") from None

    def act(self, step, thought):
        try:
            self.worker._lineage(self.scope, self.task_run_id, self.agent_run_id, self.command)
            generate = (self.worker._generation.generate if self.formal_source is None
                        else self.worker._generation.generate_with_formal_source)
            ref = generate(self.scope, self.agent_run_id, self.command,
                actor=self.actor, markings=self.markings, clock=self.clock,
                max_source_age=self.max_source_age, max_bytes=self.max_bytes,
                **(self.formal_source or {}))
            return {"insightRef": ref.model_dump(mode="json", by_alias=True)}
        except Exception:
            # Keep the original attempt for recovery. Do not flatten an unknown
            # outcome into the runner's generic failed/retryable adapter path.
            raise AipTaskTransitionBlocked("D01 generation outcome requires recovery; do not resubmit") from None

    def verify(self, step, action):
        try:
            ref = AnalystExactRef.model_validate(action["insightRef"])
            insight = self.worker._analyst.get_insight_exact(self.scope, ref)
            attempt = self.worker._attempts.get(self.scope, self.command.attempt_id)
            identity = canonical_hash({"tenant": {"orgId": self.scope.org_id, "projectId": self.scope.project_id},
                                       "attemptId": self.command.attempt_id})
            artifact = attempt.output_artifact_ref
            if (ref.resource_type != "InsightRevision" or ref.revision != 1
                    or ref.resource_id != "portrait-" + identity[:40]
                    or insight.method_ref != self.command.method_ref or insight.eval_ref != self.command.eval_ref
                    or insight.cutoff_at != self.command.cutoff_at or insight.created_by != self.actor
                    or attempt.agent_run_id != self.agent_run_id or attempt.status != "succeeded" or artifact is None
                    or insight.generation_artifact_ref != AnalystExactRef(resourceType="Artifact",
                        resourceId=artifact.artifact_id, revision=1, contentHash=artifact.content_hash)):
                raise ValueError("portrait output drifted")
            return {"passed": True, "insightRef": action["insightRef"]}
        except Exception:
            raise AipTaskTransitionBlocked("D01 formal portrait verification failed; recovery required") from None

    def observe(self, step, action, verification):
        return {"insightRef": verification["insightRef"], "artifacts": []}
