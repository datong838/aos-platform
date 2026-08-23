"""FDE S1-S6 planning and deterministic execution on canonical AIP Task runtime."""
from __future__ import annotations

import hashlib
import json
import re
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
from aos_api.aip_fde_reflection import RULE_SET_HASH, RULE_SET_REF, evaluate_reflection
from aos_api.aip_task_models import CreatePlanRevisionRequest, CreateTaskRequest
from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked
from aos_api.tenant_scope import TenantScope
from aos_api.source_readiness_contracts import SourceReadinessEnvelope, SourceReadinessStatus

_KNOWN_PLATFORMS = {"niushop"}
_CAPABILITY_REVISIONS = {
    "fde.s1.requirement": "1.0.0",
    "fde.s2.auth-draft": "1.0.0",
    "fde.s3.capability-probe": "1.0.0",
    "fde.s4.mapping-proposal": "1.0.0",
    "fde.s5.controlled-sync": "1.0.0",
    "fde.s6.validation": "1.0.0",
}


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _canonical_pipeline_id(prefix: str | None, object_type: str | None) -> str | None:
    if not prefix or not object_type:
        return None
    slug = re.sub(r"(?<!^)(?=[A-Z])", "-", object_type).lower()
    return f"{prefix}-{slug}-qyh"


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


class FdeS1S6Orchestrator:
    """Canonical six-skill FDE planner and evidence evaluator."""

    def __init__(
        self,
        inspector: FdeAdapterPackInspector | None = None,
        readiness: SourceReadinessEnvelope | None = None,
        execution_scope: TenantScope | None = None,
    ) -> None:
        self._inspector = inspector or FdeAdapterPackInspector()
        self._readiness = readiness
        self._execution_scope = execution_scope

    def preview(self, scope: TenantScope, intake: FdeIntakeRequest) -> FdeSessionPreview:
        s1 = self._s1(intake)
        s2 = self._s2(intake)
        s3 = self._s3(intake)
        s4 = self._s4(intake)
        s5 = self._s5(intake)
        s6 = self._s6(scope, intake)
        steps = [s1, s2, s3, s4, s5, s6]
        statuses = {step.status for step in steps}
        if FdeStepStatus.BLOCKED in statuses:
            status = FdeStepStatus.BLOCKED
        elif FdeStepStatus.PAUSED in statuses:
            status = FdeStepStatus.PAUSED
        elif FdeStepStatus.PARTIAL in statuses:
            status = FdeStepStatus.PARTIAL
        else:
            status = FdeStepStatus.EXTERNAL_REQUIRED
        plan_hash = _hash(
            {
                "steps": [step.model_dump(mode="json", by_alias=True) for step in steps],
                "reflectionRuleSetHash": RULE_SET_HASH,
            }
        )
        return FdeSessionPreview(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            status=status,
            executable=status is FdeStepStatus.EXTERNAL_REQUIRED,
            plan_hash=plan_hash,
            steps=steps,
            reflection_rule_set_ref=RULE_SET_REF,
            reflection_rule_set_hash=RULE_SET_HASH,
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
                description="FDE S1-S6 canonical onboarding plan",
                priority=60,
                goal={"fdeIntake": intake_payload, "previewHash": preview.plan_hash},
                policy_revision="fde-s1-s6@1.0.0",
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
                    },
                    {
                        "resourceType": "ReflectionRuleSet",
                        "resourceId": RULE_SET_REF,
                        "revision": "1.0.0",
                        "contentHash": RULE_SET_HASH,
                        "authority": "AIP Capability Registry",
                    },
                    {
                        "resourceType": "SourceReadinessEnvelope",
                        "resourceId": "canonical://data/source-readiness",
                        "authority": "Data/Adapter owner",
                        "requiredFor": "fde.s6.validation",
                    },
                ],
                risk={
                    "sideEffect": False,
                    "secretPayload": False,
                    "externalCall": False,
                    "syncExecution": "not_authorized",
                    "reflectionRuleSetHash": RULE_SET_HASH,
                },
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
        if step_key == "fde.s4.mapping-proposal":
            return self._s4(intake)
        if step_key == "fde.s5.controlled-sync":
            return self._s5(intake)
        if step_key == "fde.s6.validation":
            scope_payload = self._execution_scope
            if not isinstance(scope_payload, TenantScope):
                raise ValueError("S6 execution requires tenant scope")
            return self._s6(scope_payload, intake)
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
                ("fde.s4.mapping-proposal", "S4 字段映射提案"),
                ("fde.s5.controlled-sync", "S5 受控同步计划"),
                ("fde.s6.validation", "S6 验证、对账与回滚证据包"),
            )
        ]

    @staticmethod
    def _s1(intake: FdeIntakeRequest) -> FdeStepEvidence:
        blockers: list[str] = []
        if intake.platform not in _KNOWN_PLATFORMS:
            blockers.append("FDE_PLATFORM_UNKNOWN")
        status = FdeStepStatus.PAUSED if blockers else FdeStepStatus.READY
        facts = {
            "requirement": intake.requirement,
            "platform": intake.platform,
            "dataTypes": intake.data_types,
            "syncFrequency": intake.sync_frequency,
            "merchantRef": intake.merchant_ref,
            "confidence": 1.0 if not blockers else 0.0,
            "clarifications": ["请选择已登记的平台 AdapterPack"] if blockers else [],
            "inlineSecretDetected": False,
        }
        facts["reflection"] = evaluate_reflection("fde.s1.requirement", facts)
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
            "secretPayloadRead": False,
        }
        facts["reflection"] = evaluate_reflection("fde.s2.auth-draft", facts)
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
        facts["reflection"] = evaluate_reflection("fde.s3.capability-probe", facts)
        return _evidence("fde.s3.capability-probe", status, "FdeCapabilitySnapshotArtifact", "AdapterPack 文件证据已探测；线上能力仍需独立授权" if status is FdeStepStatus.EXTERNAL_REQUIRED else "AdapterPack 能力不完整", blockers, facts)

    def _s4(self, intake: FdeIntakeRequest) -> FdeStepEvidence:
        proposal = self._inspector.mapping_proposal(intake.adapter_pack_ref, intake.data_types)
        mappings = proposal.get("mappings") if isinstance(proposal.get("mappings"), list) else []
        conflicts = [
            {"dataType": row.get("dataType"), "targets": row.get("duplicateTargets")}
            for row in mappings
            if row.get("duplicateTargets")
        ]
        unsupported = sorted(
            {
                field.get("type")
                for row in mappings
                for field in row.get("fieldMappings", [])
                if field.get("type") not in proposal.get("allowedFieldTypes", [])
            }
        )
        coverage = min((float(row.get("coverage", 0.0)) for row in mappings), default=0.0)
        required_targets_present = bool(mappings) and all(row.get("primaryTarget") for row in mappings)
        reflection_context = {
            "coverage": coverage,
            "requiredTargetsPresent": required_targets_present,
            "mappingConflicts": conflicts,
            "unsupportedTypes": unsupported,
            "expressionExecution": proposal.get("expressionExecution"),
        }
        reflection = evaluate_reflection("fde.s4.mapping-proposal", reflection_context)
        hard_failures = [row["ruleKey"] for row in reflection if row["status"] == "failed"]
        blockers = list(proposal.get("blockers") or []) + [f"FDE_REFLECTION_FAILED:{key}" for key in hard_failures]
        if proposal.get("missingDataTypes"):
            blockers.append("FDE_MAPPING_DATA_TYPE_MISSING")
        status = FdeStepStatus.PARTIAL if blockers else FdeStepStatus.EXTERNAL_REQUIRED
        facts = {
            **proposal,
            "coverage": coverage,
            "requiredTargetsPresent": required_targets_present,
            "mappingConflicts": conflicts,
            "unsupportedTypes": unsupported,
            "reflection": reflection,
            "reflectionRuleSetRef": RULE_SET_REF,
            "reflectionRuleSetHash": RULE_SET_HASH,
            "onlineVerification": "not_started",
        }
        return _evidence(
            "fde.s4.mapping-proposal",
            status,
            "FdeMappingProposalArtifact",
            "静态字段映射提案已生成；待外部审批与线上验证" if not blockers else "字段映射提案未通过硬规则",
            sorted(set(blockers)),
            facts,
        )

    def _s5(self, intake: FdeIntakeRequest) -> FdeStepEvidence:
        proposal = self._inspector.mapping_proposal(intake.adapter_pack_ref, intake.data_types)
        mappings = proposal.get("mappings") if isinstance(proposal.get("mappings"), list) else []
        strategies = sorted({row.get("incrementalStrategy") for row in mappings if row.get("incrementalStrategy")})
        blockers: list[str] = []
        if intake.access_mode == "browser":
            blockers.append("FDE_BROWSER_ADAPTER_DEFERRED")
        if not mappings or proposal.get("blockers") or proposal.get("missingDataTypes"):
            blockers.append("FDE_MAPPING_PROPOSAL_NOT_READY")
        status = FdeStepStatus.BLOCKED if blockers else FdeStepStatus.EXTERNAL_REQUIRED
        facts = {
            "executionMode": "plan_only",
            "accessMode": intake.access_mode,
            "pipelinePlans": [
                {
                    "pipelineId": _canonical_pipeline_id(row.get("pipelineId"), row.get("targetObjectType")),
                    "sourceTable": row.get("sourceTable"),
                    "targetObjectType": row.get("targetObjectType"),
                    "syncStrategy": row.get("incrementalStrategy"),
                    "incrementalCursor": row.get("incrementalCursor"),
                    "mappingRef": row.get("mappingRef"),
                    "mappingHash": row.get("contentHash"),
                }
                for row in mappings
            ],
            "syncStrategies": strategies,
            "requestedFrequency": intake.sync_frequency,
            "pipelineExecuted": False,
            "databaseWrite": False,
            "sideEffectAuthorized": False,
            "sideEffectLeaseRequired": True,
            "sourceReadinessRefRequired": True,
            "automaticRetry": False,
            "retryMode": "new_authorized_attempt",
            "adapterStatus": "blocked" if intake.access_mode == "browser" else "external_required",
            "claimBoundary": "Plan-only artifact; no Pipeline, database or platform action occurred.",
        }
        facts["reflection"] = evaluate_reflection(
            "fde.s5.controlled-sync",
            {
                **facts,
                "syncStrategy": strategies[0] if len(strategies) == 1 else None,
                "firstSyncStatus": "not_started",
                "firstSyncReceiptRef": None,
            },
        )
        return _evidence(
            "fde.s5.controlled-sync",
            status,
            "FdeControlledSyncPlanArtifact",
            "同步计划已生成；真实副作用未授权" if not blockers else "所选 Adapter 模式或映射未满足启动门",
            sorted(set(blockers + (["FDE_SIDE_EFFECT_AUTHORITY_REQUIRED"] if not blockers else []))),
            facts,
        )

    def _s6(self, scope: TenantScope, intake: FdeIntakeRequest) -> FdeStepEvidence:
        del intake
        envelope = self._readiness
        if envelope is None:
            return _evidence(
                "fde.s6.validation",
                FdeStepStatus.EXTERNAL_REQUIRED,
                "FdeValidationEvidencePackArtifact",
                "等待 canonical SourceReadinessEnvelope 与同 cutoff EvidencePack",
                ["FDE_SOURCE_READINESS_REQUIRED"],
                {
                    "sourceReadinessStatus": "not_supplied",
                    "sourceCount": 0,
                    "pipelineIds": [],
                    "rollbackTarget": "CP4",
                    "rollbackApiRef": "/v1/aip/task-runs/{runId}/rollback",
                    "businessDataDelete": False,
                    "claimBoundary": "No readiness result is inferred without the canonical envelope.",
                },
            )
        if envelope.tenant.org_id != scope.org_id or envelope.tenant.project_id != scope.project_id:
            return _evidence(
                "fde.s6.validation",
                FdeStepStatus.BLOCKED,
                "FdeValidationEvidencePackArtifact",
                "SourceReadiness 租户与 FDE Task 不一致",
                ["FDE_SOURCE_READINESS_TENANT_MISMATCH"],
                {"sourceReadinessStatus": envelope.status.value, "sourceCount": len(envelope.sources), "businessDataDelete": False},
            )
        same_cutoff = all(item.data_cutoff == envelope.cutoff_at for item in envelope.sources)
        has_receipt = envelope.receipt_ref is not None
        ready = envelope.status is SourceReadinessStatus.READY and same_cutoff and has_receipt
        blocker_codes: list[str] = []
        if envelope.status is not SourceReadinessStatus.READY:
            blocker_codes.append(f"FDE_SOURCE_READINESS_{envelope.status.value.upper()}")
        if not same_cutoff:
            blocker_codes.append("FDE_SOURCE_READINESS_CUTOFF_MISMATCH")
        if not has_receipt:
            blocker_codes.append("FDE_SOURCE_READINESS_RECEIPT_REQUIRED")
        facts = {
            "sourceReadinessStatus": envelope.status.value,
            "checkedAt": envelope.checked_at.isoformat(),
            "cutoffAt": envelope.cutoff_at.isoformat(),
            "receiptRef": envelope.receipt_ref.model_dump(mode="json", by_alias=True) if envelope.receipt_ref else None,
            "sourceCount": len(envelope.sources),
            "pipelineIds": [item.pipeline_id for item in envelope.sources],
            "qualityStatuses": [item.quality.status.value for item in envelope.sources],
            "reconciliationStatuses": [item.reconciliation.status.value for item in envelope.sources],
            "latestRunStatuses": [item.latest_run.status.value for item in envelope.sources],
            "freshnessStatus": "pass" if ready else "fail",
            "schemaStatus": "pass" if ready else "fail",
            "qualityStatus": "pass" if ready else "fail",
            "duplicateCount": 0 if ready else None,
            "rollbackTarget": "CP4",
            "rollbackApiRef": "/v1/aip/task-runs/{runId}/rollback",
            "businessDataDelete": False,
            "claimBoundary": "Validation reflects only the supplied canonical envelope at its exact cutoff.",
        }
        facts["reflection"] = evaluate_reflection("fde.s6.validation", facts)
        return _evidence(
            "fde.s6.validation",
            FdeStepStatus.READY if ready else FdeStepStatus.BLOCKED,
            "FdeValidationEvidencePackArtifact",
            "canonical SourceReadiness 同 cutoff 对账通过" if ready else "canonical SourceReadiness 尚未通过",
            blocker_codes,
            facts,
        )


FdeS1S3Orchestrator = FdeS1S6Orchestrator


class FdeS1S3Adapter:
    """CanonicalTaorAdapter implementation with no external side effects."""

    def __init__(self, orchestrator: FdeS1S6Orchestrator | None = None) -> None:
        self._orchestrator = orchestrator or FdeS1S6Orchestrator()

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
