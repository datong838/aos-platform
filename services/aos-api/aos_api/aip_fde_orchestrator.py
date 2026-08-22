"""FDE S1-S3 planning and deterministic execution on canonical AIP Task runtime."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from aos_api.aip_contracts import PlanStep, ResourceRef, TenantContext
from aos_api.aip_fde_assets import FdeAdapterPackInspector
from aos_api.aip_fde_contracts import (
    FdeIntakeRequest,
    FdeSessionCreated,
    FdeSessionPreview,
    FdeStepEvidence,
    FdeStepStatus,
)
from aos_api.aip_task_models import CreatePlanRevisionRequest, CreateTaskRequest
from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked
from aos_api.tenant_scope import TenantScope

_KNOWN_PLATFORMS = {"niushop"}
_CAPABILITY_REVISIONS = {
    "fde.s1.requirement": "1.0.0",
    "fde.s2.auth-draft": "1.0.0",
    "fde.s3.capability-probe": "1.0.0",
}


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _evidence(
    step_key: str,
    status: FdeStepStatus,
    artifact_type: str,
    summary: str,
    blocker_codes: list[str],
    facts: dict[str, Any],
) -> FdeStepEvidence:
    content_hash = _hash(
        {"stepKey": step_key, "status": status.value, "artifactType": artifact_type, "blockerCodes": blocker_codes, "facts": facts}
    )
    return FdeStepEvidence(
        step_key=step_key,
        status=status,
        artifact_type=artifact_type,
        artifact_ref=f"evidence://fde/{step_key}/{content_hash}",
        content_hash=content_hash,
        summary=summary,
        blocker_codes=blocker_codes,
        facts=facts,
    )


class FdeS1S3Orchestrator:
    def __init__(self, inspector: FdeAdapterPackInspector | None = None) -> None:
        self._inspector = inspector or FdeAdapterPackInspector()

    def preview(self, scope: TenantScope, intake: FdeIntakeRequest) -> FdeSessionPreview:
        s1 = self._s1(intake)
        s2 = self._s2(intake)
        s3 = self._s3(intake)
        steps = [s1, s2, s3]
        statuses = {step.status for step in steps}
        if FdeStepStatus.BLOCKED in statuses:
            status = FdeStepStatus.BLOCKED
        elif FdeStepStatus.PAUSED in statuses:
            status = FdeStepStatus.PAUSED
        elif FdeStepStatus.PARTIAL in statuses:
            status = FdeStepStatus.PARTIAL
        else:
            status = FdeStepStatus.EXTERNAL_REQUIRED
        plan_hash = _hash([step.model_dump(mode="json", by_alias=True) for step in steps])
        return FdeSessionPreview(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            status=status,
            executable=status is FdeStepStatus.EXTERNAL_REQUIRED,
            plan_hash=plan_hash,
            steps=steps,
        )

    def create_session(
        self,
        store: AipTaskStore,
        scope: TenantScope,
        actor: str,
        idempotency_key: str,
        intake: FdeIntakeRequest,
    ) -> FdeSessionCreated:
        preview = self.preview(scope, intake)
        if not preview.executable:
            raise AipTaskTransitionBlocked("FDE preview is blocked or paused")
        intake_payload = intake.model_dump(mode="json", by_alias=True)
        task = store.create_task(
            scope,
            actor,
            f"{idempotency_key}:task",
            CreateTaskRequest(
                type="fde_platform_onboarding",
                title=f"FDE 接入 · {intake.platform}",
                description="FDE S1-S3 canonical onboarding plan",
                priority=60,
                goal={"fdeIntake": intake_payload, "previewHash": preview.plan_hash},
                policy_revision="fde-s1-s3@1.0.0",
            ),
        )
        plan = store.create_plan(
            scope,
            actor,
            task.id,
            f"{idempotency_key}:plan",
            CreatePlanRevisionRequest(
                expected_task_version=1,
                steps=self._plan_steps(intake),
                dependencies=[
                    {
                        "resourceType": "PlatformAdapterPack",
                        "resourceId": intake.adapter_pack_ref,
                        "authority": "AOS Asset Registry",
                    }
                ],
                risk={"sideEffect": False, "secretPayload": False, "externalCall": False},
            ),
        )
        return FdeSessionCreated(preview=preview, task=store.get_task(scope, task.id), plan=plan)

    def step(self, step_key: str, intake: FdeIntakeRequest) -> FdeStepEvidence:
        if step_key == "fde.s1.requirement":
            return self._s1(intake)
        if step_key == "fde.s2.auth-draft":
            return self._s2(intake)
        if step_key == "fde.s3.capability-probe":
            return self._s3(intake)
        raise ValueError(f"unsupported FDE step: {step_key}")

    @staticmethod
    def _plan_steps(intake: FdeIntakeRequest) -> list[PlanStep]:
        adapter_ref = ResourceRef(
            resource_type="PlatformAdapterPack",
            resource_id=intake.adapter_pack_ref,
            revision="1.0.0",
            authority="AOS Asset Registry",
        )
        return [
            PlanStep(
                step_key=step_key,
                title=title,
                capability_ref=ResourceRef(
                    resource_type="CapabilityRevision",
                    resource_id=step_key,
                    revision=_CAPABILITY_REVISIONS[step_key],
                    authority="AIP Capability Registry",
                ),
                input_refs=[adapter_ref],
            )
            for step_key, title in (
                ("fde.s1.requirement", "S1 需求理解"),
                ("fde.s2.auth-draft", "S2 认证草案"),
                ("fde.s3.capability-probe", "S3 能力与 Schema 只读探测"),
            )
        ]

    @staticmethod
    def _s1(intake: FdeIntakeRequest) -> FdeStepEvidence:
        blockers: list[str] = []
        if intake.platform not in _KNOWN_PLATFORMS:
            blockers.append("FDE_PLATFORM_UNKNOWN")
        status = FdeStepStatus.PAUSED if blockers else FdeStepStatus.READY
        facts = {
            "platform": intake.platform,
            "dataTypes": intake.data_types,
            "syncFrequency": intake.sync_frequency,
            "merchantRef": intake.merchant_ref,
            "confidence": 1.0 if not blockers else 0.0,
            "clarifications": ["请选择已登记的平台 AdapterPack"] if blockers else [],
        }
        return _evidence("fde.s1.requirement", status, "FdeRequirementArtifact", "需求已确定性规范化" if not blockers else "平台尚未登记", blockers, facts)

    @staticmethod
    def _s2(intake: FdeIntakeRequest) -> FdeStepEvidence:
        blockers = [] if intake.secret_ref else ["FDE_SECRET_REF_REQUIRED"]
        status = FdeStepStatus.EXTERNAL_REQUIRED if not blockers else FdeStepStatus.BLOCKED
        facts = {
            "platform": intake.platform,
            "authScheme": intake.auth_scheme or "platform_default",
            "secretRef": intake.secret_ref,
            "secretVersion": intake.secret_version,
            "approvalRequired": True,
            "connectivity": "not_tested",
        }
        return _evidence("fde.s2.auth-draft", status, "FdeAuthConfigDraftArtifact", "仅生成 opaque secretRef 认证草案" if not blockers else "缺少 opaque secretRef", blockers, facts)

    def _s3(self, intake: FdeIntakeRequest) -> FdeStepEvidence:
        snapshot = self._inspector.inspect(intake.adapter_pack_ref, intake.data_types)
        missing = list(snapshot.get("missingDataTypes") or [])
        blockers = ["FDE_ADAPTER_PACK_UNKNOWN"] if snapshot.get("packStatus") == "unknown" else []
        if missing:
            blockers.append("FDE_CAPABILITY_MAPPING_INCOMPLETE")
        if blockers:
            status = FdeStepStatus.PARTIAL if snapshot.get("packStatus") == "probed" else FdeStepStatus.BLOCKED
        else:
            status = FdeStepStatus.EXTERNAL_REQUIRED
            blockers = ["FDE_LIVE_PROBE_REQUIRED"]
        facts = {**snapshot, "onlineVerification": "not_started", "secretPayloadRead": False}
        return _evidence("fde.s3.capability-probe", status, "FdeCapabilitySnapshotArtifact", "AdapterPack 文件证据已探测；线上能力仍需独立授权" if status is FdeStepStatus.EXTERNAL_REQUIRED else "AdapterPack 能力不完整", blockers, facts)


class FdeS1S3Adapter:
    """CanonicalTaorAdapter implementation with no external side effects."""

    def __init__(self, orchestrator: FdeS1S3Orchestrator | None = None) -> None:
        self._orchestrator = orchestrator or FdeS1S3Orchestrator()

    @staticmethod
    def _intake(context: dict[str, Any]) -> FdeIntakeRequest:
        goal = context.get("taskGoal")
        if not isinstance(goal, dict) or not isinstance(goal.get("fdeIntake"), dict):
            raise ValueError("canonical Task goal does not contain fdeIntake")
        return FdeIntakeRequest.model_validate(goal["fdeIntake"])

    def think(self, step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        intake = self._intake(context)
        return {"stepKey": step["stepKey"], "platform": intake.platform, "externalCall": False}

    def act(self, step: dict[str, Any], thought: dict[str, Any]) -> dict[str, Any]:
        del thought
        raise RuntimeError("FDE adapter act requires the canonical execution context")

    def act_with_context(self, step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        evidence = self._orchestrator.step(step["stepKey"], self._intake(context))
        return evidence.model_dump(mode="json", by_alias=True)

    @staticmethod
    def verify(step: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
        del step
        status = action.get("status")
        return {
            "passed": status in {"ready", "external_required"},
            "message": "FDE step is blocked" if status not in {"ready", "external_required"} else "",
            "status": status,
        }

    @staticmethod
    def observe(step: dict[str, Any], action: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
        del verification
        return {
            "stepKey": step["stepKey"],
            "status": action["status"],
            "artifacts": [
                {
                    "type": action["artifactType"],
                    "ref": action["artifactRef"],
                    "contentHash": action["contentHash"],
                    "summary": action["summary"],
                }
            ],
        }
