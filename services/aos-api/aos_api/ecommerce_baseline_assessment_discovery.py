"""Fail-closed eligibility for the first plan-empty store baseline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from aos_api.automation_occurrence_store import ClaimedOccurrence
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationAnalysisType,
    BusinessInvestigationCaseLifecycle,
    BusinessInvestigationCaseRevision,
    BusinessInvestigationCaseStore,
)
from aos_api.ecommerce_business_investigation_schedule import (
    BusinessInvestigationScheduleCadence,
    BusinessInvestigationScheduleKind,
    BusinessInvestigationSchedulePolicyRevision,
    BusinessInvestigationScheduleStore,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_schedule_policy_control import SchedulePolicyControlReceipt
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.tenant_scope import TenantScope


class BaselineAssessmentBlocked(RuntimeError):
    pass


class BaselineAssessmentNotApplicable(RuntimeError):
    """A valid occurrence that must settle without starting another baseline."""


@dataclass(frozen=True, slots=True)
class BaselineAssessmentRoute:
    scope: TenantScope
    occurrence_id: UUID
    case: BusinessInvestigationCaseRevision
    policy: BusinessInvestigationSchedulePolicyRevision
    installation_id: UUID
    generation: UUID
    execution_epoch: int
    source_group_id: UUID
    source_run_id: str
    source_actor: str
    source_control_ref: PipelineExactRef
    source_selection_ref: PipelineExactRef
    schedule_control: SchedulePolicyControlReceipt
    max_source_age_seconds: int
    cutoff_at: datetime


class BaselineAssessmentDiscovery:
    def __init__(self, *, max_source_age: timedelta = timedelta(hours=24)) -> None:
        if max_source_age <= timedelta(0) or max_source_age > timedelta(days=7):
            raise ValueError("bounded baseline source age required")
        self._max_source_age = max_source_age

    def read(
        self,
        transaction: HostTransaction,
        scope: TenantScope,
        claimed: ClaimedOccurrence,
        *,
        observed_at: datetime,
    ) -> BaselineAssessmentRoute:
        if (
            type(transaction) is not HostTransaction
            or type(scope) is not TenantScope
            or type(claimed) is not ClaimedOccurrence
        ):
            raise TypeError("exact baseline transaction, tenant and claim required")
        if observed_at.utcoffset() is None:
            raise ValueError("baseline observation time must include timezone")
        now = observed_at.astimezone(UTC)
        if claimed.operation_id != "ecommerce_growth_schedule_trigger":
            raise BaselineAssessmentBlocked("schedule occurrence is required")
        occurrence = transaction.lock_automation_claim(scope=scope, claimed=claimed)
        if (
            occurrence["trigger_source"] != "schedule"
            or occurrence["source_event_id"] is not None
            or occurrence["scheduled_at"] is None
            or occurrence["policy_id"] != claimed.policy_id
            or int(occurrence["policy_revision"]) != claimed.policy_revision
        ):
            raise BaselineAssessmentBlocked("claimed occurrence is not the current schedule slot")

        factory = TransactionBoundConnectFactory(transaction, scope)
        policy = BusinessInvestigationScheduleStore(factory).get(scope, claimed.policy_id)
        case = BusinessInvestigationCaseStore(factory).get(scope, policy.case_ref.resource_id)
        expected_policy_ref = InvestigationExactRef(
            resourceType="SchedulePolicyRevision",
            resourceId=policy.schedule_policy_id,
            revision=policy.revision,
            contentHash=policy.content_hash,
        )
        if (
            policy.revision != claimed.policy_revision
            or policy.content_hash != occurrence["policy_hash"]
            or policy.policy_kind is not BusinessInvestigationScheduleKind.INITIAL_CHECKUP
            or policy.cadence is not BusinessInvestigationScheduleCadence.ONCE
            or not policy.enabled
            or policy.analysis_type is not BusinessInvestigationAnalysisType.INITIAL_STORE_ANALYSIS
            or case.lifecycle is not BusinessInvestigationCaseLifecycle.ACTIVE
            or case.analysis_type is not policy.analysis_type
            or case.schedule_policy_ref != expected_policy_ref
            or policy.case_ref.resource_id != case.case_id
        ):
            raise BaselineAssessmentBlocked("current once baseline Case or Policy differs")

        active = transaction.execute(
            """SELECT s.run_id,r.trigger_key FROM ecommerce_investigation_run_active_slot s
                JOIN ecommerce_investigation_run r
                  ON r.org_id=s.org_id AND r.project_id=s.project_id AND r.run_id=s.run_id
                WHERE s.org_id=%s AND s.project_id=%s AND s.case_id=%s
                  AND s.analysis_type='initial_store_analysis' LIMIT 2""",
            (*scope.key, case.case_id),
        ).fetchall()
        if active and (len(active) != 1 or active[0].get("trigger_key") != claimed.target_idempotency_key):
            raise BaselineAssessmentNotApplicable("ACTIVE_BASELINE_RUN_EXISTS")
        plans = transaction.execute(
            """SELECT r.payload->>'lifecycle' AS lifecycle
                 FROM ecommerce_analyst_growth_plan_head h
                 JOIN ecommerce_analyst_growth_plan_revision r
                   ON r.org_id=h.org_id AND r.project_id=h.project_id
                  AND r.plan_id=h.plan_id AND r.revision=h.current_revision
                WHERE h.org_id=%s AND h.project_id=%s
                  AND r.payload->>'lifecycle' IN ('draft','approved') LIMIT 2""",
            scope.key,
        ).fetchall()
        if plans:
            raise BaselineAssessmentNotApplicable("CURRENT_GROWTH_PLAN_EXISTS")

        analysis_dispatch = transaction.execute(
            """SELECT handler_kind,installation_id,generation,execution_epoch,operation_fence
                 FROM extension_operation_dispatch_binding
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_analysis_advance'""",
            scope.key,
        ).fetchone()
        if (
            analysis_dispatch is None
            or analysis_dispatch["handler_kind"] != "extension"
            or analysis_dispatch["operation_fence"] is not False
            or UUID(str(analysis_dispatch["installation_id"])) != claimed.installation_id
            or UUID(str(analysis_dispatch["generation"])) != claimed.generation
            or int(analysis_dispatch["execution_epoch"]) != claimed.execution_epoch
        ):
            raise BaselineAssessmentBlocked("current analysis route differs from schedule occurrence")

        control_row = transaction.execute(
            """SELECT authority FROM ecommerce_schedule_policy_control_receipt
                WHERE org_id=%s AND project_id=%s
                  AND schedule_policy_id=%s AND policy_revision=%s""",
            (*scope.key, policy.schedule_policy_id, policy.revision),
        ).fetchone()
        if control_row is None:
            raise BaselineAssessmentBlocked("current baseline SchedulePolicy control Receipt is unavailable")
        schedule_control = SchedulePolicyControlReceipt.model_validate(control_row["authority"])
        if (
            schedule_control.tenant.org_id != scope.org_id
            or schedule_control.tenant.project_id != scope.project_id
            or schedule_control.policy_ref != expected_policy_ref
            or schedule_control.case_ref.resource_id != case.case_id
            or schedule_control.case_ref.revision != case.revision
            or schedule_control.case_ref.content_hash != case.content_hash
            or UUID(schedule_control.dispatch.installation_id) != claimed.installation_id
            or UUID(schedule_control.dispatch.generation) != claimed.generation
            or schedule_control.dispatch.execution_epoch != claimed.execution_epoch
        ):
            raise BaselineAssessmentBlocked("current baseline SchedulePolicy control Receipt differs")

        sources = transaction.execute(
            """SELECT gi.group_id,gi.read_completed_at,c.run_id,c.actor,
                      c.control_id,c.control_revision,c.control_hash,
                      r.selection_id,r.selection_revision,r.selection_hash
                 FROM pipeline_snapshot_group_input gi
                 JOIN pipeline_snapshot_group_member gm
                   ON gm.org_id=gi.org_id AND gm.project_id=gi.project_id
                  AND gm.group_id=gi.group_id
                 JOIN pipeline_controlled_source_claim c
                   ON c.org_id=gm.org_id AND c.project_id=gm.project_id
                  AND c.run_id=gm.run_id
                 JOIN pipeline_runtime_control_revision r
                   ON r.org_id=c.org_id AND r.project_id=c.project_id
                  AND r.installation_id=c.installation_id AND r.generation=c.generation
                  AND r.pipeline_id=c.pipeline_id AND r.control_id=c.control_id
                  AND r.revision=c.control_revision AND r.content_hash=c.control_hash
                WHERE gi.org_id=%s AND gi.project_id=%s
                  AND c.installation_id=%s AND c.generation=%s
                  AND c.pipeline_id='P02-product-qyh'
                  AND gi.read_completed_at<=%s
                ORDER BY gi.read_completed_at DESC,gi.group_id DESC LIMIT 2""",
            (*scope.key, claimed.installation_id, claimed.generation, now),
        ).fetchall()
        if not sources:
            raise BaselineAssessmentBlocked("current governed Product snapshot group is unavailable")
        latest = sources[0]
        if now - latest["read_completed_at"].astimezone(UTC) > self._max_source_age:
            raise BaselineAssessmentBlocked("current governed Product snapshot group is stale")
        if len(sources) > 1 and sources[1]["read_completed_at"] == latest["read_completed_at"]:
            raise BaselineAssessmentBlocked("latest governed Product snapshot group is ambiguous")
        return BaselineAssessmentRoute(
            scope=scope,
            occurrence_id=claimed.occurrence_id,
            case=case,
            policy=policy,
            installation_id=claimed.installation_id,
            generation=claimed.generation,
            execution_epoch=claimed.execution_epoch,
            source_group_id=UUID(str(latest["group_id"])),
            source_run_id=str(latest["run_id"]),
            source_actor=str(latest["actor"]),
            source_control_ref=PipelineExactRef(
                resourceType="PipelineRuntimeControlRevision",
                resourceId="pipeline-control-" + str(latest["control_id"]),
                revision=int(latest["control_revision"]),
                contentHash=str(latest["control_hash"]),
            ),
            source_selection_ref=PipelineExactRef(
                resourceType="SourceSelectionRevision",
                resourceId="source-selection-" + str(latest["selection_id"]),
                revision=int(latest["selection_revision"]),
                contentHash=str(latest["selection_hash"]),
            ),
            schedule_control=schedule_control,
            max_source_age_seconds=int(self._max_source_age.total_seconds()),
            cutoff_at=latest["read_completed_at"],
        )


__all__ = [
    "BaselineAssessmentBlocked",
    "BaselineAssessmentDiscovery",
    "BaselineAssessmentNotApplicable",
    "BaselineAssessmentRoute",
]
