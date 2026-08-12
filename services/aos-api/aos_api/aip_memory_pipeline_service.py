"""Fail-closed policy and trusted-adapter boundary for AIP knowledge pipelines.

The service coordinates existing PostgreSQL authorities.  It does not fetch
external content, trust provider checkpoints, or turn an adapter registry into
memory authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Protocol

from pydantic import Field

from aos_api.aip_contracts import AipContractModel, ResourceRef
from aos_api.aip_memory_contracts import (
    KnowledgeScope,
    KnowledgeSourceKind,
    LicensePolicyDecision,
    SubmitMemoryCandidateRequest,
)
from aos_api.aip_memory_pipeline_contracts import (
    CreateKnowledgePipelineScheduleRequest,
    KnowledgePipelineDependencySnapshot,
    KnowledgePipelineDependencyStatus,
    KnowledgePipelineInputReceipt,
    KnowledgePipelineKind,
    KnowledgePipelinePolicy,
    KnowledgePipelineRunStatus,
    KnowledgePipelineScheduleStatus,
    KnowledgePipelineTrigger,
    StartKnowledgePipelineRunRequest,
    TransitionKnowledgePipelineScheduleRequest,
    TrustedKnowledgeAdapterDefinition,
    TrustedKnowledgeCandidateDraft,
)
from aos_api.aip_memory_pipeline_store import AipMemoryPipelineStore
from aos_api.aip_memory_store import AipMemoryStore
from aos_api.tenant_scope import TenantScope


class AipMemoryPipelinePolicyError(RuntimeError):
    code = "AIP_MEMORY_PIPELINE_POLICY_ERROR"


class AipMemoryPipelinePolicyBlocked(AipMemoryPipelinePolicyError):
    code = "AIP_MEMORY_PIPELINE_POLICY_BLOCKED"

    def __init__(self, reasons: list[str] | str) -> None:
        self.reasons = [reasons] if isinstance(reasons, str) else reasons
        super().__init__(", ".join(self.reasons))


class KnowledgePipelineDependencyDecision(AipContractModel):
    pipeline_kind: KnowledgePipelineKind
    allowed: bool
    reason_codes: list[str] = Field(default_factory=list)
    snapshot: KnowledgePipelineDependencySnapshot | None = None


class TrustedKnowledgeAdapter(Protocol):
    def adapt(
        self,
        receipt: KnowledgePipelineInputReceipt,
        *,
        pipeline_kind: KnowledgePipelineKind,
    ) -> list[TrustedKnowledgeCandidateDraft]: ...


DependencyResolver = Callable[
    [TenantScope, KnowledgePipelineKind], KnowledgePipelineDependencySnapshot | None
]
ReceiptResolver = Callable[
    [TenantScope, ResourceRef], KnowledgePipelineInputReceipt | None
]
LicenseResolver = Callable[
    [TenantScope, KnowledgePipelineInputReceipt], LicensePolicyDecision
]


_COMMON_DEPENDENCIES = {
    "task_run_authority",
    "memory_governance",
    "license",
    "freshness",
}


def _policy(
    kind: KnowledgePipelineKind,
    *,
    triggers: list[KnowledgePipelineTrigger],
    status: KnowledgePipelineScheduleStatus,
    dependencies: set[str],
    receipts: list[str],
    sources: list[KnowledgeSourceKind],
) -> KnowledgePipelinePolicy:
    return KnowledgePipelinePolicy(
        pipeline_kind=kind,
        allowed_triggers=triggers,
        default_status=status,
        required_dependencies=sorted(_COMMON_DEPENDENCIES | dependencies),
        allowed_receipt_types=receipts,
        allowed_source_kinds=sources,
    )


_POLICIES: Mapping[KnowledgePipelineKind, KnowledgePipelinePolicy] = {
    KnowledgePipelineKind.SEED_IMPORT: _policy(
        KnowledgePipelineKind.SEED_IMPORT,
        triggers=[KnowledgePipelineTrigger.MANUAL],
        status=KnowledgePipelineScheduleStatus.PAUSED,
        dependencies={"authorized_source"},
        receipts=["aip.artifact_receipt"],
        sources=[KnowledgeSourceKind.AUTHORIZED_DOCUMENT],
    ),
    KnowledgePipelineKind.OPERATIONAL_LEARNING: _policy(
        KnowledgePipelineKind.OPERATIONAL_LEARNING,
        triggers=[KnowledgePipelineTrigger.TASK_EVENT],
        status=KnowledgePipelineScheduleStatus.PAUSED,
        dependencies={"effect_evidence"},
        receipts=["aip.effect_receipt"],
        sources=[KnowledgeSourceKind.TASK_EVIDENCE, KnowledgeSourceKind.EFFECT_REVIEW],
    ),
    KnowledgePipelineKind.NETWORK_LEARNING: _policy(
        KnowledgePipelineKind.NETWORK_LEARNING,
        triggers=[KnowledgePipelineTrigger.SCHEDULED, KnowledgePipelineTrigger.MANUAL],
        status=KnowledgePipelineScheduleStatus.DISABLED,
        dependencies={"trusted_adapter", "source_allowlist", "prompt_injection_guard"},
        receipts=["aip.research_artifact_receipt"],
        sources=[KnowledgeSourceKind.RESEARCH_ARTIFACT],
    ),
    KnowledgePipelineKind.COMPETITOR_ANALYSIS: _policy(
        KnowledgePipelineKind.COMPETITOR_ANALYSIS,
        triggers=[KnowledgePipelineTrigger.SCHEDULED, KnowledgePipelineTrigger.MANUAL],
        status=KnowledgePipelineScheduleStatus.DISABLED,
        dependencies={
            "trusted_adapter",
            "source_allowlist",
            "summary_only",
            "prompt_injection_guard",
        },
        receipts=["aip.research_artifact_receipt"],
        sources=[KnowledgeSourceKind.RESEARCH_ARTIFACT],
    ),
    KnowledgePipelineKind.PROFESSIONAL_DATABASE: _policy(
        KnowledgePipelineKind.PROFESSIONAL_DATABASE,
        triggers=[KnowledgePipelineTrigger.SCHEDULED, KnowledgePipelineTrigger.VERSION_EVENT],
        status=KnowledgePipelineScheduleStatus.DISABLED,
        dependencies={"trusted_adapter", "source_version"},
        receipts=["aip.research_artifact_receipt"],
        sources=[KnowledgeSourceKind.PROFESSIONAL_DATABASE],
    ),
    KnowledgePipelineKind.CUSTOMER_FEEDBACK: _policy(
        KnowledgePipelineKind.CUSTOMER_FEEDBACK,
        triggers=[KnowledgePipelineTrigger.DOMAIN_EVENT, KnowledgePipelineTrigger.SCHEDULED],
        status=KnowledgePipelineScheduleStatus.PAUSED,
        dependencies={"aggregate_redaction"},
        receipts=["aip.customer_aggregate_receipt"],
        sources=[KnowledgeSourceKind.CUSTOMER_AGGREGATE],
    ),
    KnowledgePipelineKind.HUMAN_EXPERIENCE: _policy(
        KnowledgePipelineKind.HUMAN_EXPERIENCE,
        triggers=[KnowledgePipelineTrigger.MANUAL],
        status=KnowledgePipelineScheduleStatus.PAUSED,
        dependencies={"author", "applicability", "review_due"},
        receipts=["aip.artifact_receipt"],
        sources=[KnowledgeSourceKind.HUMAN_EXPERIENCE],
    ),
}


def knowledge_pipeline_policies() -> dict[KnowledgePipelineKind, KnowledgePipelinePolicy]:
    """Return defensive copies so callers cannot change the frozen policy matrix."""

    return {kind: policy.model_copy(deep=True) for kind, policy in _POLICIES.items()}


class TrustedKnowledgeAdapterRegistry:
    """Versioned code registry; empty by default and never stores credentials."""

    def __init__(self) -> None:
        self._entries: dict[
            tuple[str, int], tuple[TrustedKnowledgeAdapterDefinition, TrustedKnowledgeAdapter]
        ] = {}

    def register(
        self,
        definition: TrustedKnowledgeAdapterDefinition,
        adapter: TrustedKnowledgeAdapter,
    ) -> None:
        key = (definition.adapter_id, definition.revision)
        existing = self._entries.get(key)
        if existing is not None:
            if existing[0] != definition or existing[1] is not adapter:
                raise AipMemoryPipelinePolicyBlocked("adapter_revision_conflict")
            return
        self._entries[key] = (definition.model_copy(deep=True), adapter)

    def resolve(
        self, adapter_id: str, revision: int
    ) -> tuple[TrustedKnowledgeAdapterDefinition, TrustedKnowledgeAdapter]:
        entry = self._entries.get((adapter_id, revision))
        if entry is None:
            raise AipMemoryPipelinePolicyBlocked("trusted_adapter_not_registered")
        return entry[0].model_copy(deep=True), entry[1]

    def supports_kind(self, kind: KnowledgePipelineKind) -> bool:
        return any(
            kind in definition.pipeline_kinds
            for definition, _ in self._entries.values()
        )

    def list_definitions(self) -> list[TrustedKnowledgeAdapterDefinition]:
        return [
            definition.model_copy(deep=True)
            for definition, _ in sorted(
                self._entries.values(),
                key=lambda item: (item[0].adapter_id, item[0].revision),
            )
        ]


class AipMemoryPipelineService:
    def __init__(
        self,
        *,
        dependency_resolver: DependencyResolver,
        receipt_resolver: ReceiptResolver,
        license_resolver: LicenseResolver,
        pipeline_store: AipMemoryPipelineStore | None = None,
        memory_store: AipMemoryStore | None = None,
        adapter_registry: TrustedKnowledgeAdapterRegistry | None = None,
    ) -> None:
        self._dependency_resolver = dependency_resolver
        self._receipt_resolver = receipt_resolver
        self._license_resolver = license_resolver
        self._pipeline_store = pipeline_store or AipMemoryPipelineStore()
        self._memory_store = memory_store or AipMemoryStore()
        self._adapter_registry = adapter_registry or TrustedKnowledgeAdapterRegistry()

    def policy_for(self, kind: KnowledgePipelineKind) -> KnowledgePipelinePolicy:
        return _POLICIES[kind].model_copy(deep=True)

    @staticmethod
    def policy_kinds() -> list[KnowledgePipelineKind]:
        return list(KnowledgePipelineKind)

    def create_schedule(
        self,
        scope: TenantScope,
        request: CreateKnowledgePipelineScheduleRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ):
        policy = self.policy_for(request.pipeline_kind)
        reasons: list[str] = []
        if request.trigger not in policy.allowed_triggers:
            reasons.append("trigger_not_allowed")
        if request.initial_status is not policy.default_status:
            reasons.append("default_status_mismatch")
        if reasons:
            raise AipMemoryPipelinePolicyBlocked(reasons)
        return self._pipeline_store.create_schedule(
            scope,
            request,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )

    def evaluate_dependencies(
        self,
        scope: TenantScope,
        kind: KnowledgePipelineKind,
        *,
        occurred_at: datetime,
    ) -> KnowledgePipelineDependencyDecision:
        policy = self.policy_for(kind)
        try:
            snapshot = self._dependency_resolver(scope, kind)
        except Exception:
            snapshot = None
        if snapshot is None:
            return KnowledgePipelineDependencyDecision(
                pipeline_kind=kind,
                allowed=False,
                reason_codes=["dependency_review_unknown"],
            )
        reasons: list[str] = []
        if snapshot.pipeline_kind is not kind:
            reasons.append("dependency_kind_mismatch")
        expected = set(policy.required_dependencies)
        actual = {item.dependency for item in snapshot.dependencies}
        if actual != expected:
            reasons.append("dependency_set_mismatch")
        if snapshot.reviewed_at > occurred_at:
            reasons.append("dependency_review_from_future")
        if snapshot.expires_at <= occurred_at:
            reasons.append("dependency_review_expired")
        if not reasons:
            for result in sorted(snapshot.dependencies, key=lambda item: item.dependency):
                if result.status is not KnowledgePipelineDependencyStatus.AVAILABLE:
                    reasons.append(f"dependency_{result.status.value}:{result.dependency}")
        if "trusted_adapter" in expected and not self._adapter_registry.supports_kind(kind):
            reasons.append("trusted_adapter_not_registered")
        return KnowledgePipelineDependencyDecision(
            pipeline_kind=kind,
            allowed=not reasons,
            reason_codes=reasons,
            snapshot=snapshot,
        )

    def transition_schedule(
        self,
        scope: TenantScope,
        schedule_id: str,
        *,
        expected_version: int,
        from_status: KnowledgePipelineScheduleStatus,
        to_status: KnowledgePipelineScheduleStatus,
        reason_code: str,
        actor: str,
        occurred_at: datetime,
    ):
        schedule = self._pipeline_store.get_schedule(scope, schedule_id)
        review_ref = None
        if (
            from_status is KnowledgePipelineScheduleStatus.DISABLED
            or to_status is KnowledgePipelineScheduleStatus.ACTIVE
        ):
            decision = self.evaluate_dependencies(
                scope, schedule.pipeline_kind, occurred_at=occurred_at
            )
            if not decision.allowed or decision.snapshot is None:
                raise AipMemoryPipelinePolicyBlocked(decision.reason_codes)
            review_ref = decision.snapshot.review_ref
        request = TransitionKnowledgePipelineScheduleRequest(
            expected_version=expected_version,
            from_status=from_status,
            to_status=to_status,
            reason_code=reason_code,
            dependency_review=review_ref,
        )
        return self._pipeline_store.transition_schedule(
            scope,
            schedule_id,
            request,
            actor=actor,
            occurred_at=occurred_at,
        )

    def start_run(
        self,
        scope: TenantScope,
        request: StartKnowledgePipelineRunRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
        authorized_manual: bool = False,
    ):
        schedule = self._pipeline_store.get_schedule(scope, request.schedule_id)
        policy = self.policy_for(schedule.pipeline_kind)
        reasons: list[str] = []
        if request.trigger not in policy.allowed_triggers:
            reasons.append("trigger_not_allowed")
        if request.trigger is not schedule.trigger:
            reasons.append("schedule_trigger_mismatch")
        if schedule.status is KnowledgePipelineScheduleStatus.DISABLED:
            reasons.append("schedule_disabled")
        elif schedule.status is KnowledgePipelineScheduleStatus.PAUSED:
            if request.trigger is not KnowledgePipelineTrigger.MANUAL:
                reasons.append("paused_schedule_requires_manual")
            if not authorized_manual:
                reasons.append("manual_authorization_required")
        decision = self.evaluate_dependencies(
            scope, schedule.pipeline_kind, occurred_at=occurred_at
        )
        reasons.extend(decision.reason_codes)
        if reasons:
            raise AipMemoryPipelinePolicyBlocked(list(dict.fromkeys(reasons)))
        return self._pipeline_store.start_run(
            scope,
            request,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )

    def adapt_receipt_to_candidates(
        self,
        scope: TenantScope,
        pipeline_run_id: str,
        *,
        adapter_id: str,
        adapter_revision: int,
        receipt_ref: ResourceRef,
        actor: str,
        occurred_at: datetime,
    ) -> list[object]:
        run = self._pipeline_store.get_run(scope, pipeline_run_id)
        if run.status is not KnowledgePipelineRunStatus.RUNNING:
            raise AipMemoryPipelinePolicyBlocked("pipeline_run_not_running")
        schedule = self._pipeline_store.get_schedule(scope, run.schedule_id)
        policy = self.policy_for(schedule.pipeline_kind)
        decision = self.evaluate_dependencies(
            scope, schedule.pipeline_kind, occurred_at=occurred_at
        )
        if not decision.allowed:
            raise AipMemoryPipelinePolicyBlocked(decision.reason_codes)
        definition, adapter = self._adapter_registry.resolve(adapter_id, adapter_revision)
        receipt = self._resolve_receipt(scope, receipt_ref)
        self._validate_adapter_input(
            scope,
            run,
            policy,
            definition,
            receipt,
            occurred_at=occurred_at,
        )
        try:
            drafts = adapter.adapt(receipt, pipeline_kind=schedule.pipeline_kind)
        except AipMemoryPipelinePolicyError:
            raise
        except Exception as exc:
            raise AipMemoryPipelinePolicyBlocked("trusted_adapter_failed") from exc
        try:
            normalized_drafts = [
                TrustedKnowledgeCandidateDraft.model_validate(
                    draft.model_dump(mode="json", by_alias=True)
                    if isinstance(draft, TrustedKnowledgeCandidateDraft)
                    else draft
                )
                for draft in drafts
            ]
        except Exception as exc:
            raise AipMemoryPipelinePolicyBlocked("adapter_output_invalid") from exc
        self._validate_drafts(scope, normalized_drafts)
        candidates = []
        for draft in normalized_drafts:
            request = SubmitMemoryCandidateRequest(
                candidate_layer=draft.candidate_layer,
                task_id=run.task_id,
                run_id=run.run_id,
                subject=draft.subject,
                payload=receipt.artifact,
                source=receipt.source,
                confidence=draft.confidence,
                marking=draft.marking,
            )
            self._memory_store.create_source_revision(
                scope,
                draft.source_id,
                draft.source_revision,
                receipt.source,
                actor=actor,
            )
            candidates.append(
                self._memory_store.submit_candidate(
                    scope,
                    draft.candidate_id,
                    request,
                    source_id=draft.source_id,
                    source_revision=draft.source_revision,
                    knowledge_scope=draft.knowledge_scope,
                    actor=actor,
                    occurred_at=occurred_at,
                )
            )
        return candidates

    def _resolve_receipt(
        self, scope: TenantScope, receipt_ref: ResourceRef
    ) -> KnowledgePipelineInputReceipt:
        if receipt_ref.authority != "postgresql" or not receipt_ref.revision:
            raise AipMemoryPipelinePolicyBlocked("receipt_authority_invalid")
        try:
            receipt = self._receipt_resolver(scope, receipt_ref)
        except Exception as exc:
            raise AipMemoryPipelinePolicyBlocked("receipt_resolution_unknown") from exc
        if receipt is None:
            raise AipMemoryPipelinePolicyBlocked("receipt_not_found")
        try:
            receipt = KnowledgePipelineInputReceipt.model_validate(
                receipt.model_dump(mode="json", by_alias=True)
                if isinstance(receipt, KnowledgePipelineInputReceipt)
                else receipt
            )
        except Exception as exc:
            raise AipMemoryPipelinePolicyBlocked("receipt_contract_invalid") from exc
        if receipt.receipt_ref != receipt_ref:
            raise AipMemoryPipelinePolicyBlocked("receipt_ref_drift")
        return receipt

    def _validate_adapter_input(
        self,
        scope: TenantScope,
        run,
        policy: KnowledgePipelinePolicy,
        definition: TrustedKnowledgeAdapterDefinition,
        receipt: KnowledgePipelineInputReceipt,
        *,
        occurred_at: datetime,
    ) -> None:
        reasons: list[str] = []
        if (receipt.tenant.org_id, receipt.tenant.project_id) != scope.key:
            reasons.append("receipt_tenant_mismatch")
        if (receipt.task_id, receipt.run_id) != (run.task_id, run.run_id):
            reasons.append("receipt_task_run_mismatch")
        if policy.pipeline_kind not in definition.pipeline_kinds:
            reasons.append("adapter_kind_not_allowed")
        if receipt.receipt_ref.resource_type not in policy.allowed_receipt_types:
            reasons.append("receipt_type_not_allowed")
        if receipt.receipt_ref.resource_type not in definition.receipt_types:
            reasons.append("adapter_receipt_type_not_allowed")
        if receipt.source.source_kind not in policy.allowed_source_kinds:
            reasons.append("source_kind_not_allowed")
        if receipt.source.source_kind not in definition.source_kinds:
            reasons.append("adapter_source_kind_not_allowed")
        if receipt.source.observed_at > occurred_at:
            reasons.append("source_observed_in_future")
        if receipt.source.freshness_expires_at <= occurred_at:
            reasons.append("source_stale")
        try:
            license_decision = self._license_resolver(scope, receipt)
        except Exception:
            license_decision = LicensePolicyDecision.UNKNOWN
        if license_decision is LicensePolicyDecision.DENIED:
            reasons.append("license_denied")
        elif license_decision is not LicensePolicyDecision.ALLOWED:
            reasons.append("license_status_unknown")
        if reasons:
            raise AipMemoryPipelinePolicyBlocked(list(dict.fromkeys(reasons)))

    @staticmethod
    def _validate_drafts(
        scope: TenantScope, drafts: list[TrustedKnowledgeCandidateDraft]
    ) -> None:
        candidate_ids = [draft.candidate_id for draft in drafts]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise AipMemoryPipelinePolicyBlocked("candidate_id_duplicate")
        required_markings = {f"org:{scope.org_id}", f"project:{scope.project_id}"}
        for draft in drafts:
            if draft.knowledge_scope is KnowledgeScope.PUBLIC_PACKAGE:
                raise AipMemoryPipelinePolicyBlocked("public_package_write_not_allowed")
            if not required_markings.issubset(set(draft.marking)):
                raise AipMemoryPipelinePolicyBlocked("candidate_scope_marking_missing")


__all__ = [
    "AipMemoryPipelinePolicyBlocked",
    "AipMemoryPipelinePolicyError",
    "AipMemoryPipelineService",
    "KnowledgePipelineDependencyDecision",
    "TrustedKnowledgeAdapter",
    "TrustedKnowledgeAdapterRegistry",
    "knowledge_pipeline_policies",
]
