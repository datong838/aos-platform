from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json

import pytest

from aos_api.aip_content_contracts import (
    ContentDraftReadinessDecision,
    ContentDraftRegisterRequest,
)
from aos_api.aip_content_draft_store import (
    AipContentDraftStore,
    ContentDraftRegistrationBlocked,
    ContentDraftRegistrationConflict,
)
from aos_api.tenant_scope import TenantScope


HASH = "a" * 64
SCOPE = TenantScope("org-org", "dev-project")


def exact(resource_type: str, resource_id: str) -> dict[str, object]:
    return {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": 1,
        "contentHash": HASH,
    }


def resource(resource_type: str, resource_id: str) -> dict[str, object]:
    return {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": "1",
        "authority": "pytest",
    }


def register_payload(prompt_hash: str = HASH) -> dict[str, object]:
    brief = exact("TaskBriefRevision", "brief-1")
    return {
        "readinessRequest": {
            "briefRef": brief,
            "pipeline": {
                "briefRef": brief,
                "stageTemplateRef": exact("StageTemplateRevision", "stage-1"),
                "responsibilityPlanRef": exact(
                    "ResponsibilityPlanRevision", "plan-1"
                ),
                "evalContractRef": exact("EvalContractRevision", "eval-1"),
                "modelRouteRef": exact("ModelRouteRevision", "route-1"),
                "runtimePolicyRef": exact("RuntimePolicyRevision", "policy-1"),
                "capabilityRefs": [
                    exact("CapabilityRevision", "content.generate")
                ],
                "toolBindingRefs": [],
                "budgetRef": exact("BudgetRevision", "budget-1"),
                "readiness": "ready",
                "blockers": [],
            },
            "taskRunRef": resource("TaskRun", "task-run-1"),
            "agentRunRef": resource("AgentRun", "agent-run-1"),
            "variantKey": "weapp-seed-copy-v1",
            "channel": "weapp",
        },
        "contentObject": {
            "contentRef": "aos-object://content/draft-1.md",
            "contentHash": HASH,
            "schemaRef": resource("Schema", "content-draft-v1"),
            "byteSize": 128,
            "mediaType": "text/markdown",
            "marking": ["internal"],
        },
        "promptHash": prompt_hash,
        "evidenceBundleRef": exact("EvidenceBundleRevision", "evidence-1"),
        "sourceAssets": [],
    }


class ReadyService:
    def evaluate(self, scope, _body) -> ContentDraftReadinessDecision:
        return ContentDraftReadinessDecision(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            readiness="ready",
            requestHash=HASH,
            dependencySnapshotHash=HASH,
            blockers=[],
            evaluatedAt=datetime.now(UTC),
        )


class VerifiedContentObject:
    def __init__(self) -> None:
        self.calls = 0

    def verify(self, scope, body) -> None:
        self.calls += 1
        assert scope.key == SCOPE.key
        assert body.content_object.content_ref.startswith("aos-object://")


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self) -> None:
        self.receipt = None
        self.artifact = None
        self.inserts: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0

    def execute(self, sql: str, params: tuple[object, ...]):
        if sql.startswith("SELECT request_hash"):
            return Result(self.receipt)
        if "FROM aip_task_run" in sql:
            return Result({"version": 1, "status": "running"})
        if "FROM aip_agent_run" in sql:
            return Result({"version": 1, "status": "running"})
        if sql.startswith("SELECT content_hash FROM aip_artifact"):
            return Result(self.artifact)
        if "INSERT INTO aip_artifact" in sql:
            self.inserts.append((sql, params))
            self.artifact = {"content_hash": params[9]}
            return Result(None)
        if "INSERT INTO aip_production_contract_receipt" in sql:
            self.inserts.append((sql, params))
            self.receipt = {
                "request_hash": params[5],
                "result_ref": json.loads(str(params[6])),
            }
            return Result(None)
        raise AssertionError(f"unexpected SQL: {sql}")

    def commit(self) -> None:
        self.commits += 1


def test_default_object_authority_fails_before_any_database_write() -> None:
    entered = False

    @contextmanager
    def forbidden_connect(_scope):
        nonlocal entered
        entered = True
        yield FakeConnection()

    store = AipContentDraftStore(
        forbidden_connect,
        readiness_service=ReadyService(),
    )
    with pytest.raises(ContentDraftRegistrationBlocked, match="OBJECT_AUTHORITY"):
        store.register(
            SCOPE,
            "executor",
            "draft-key-1",
            ContentDraftRegisterRequest.model_validate(register_payload()),
        )
    assert entered is False


def test_registration_writes_only_artifact_and_receipt_and_replays_idempotently() -> None:
    connection = FakeConnection()
    verifier = VerifiedContentObject()

    @contextmanager
    def connect_factory(scope):
        assert scope.key == SCOPE.key
        yield connection

    store = AipContentDraftStore(
        connect_factory,
        readiness_service=ReadyService(),
        content_verifier=verifier,
    )
    body = ContentDraftRegisterRequest.model_validate(register_payload())
    first = store.register(SCOPE, "executor", "draft-key-1", body)
    second = store.register(SCOPE, "executor", "draft-key-1", body)

    assert first == second
    assert first.draft.artifact_ref.artifact_type == "content_draft"
    assert first.draft.artifact_ref.content_hash == HASH
    assert first.content_ref == "aos-object://content/draft-1.md"
    assert len(connection.inserts) == 2
    assert connection.commits == 1
    assert verifier.calls == 2
    assert all(params[:2] == SCOPE.key for _, params in connection.inserts)
    artifact_params = connection.inserts[0][1]
    assert "aos-object://content/draft-1.md" in artifact_params
    assert not any("inline" in str(value).lower() for value in artifact_params)


def test_same_idempotency_key_with_different_payload_conflicts() -> None:
    connection = FakeConnection()

    @contextmanager
    def connect_factory(_scope):
        yield connection

    store = AipContentDraftStore(
        connect_factory,
        readiness_service=ReadyService(),
        content_verifier=VerifiedContentObject(),
    )
    store.register(
        SCOPE,
        "executor",
        "draft-key-1",
        ContentDraftRegisterRequest.model_validate(register_payload()),
    )
    with pytest.raises(ContentDraftRegistrationConflict, match="payload drifted"):
        store.register(
            SCOPE,
            "executor",
            "draft-key-1",
            ContentDraftRegisterRequest.model_validate(
                register_payload(prompt_hash="b" * 64)
            ),
        )
