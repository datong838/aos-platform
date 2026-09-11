"""Trusted D03 worker over canonical scheduling and governed generation.

No public route, AgentRun provisioning, automatic approval or model selection.
Callers provide scoped factories that open independent per-call connections.
"""
from datetime import timedelta

from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_task_models import RunControlResult
from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked, _canonical_hash
from aos_api.aip_taor_loop import CanonicalTaorRunner
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
from aos_api.ecommerce_analyst_growth_plan_generation import GrowthPlanGenerationService
from aos_api.ecommerce_analyst_growth_plan_sources import require_growth_plan_sources
from aos_api.public_contracts import TaskStatus


def growth_stage_attempt_id(scope, timeline) -> str:
    return "growth-taor-" + canonical_hash({
        "tenant": scope.key, "taskRunId": timeline.run.id,
        "planRevisionId": timeline.plan.id, "planContentHash": timeline.plan.content_hash,
        "stepKey": "solution-design",
    })[:40]


def require_growth_stage_lineage(scope, timeline, agent_run, command) -> None:
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
        or request.skill.asset_type != "SkillTemplate" or request.skill.asset_id != "ecommerce.skill.D03"
        or command.attempt_id != growth_stage_attempt_id(scope, timeline) or command.attempt_no != 1
    ):
        raise AipTaskTransitionBlocked("D03 task, plan, agent run or stable attempt lineage mismatch")
    completed = [x["step_key"] for x in timeline.steps if x.get("status") == "succeeded"]
    if sorted(completed) != ["diagnosis", "portrait"]:
        raise AipTaskTransitionBlocked("D03 requires completed portrait and diagnosis only")
    assignees = [ref for ref in plan.steps[-1].assignee_refs if ref.resource_type == "AgentInstance"]
    instance = request.agent_instance
    if (len(assignees) != 1 or assignees[0].authority != "aip-assignee-directory"
            or (assignees[0].resource_id, assignees[0].revision) != (agent_run.instance_id, str(agent_run.instance_version))
            or instance.asset_type != "AgentInstance"
            or (instance.asset_id, instance.revision) != (agent_run.instance_id, agent_run.instance_version)):
        raise AipTaskTransitionBlocked("D03 agent instance does not match the approved stage assignee")


class GrowthPlanTaorWorker:
    def __init__(self, connect_factory, executor):
        self._generation = GrowthPlanGenerationService(connect_factory, executor)
        self._connect = connect_factory
        self._tasks = AipTaskStore(connect_factory=connect_factory)
        self._runs = AipAgentRunService(connect_factory)
        self._plans = EcommerceAnalystAuthorityStore(connect_factory)

    def _lineage(self, scope, task_run_id, agent_run_id, command):
        timeline = self._tasks.timeline(scope, task_run_id)
        agent_run = self._runs.get(scope, agent_run_id)
        if timeline.run.id != task_run_id or agent_run.agent_run_id != agent_run_id:
            raise AipTaskTransitionBlocked("D03 requested runtime identity mismatch")
        require_growth_stage_lineage(scope, timeline, agent_run, command)
        return timeline

    def run(self, scope, task_run_id, agent_run_id, command, *, actor, worker_id,
            markings, clock, max_source_age: timedelta, lease_seconds=30) -> RunControlResult:
        if not callable(clock) or not actor.strip() or not worker_id.strip():
            raise ValueError("D03 worker requires clock, actor and worker identity")
        command = command.model_copy(deep=True)
        timeline = self._lineage(scope, task_run_id, agent_run_id, command)
        adapter = _GrowthPlanAdapter(self, scope, task_run_id, agent_run_id, command,
                                    actor, list(markings), clock, max_source_age, timeline.plan.content_hash)
        return CanonicalTaorRunner(self._tasks).run(scope, task_run_id, actor=actor, worker_id=worker_id,
            adapter=adapter, lease_seconds=lease_seconds, renew_step_lease=True)


class _GrowthPlanAdapter:
    def __init__(self, worker, scope, task_run_id, agent_run_id, command, actor, markings, clock, max_source_age, plan_hash):
        self.worker, self.scope = worker, scope
        self.task_run_id, self.agent_run_id, self.command = task_run_id, agent_run_id, command
        self.actor, self.markings, self.clock = actor, markings, clock
        self.max_source_age, self.plan_hash = max_source_age, plan_hash

    def think(self, step, context):
        try:
            if step["stepKey"] != "solution-design" or context["runRef"] != self.task_run_id or context["planContentHash"] != self.plan_hash:
                raise ValueError("stage context drifted")
            with self.worker._connect(self.scope) as conn:
                decision = require_growth_plan_sources(conn, self.scope, self.command.decision_ref,
                    markings=self.markings, now=self.clock(), max_source_age=self.max_source_age)
            if (AnalystExactRef.model_validate(context["step:diagnosis"]["decisionRef"]) != self.command.decision_ref
                    or AnalystExactRef.model_validate(context["step:portrait"]["insightRef"]) != decision.insight_ref):
                raise ValueError("predecessor source drifted")
            return {"attemptId": self.command.attempt_id, "generationCommandHash": canonical_hash(self.command.model_dump(mode="json", by_alias=True))}
        except Exception:
            raise AipTaskTransitionBlocked("D03 predecessor evidence or current planning inputs are not usable") from None

    def act(self, step, thought):
        try:
            self.worker._lineage(self.scope, self.task_run_id, self.agent_run_id, self.command)
            ref = self.worker._generation.generate(self.scope, self.agent_run_id, self.command,
                actor=self.actor, markings=self.markings, now=self.clock(), max_source_age=self.max_source_age)
            return {"growthPlanRef": ref.model_dump(mode="json", by_alias=True)}
        except Exception:
            # Keep the original attempt for recovery. Do not flatten an unknown
            # outcome into the runner's generic failed/retryable adapter path.
            raise AipTaskTransitionBlocked("D03 generation outcome requires recovery; do not resubmit") from None

    def verify(self, step, action):
        try:
            ref = AnalystExactRef.model_validate(action["growthPlanRef"])
            plan = self.worker._plans.get_plan_exact(self.scope, ref)
            if (ref.resource_type != "GrowthPlanRevision" or ref.revision != 1 or plan.plan_id != ref.resource_id
                    or plan.lifecycle.value != "draft" or plan.decision_ref != self.command.decision_ref
                    or plan.budget != self.command.plan_budget or plan.created_by != self.actor
                    or plan.generation_artifact_ref is None
                    or plan.content_hash != canonical_hash(plan.model_dump(mode="json", by_alias=True, exclude={"content_hash"}))):
                raise ValueError("draft output drifted")
            return {"passed": True, "growthPlanRef": action["growthPlanRef"]}
        except Exception:
            raise AipTaskTransitionBlocked("D03 formal draft verification failed; recovery required") from None

    def observe(self, step, action, verification):
        return {"growthPlanRef": verification["growthPlanRef"], "artifacts": []}
