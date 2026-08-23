from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_memory_contracts import (
    KnowledgeScope,
    KnowledgeSourceKind,
    KnowledgeSourceRef,
    LicensePolicyDecision,
    RuntimeMemoryLayer,
)
from aos_api.aip_memory_pipeline_contracts import (
    CreateKnowledgePipelineScheduleRequest,
    KnowledgePipelineDependencyResult,
    KnowledgePipelineDependencySnapshot,
    KnowledgePipelineDependencyStatus,
    KnowledgePipelineActivitySnapshot,
    KnowledgePipelineInputReceipt,
    KnowledgePipelineKind,
    KnowledgePipelineRunStatus,
    KnowledgePipelineScheduleStatus,
    KnowledgePipelineTrigger,
    StartKnowledgePipelineRunRequest,
    TrustedKnowledgeAdapterDefinition,
    TrustedKnowledgeCandidateDraft,
    KnowledgePipelineReceipt,
    KnowledgePipelineSchedule,
    KnowledgePipelineStatusCount,
)
from aos_api.aip_memory_pipeline_service import (
    AipMemoryPipelinePolicyBlocked,
    AipMemoryPipelineService,
    TrustedKnowledgeAdapterRegistry,
    knowledge_pipeline_policies,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 13, 1, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64


def resource(kind: str, identifier: str, authority: str = "postgresql") -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=identifier,
        revision="1",
        authority=authority,
    )


def artifact(identifier: str, artifact_type: str = "pipeline-config") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=identifier,
        artifact_type=artifact_type,
        revision="1",
        content_hash=HASH_A,
    )


def dependency_snapshot(
    kind: KnowledgePipelineKind,
    *,
    overrides: dict[str, KnowledgePipelineDependencyStatus] | None = None,
    names: set[str] | None = None,
    expires_at: datetime | None = None,
) -> KnowledgePipelineDependencySnapshot:
    policy = knowledge_pipeline_policies()[kind]
    required = names or set(policy.required_dependencies)
    overrides = overrides or {}
    dependencies = []
    for name in sorted(required):
        status = overrides.get(name, KnowledgePipelineDependencyStatus.AVAILABLE)
        dependencies.append(
            KnowledgePipelineDependencyResult(
                dependency=name,
                status=status,
                evidence_ref=(
                    resource("aip.eval_report", f"dep-{name}")
                    if status is KnowledgePipelineDependencyStatus.AVAILABLE
                    else None
                ),
                reason_code=None if status is KnowledgePipelineDependencyStatus.AVAILABLE else f"{name}_{status.value}",
            )
        )
    return KnowledgePipelineDependencySnapshot(
        pipeline_kind=kind,
        review_ref=resource("aip.eval_report", f"review-{kind.value}"),
        review_hash=HASH_B,
        dependencies=dependencies,
        reviewed_at=NOW - timedelta(minutes=5),
        expires_at=expires_at or NOW + timedelta(hours=1),
    )


def source(
    receipt_ref: ResourceRef,
    *,
    kind: KnowledgeSourceKind = KnowledgeSourceKind.RESEARCH_ARTIFACT,
    expires_at: datetime | None = None,
) -> KnowledgeSourceRef:
    return KnowledgeSourceRef(
        source_kind=kind,
        source_ref=receipt_ref,
        observed_at=NOW - timedelta(minutes=10),
        freshness_expires_at=expires_at or NOW + timedelta(hours=2),
        license_id="authorized-license",
        usage_policy="summary-and-citation",
        content_hash=HASH_A,
        provider="fake-provider",
        provider_version="1",
        applicability=["vertical:ecommerce"],
    )


@dataclass
class FakePipelineStore:
    schedule: object | None = None
    run: object | None = None
    created: list[CreateKnowledgePipelineScheduleRequest] = field(default_factory=list)
    started: list[StartKnowledgePipelineRunRequest] = field(default_factory=list)
    transitioned: list[object] = field(default_factory=list)

    def create_schedule(self, _scope, request, **_kwargs):
        self.created.append(request)
        return SimpleNamespace(**request.model_dump(), status=request.initial_status, version=1)

    def get_schedule(self, _scope, _schedule_id):
        return self.schedule

    def transition_schedule(self, _scope, _schedule_id, request, **_kwargs):
        self.transitioned.append(request)
        return SimpleNamespace(status=request.to_status), SimpleNamespace(
            dependency_review=request.dependency_review
        )

    def start_run(self, _scope, request, **_kwargs):
        self.started.append(request)
        return SimpleNamespace(**request.model_dump(), status=KnowledgePipelineRunStatus.QUEUED)

    def get_run(self, _scope, _pipeline_run_id):
        return self.run

    def summarize_activity(self, _scope):
        return {
            kind: KnowledgePipelineActivitySnapshot(pipeline_kind=kind)
            for kind in KnowledgePipelineKind
        }


@dataclass
class FakeMemoryStore:
    sources: list[tuple] = field(default_factory=list)
    candidates: list[tuple] = field(default_factory=list)

    def create_source_revision(self, scope, source_id, revision, candidate_source, **kwargs):
        self.sources.append((scope, source_id, revision, candidate_source, kwargs))
        return candidate_source

    def submit_candidate(self, scope, candidate_id, request, **kwargs):
        self.candidates.append((scope, candidate_id, request, kwargs))
        return SimpleNamespace(candidate_id=candidate_id, request=request)


class FakeAdapter:
    def __init__(self, draft: TrustedKnowledgeCandidateDraft) -> None:
        self.draft = draft
        self.calls: list[tuple] = []

    def adapt(self, receipt, *, pipeline_kind):
        self.calls.append((receipt, pipeline_kind))
        return [self.draft]


def adapter_definition() -> TrustedKnowledgeAdapterDefinition:
    return TrustedKnowledgeAdapterDefinition(
        adapter_id="research-receipt-adapter",
        revision=1,
        contract_hash=HASH_B,
        pipeline_kinds=[KnowledgePipelineKind.NETWORK_LEARNING],
        receipt_types=["aip.research_artifact_receipt"],
        source_kinds=[KnowledgeSourceKind.RESEARCH_ARTIFACT],
    )


def adapter_draft() -> TrustedKnowledgeCandidateDraft:
    return TrustedKnowledgeCandidateDraft(
        candidate_id="candidate-1",
        source_id="source-1",
        source_revision=1,
        knowledge_scope=KnowledgeScope.WORKSPACE,
        candidate_layer=RuntimeMemoryLayer.EPISODIC,
        subject=resource("ontology.object", "product-1", "ontology"),
        confidence=0.72,
        marking=["org:org-org", "project:dev-project"],
    )


def test_policy_matrix_freezes_all_seven_independent_defaults() -> None:
    policies = knowledge_pipeline_policies()

    assert set(policies) == set(KnowledgePipelineKind)
    assert policies[KnowledgePipelineKind.SEED_IMPORT].default_status is KnowledgePipelineScheduleStatus.PAUSED
    assert policies[KnowledgePipelineKind.OPERATIONAL_LEARNING].allowed_triggers == [KnowledgePipelineTrigger.TASK_EVENT]
    assert policies[KnowledgePipelineKind.NETWORK_LEARNING].default_status is KnowledgePipelineScheduleStatus.DISABLED
    assert policies[KnowledgePipelineKind.COMPETITOR_ANALYSIS].allowed_receipt_types == ["aip.research_artifact_receipt"]
    assert policies[KnowledgePipelineKind.PROFESSIONAL_DATABASE].allowed_triggers == [KnowledgePipelineTrigger.SCHEDULED, KnowledgePipelineTrigger.VERSION_EVENT]
    assert policies[KnowledgePipelineKind.CUSTOMER_FEEDBACK].allowed_source_kinds == [KnowledgeSourceKind.CUSTOMER_AGGREGATE]
    assert policies[KnowledgePipelineKind.HUMAN_EXPERIENCE].allowed_triggers == [KnowledgePipelineTrigger.MANUAL]


def test_operational_readiness_returns_all_seven_and_fails_closed_without_authorities() -> None:
    service = AipMemoryPipelineService(
        pipeline_store=FakePipelineStore(),
        memory_store=FakeMemoryStore(),
        dependency_resolver=lambda *_args: None,
        receipt_resolver=lambda *_args: None,
        license_resolver=lambda *_args: LicensePolicyDecision.UNKNOWN,
    )

    result = service.operational_readiness(SCOPE, occurred_at=NOW)

    assert result.tenant.org_id == "org-org"
    assert [item.pipeline_kind for item in result.pipelines] == list(KnowledgePipelineKind)
    assert all(item.operational_status.value == "unconfigured" for item in result.pipelines)
    assert all("dependency_review_unknown" in item.blocker_codes for item in result.pipelines)
    assert all("schedule_not_registered" in item.blocker_codes for item in result.pipelines)


def test_operational_readiness_only_marks_active_successful_pipeline_ready() -> None:
    store = FakePipelineStore()
    receipt = KnowledgePipelineReceipt(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        receipt_id="receipt-1",
        pipeline_run_id="run-1",
        status="succeeded",
        input_hash=HASH_A,
        output_hash=HASH_B,
        candidate_refs=[],
        checkpoint_before_version=0,
        checkpoint_after_version=0,
        produced_count=0,
        failed_count=0,
        error_codes=[],
        receipt_hash=HASH_A,
        created_at=NOW,
    )
    store.summarize_activity = lambda _scope: {
        kind: (
            KnowledgePipelineActivitySnapshot(
                pipeline_kind=kind,
                schedule_counts=[KnowledgePipelineStatusCount(status="active", count=1)],
                last_receipt=receipt,
            )
            if kind is KnowledgePipelineKind.SEED_IMPORT
            else KnowledgePipelineActivitySnapshot(pipeline_kind=kind)
        )
        for kind in KnowledgePipelineKind
    }
    service = AipMemoryPipelineService(
        pipeline_store=store,
        memory_store=FakeMemoryStore(),
        dependency_resolver=lambda _scope, kind: dependency_snapshot(kind),
        receipt_resolver=lambda *_args: None,
        license_resolver=lambda *_args: LicensePolicyDecision.ALLOWED,
    )

    result = service.operational_readiness(SCOPE, occurred_at=NOW)

    seed = result.pipelines[0]
    assert seed.operational_status.value == "ready"
    assert seed.blocker_codes == []
    assert result.pipelines[2].operational_status.value == "unconfigured"
    assert "trusted_adapter_not_registered" in result.pipelines[2].blocker_codes


def test_schedule_creation_requires_policy_trigger_and_exact_default_status() -> None:
    store = FakePipelineStore()
    service = AipMemoryPipelineService(
        pipeline_store=store,
        memory_store=FakeMemoryStore(),
        dependency_resolver=lambda _scope, kind: dependency_snapshot(kind),
        receipt_resolver=lambda *_args: None,
        license_resolver=lambda *_args: LicensePolicyDecision.ALLOWED,
    )
    valid = CreateKnowledgePipelineScheduleRequest(
        schedule_id="seed-1",
        pipeline_kind=KnowledgePipelineKind.SEED_IMPORT,
        trigger=KnowledgePipelineTrigger.MANUAL,
        config=artifact("config-1"),
        initial_status=KnowledgePipelineScheduleStatus.PAUSED,
    )

    service.create_schedule(SCOPE, valid, idempotency_key="key-1", actor="operator", occurred_at=NOW)
    assert store.created == [valid]

    with pytest.raises(AipMemoryPipelinePolicyBlocked, match="default_status_mismatch"):
        service.create_schedule(
            SCOPE,
            valid.model_copy(update={"pipeline_kind": KnowledgePipelineKind.NETWORK_LEARNING}),
            idempotency_key="key-2",
            actor="operator",
            occurred_at=NOW,
        )
    with pytest.raises(AipMemoryPipelinePolicyBlocked, match="trigger_not_allowed"):
        service.create_schedule(
            SCOPE,
            valid.model_copy(update={"trigger": KnowledgePipelineTrigger.SCHEDULED, "schedule_spec": "0 1 * * *"}),
            idempotency_key="key-3",
            actor="operator",
            occurred_at=NOW,
        )


@pytest.mark.parametrize(
    ("snapshot", "reason"),
    [
        (lambda: dependency_snapshot(KnowledgePipelineKind.SEED_IMPORT, overrides={"license": KnowledgePipelineDependencyStatus.UNKNOWN}), "dependency_unknown:license"),
        (lambda: dependency_snapshot(KnowledgePipelineKind.SEED_IMPORT, names={"license"}), "dependency_set_mismatch"),
        (lambda: dependency_snapshot(KnowledgePipelineKind.SEED_IMPORT, expires_at=NOW - timedelta(seconds=1)), "dependency_review_expired"),
    ],
)
def test_dependency_unknown_missing_and_expired_fail_closed(snapshot, reason) -> None:
    service = AipMemoryPipelineService(
        pipeline_store=FakePipelineStore(),
        memory_store=FakeMemoryStore(),
        dependency_resolver=lambda *_args: snapshot(),
        receipt_resolver=lambda *_args: None,
        license_resolver=lambda *_args: LicensePolicyDecision.ALLOWED,
    )

    decision = service.evaluate_dependencies(SCOPE, KnowledgePipelineKind.SEED_IMPORT, occurred_at=NOW)
    assert decision.allowed is False
    assert reason in decision.reason_codes


def test_available_dependency_rejects_non_eval_evidence() -> None:
    with pytest.raises(ValueError, match="exact PostgreSQL evidence"):
        KnowledgePipelineDependencyResult(
            dependency="license",
            status=KnowledgePipelineDependencyStatus.AVAILABLE,
            evidence_ref=resource("artifact", "not-an-eval"),
        )


def test_external_pipeline_stays_blocked_without_registered_adapter() -> None:
    service = AipMemoryPipelineService(
        pipeline_store=FakePipelineStore(),
        memory_store=FakeMemoryStore(),
        dependency_resolver=lambda _scope, kind: dependency_snapshot(kind),
        receipt_resolver=lambda *_args: None,
        license_resolver=lambda *_args: LicensePolicyDecision.ALLOWED,
    )

    decision = service.evaluate_dependencies(SCOPE, KnowledgePipelineKind.NETWORK_LEARNING, occurred_at=NOW)
    assert decision.allowed is False
    assert decision.reason_codes == ["trusted_adapter_not_registered"]


def test_paused_schedule_allows_only_explicitly_authorized_manual_run() -> None:
    store = FakePipelineStore()
    store.schedule = SimpleNamespace(
        pipeline_kind=KnowledgePipelineKind.SEED_IMPORT,
        trigger=KnowledgePipelineTrigger.MANUAL,
        status=KnowledgePipelineScheduleStatus.PAUSED,
    )
    service = AipMemoryPipelineService(
        pipeline_store=store,
        memory_store=FakeMemoryStore(),
        dependency_resolver=lambda _scope, kind: dependency_snapshot(kind),
        receipt_resolver=lambda *_args: None,
        license_resolver=lambda *_args: LicensePolicyDecision.ALLOWED,
    )
    request = StartKnowledgePipelineRunRequest(
        pipeline_run_id="pipeline-run-1",
        schedule_id="seed-1",
        task_id="task-1",
        run_id="run-1",
        trigger=KnowledgePipelineTrigger.MANUAL,
        expected_checkpoint_version=0,
        scheduled_for=NOW,
    )

    with pytest.raises(AipMemoryPipelinePolicyBlocked, match="manual_authorization_required"):
        service.start_run(SCOPE, request, idempotency_key="run-key", actor="operator", occurred_at=NOW)
    service.start_run(
        SCOPE,
        request,
        idempotency_key="run-key",
        actor="operator",
        occurred_at=NOW,
        authorized_manual=True,
    )
    assert store.started == [request]


def test_service_uses_server_dependency_review_for_recovery() -> None:
    store = FakePipelineStore()
    store.schedule = SimpleNamespace(pipeline_kind=KnowledgePipelineKind.SEED_IMPORT)
    snapshot = dependency_snapshot(KnowledgePipelineKind.SEED_IMPORT)
    service = AipMemoryPipelineService(
        pipeline_store=store,
        memory_store=FakeMemoryStore(),
        dependency_resolver=lambda *_args: snapshot,
        receipt_resolver=lambda *_args: None,
        license_resolver=lambda *_args: LicensePolicyDecision.ALLOWED,
    )

    _schedule, event = service.transition_schedule(
        SCOPE,
        "seed-1",
        expected_version=1,
        from_status=KnowledgePipelineScheduleStatus.DISABLED,
        to_status=KnowledgePipelineScheduleStatus.PAUSED,
        reason_code="dependencies_recovered",
        actor="operator",
        occurred_at=NOW,
    )

    assert store.transitioned[0].dependency_review == snapshot.review_ref
    assert event.dependency_review == snapshot.review_ref


def test_trusted_adapter_consumes_receipt_and_writes_exact_candidate_binding() -> None:
    receipt_ref = resource("aip.research_artifact_receipt", "receipt-1")
    input_receipt = KnowledgePipelineInputReceipt(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        receipt_ref=receipt_ref,
        artifact=artifact("research-artifact", "research-summary"),
        task_id="task-1",
        run_id="run-1",
        source=source(receipt_ref),
    )
    adapter = FakeAdapter(adapter_draft())
    registry = TrustedKnowledgeAdapterRegistry()
    registry.register(adapter_definition(), adapter)
    pipeline_store = FakePipelineStore(
        schedule=SimpleNamespace(pipeline_kind=KnowledgePipelineKind.NETWORK_LEARNING),
        run=SimpleNamespace(
            schedule_id="network-1",
            task_id="task-1",
            run_id="run-1",
            status=KnowledgePipelineRunStatus.RUNNING,
        ),
    )
    memory_store = FakeMemoryStore()
    service = AipMemoryPipelineService(
        pipeline_store=pipeline_store,
        memory_store=memory_store,
        dependency_resolver=lambda _scope, kind: dependency_snapshot(kind),
        receipt_resolver=lambda scope, ref: input_receipt if scope == SCOPE and ref == receipt_ref else None,
        license_resolver=lambda *_args: LicensePolicyDecision.ALLOWED,
        adapter_registry=registry,
    )

    candidates = service.adapt_receipt_to_candidates(
        SCOPE,
        "pipeline-run-1",
        adapter_id="research-receipt-adapter",
        adapter_revision=1,
        receipt_ref=receipt_ref,
        actor="trusted-executor",
        occurred_at=NOW,
    )

    assert [item.candidate_id for item in candidates] == ["candidate-1"]
    assert adapter.calls == [(input_receipt, KnowledgePipelineKind.NETWORK_LEARNING)]
    assert memory_store.sources[0][1:4] == ("source-1", 1, input_receipt.source)
    request = memory_store.candidates[0][2]
    assert (request.task_id, request.run_id) == ("task-1", "run-1")
    assert request.payload == input_receipt.artifact
    assert request.source == input_receipt.source


@pytest.mark.parametrize(
    ("receipt_mutator", "license_decision", "reason"),
    [
        (lambda item: item.model_copy(update={"tenant": TenantContext(org_id=CANARY.org_id, project_id=CANARY.project_id)}), LicensePolicyDecision.ALLOWED, "receipt_tenant_mismatch"),
        (lambda item: item.model_copy(update={"run_id": "other-run"}), LicensePolicyDecision.ALLOWED, "receipt_task_run_mismatch"),
        (lambda item: item.model_copy(update={"source": source(item.receipt_ref, kind=KnowledgeSourceKind.AUTHORIZED_DOCUMENT)}), LicensePolicyDecision.ALLOWED, "source_kind_not_allowed"),
        (lambda item: item.model_copy(update={"source": source(item.receipt_ref, expires_at=NOW - timedelta(seconds=1))}), LicensePolicyDecision.ALLOWED, "source_stale"),
        (lambda item: item, LicensePolicyDecision.UNKNOWN, "license_status_unknown"),
    ],
)
def test_adapter_boundary_rejects_drift_stale_and_unknown_license(receipt_mutator, license_decision, reason) -> None:
    receipt_ref = resource("aip.research_artifact_receipt", "receipt-1")
    base = KnowledgePipelineInputReceipt(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        receipt_ref=receipt_ref,
        artifact=artifact("research-artifact", "research-summary"),
        task_id="task-1",
        run_id="run-1",
        source=source(receipt_ref),
    )
    receipt = receipt_mutator(base)
    adapter = FakeAdapter(adapter_draft())
    registry = TrustedKnowledgeAdapterRegistry()
    registry.register(adapter_definition(), adapter)
    service = AipMemoryPipelineService(
        pipeline_store=FakePipelineStore(
            schedule=SimpleNamespace(pipeline_kind=KnowledgePipelineKind.NETWORK_LEARNING),
            run=SimpleNamespace(schedule_id="network-1", task_id="task-1", run_id="run-1", status=KnowledgePipelineRunStatus.RUNNING),
        ),
        memory_store=FakeMemoryStore(),
        dependency_resolver=lambda _scope, kind: dependency_snapshot(kind),
        receipt_resolver=lambda *_args: receipt,
        license_resolver=lambda *_args: license_decision,
        adapter_registry=registry,
    )

    with pytest.raises(AipMemoryPipelinePolicyBlocked, match=reason):
        service.adapt_receipt_to_candidates(
            SCOPE,
            "pipeline-run-1",
            adapter_id="research-receipt-adapter",
            adapter_revision=1,
            receipt_ref=receipt_ref,
            actor="trusted-executor",
            occurred_at=NOW,
        )

    assert adapter.calls == []


def test_registry_is_empty_by_default_and_rejects_definition_drift() -> None:
    registry = TrustedKnowledgeAdapterRegistry()
    assert registry.list_definitions() == []
    adapter = FakeAdapter(adapter_draft())
    definition = adapter_definition()
    registry.register(definition, adapter)
    registry.register(definition, adapter)

    with pytest.raises(AipMemoryPipelinePolicyBlocked, match="adapter_revision_conflict"):
        registry.register(
            definition.model_copy(update={"contract_hash": HASH_A}),
            adapter,
        )


def test_adapter_output_is_revalidated_at_the_service_boundary() -> None:
    receipt_ref = resource("aip.research_artifact_receipt", "receipt-1")
    input_receipt = KnowledgePipelineInputReceipt(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        receipt_ref=receipt_ref,
        artifact=artifact("research-artifact", "research-summary"),
        task_id="task-1",
        run_id="run-1",
        source=source(receipt_ref),
    )
    bad_adapter = FakeAdapter(adapter_draft())
    bad_adapter.adapt = lambda *_args, **_kwargs: [{"candidateId": "incomplete"}]
    registry = TrustedKnowledgeAdapterRegistry()
    registry.register(adapter_definition(), bad_adapter)
    service = AipMemoryPipelineService(
        pipeline_store=FakePipelineStore(
            schedule=SimpleNamespace(pipeline_kind=KnowledgePipelineKind.NETWORK_LEARNING),
            run=SimpleNamespace(schedule_id="network-1", task_id="task-1", run_id="run-1", status=KnowledgePipelineRunStatus.RUNNING),
        ),
        memory_store=FakeMemoryStore(),
        dependency_resolver=lambda _scope, kind: dependency_snapshot(kind),
        receipt_resolver=lambda *_args: input_receipt,
        license_resolver=lambda *_args: LicensePolicyDecision.ALLOWED,
        adapter_registry=registry,
    )

    with pytest.raises(AipMemoryPipelinePolicyBlocked, match="adapter_output_invalid"):
        service.adapt_receipt_to_candidates(
            SCOPE,
            "pipeline-run-1",
            adapter_id="research-receipt-adapter",
            adapter_revision=1,
            receipt_ref=receipt_ref,
            actor="trusted-executor",
            occurred_at=NOW,
        )
