from datetime import UTC, datetime

from aos_api.aip_agent_registry_contracts import (
    AgentRun,
    AgentRunStatus,
    RegistryReceipt,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound
from aos_api.aip_agent_run_execution_contracts import (
    AgentRunExecutionAttempt,
    AgentRunExecutionStatus,
    ExecuteAgentRunRequest,
)
from aos_api.aip_agent_run_executor import AipAgentRunExecutor, AipAgentRunExecutorError
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 18, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
HASH = "a" * 64


def asset(kind: str, value: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        assetType=kind, assetId=value, revision=1, contentHash=HASH
    )


def resource(kind: str, value: str, revision: str = "1") -> ResourceRef:
    return ResourceRef(
        resourceType=kind,
        resourceId=value,
        revision=revision,
        authority="postgresql",
    )


def run(status: AgentRunStatus = AgentRunStatus.RUNNING, version: int = 2) -> AgentRun:
    return AgentRun(
        tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        agentRunId="run-1",
        taskId="task-1",
        taskRunId="task-run-1",
        instanceId="instance-1",
        instanceVersion=1,
        skillBindingId="skill-binding-1",
        request={
            "taskRef": resource("Task", "task-1"),
            "planRef": resource("PlanRevision", "plan-1"),
            "agentInstance": asset("AgentInstance", "instance-1"),
            "skill": asset("SkillTemplate", "skill-1"),
            "logic": asset("LogicRevision", "logic-1"),
            "modelRoute": asset("ModelRouteRevision", "route-1"),
            "policy": asset("RuntimePolicyRevision", "policy-1"),
            "inputRefs": [],
        },
        status=status,
        version=version,
        createdAt=NOW,
        updatedAt=NOW,
    )


def resolution(
    readiness: ModelRuntimeReadiness = ModelRuntimeReadiness.READY,
) -> ModelRouteResolution:
    selected = readiness is ModelRuntimeReadiness.READY
    return ModelRouteResolution(
        tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        route=asset("ModelRouteRevision", "route-1"),
        policy=asset("RuntimePolicyRevision", "policy-1"),
        readiness=readiness,
        selectedModel=asset("RegisteredModelRevision", "model-1") if selected else None,
        selectedProvider=asset("ProviderInstanceRevision", "provider-1") if selected else None,
        selectedPriceSnapshot=asset("ModelPriceSnapshotRevision", "price-1") if selected else None,
        blockerCodes=[] if selected else ["provider_health_stale"],
        resolvedAt=NOW,
    )


def execute_request() -> ExecuteAgentRunRequest:
    return ExecuteAgentRunRequest(
        expectedAgentRunVersion=2,
        attemptId="attempt-1",
        attemptNo=1,
        budgetRef=asset("BudgetRevision", "budget-1"),
        capacityReservationRef=resource("CapacityReservation", "capacity-1"),
        query="只基于给定事实生成一条运营建议",
        systemPrompt="不要调用工具",
        dataClassification="internal",
    )


def receipt() -> RegistryReceipt:
    return RegistryReceipt(
        tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        receiptId="receipt-1",
        operation="agent_run_execution_attempt.create",
        idempotencyKey="idem-1",
        requestHash="b" * 64,
        resourceRef=resource("AgentRun", "run-1"),
        resultRef=resource("AgentRunExecutionAttempt", "attempt-1"),
        status="applied",
        createdBy="pytest",
        createdAt=NOW,
    )


class RunService:
    def __init__(self) -> None:
        self.value = run()
        self.transitions: list[AgentRunStatus] = []

    def get(self, scope, agent_run_id):
        assert scope == SCOPE and agent_run_id == "run-1"
        return self.value

    def transition(self, scope, agent_run_id, *, expected_version, from_status, to_status, actor, occurred_at):
        assert expected_version == self.value.version
        assert from_status is AgentRunStatus.RUNNING
        self.transitions.append(to_status)
        self.value = self.value.model_copy(
            update={"status": to_status, "version": self.value.version + 1, "updated_at": occurred_at}
        )
        return self.value


class AttemptService:
    def __init__(self) -> None:
        self.value: AgentRunExecutionAttempt | None = None
        self.transitions: list[AgentRunExecutionStatus] = []

    def get(self, scope, attempt_id):
        assert scope == SCOPE and attempt_id == "attempt-1"
        if self.value is None:
            raise AipAgentRegistryNotFound("attempt not found")
        return self.value

    def create(self, scope, body, *, idempotency_key, actor, occurred_at):
        if self.value is None:
            self.value = AgentRunExecutionAttempt(
                tenant=TenantContext(orgId=scope.org_id, projectId=scope.project_id),
                attemptId=body.attempt_id,
                agentRunId=body.agent_run_ref.resource_id,
                agentRunVersion=int(body.agent_run_ref.revision),
                attemptNo=body.attempt_no,
                routeRef=body.route_ref,
                policyRef=body.policy_ref,
                modelRef=body.model_ref,
                providerRef=body.provider_ref,
                priceSnapshotRef=body.price_snapshot_ref,
                budgetRef=body.budget_ref,
                capacityReservationRef=body.capacity_reservation_ref,
                dataClassification=body.data_classification,
                lineageId=body.lineage_id,
                requestHash=body.request_hash,
                status="prepared",
                version=1,
                preparedAt=occurred_at,
                createdBy=actor,
                updatedAt=occurred_at,
            )
        return self.value, receipt()

    def transition(self, scope, attempt_id, body, *, idempotency_key, actor, occurred_at):
        assert self.value is not None and body.expected_version == self.value.version
        assert body.from_status is self.value.status
        self.transitions.append(body.to_status)
        self.value = self.value.model_copy(
            update={
                "status": body.to_status,
                "version": self.value.version + 1,
                "provider_receipt_id": body.provider_receipt_id,
                "usage_receipt_ids": body.usage_receipt_ids,
                "output_artifact_ref": body.output_artifact_ref,
                "reason_code": body.reason_code,
                "updated_at": occurred_at,
            }
        )
        return self.value, receipt()


class Resolver:
    def __init__(self, value=None) -> None:
        self.value = value or resolution()

    def resolve(self, scope, route_id):
        assert scope == SCOPE and route_id == "route-1"
        return self.value


class Llm:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def chat_exact(self, scope, route_id, query, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return {
            "answer": "建议优先跟进高意向客户。",
            "providerReceiptId": "provider-receipt-1",
            "usageReceiptIds": ["usage-1"],
        }


class Artifacts:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.payload = None

    def record_artifact(self, scope, run_id, actor, artifact_type, payload):
        if self.error:
            raise self.error
        self.payload = payload
        return "artifact-1"


class Lineage:
    @staticmethod
    def lineage_id(root_type, root_id):
        return f"lineage-{root_id}"

    def reconcile(self, scope, root_type, root_id):
        return ["event-1", "event-2"]


def executor(*, llm=None, artifacts=None, resolver_value=None):
    runs = RunService()
    attempts = AttemptService()
    llm = llm or Llm()
    artifacts = artifacts or Artifacts()
    value = AipAgentRunExecutor(
        run_service=runs,
        attempt_service=attempts,
        resolver=Resolver(resolver_value),
        llm_adapter=llm,
        artifact_store=artifacts,
        lineage_service=Lineage(),
    )
    return value, runs, attempts, llm, artifacts


def test_success_persists_only_answer_hash_and_exact_evidence() -> None:
    value, runs, attempts, llm, artifacts = executor()
    result = value.execute(
        SCOPE, "run-1", execute_request(), idempotency_key="idem-1",
        actor="pytest", occurred_at=NOW,
    )
    assert result.answer == "建议优先跟进高意向客户。"
    assert result.attempt.status is AgentRunExecutionStatus.SUCCEEDED
    assert result.agent_run.status is AgentRunStatus.SUCCEEDED
    assert result.lineage_event_count == 2 and llm.calls == 1
    assert artifacts.payload["contentRef"].startswith("sha256://")
    assert "建议优先" not in str(artifacts.payload)
    assert attempts.transitions == [
        AgentRunExecutionStatus.INVOKING,
        AgentRunExecutionStatus.SUCCEEDED,
    ]
    assert runs.transitions == [AgentRunStatus.SUCCEEDED]


def test_terminal_replay_never_invokes_provider_again() -> None:
    value, _, attempts, llm, _ = executor()
    first = value.execute(
        SCOPE, "run-1", execute_request(), idempotency_key="idem-1",
        actor="pytest", occurred_at=NOW,
    )
    second = value.execute(
        SCOPE, "run-1", execute_request(), idempotency_key="idem-1",
        actor="pytest", occurred_at=NOW,
    )
    assert first.attempt.status is AgentRunExecutionStatus.SUCCEEDED
    assert second.replayed and second.answer is None
    assert llm.calls == 1 and attempts.value.status is AgentRunExecutionStatus.SUCCEEDED


def test_invoking_replay_becomes_unknown_without_second_provider_call() -> None:
    value, runs, attempts, llm, _ = executor()
    request = execute_request()
    request_hash = value._request_hash("run-1", request)
    attempts.create(
        SCOPE,
        type("Body", (), {
            "attempt_id": "attempt-1", "agent_run_ref": resource("AgentRun", "run-1", "2"),
            "attempt_no": 1, "route_ref": asset("ModelRouteRevision", "route-1"),
            "policy_ref": asset("RuntimePolicyRevision", "policy-1"),
            "model_ref": asset("RegisteredModelRevision", "model-1"),
            "provider_ref": asset("ProviderInstanceRevision", "provider-1"),
            "price_snapshot_ref": asset("ModelPriceSnapshotRevision", "price-1"),
            "budget_ref": request.budget_ref,
            "capacity_reservation_ref": request.capacity_reservation_ref,
            "data_classification": "internal", "lineage_id": "lineage-task-run-1",
            "request_hash": request_hash,
        })(),
        idempotency_key="idem-1", actor="pytest", occurred_at=NOW,
    )
    attempts.value = attempts.value.model_copy(
        update={"status": AgentRunExecutionStatus.INVOKING, "version": 2}
    )
    result = value.execute(
        SCOPE, "run-1", request, idempotency_key="idem-1",
        actor="pytest", occurred_at=NOW,
    )
    assert result.attempt.status is AgentRunExecutionStatus.UNKNOWN
    assert result.attempt.reason_code == "INVOCATION_OUTCOME_UNPROVEN"
    assert llm.calls == 0 and runs.transitions == [AgentRunStatus.UNKNOWN]


def test_provider_error_after_invoking_is_unknown_not_retryable() -> None:
    value, runs, attempts, llm, _ = executor(llm=Llm(RuntimeError("transport")))
    result = value.execute(
        SCOPE, "run-1", execute_request(), idempotency_key="idem-1",
        actor="pytest", occurred_at=NOW,
    )
    assert result.attempt.status is AgentRunExecutionStatus.UNKNOWN
    assert result.attempt.reason_code == "PROVIDER_RESULT_UNKNOWN"
    assert llm.calls == 1 and runs.transitions == [AgentRunStatus.UNKNOWN]
    assert attempts.transitions[-1] is AgentRunExecutionStatus.UNKNOWN


def test_artifact_failure_preserves_provider_and_usage_refs_as_unknown() -> None:
    value, _, _, _, _ = executor(artifacts=Artifacts(RuntimeError("store")))
    result = value.execute(
        SCOPE, "run-1", execute_request(), idempotency_key="idem-1",
        actor="pytest", occurred_at=NOW,
    )
    assert result.attempt.status is AgentRunExecutionStatus.UNKNOWN
    assert result.attempt.reason_code == "ARTIFACT_WRITE_FAILED"
    assert result.attempt.provider_receipt_id == "provider-receipt-1"
    assert result.attempt.usage_receipt_ids == ["usage-1"]


def test_stale_preflight_blocks_before_attempt_and_provider() -> None:
    value, runs, attempts, llm, _ = executor(
        resolver_value=resolution(ModelRuntimeReadiness.BLOCKED)
    )
    try:
        value.execute(
            SCOPE, "run-1", execute_request(), idempotency_key="idem-1",
            actor="pytest", occurred_at=NOW,
        )
    except AipAgentRunExecutorError as exc:
        assert exc.reason_code == "provider_health_stale"
    else:
        raise AssertionError("blocked preflight must fail")
    assert attempts.value is None and llm.calls == 0
    assert runs.transitions == [AgentRunStatus.FAILED]


def test_unknown_attempt_write_failure_still_terminalizes_agent_run() -> None:
    class FailingUnknownAttemptService(AttemptService):
        def transition(self, scope, attempt_id, body, **kwargs):
            if body.to_status is AgentRunExecutionStatus.UNKNOWN:
                raise RuntimeError("attempt store unavailable")
            return super().transition(scope, attempt_id, body, **kwargs)

    runs = RunService()
    attempts = FailingUnknownAttemptService()
    llm = Llm(RuntimeError("transport"))
    value = AipAgentRunExecutor(
        run_service=runs,
        attempt_service=attempts,
        resolver=Resolver(),
        llm_adapter=llm,
        artifact_store=Artifacts(),
        lineage_service=Lineage(),
    )
    try:
        value.execute(
            SCOPE, "run-1", execute_request(), idempotency_key="idem-1",
            actor="pytest", occurred_at=NOW,
        )
    except AipAgentRunExecutorError as exc:
        assert exc.reason_code == "ATTEMPT_UNKNOWN_COMMIT_FAILED"
    else:
        raise AssertionError("unknown write failure must be visible")
    assert runs.transitions == [AgentRunStatus.UNKNOWN]
    assert llm.calls == 1
