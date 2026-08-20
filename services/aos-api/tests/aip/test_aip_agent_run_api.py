from datetime import UTC, datetime

from aos_api.aip_agent_registry_contracts import AgentRun, RegistryReceipt, VersionedAssetRef
from aos_api.aip_agent_run_execution_contracts import (
    AgentRunExecutionAttempt,
    AgentRunExecutionStatus,
    ExecuteAgentRunResponse,
)
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.routers import aip_agent_runs


NOW = datetime(2026, 8, 17, tzinfo=UTC)
HASH = "a" * 64


def headers(org_id: str = "org-org", **extra: str) -> dict[str, str]:
    return {"Authorization":"Bearer dev","X-Org-Id":org_id,"X-Project-Id":"dev-project",**extra}


def asset(kind: str, value: str):
    return VersionedAssetRef(assetType=kind, assetId=value, revision=1, contentHash=HASH)


def attempt(org_id: str) -> AgentRunExecutionAttempt:
    return AgentRunExecutionAttempt(
        tenant=TenantContext(orgId=org_id, projectId="dev-project"), attemptId="attempt-1",
        agentRunId="run-1", agentRunVersion=1, attemptNo=1,
        routeRef=asset("ModelRouteRevision","route-1"), policyRef=asset("RuntimePolicyRevision","policy-1"),
        modelRef=asset("RegisteredModelRevision","model-1"), providerRef=asset("ProviderInstanceRevision","provider-1"),
        priceSnapshotRef=asset("ModelPriceSnapshotRevision","price-1"), budgetRef=asset("BudgetRevision","budget-1"),
        capacityReservationRef=ResourceRef(resourceType="CapacityReservation",resourceId="cap-1",revision="1",authority="postgresql"),
        dataClassification="internal", lineageId="lineage-1", requestHash="b"*64,
        status="prepared", version=1, preparedAt=NOW, createdBy="user:dev", updatedAt=NOW,
    )


def receipt(org_id: str) -> RegistryReceipt:
    return RegistryReceipt(
        tenant=TenantContext(orgId=org_id,projectId="dev-project"), receiptId="receipt-1",
        operation="agent_run_execution_attempt.create", idempotencyKey="idem-1", requestHash="c"*64,
        resourceRef=ResourceRef(resourceType="AgentRun",resourceId="run-1",authority="postgresql"),
        resultRef=ResourceRef(resourceType="AgentRunExecutionAttempt",resourceId="attempt-1",authority="postgresql"),
        status="applied", createdBy="user:dev", createdAt=NOW,
    )


class Service:
    def __init__(self): self.scope=None
    def get(self, scope, attempt_id): self.scope=scope; return attempt(scope.org_id)
    def list(self, scope, *, agent_run_id, limit): self.scope=scope; return [attempt(scope.org_id)]


def agent_run(org_id: str) -> AgentRun:
    return AgentRun(
        tenant=TenantContext(orgId=org_id, projectId="dev-project"),
        agentRunId="run-1", taskId="task-1", taskRunId="task-run-1",
        instanceId="instance-1", instanceVersion=1, skillBindingId="binding-1",
        request={
            "taskRef": ResourceRef(resourceType="Task",resourceId="task-1",revision="1",authority="postgresql"),
            "planRef": ResourceRef(resourceType="PlanRevision",resourceId="plan-1",revision="1",authority="postgresql"),
            "agentInstance": asset("AgentInstance","instance-1"),
            "skill": asset("SkillTemplate","skill-1"),
            "logic": asset("LogicRevision","logic-1"),
            "modelRoute": asset("ModelRouteRevision","route-1"),
            "policy": asset("RuntimePolicyRevision","policy-1"),
            "inputRefs": [],
        },
        status="succeeded", version=3, createdAt=NOW, updatedAt=NOW,
    )


class Executor:
    def __init__(self): self.scope=None; self.body=None
    def execute(self, scope, agent_run_id, body, **kwargs):
        self.scope=scope; self.body=body
        return ExecuteAgentRunResponse(
            tenant=TenantContext(orgId=scope.org_id,projectId=scope.project_id),
            agentRun=agent_run(scope.org_id),
            attempt=attempt(scope.org_id).model_copy(
                update={"status":AgentRunExecutionStatus.SUCCEEDED}
            ),
            attemptReceipt=receipt(scope.org_id), answer="建议", replayed=False,
            lineageEventCount=2,
        )


def test_read_api_is_principal_scoped_and_canary_isolated(client) -> None:
    service = Service()
    client.app.dependency_overrides[aip_agent_runs.get_agent_run_execution_service] = lambda: service
    try:
        response = client.get("/v1/aip/agent-runs/execution-attempts/attempt-1", headers=headers())
        assert response.status_code == 200 and response.json()["tenant"]["orgId"] == "org-org"
        assert service.scope.key == ("org-org","dev-project")
        response = client.get("/v1/aip/agent-runs/execution-attempts/attempt-1", headers=headers("dev-org"))
        assert response.status_code == 200 and response.json()["tenant"]["orgId"] == "dev-org"
        assert service.scope.key == ("dev-org","dev-project")
    finally:
        client.app.dependency_overrides.pop(aip_agent_runs.get_agent_run_execution_service, None)


def test_write_requires_idempotency_header(client) -> None:
    response = client.post("/v1/aip/agent-runs/execution-attempts", headers=headers(), json={})
    assert response.status_code == 400


def test_execute_api_is_principal_scoped_and_uses_canonical_executor(client) -> None:
    executor = Executor()
    client.app.dependency_overrides[aip_agent_runs.get_agent_run_executor] = lambda: executor
    body = {
        "expectedAgentRunVersion":2, "attemptId":"attempt-1", "attemptNo":1,
        "budgetRef":asset("BudgetRevision","budget-1").model_dump(mode="json",by_alias=True),
        "capacityReservationRef":ResourceRef(resourceType="CapacityReservation",resourceId="cap-1",revision="1",authority="postgresql").model_dump(mode="json",by_alias=True),
        "query":"生成建议", "systemPrompt":"不要调用工具", "dataClassification":"internal",
    }
    try:
        response = client.post(
            "/v1/aip/agent-runs/run-1/execute",
            headers=headers(**{"Idempotency-Key":"idem-1"}), json=body,
        )
        assert response.status_code == 200
        assert response.json()["attempt"]["status"] == "succeeded"
        assert response.json()["lineageEventCount"] == 2
        assert executor.scope.key == ("org-org","dev-project")
        assert executor.body.query == "生成建议"
        response = client.post(
            "/v1/aip/agent-runs/run-1/execute",
            headers=headers("dev-org", **{"Idempotency-Key":"idem-canary"}), json=body,
        )
        assert response.status_code == 200
        assert response.json()["tenant"]["orgId"] == "dev-org"
        assert executor.scope.key == ("dev-org","dev-project")
    finally:
        client.app.dependency_overrides.pop(aip_agent_runs.get_agent_run_executor, None)


def test_openapi_registers_execution_attempt_authority(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/aip/agent-runs/execution-attempts" in paths
    assert "/v1/aip/agent-runs/execution-attempts/{attempt_id}" in paths
    assert "/v1/aip/agent-runs/execution-attempts/{attempt_id}/transition" in paths
    assert "/v1/aip/agent-runs/{agent_run_id}/execute" in paths
    assert "/v1/aip/agent-runs" in paths
    assert "/v1/aip/agent-runs/{agent_run_id}" in paths


class AgentRunAuthority:
    def __init__(self) -> None:
        self.scope = None

    def create(self, scope, request, *, idempotency_key, actor, occurred_at):
        self.scope = scope
        return agent_run(scope.org_id), receipt(scope.org_id)

    def get(self, scope, agent_run_id):
        self.scope = scope
        return agent_run(scope.org_id)


def test_agent_run_create_get_are_principal_scoped(client) -> None:
    service = AgentRunAuthority()
    client.app.dependency_overrides[aip_agent_runs.get_agent_run_service] = lambda: service
    body = {
        "agentRunId": "run-1",
        "taskRunRef": ResourceRef(resourceType="TaskRun", resourceId="task-run-1", revision="1", authority="postgresql").model_dump(mode="json", by_alias=True),
        "skillBindingId": "binding-1",
        "run": agent_run("org-org").request.model_dump(mode="json", by_alias=True)
        if hasattr(agent_run("org-org").request, "model_dump")
        else {
            "taskRef": ResourceRef(resourceType="Task", resourceId="task-1", revision="1", authority="postgresql").model_dump(mode="json", by_alias=True),
            "planRef": ResourceRef(resourceType="PlanRevision", resourceId="plan-1", revision="1", authority="postgresql").model_dump(mode="json", by_alias=True),
            "agentInstance": asset("AgentInstance", "instance-1").model_dump(mode="json", by_alias=True),
            "skill": asset("SkillTemplate", "skill-1").model_dump(mode="json", by_alias=True),
            "logic": asset("LogicRevision", "logic-1").model_dump(mode="json", by_alias=True),
            "modelRoute": asset("ModelRouteRevision", "route-1").model_dump(mode="json", by_alias=True),
            "policy": asset("RuntimePolicyRevision", "policy-1").model_dump(mode="json", by_alias=True),
            "inputRefs": [],
        },
    }
    try:
        created = client.post("/v1/aip/agent-runs", headers=headers(**{"Idempotency-Key": "create-1"}), json=body)
        assert created.status_code == 201
        assert created.json()["agentRun"]["agentRunId"] == "run-1"
        assert service.scope.key == ("org-org", "dev-project")
        got = client.get("/v1/aip/agent-runs/run-1", headers=headers())
        assert got.status_code == 200 and got.json()["agentRunId"] == "run-1"
        # static execution-attempts path must not be stolen by /{agent_run_id}
        listed = client.get("/v1/aip/agent-runs/execution-attempts", headers=headers())
        assert listed.status_code == 200
    finally:
        client.app.dependency_overrides.pop(aip_agent_runs.get_agent_run_service, None)
