#!/usr/bin/env python3
"""Execute the single approved V01 real-provider pilot.

The command prints metadata only. Provider prompt/answer bodies, secret payloads,
headers and cookies are intentionally excluded from every result and evidence row.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from typing import Any, NamedTuple

from aos_api.aip_agent_registry_contracts import (
    AgentInstanceStatus,
    AgentRunRequest,
    AgentRunStatus,
    CapabilityReadiness,
    CreateAgentRunRequest,
    EvaluateOperationalBindingRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_agent_run_execution_contracts import ExecuteAgentRunRequest
from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
from aos_api.aip_agent_run_executor import AipAgentRunExecutor
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_budget_store import AipBudgetAuthorityStore
from aos_api.aip_contracts import PlanStep, ResourceRef
from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
from aos_api.aip_model_capacity_reservation import AipModelCapacityReservationGate
from aos_api.aip_model_runtime_contracts import ModelRuntimeReadiness
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.aip_task_models import (
    CreatePlanRevisionRequest,
    CreateTaskRequest,
    CreateTaskRunRequest,
)
from aos_api.aip_task_store import AipTaskStore
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
CANARY_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "aip-r2-v01-real-pilot"
APPROVAL_REF = "46-R2-V01-VIDEO-DRAFT"
REQUIRED_ALEMBIC_HEAD = "aip10_006"

INSTANCE_ID = "ecommerce.content_officer.default"
SKILL_ID = "ecommerce.skill.V01"
SKILL_REVISION = 2
SKILL_BINDING_ID = "ecommerce.content_officer.skill.V01.r2"
ROUTE_ID = "route-qyh-video-dev"
CAPABILITY_BINDING_ID = "ecommerce.content_officer.video.generate.r2"
TASK_KEY = "r2-v01-real-pilot-task-v1"
PLAN_KEY = "r2-v01-real-pilot-plan-v1"
TASK_RUN_KEY = "r2-v01-real-pilot-task-run-v1"
AGENT_RUN_ID = "ecommerce.content_officer.V01.real-pilot.v1"
ATTEMPT_ID = "ecommerce.content_officer.V01.real-pilot.v1.attempt-1"
EXECUTE_KEY = "r2-v01-real-pilot-execute-v1"
STEP_KEY = "execute-v01-pilot"

INCIDENT_AGENT_RUN_ID = "ecommerce.content_officer.V01.real-pilot.v7"
INCIDENT_ATTEMPT_ID = "ecommerce.content_officer.V01.real-pilot.v7.attempt-1"
PRIOR_INCIDENT_V6_AGENT_RUN_ID = "ecommerce.content_officer.V01.real-pilot.v6"
PRIOR_INCIDENT_V6_ATTEMPT_ID = "ecommerce.content_officer.V01.real-pilot.v6.attempt-1"
PRIOR_INCIDENT_V5_AGENT_RUN_ID = "ecommerce.content_officer.V01.real-pilot.v5"
PRIOR_INCIDENT_V5_ATTEMPT_ID = "ecommerce.content_officer.V01.real-pilot.v5.attempt-1"
PRIOR_INCIDENT_V4_AGENT_RUN_ID = "ecommerce.content_officer.V01.real-pilot.v4"
PRIOR_INCIDENT_V4_ATTEMPT_ID = "ecommerce.content_officer.V01.real-pilot.v4.attempt-1"
PRIOR_INCIDENT_V3_AGENT_RUN_ID = "ecommerce.content_officer.V01.real-pilot.v3"
PRIOR_INCIDENT_V3_ATTEMPT_ID = "ecommerce.content_officer.V01.real-pilot.v3.attempt-1"
PRIOR_INCIDENT_V2_AGENT_RUN_ID = "ecommerce.content_officer.V01.real-pilot.v2"
PRIOR_INCIDENT_V2_ATTEMPT_ID = "ecommerce.content_officer.V01.real-pilot.v2.attempt-1"
EARLIER_INCIDENT_AGENT_RUN_ID = "ecommerce.content_officer.V01.real-pilot.incident-v0"
EARLIER_INCIDENT_ATTEMPT_ID = "ecommerce.content_officer.V01.real-pilot.incident-v0.attempt-1"

QUERY = (
    "请基于以下无敏感信息的内部演示目标生成一条主图视频草稿描述："
    "提升复购主题；不得输出真实 URL/二进制；不得调用工具、执行发布或接触客户数据。"
)
SYSTEM_PROMPT = "你是受限的视频草稿师，只给出视频草稿方案建议，不执行任何外部动作。"


class PilotBlocked(RuntimeError):
    def __init__(self, code: str, reasons: list[str] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.reasons = sorted(set(reasons or []))


class PilotAuthority(NamedTuple):
    instance: Any
    binding: Any
    skill: Any
    resolution: Any
    budget_ref: VersionedAssetRef


def exact_ref(asset_type: str, item: Any, id_attr: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        assetType=asset_type,
        assetId=str(getattr(item, id_attr)),
        revision=int(item.revision),
        contentHash=str(item.content_hash),
    )


def build_plan() -> dict[str, Any]:
    return {
        "status": "planned",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "approvalRef": APPROVAL_REF,
        "recoveryOf": None,
        "priorIncidents": [],
        "steps": [
            "read exact runtime and binding authority",
            "create canonical Task/Plan/TaskRun and AgentRun",
            "reserve capacity and invoke Provider once",
            "read Usage/Artifact/Lineage/Receipt and seal TaskRun",
        ],
        "providerBusinessCallLimit": 1,
        "secretPayloadReads": 0,
        "externalBusinessActions": 0,
        "sensitiveBodiesPrinted": 0,
    }


def _require_schema_head() -> None:
    with db_connect(SCOPE) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    actual = str(row["version_num"]) if row else ""
    if actual != REQUIRED_ALEMBIC_HEAD:
        raise PilotBlocked(
            "SCHEMA_HEAD_MISMATCH",
            [f"expected={REQUIRED_ALEMBIC_HEAD}", f"actual={actual}"],
        )


def _counts(scope: TenantScope) -> dict[str, int]:
    with db_connect(scope) as conn:
        tables = {
            "agentRun": ("aip_agent_run", "agent_run_id", AGENT_RUN_ID),
            "attempt": (
                "aip_agent_run_execution_attempt",
                "attempt_id",
                ATTEMPT_ID,
            ),
            "skillBinding": (
                "aip_skill_binding",
                "binding_id",
                SKILL_BINDING_ID,
            ),
            "task": ("aip_task", "idempotency_key", TASK_KEY),
            "taskRun": ("aip_task_run", "idempotency_key", TASK_RUN_KEY),
        }
        return {
            key: int(
                conn.execute(
                    f"SELECT COUNT(*) AS n FROM {table} "
                    f"WHERE org_id=%s AND project_id=%s AND {column}=%s",
                    (*scope.key, value),
                ).fetchone()["n"]
            )
            for key, (table, column, value) in tables.items()
        }


def _existing_terminal_attempt() -> dict[str, str] | None:
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            "SELECT status,reason_code FROM aip_agent_run_execution_attempt "
            "WHERE org_id=%s AND project_id=%s AND attempt_id=%s",
            (*SCOPE.key, ATTEMPT_ID),
        ).fetchone()
    if row is None or row["status"] not in {"succeeded", "failed", "unknown"}:
        return None
    return {
        "attemptStatus": str(row["status"]),
        "reasonCode": str(row["reason_code"] or ""),
    }


def load_authority(*, now: datetime) -> PilotAuthority:
    _require_schema_head()
    instance = AipAgentRegistryStore().get_instance(SCOPE, INSTANCE_ID)
    if instance.status is not AgentInstanceStatus.ACTIVE:
        raise PilotBlocked("AGENT_INSTANCE_NOT_ACTIVE")
    binding = AipSkillRegistry().get_binding(SCOPE, SKILL_BINDING_ID)
    if binding.status != "active":
        raise PilotBlocked("SKILL_BINDING_NOT_ACTIVE")
    if (
        binding.readiness is not CapabilityReadiness.AVAILABLE
        or binding.readiness_expires_at is None
        or binding.readiness_expires_at <= now
    ):
        raise PilotBlocked("SKILL_BINDING_READINESS_STALE")
    if binding.instance_id != INSTANCE_ID:
        raise PilotBlocked("SKILL_BINDING_INSTANCE_DRIFT")
    if binding.skill.asset_id != SKILL_ID or binding.skill.revision != SKILL_REVISION:
        raise PilotBlocked("SKILL_BINDING_EXACT_SKILL_DRIFT")
    skill = AipSkillRegistry().get_skill(SKILL_ID, SKILL_REVISION)
    if exact_ref("SkillTemplate", skill, "skill_id") != binding.skill:
        raise PilotBlocked("SKILL_EXACT_REF_DRIFT")
    if skill.logic_revision_ref is None:
        raise PilotBlocked("SKILL_LOGIC_EXACT_REF_MISSING")
    resolution = AipModelRuntimeResolver().resolve(SCOPE, ROUTE_ID, now=now)
    if resolution.readiness is not ModelRuntimeReadiness.READY:
        raise PilotBlocked("MODEL_RUNTIME_NOT_READY", list(resolution.blocker_codes))
    if (
        binding.dependencies.model_route_ref != resolution.route
        or binding.dependencies.runtime_policy_ref != resolution.policy
    ):
        raise PilotBlocked("SKILL_BINDING_RUNTIME_EXACT_REF_DRIFT")
    budget_policy_ref = binding.budget_policy_ref
    budget_policy = AipModelGovernancePolicyStore().get_budget(
        SCOPE, budget_policy_ref.asset_id, budget_policy_ref.revision
    )
    if budget_policy.content_hash != budget_policy_ref.content_hash:
        raise PilotBlocked("BUDGET_POLICY_EXACT_REF_DRIFT")
    budget = AipBudgetAuthorityStore().get(
        SCOPE,
        budget_policy.budget_revision_ref.asset_id,
        budget_policy.budget_revision_ref.revision,
    )
    budget_ref = exact_ref("BudgetRevision", budget, "budget_id")
    if budget_ref != budget_policy.budget_revision_ref:
        raise PilotBlocked("BUDGET_REVISION_EXACT_REF_DRIFT")
    return PilotAuthority(instance, binding, skill, resolution, budget_ref)


def refresh_active_binding_readiness(*, now: datetime) -> dict[str, str]:
    """Refresh short-lived snapshots without changing either active lifecycle."""
    with db_connect(SCOPE) as conn:
        health = conn.execute(
            "SELECT observation_id,expires_at FROM aip_provider_health_observation "
            "WHERE org_id=%s AND project_id=%s AND status='healthy' "
            "ORDER BY observed_at DESC LIMIT 1",
            SCOPE.key,
        ).fetchone()
    if health is None or health["expires_at"] <= now:
        raise PilotBlocked("PROVIDER_HEALTH_REFRESH_REQUIRED")
    health_key = str(health["observation_id"])
    capability_service = AipCapabilityBindingService()
    capability = capability_service.get(SCOPE, CAPABILITY_BINDING_ID)
    skill_service = AipSkillRegistry()
    binding = skill_service.get_binding(SCOPE, SKILL_BINDING_ID)

    capability_is_fresh = (
        capability.status == "active"
        and capability.operational_readiness is CapabilityReadiness.AVAILABLE
        and capability.readiness_expires_at is not None
        and capability.readiness_expires_at > now
    )
    if not capability_is_fresh:
        capability, capability_readiness, _ = capability_service.evaluate(
            SCOPE,
            CAPABILITY_BINDING_ID,
            EvaluateOperationalBindingRequest(
                expectedVersion=capability.version,
                dependencies=capability.dependencies,
            ),
            idempotency_key=f"{EXECUTE_KEY}:capability-readiness:{health_key}",
            actor=ACTOR,
            evaluated_at=now,
        )
        if (
            capability.status != "active"
            or capability_readiness.readiness is not CapabilityReadiness.AVAILABLE
        ):
            raise PilotBlocked(
                "CAPABILITY_BINDING_NOT_READY", capability_readiness.reasons
            )

    skill_is_fresh = (
        binding.status == "active"
        and binding.readiness is CapabilityReadiness.AVAILABLE
        and binding.readiness_expires_at is not None
        and binding.readiness_expires_at > now
    )
    if not skill_is_fresh:
        binding, skill_readiness, _ = skill_service.evaluate_binding(
            SCOPE,
            SKILL_BINDING_ID,
            EvaluateOperationalBindingRequest(
                expectedVersion=binding.version,
                dependencies=binding.dependencies,
            ),
            idempotency_key=f"{EXECUTE_KEY}:skill-readiness:{health_key}",
            actor=ACTOR,
            evaluated_at=now,
        )
        if (
            binding.status != "active"
            or skill_readiness.readiness is not CapabilityReadiness.AVAILABLE
        ):
            raise PilotBlocked("SKILL_BINDING_NOT_READY", skill_readiness.reasons)
    return {
        "healthObservationId": health_key,
        "capabilitySnapshotHash": str(capability.dependency_snapshot_hash),
        "skillSnapshotHash": str(binding.dependency_snapshot_hash),
    }


def inspect(*, now: datetime | None = None) -> dict[str, Any]:
    before = _counts(SCOPE)
    canary = _counts(CANARY_SCOPE)
    if any(canary.values()):
        return {
            **build_plan(),
            "status": "blocked",
            "blockerCode": "NEGATIVE_CANARY_DIRTY",
            "sideEffectCounts": before,
            "canaryCounts": canary,
        }
    terminal = _existing_terminal_attempt()
    if terminal is not None:
        return {
            **build_plan(),
            "status": "blocked",
            "blockerCode": "EXISTING_ATTEMPT_TERMINAL",
            "blockerReasons": [terminal["attemptStatus"], terminal["reasonCode"]],
            "sideEffectCounts": before,
            "canaryCounts": canary,
        }
    try:
        authority = load_authority(now=now or datetime.now(UTC))
    except PilotBlocked as exc:
        return {
            **build_plan(),
            "status": "blocked",
            "blockerCode": exc.code,
            "blockerReasons": exc.reasons,
            "sideEffectCounts": before,
            "canaryCounts": canary,
        }
    return {
        **build_plan(),
        "status": "ready",
        "routeRef": authority.resolution.route.model_dump(
            mode="json", by_alias=True
        ),
        "providerRef": authority.resolution.selected_provider.model_dump(
            mode="json", by_alias=True
        ),
        "sideEffectCounts": before,
        "canaryCounts": canary,
    }


def _task_chain(authority: PilotAuthority):
    tasks = AipTaskStore()
    task = tasks.create_task(
        SCOPE,
        ACTOR,
        TASK_KEY,
        CreateTaskRequest(
            type="aip.runtime.acceptance",
            title="R2-4J V01 数据参谋 v6 单次真实 Provider 验收",
            description=(
                "独立 v6 有界验收；仅验证受限文本建议链，不包含客户数据、工具或外部业务动作。"
            ),
            goal={
                "approvalRef": APPROVAL_REF,
                "agentRunId": AGENT_RUN_ID,
                "providerBusinessCallLimit": 1,
                "recoveryOf": None,
                "priorIncidents": [],
            },
        ),
    )
    with db_connect(SCOPE) as conn:
        plan_row = conn.execute(
            "SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s "
            "AND task_id=%s AND idempotency_key=%s",
            (*SCOPE.key, task.id, PLAN_KEY),
        ).fetchone()
    if plan_row is None:
        plan = tasks.create_plan(
            SCOPE,
            ACTOR,
            task.id,
            PLAN_KEY,
            CreatePlanRevisionRequest(
                expectedTaskVersion=task.version,
                steps=[PlanStep(stepKey=STEP_KEY, title="执行并核验 V01 单次真实 Pilot")],
                dependencies=[
                    {
                        "skillBindingId": SKILL_BINDING_ID,
                        "routeRef": authority.resolution.route.model_dump(
                            mode="json", by_alias=True
                        ),
                    }
                ],
                risk={
                    "providerCalls": 1,
                    "tools": False,
                    "externalBusinessActions": False,
                    "dataClassification": "internal",
                    "recoveryOfUnknownAttempt": None,
                    "priorUnknownAttempts": [],
                },
            ),
        )
    else:
        plan = tasks._plan(plan_row)
    task = tasks.get_task(SCOPE, task.id)
    if plan.approval_status == "draft":
        plan = tasks.approve_plan(
            SCOPE, ACTOR, task.id, plan.revision, task.version, plan.content_hash
        )
    task = tasks.get_task(SCOPE, task.id)
    with db_connect(SCOPE) as conn:
        run_row = conn.execute(
            "SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s "
            "AND task_id=%s AND idempotency_key=%s",
            (*SCOPE.key, task.id, TASK_RUN_KEY),
        ).fetchone()
    if run_row is None:
        task_run = tasks.create_run(
            SCOPE,
            ACTOR,
            task.id,
            TASK_RUN_KEY,
            CreateTaskRunRequest(
                planRevisionId=plan.id,
                expectedTaskVersion=task.version,
                logicGraphId=authority.skill.logic_revision_ref.asset_id,
                logicRevision=authority.skill.logic_revision_ref.revision,
            ),
        )
    else:
        task_run = tasks._run(run_row)
    task = tasks.get_task(SCOPE, task.id)
    if task_run.status.value == "queued":
        started = tasks.start_run(
            SCOPE,
            task_run.id,
            expected_run_version=task_run.version,
            expected_task_version=task.version,
            actor=ACTOR,
            idempotency_key=f"{TASK_RUN_KEY}:start",
        )
        task_run, task = started.run, started.task
    return tasks, task, plan, task_run


def _resource(kind: str, value: str, revision: int | str, authority: str) -> ResourceRef:
    return ResourceRef(
        resourceType=kind,
        resourceId=value,
        revision=str(revision),
        authority=authority,
    )


def _agent_run(authority: PilotAuthority, task: Any, plan: Any, task_run: Any):
    service = AipAgentRunService()
    try:
        run = service.get(SCOPE, AGENT_RUN_ID)
    except Exception as exc:
        if exc.__class__.__name__ != "AipAgentRegistryNotFound":
            raise
        run, _ = service.create(
            SCOPE,
            CreateAgentRunRequest(
                agentRunId=AGENT_RUN_ID,
                taskRunRef=_resource(
                    "TaskRun", task_run.id, task_run.version, "aip-task-store"
                ),
                skillBindingId=SKILL_BINDING_ID,
                run=AgentRunRequest(
                    taskRef=_resource("Task", task.id, task.version, "aip-task-store"),
                    planRef=_resource(
                        "PlanRevision", plan.id, plan.revision, "aip-task-store"
                    ),
                    agentInstance=authority.instance.instance_ref,
                    skill=authority.binding.skill,
                    logic=authority.skill.logic_revision_ref,
                    modelRoute=authority.resolution.route,
                    policy=authority.resolution.policy,
                    inputRefs=[],
                ),
            ),
            idempotency_key=f"{EXECUTE_KEY}:agent-run-create",
            actor=ACTOR,
            occurred_at=datetime.now(UTC),
        )
    if run.status is AgentRunStatus.QUEUED:
        run = service.transition(
            SCOPE,
            run.agent_run_id,
            expected_version=run.version,
            from_status=AgentRunStatus.QUEUED,
            to_status=AgentRunStatus.RUNNING,
            actor=ACTOR,
            occurred_at=datetime.now(UTC),
        )
    return service, run


def _capacity_ref(agent_run_id: str, resolution) -> ResourceRef:
    reservation_id = AipModelCapacityReservationGate().reserve(
        SCOPE, resolution, agent_run_id
    )
    return ResourceRef(
        resourceType="CapacityReservation",
        resourceId=reservation_id,
        authority="postgresql",
    )


def _seal_task(tasks: AipTaskStore, task_run: Any, response: Any) -> Any:
    if task_run.status.value == "succeeded":
        return task_run
    with db_connect(SCOPE) as conn:
        step = conn.execute(
            "SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s "
            "AND run_id=%s AND step_key=%s ORDER BY attempt DESC LIMIT 1",
            (*SCOPE.key, task_run.id, STEP_KEY),
        ).fetchone()
    if step is not None and step["status"] == "succeeded":
        return tasks.complete_run(SCOPE, task_run.id).run
    lease = tasks.claim_step(
        SCOPE, task_run.id, STEP_KEY, ACTOR, lease_seconds=300
    )
    attempt = response.attempt
    artifact = attempt.output_artifact_ref
    metadata = {
        "agentRunId": response.agent_run.agent_run_id,
        "attemptId": attempt.attempt_id,
        "attemptStatus": attempt.status.value,
        "providerReceiptId": attempt.provider_receipt_id,
        "usageReceiptIds": attempt.usage_receipt_ids,
        "outputArtifactId": artifact.artifact_id if artifact else None,
        "outputContentHash": artifact.content_hash if artifact else None,
        "lineageEventCount": response.lineage_event_count,
    }
    for phase, payload in (
        ("think", {"approvalRef": APPROVAL_REF, "decision": "bounded_i01_only"}),
        ("act", {"providerCalls": 1, "tools": 0, "externalBusinessActions": 0}),
        ("verify", metadata),
        ("observe", {"outcome": "succeeded", "sensitiveBodiesPersisted": 0}),
    ):
        tasks.record_step_phase(SCOPE, lease.step_run_id, ACTOR, ACTOR, phase, payload)
    tasks.complete_step(SCOPE, lease.step_run_id, ACTOR, ACTOR)
    return tasks.complete_run(SCOPE, task_run.id).run


def _readback(response: Any, task_run: Any) -> dict[str, Any]:
    attempt = AipAgentRunExecutionService().get(SCOPE, ATTEMPT_ID)
    with db_connect(SCOPE) as conn:
        usage = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM aip_usage_receipt WHERE org_id=%s AND project_id=%s "
                "AND receipt_id=ANY(%s)",
                (*SCOPE.key, attempt.usage_receipt_ids),
            ).fetchone()["n"]
        )
        artifact = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM aip_artifact WHERE org_id=%s AND project_id=%s "
                "AND artifact_id=%s",
                (*SCOPE.key, attempt.output_artifact_ref.artifact_id),
            ).fetchone()["n"]
        )
        lineage = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM aip_lineage_event WHERE org_id=%s AND project_id=%s "
                "AND lineage_id=%s",
                (*SCOPE.key, attempt.lineage_id),
            ).fetchone()["n"]
        )
        capacity = conn.execute(
            "SELECT status FROM aip_model_capacity_reservation WHERE org_id=%s "
            "AND project_id=%s AND agent_run_id=%s",
            (*SCOPE.key, AGENT_RUN_ID),
        ).fetchone()
    if usage != len(attempt.usage_receipt_ids) or artifact != 1 or lineage < 1:
        raise PilotBlocked("EXECUTION_EVIDENCE_CHAIN_INCOMPLETE")
    if capacity is None or capacity["status"] != "released":
        raise PilotBlocked("CAPACITY_NOT_RELEASED")
    return {
        **build_plan(),
        "status": "R2_V01_REAL_PILOT_GREEN",
        "taskRunId": task_run.id,
        "taskRunStatus": task_run.status.value,
        "agentRunId": response.agent_run.agent_run_id,
        "agentRunStatus": response.agent_run.status.value,
        "attemptId": attempt.attempt_id,
        "attemptStatus": attempt.status.value,
        "providerReceiptId": attempt.provider_receipt_id,
        "usageReceiptCount": usage,
        "artifactCount": artifact,
        "lineageEventCount": lineage,
        "outputContentHash": attempt.output_artifact_ref.content_hash,
        "answerLength": len(response.answer) if response.answer is not None else None,
        "providerBusinessCalls": 0 if response.replayed else 1,
        "canaryCounts": _counts(CANARY_SCOPE),
    }


def apply() -> dict[str, Any]:
    canary_before = _counts(CANARY_SCOPE)
    if any(canary_before.values()):
        raise PilotBlocked("NEGATIVE_CANARY_DIRTY")
    terminal = _existing_terminal_attempt()
    if terminal is not None:
        raise PilotBlocked(
            "EXISTING_ATTEMPT_TERMINAL",
            [terminal["attemptStatus"], terminal["reasonCode"]],
        )
    refresh_active_binding_readiness(now=datetime.now(UTC))
    authority = load_authority(now=datetime.now(UTC))
    tasks, task, plan, task_run = _task_chain(authority)
    _, run = _agent_run(authority, task, plan, task_run)
    if run.status not in {
        AgentRunStatus.RUNNING,
        AgentRunStatus.SUCCEEDED,
        AgentRunStatus.FAILED,
        AgentRunStatus.UNKNOWN,
    }:
        raise PilotBlocked("AGENT_RUN_NOT_EXECUTABLE")
    response = AipAgentRunExecutor().execute(
        SCOPE,
        run.agent_run_id,
        ExecuteAgentRunRequest(
            expectedAgentRunVersion=run.version,
            attemptId=ATTEMPT_ID,
            attemptNo=1,
            budgetRef=authority.budget_ref,
            capacityReservationRef=_capacity_ref(run.agent_run_id, authority.resolution),
            query=QUERY,
            systemPrompt=SYSTEM_PROMPT,
            dataClassification="internal",
        ),
        idempotency_key=EXECUTE_KEY,
        actor=ACTOR,
        occurred_at=datetime.now(UTC),
    )
    if response.attempt.status.value != "succeeded":
        reason = getattr(response.attempt, "reason_code", None) or ""
        raise PilotBlocked(
            "AGENT_RUN_EXECUTION_NOT_SUCCEEDED",
            [response.attempt.status.value, str(reason)],
        )
    task_run = _seal_task(tasks, task_run, response)
    if _counts(CANARY_SCOPE) != canary_before:
        raise PilotBlocked("NEGATIVE_CANARY_MUTATED")
    return _readback(response, task_run)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = apply() if args.apply else inspect()
    except PilotBlocked as exc:
        result = {
            **build_plan(),
            "status": "blocked",
            "blockerCode": exc.code,
            "blockerReasons": exc.reasons,
            "sideEffectCounts": _counts(SCOPE),
            "canaryCounts": _counts(CANARY_SCOPE),
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0 if result.get("status") in {"ready", "R2_V01_REAL_PILOT_GREEN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
