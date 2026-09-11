"""Trusted D02 worker over canonical scheduling and governed generation.

No public route, AgentRun provisioning, automatic approval or model selection.
Callers provide scoped factories that open independent per-call connections.
"""
from datetime import timedelta

from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
from aos_api.aip_task_models import RunControlResult
from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked, _canonical_hash
from aos_api.aip_taor_loop import CanonicalTaorRunner
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
from aos_api.ecommerce_analyst_diagnosis_service import DiagnosisGenerationService
from aos_api.ecommerce_analyst_diagnosis_receiver import read_diagnosis_inputs
from aos_api.public_contracts import TaskStatus


def diagnosis_stage_attempt_id(scope, timeline) -> str:
    return "diagnosis-taor-" + canonical_hash({
        "tenant": scope.key, "taskRunId": timeline.run.id,
        "planRevisionId": timeline.plan.id, "planContentHash": timeline.plan.content_hash,
        "stepKey": "diagnosis",
    })[:40]


def require_diagnosis_stage_lineage(scope, timeline, agent_run, command) -> None:
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
        or request.skill.asset_type != "SkillTemplate" or request.skill.asset_id != "ecommerce.skill.D02"
        or command.attempt_id != diagnosis_stage_attempt_id(scope, timeline) or command.attempt_no != 1
    ):
        raise AipTaskTransitionBlocked("D02 task, plan, agent run or stable attempt lineage mismatch")
    completed = [x["step_key"] for x in timeline.steps if x.get("status") == "succeeded"]
    if completed != ["portrait"]:
        raise AipTaskTransitionBlocked("D02 requires completed portrait only")
    assignees = [ref for ref in plan.steps[1].assignee_refs if ref.resource_type == "AgentInstance"]
    instance = request.agent_instance
    if (len(assignees) != 1 or assignees[0].authority != "aip-assignee-directory"
            or (assignees[0].resource_id, assignees[0].revision) != (agent_run.instance_id, str(agent_run.instance_version))
            or instance.asset_type != "AgentInstance"
            or (instance.asset_id, instance.revision) != (agent_run.instance_id, agent_run.instance_version)):
        raise AipTaskTransitionBlocked("D02 agent instance does not match the approved stage assignee")


class DiagnosisTaorWorker:
    def __init__(self, connect_factory, executor):
        self._generation = DiagnosisGenerationService(connect_factory, executor)
        self._connect = connect_factory
        self._tasks = AipTaskStore(connect_factory=connect_factory)
        self._runs = AipAgentRunService(connect_factory)
        self._analyst = EcommerceAnalystAuthorityStore(connect_factory)
        self._attempts = AipAgentRunExecutionService(connect_factory)

    def _lineage(self, scope, task_run_id, agent_run_id, command):
        timeline = self._tasks.timeline(scope, task_run_id)
        agent_run = self._runs.get(scope, agent_run_id)
        if timeline.run.id != task_run_id or agent_run.agent_run_id != agent_run_id:
            raise AipTaskTransitionBlocked("D02 requested runtime identity mismatch")
        require_diagnosis_stage_lineage(scope, timeline, agent_run, command)
        return timeline

    def run(self, scope, task_run_id, agent_run_id, command, *, actor, worker_id,
            markings, clock, max_source_age: timedelta, max_bytes: int, lease_seconds=30) -> RunControlResult:
        if not callable(clock) or not actor.strip() or not worker_id.strip():
            raise ValueError("D02 worker requires clock, actor and worker identity")
        command = command.model_copy(deep=True)
        timeline = self._lineage(scope, task_run_id, agent_run_id, command)
        adapter = _DiagnosisAdapter(self, scope, task_run_id, agent_run_id, command,
                                    actor, list(markings), clock, max_source_age, max_bytes, timeline.plan.content_hash)
        return CanonicalTaorRunner(self._tasks).run(scope, task_run_id, actor=actor, worker_id=worker_id,
            adapter=adapter, lease_seconds=lease_seconds, renew_step_lease=True, stop_after_step="diagnosis")


class _DiagnosisAdapter:
    def __init__(self, worker, scope, task_run_id, agent_run_id, command, actor, markings, clock, max_source_age, max_bytes, plan_hash):
        self.worker, self.scope = worker, scope
        self.task_run_id, self.agent_run_id, self.command = task_run_id, agent_run_id, command
        self.actor, self.markings, self.clock = actor, markings, clock
        self.max_source_age, self.plan_hash, self.max_bytes = max_source_age, plan_hash, max_bytes

    def think(self, step, context):
        try:
            if step["stepKey"] != "diagnosis" or context["runRef"] != self.task_run_id or context["planContentHash"] != self.plan_hash:
                raise ValueError("stage context drifted")
            if AnalystExactRef.model_validate(context["step:portrait"]["insightRef"]) != self.command.insight_ref:
                raise ValueError("predecessor source drifted")
            run = self.worker._runs.get(self.scope, self.agent_run_id)
            with self.worker._connect(self.scope) as conn:
                read_diagnosis_inputs(conn=conn, scope=self.scope, insight_ref=self.command.insight_ref,
                    source_requests=self.command.source_requests, run=run, actor=self.actor, markings=self.markings,
                    now=self.clock(), max_source_age=self.max_source_age, max_bytes=self.max_bytes)
            return {"attemptId": self.command.attempt_id, "generationCommandHash": canonical_hash(self.command.model_dump(mode="json", by_alias=True))}
        except Exception:
            raise AipTaskTransitionBlocked("D02 predecessor evidence or current diagnosis inputs are not usable") from None

    def act(self, step, thought):
        try:
            self.worker._lineage(self.scope, self.task_run_id, self.agent_run_id, self.command)
            ref = self.worker._generation.generate(self.scope, self.agent_run_id, self.command,
                actor=self.actor, markings=self.markings, clock=self.clock, max_source_age=self.max_source_age, max_bytes=self.max_bytes)
            return {"decisionRef": ref.model_dump(mode="json", by_alias=True)}
        except Exception:
            # Keep the original attempt for recovery. Do not flatten an unknown
            # outcome into the runner's generic failed/retryable adapter path.
            raise AipTaskTransitionBlocked("D02 generation outcome requires recovery; do not resubmit") from None

    def verify(self, step, action):
        try:
            ref = AnalystExactRef.model_validate(action["decisionRef"])
            decision = self.worker._analyst.get_decision_exact(self.scope, ref)
            attempt = self.worker._attempts.get(self.scope, self.command.attempt_id)
            identity = canonical_hash({"tenant": {"orgId": self.scope.org_id, "projectId": self.scope.project_id},
                                       "attemptId": self.command.attempt_id})
            artifact = attempt.output_artifact_ref
            if (ref.resource_type != "DecisionSummaryRevision" or ref.revision != 1
                    or ref.resource_id != "diagnosis-" + identity[:40]
                    or decision.insight_ref != self.command.insight_ref or decision.created_by != self.actor
                    or attempt.agent_run_id != self.agent_run_id or attempt.status != "succeeded" or artifact is None
                    or decision.generation_artifact_ref != AnalystExactRef(resourceType="Artifact",
                        resourceId=artifact.artifact_id, revision=1, contentHash=artifact.content_hash)):
                raise ValueError("diagnosis output drifted")
            return {"passed": True, "decisionRef": action["decisionRef"]}
        except Exception:
            raise AipTaskTransitionBlocked("D02 formal diagnosis verification failed; recovery required") from None

    def observe(self, step, action, verification):
        return {"decisionRef": verification["decisionRef"], "artifacts": []}
