"""BI-W8-06 compile-only bridge from an approved investigation plan to Handoff."""

from __future__ import annotations

from collections.abc import Collection
from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import Field, field_validator, model_validator

from aos_api.aip_business_investigation_compile_saga import (
    BusinessInvestigationCompilationReceiptStore,
)
from aos_api.aip_contracts import AipContractModel, HandoffResourceRef, ResourceRef, TenantContext
from aos_api.aip_task_store import AipTaskStore
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_analyst_authority_contracts import (
    AnalystExactRef,
    GrowthPlanLifecycle,
)
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore
from aos_api.ecommerce_business_investigation_projection import (
    BusinessInvestigationProjectionBuilder,
    BusinessInvestigationWorkbenchView,
    CanonicalBusinessInvestigationProjectionReader,
)
from aos_api.ecommerce_workshop_catalog import build_ecommerce_workshop_catalog
from aos_api.ecommerce_workshop_handoff_contracts import (
    MODULE_ID_PATTERN,
    ModuleHandoffCompileRequest,
    ModuleHandoffCompileResponse,
)
from aos_api.ecommerce_workshop_handoff_service import ModuleHandoffCompiler
from aos_api.ecommerce_workshop_task_cockpit import EcommerceWorkshopTaskCockpit
from aos_api.tenant_scope import TenantScope


ANALYST_MODULE_ID = "ecommerce.analyst"
HANDOFF_TARGET_MODULE_IDS = (
    "ecommerce.task-cockpit",
    "ecommerce.operations",
    "ecommerce.content-campaign",
    "ecommerce.creator-growth",
    "ecommerce.media-studio",
    "ecommerce.price-governance",
    "ecommerce.customer",
)


class BusinessInvestigationHandoffBlocked(RuntimeError):
    code = "BUSINESS_INVESTIGATION_HANDOFF_BLOCKED"


class InvestigationProjection(Protocol):
    def build(
        self, scope: TenantScope, run_id: str, *, observed_at: datetime
    ) -> BusinessInvestigationWorkbenchView: ...


class CompileBusinessInvestigationHandoffRequest(AipContractModel):
    handoff_id: str = Field(min_length=1, max_length=200)
    approved_plan_ref: AnalystExactRef
    source_slot_id: str = Field(min_length=1, max_length=160)
    target_module_id: str = Field(pattern=MODULE_ID_PATTERN)
    target_slot_id: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1, max_length=240)
    requested_outcome: str = Field(min_length=1, max_length=500)
    markings: list[str] = Field(min_length=1, max_length=32)
    expires_at: datetime

    @field_validator("markings")
    @classmethod
    def _unique_markings(cls, values: list[str]) -> list[str]:
        cleaned = [item.strip() for item in values]
        if any(not item for item in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("markings must be unique and non-blank")
        return cleaned

    @model_validator(mode="after")
    def _target(self) -> "CompileBusinessInvestigationHandoffRequest":
        if self.approved_plan_ref.resource_type != "GrowthPlanRevision":
            raise ValueError("approvedPlanRef must reference GrowthPlanRevision")
        if self.target_module_id not in HANDOFF_TARGET_MODULE_IDS:
            raise ValueError("targetModuleId must be one of the seven non-analyst Workshop modules")
        if self.source_slot_id == self.target_slot_id:
            raise ValueError("source and target slots must differ")
        return self


class BusinessInvestigationHandoffCompileResponse(AipContractModel):
    schema_version: Literal[
        "aos.ecommerce.business-investigation-handoff-compile/v1"
    ] = "aos.ecommerce.business-investigation-handoff-compile/v1"
    tenant: TenantContext
    run_ref: InvestigationExactRef
    approved_plan_ref: AnalystExactRef
    compilation_receipt_ref: InvestigationExactRef
    artifact_refs: list[InvestigationExactRef] = Field(min_length=4, max_length=4)
    handoff: ModuleHandoffCompileResponse


class EcommerceBusinessInvestigationHandoffService:
    """Derive the canonical command; never issue a token or persist a Handoff."""

    def __init__(
        self,
        *,
        projection: InvestigationProjection | None = None,
        compilation_receipts: BusinessInvestigationCompilationReceiptStore | None = None,
        plans: EcommerceAnalystAuthorityStore | None = None,
        tasks: AipTaskStore | None = None,
        compiler: ModuleHandoffCompiler | None = None,
        now=lambda: datetime.now(UTC),
    ) -> None:
        self._projection = projection or BusinessInvestigationProjectionBuilder(
            CanonicalBusinessInvestigationProjectionReader()
        )
        self._receipts = compilation_receipts or BusinessInvestigationCompilationReceiptStore()
        self._plans = plans or EcommerceAnalystAuthorityStore()
        self._tasks = tasks or AipTaskStore()
        self._compiler = compiler or ModuleHandoffCompiler(
            cockpit=EcommerceWorkshopTaskCockpit(),
            catalog=build_ecommerce_workshop_catalog(),
        )
        self._now = now

    def compile(
        self,
        scope: TenantScope,
        run_id: str,
        request: CompileBusinessInvestigationHandoffRequest,
        *,
        roles: Collection[str],
        principal_markings: Collection[str],
    ) -> BusinessInvestigationHandoffCompileResponse:
        observed_at = self._now()
        view = self._projection.build(scope, run_id, observed_at=observed_at)
        if view.runtime.binding_status != "bound" or view.runtime.task_run_ref is None:
            raise BusinessInvestigationHandoffBlocked("Run has no exact canonical TaskRun binding")

        receipt = self._receipts.get_for_run(scope, view.run_ref)
        if receipt.task_id != view.runtime.task_id:
            raise BusinessInvestigationHandoffBlocked("compile Receipt Task lineage drifted")
        task = self._tasks.get_task(scope, receipt.task_id)
        task_run = self._tasks.get_run(scope, view.runtime.task_run_ref.resource_id)
        if task_run.task_id != task.id or task_run.version != view.runtime.task_run_ref.version:
            raise BusinessInvestigationHandoffBlocked("Task/TaskRun exact lineage drifted")

        plan = self._plans.get_plan_exact(scope, request.approved_plan_ref)
        if (
            plan.lifecycle is not GrowthPlanLifecycle.APPROVED
            or not self._plans.is_current_plan(scope, request.approved_plan_ref)
        ):
            raise BusinessInvestigationHandoffBlocked("GrowthPlan must be current and APPROVED")

        artifact_refs = [item.artifact_ref for item in view.artifacts if item.status == "bound"]
        if len(artifact_refs) != 4 or any(item is None for item in artifact_refs):
            raise BusinessInvestigationHandoffBlocked(
                "all four governed investigation artifacts must be bound"
            )
        exact_artifacts = [item for item in artifact_refs if item is not None]
        handoff = self._compiler.compile(
            scope,
            task_run.id,
            ModuleHandoffCompileRequest(
                handoffId=request.handoff_id,
                taskRef=ResourceRef(
                    resourceType="Task",
                    resourceId=task.id,
                    revision=str(task.version),
                    authority="aip-task-runtime",
                ),
                runRef=ResourceRef(
                    resourceType="TaskRun",
                    resourceId=task_run.id,
                    revision=str(task_run.version),
                    authority="aip-task-runtime",
                ),
                sourceModuleId=ANALYST_MODULE_ID,
                targetModuleId=request.target_module_id,
                sourceSlotId=request.source_slot_id,
                targetSlotId=request.target_slot_id,
                purpose=request.purpose,
                requestedOutcome=request.requested_outcome,
                objectRefs=[
                    HandoffResourceRef(
                        resourceType="GrowthPlanRevision",
                        resourceId=request.approved_plan_ref.resource_id,
                        revision=str(request.approved_plan_ref.revision),
                        authority="ecommerce-analyst",
                        contentHash=f"sha256:{request.approved_plan_ref.content_hash}",
                    )
                ],
                artifactRefs=[
                    HandoffResourceRef(
                        resourceType=item.resource_type,
                        resourceId=item.resource_id,
                        revision=str(item.revision),
                        authority="business-investigation-artifact",
                        contentHash=item.content_hash,
                    )
                    for item in exact_artifacts
                ],
                evidenceRefs=[],
                context={},
                allowedContextFields=[],
                markings=request.markings,
                expiresAt=request.expires_at,
            ),
            roles=roles,
            principal_markings=principal_markings,
        )
        return BusinessInvestigationHandoffCompileResponse(
            tenant=TenantContext(orgId=scope.org_id, projectId=scope.project_id),
            runRef=view.run_ref,
            approvedPlanRef=request.approved_plan_ref,
            compilationReceiptRef=receipt.exact_ref,
            artifactRefs=exact_artifacts,
            handoff=handoff,
        )


__all__ = [
    "ANALYST_MODULE_ID",
    "HANDOFF_TARGET_MODULE_IDS",
    "BusinessInvestigationHandoffBlocked",
    "BusinessInvestigationHandoffCompileResponse",
    "CompileBusinessInvestigationHandoffRequest",
    "EcommerceBusinessInvestigationHandoffService",
]
