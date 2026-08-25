from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.aip_agent_registry_contracts import AgentInstance, VersionedAssetRef
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_workshop_handoff_contracts import ModuleHandoffCompileRequest
from aos_api.ecommerce_workshop_handoff_service import (
    ModuleHandoffCompiler,
    ModuleHandoffCompilerDrift,
)
from aos_api.ecommerce_workshop_task_cockpit_contracts import (
    TaskCockpitAssigneeResolutionReceipt,
    TaskCockpitResponsibilityHandoffEnvelope,
    TaskCockpitResponsibilitySlot,
    TaskCockpitStructuralAssignee,
)
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_workshop
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 25, 1, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
HASH = "a" * 64


def _resource(kind: str, value: str, revision: str = "1") -> ResourceRef:
    return ResourceRef(resourceType=kind, resourceId=value, revision=revision, authority="postgresql")


def _instance(value: str, revision: int) -> VersionedAssetRef:
    return VersionedAssetRef(
        assetType="AgentInstance", assetId=value, revision=revision, contentHash=HASH
    )


def _slot(slot_id: str, instance_id: str, revision: int, *, ready: bool = True) -> TaskCockpitResponsibilitySlot:
    receipts = []
    if ready:
        receipts = [
            TaskCockpitAssigneeResolutionReceipt(
                receiptId=f"receipt-{slot_id}",
                subjectId=f"responsibility-plan:responsibility-1@1/slot:{slot_id}",
                kind="agent_instance",
                resourceId=instance_id,
                version=revision,
                status="resolved",
                blockerCodes=[],
                contentHash=HASH,
                snapshotHash="b" * 64,
                expiresAt=NOW + timedelta(minutes=5),
                requiredCapabilityCount=1,
                bindingCount=1,
                snapshotStatus="exact_fresh",
                createdAt=NOW - timedelta(minutes=5),
            )
        ]
    return TaskCockpitResponsibilitySlot(
        slotId=slot_id,
        responsibilityType="maker",
        requiredCapabilityIds=[f"capability.{slot_id}"],
        returnStage="review",
        assignee=TaskCockpitStructuralAssignee(
            kind="agent_instance",
            resourceId=instance_id,
            version=revision,
            operationalReadiness="resolved_at_observation" if ready else "unverified",
            resolutionReceipts=receipts,
        ),
    )


def _responsibility(*, org_id: str = "org-org", receiver_ready: bool = True) -> TaskCockpitResponsibilityHandoffEnvelope:
    slots = [
        _slot("content.owner", "agent-source", 2),
        _slot("content.review", "agent-target", 3, ready=receiver_ready),
    ]
    return TaskCockpitResponsibilityHandoffEnvelope(
        tenant=TenantContext(orgId=org_id, projectId="dev-project"),
        runId="run-1",
        taskId="task-1",
        evaluatedAt=NOW,
        responsibilityPlanRef=ExactRevisionRef(
            resourceType="ResponsibilityPlanRevision",
            resourceId="responsibility-1",
            revision=1,
            contentHash=HASH,
        ),
        profile="standard",
        lifecycle="frozen",
        compiledRequiredSlotIds=[item.slot_id for item in slots],
        slots=slots,
        handoffs=[],
    )


class FakeCatalog:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_readiness(self, **kwargs):
        self.calls.append(kwargs)
        return object()


class FakeCockpit:
    def __init__(self, value: TaskCockpitResponsibilityHandoffEnvelope) -> None:
        self.value = value

    def read_responsibility_handoffs(self, **kwargs):
        return self.value


class FakeInstances:
    def __init__(self, *, target_status: str = "active", target_revision: int = 3) -> None:
        self.target_status = target_status
        self.target_revision = target_revision

    def get_instance(self, scope: TenantScope, instance_id: str) -> AgentInstance:
        revision = 2 if instance_id == "agent-source" else self.target_revision
        return AgentInstance(
            tenant=TenantContext(orgId=scope.org_id, projectId=scope.project_id),
            instanceId=instance_id,
            instanceRef=_instance(instance_id, revision),
            template=_instance(f"template-{instance_id}", 1).model_copy(update={"asset_type": "AgentTemplate"}),
            status="active" if instance_id == "agent-source" else self.target_status,
            overlay={"displayName": None, "allowedCapabilityIds": []},
            version=revision,
            createdBy="system",
            createdAt=NOW - timedelta(days=1),
            updatedAt=NOW - timedelta(minutes=1),
        )


def _body() -> ModuleHandoffCompileRequest:
    return ModuleHandoffCompileRequest(
        handoffId="handoff-1",
        taskRef=_resource("Task", "task-1", "4"),
        runRef=_resource("TaskRun", "run-1", "7"),
        sourceModuleId="ecommerce.content-campaign",
        targetModuleId="ecommerce.media-studio",
        sourceSlotId="content.owner",
        targetSlotId="content.review",
        purpose="independent review",
        requestedOutcome="return a governed review decision",
        objectRefs=[_resource("Case", "case-1")],
        context={"summary": "safe summary"},
        allowedContextFields=["summary"],
        markings=["public"],
        expiresAt=NOW + timedelta(minutes=20),
    )


def _compiler(*, receiver_ready: bool = True, org_id: str = "org-org", target_status: str = "active", target_revision: int = 3) -> tuple[ModuleHandoffCompiler, FakeCatalog]:
    catalog = FakeCatalog()
    return (
        ModuleHandoffCompiler(
            cockpit=FakeCockpit(_responsibility(org_id=org_id, receiver_ready=receiver_ready)),
            catalog=catalog,  # type: ignore[arg-type]
            instances=FakeInstances(target_status=target_status, target_revision=target_revision),
            now=lambda: NOW,
        ),
        catalog,
    )


def test_compiles_one_canonical_issue_command_without_side_effects() -> None:
    compiler, catalog = _compiler()
    result = compiler.compile(
        SCOPE, "run-1", _body(), roles=["developer"], principal_markings=["public"]
    )

    assert result.readiness == "ready"
    assert result.issue_command is not None
    assert result.issue_command.envelope.task_ref.revision == "4"
    assert result.issue_command.envelope.run_ref.revision == "7"
    assert result.issue_command.envelope.context["sourceModuleId"] == "ecommerce.content-campaign"
    assert result.issue_command.envelope.context["requestedOutcome"] == "return a governed review decision"
    assert result.issue_command.envelope.allowed_context_fields == [
        "summary",
        "sourceModuleId",
        "targetModuleId",
        "sourceSlotId",
        "targetSlotId",
        "purpose",
        "requestedOutcome",
    ]
    assert result.side_effects.model_dump() == {
        "handoffs_issued": 0,
        "tokens_minted": 0,
        "decisions_created": 0,
        "agent_runs_started": 0,
    }
    assert [call["module_id"] for call in catalog.calls] == [
        "ecommerce.content-campaign",
        "ecommerce.media-studio",
    ]


def test_unverified_receiver_returns_blocker_and_no_command() -> None:
    compiler, _ = _compiler(receiver_ready=False)
    result = compiler.compile(
        SCOPE, "run-1", _body(), roles=["developer"], principal_markings=["public"]
    )
    assert result.readiness == "blocked"
    assert result.issue_command is None
    assert [item.code for item in result.blockers] == ["HANDOFF_RECEIVER_NOT_OPERATIONAL"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda body: body.model_copy(update={"run_ref": _resource("TaskRun", "run-other")}), "Task/TaskRun"),
        (lambda body: body.model_copy(update={"markings": ["restricted"]}), "markings"),
    ],
)
def test_exact_identity_and_disclosure_drift_fail_closed(mutation, message: str) -> None:
    compiler, _ = _compiler()
    with pytest.raises(ModuleHandoffCompilerDrift, match=message):
        compiler.compile(
            SCOPE,
            "run-1",
            mutation(_body()),
            roles=["developer"],
            principal_markings=["public"],
        )


def test_cross_tenant_projection_fails_closed() -> None:
    compiler, _ = _compiler(org_id="dev-org")
    with pytest.raises(ModuleHandoffCompilerDrift, match="tenant"):
        compiler.compile(
            SCOPE, "run-1", _body(), roles=["developer"], principal_markings=["public"]
        )


def test_instance_revision_drift_fails_closed() -> None:
    compiler, _ = _compiler(target_revision=4)
    with pytest.raises(ModuleHandoffCompilerDrift, match="AgentInstance"):
        compiler.compile(
            SCOPE, "run-1", _body(), roles=["developer"], principal_markings=["public"]
        )


def test_inactive_instance_blocks_without_emitting_command() -> None:
    compiler, _ = _compiler(target_status="suspended")
    result = compiler.compile(
        SCOPE, "run-1", _body(), roles=["developer"], principal_markings=["public"]
    )
    assert result.readiness == "blocked"
    assert result.issue_command is None
    assert [item.code for item in result.blockers] == ["HANDOFF_RECEIVER_INSTANCE_NOT_ACTIVE"]


def test_http_compile_surface_is_explicit_and_compile_only() -> None:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(ecommerce_workshop.router)
    compiler, catalog = _compiler()
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:dev",
        org_id="org-org",
        project_id="dev-project",
        roles=["developer"],
        markings=["public"],
    )
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_workshop_catalog] = lambda: catalog
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_workshop_handoff_compiler] = lambda: compiler
    client = TestClient(app)

    response = client.post(
        "/v1/ecommerce-workshop/views/task-cockpit/runs/run-1/handoffs/compile",
        headers={"Authorization": "Bearer dev", "X-Org-Id": "org-org", "X-Project-Id": "dev-project"},
        json=_body().model_dump(mode="json", by_alias=True),
    )
    assert response.status_code == 200
    assert response.json()["readiness"] == "ready"
    assert response.json()["sideEffects"] == {
        "handoffsIssued": 0,
        "tokensMinted": 0,
        "decisionsCreated": 0,
        "agentRunsStarted": 0,
    }
    path = app.openapi()["paths"]
    assert "/v1/ecommerce-workshop/views/task-cockpit/runs/{run_id}/handoffs/compile" in path
