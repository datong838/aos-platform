from __future__ import annotations

from datetime import datetime, timezone

from aos_api.aip_contracts import ActorRef
from aos_api.aip_fde_contracts import FdeIntakeRequest, FdeStepStatus
from aos_api.aip_fde_orchestrator import FdeS1S3Adapter, FdeS1S3Orchestrator
from aos_api.aip_task_models import PlanRevisionSnapshot, TaskSnapshot
from aos_api.public_contracts import TaskStatus
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def _intake(**overrides: object) -> FdeIntakeRequest:
    payload: dict[str, object] = {
        "requirement": "接入微商城订单与商品，只生成 S1-S6 计划",
        "platform": "niushop",
        "dataTypes": ["orders", "products"],
        "syncFrequency": "hourly",
        "secretRef": "keychain://aos/agnes-api-key",
        "secretVersion": "1",
    }
    payload.update(overrides)
    return FdeIntakeRequest.model_validate(payload)


def test_preview_is_deterministic_read_only_and_marks_live_probe_external() -> None:
    service = FdeS1S3Orchestrator()

    first = service.preview(SCOPE, _intake())
    second = service.preview(SCOPE, _intake())

    assert first.plan_hash == second.plan_hash
    assert first.tenant.org_id == "org-org"
    assert first.status is FdeStepStatus.EXTERNAL_REQUIRED
    assert first.executable is True
    assert [step.status for step in first.steps] == [
        FdeStepStatus.READY,
        FdeStepStatus.EXTERNAL_REQUIRED,
        FdeStepStatus.EXTERNAL_REQUIRED,
        FdeStepStatus.EXTERNAL_REQUIRED,
        FdeStepStatus.EXTERNAL_REQUIRED,
        FdeStepStatus.EXTERNAL_REQUIRED,
    ]
    assert first.steps[2].facts["onlineVerification"] == "not_started"
    assert first.steps[2].facts["secretPayloadRead"] is False
    assert {row["dataType"] for row in first.steps[2].facts["mappingRefs"]} == {
        "orders",
        "products",
    }


def test_preview_blocks_unknown_platform_and_incomplete_mapping() -> None:
    unknown = FdeS1S3Orchestrator().preview(
        SCOPE,
        _intake(platform="unknown", adapterPackRef="platform.ecommerce.unknown@1.0.0"),
    )
    incomplete = FdeS1S3Orchestrator().preview(
        SCOPE,
        _intake(dataTypes=["orders", "unsupported_type"]),
    )

    assert unknown.executable is False
    assert "FDE_PLATFORM_UNKNOWN" in unknown.steps[0].blocker_codes
    assert "FDE_ADAPTER_PACK_UNKNOWN" in unknown.steps[2].blocker_codes
    assert incomplete.status is FdeStepStatus.BLOCKED
    assert incomplete.executable is False
    assert incomplete.steps[2].facts["missingDataTypes"] == ["unsupported_type"]


def test_negative_canary_keeps_separate_tenant_context() -> None:
    preview = FdeS1S3Orchestrator().preview(
        TenantScope("dev-org", "dev-project"),
        _intake(),
    )

    assert preview.tenant.org_id == "dev-org"
    assert preview.tenant.project_id == "dev-project"


class _Store:
    def __init__(self) -> None:
        self.task_request = None
        self.plan_request = None
        now = datetime.now(timezone.utc)
        actor = ActorRef(actor_type="user", actor_id="pytest")
        self.task = TaskSnapshot(
            id="task-r19",
            type="fde_platform_onboarding",
            title="FDE 接入 · niushop",
            status=TaskStatus.PLANNING,
            priority=60,
            created_by=actor,
            created_at=now,
            current_plan_revision_id="plan-r19",
            version=2,
            description="FDE S1-S6 canonical onboarding plan",
            goal={},
            updated_at=now,
        )
        self.plan = PlanRevisionSnapshot(
            id="plan-r19",
            task_id="task-r19",
            revision=1,
            content_hash="a" * 64,
            steps=FdeS1S3Orchestrator._plan_steps(_intake()),
            created_at=now,
            approval_status="draft",
            created_by=actor,
        )

    def create_task(self, scope, actor, key, request):
        del scope, actor, key
        self.task_request = request
        return self.task

    def create_plan(self, scope, actor, task_id, key, request):
        del scope, actor, task_id, key
        self.plan_request = request
        return self.plan

    def get_task(self, scope, task_id):
        del scope, task_id
        return self.task.model_copy(update={"goal": self.task_request.goal})


def test_create_session_reuses_canonical_task_and_draft_plan_authority() -> None:
    store = _Store()

    created = FdeS1S3Orchestrator().create_session(
        store,
        SCOPE,
        "pytest",
        "r19-session",
        _intake(),
    )

    assert created.execution_authority == "not_approved_not_started"
    assert store.task_request.type == "fde_platform_onboarding"
    assert store.task_request.goal["fdeIntake"]["secretRef"].startswith("keychain://")
    assert store.plan_request.risk["sideEffect"] is False
    assert store.plan_request.risk["syncExecution"] == "not_authorized"
    assert [step.step_key for step in created.plan.steps] == [
        "fde.s1.requirement",
        "fde.s2.auth-draft",
        "fde.s3.capability-probe",
        "fde.s4.mapping-proposal",
        "fde.s5.controlled-sync",
        "fde.s6.validation",
    ]


def test_adapter_reads_intake_only_from_canonical_task_goal() -> None:
    intake = _intake()
    context = {
        "taskGoal": {
            "fdeIntake": intake.model_dump(mode="json", by_alias=True),
        }
    }
    adapter = FdeS1S3Adapter()
    step = {"stepKey": "fde.s1.requirement"}

    thought = adapter.think(step, context)
    action = adapter.act_with_context(step, context)

    assert thought == {
        "stepKey": "fde.s1.requirement",
        "platform": "niushop",
        "externalCall": False,
    }
    assert action["status"] == "ready"
    assert adapter.verify(step, action)["passed"] is True
