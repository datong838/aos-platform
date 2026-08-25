"""W7-09 canonical Media Studio lifecycle contribution tests."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_workshop_media_studio_lifecycle import (
    EcommerceWorkshopMediaStudioLifecycle,
    MediaStudioLifecycleConflict,
)
from aos_api.tenant_scope import TenantScope


CUTOFF = datetime(2026, 8, 26, tzinfo=UTC)
HASH = "a" * 64
SLOTS = (
    "media.producer", "media.director", "media.screenwriter", "media.art",
    "media.storyboard", "media.capture", "media.post", "media.review",
)


def ref(resource_type: str, resource_id: str, revision: int = 1):
    return SimpleNamespace(resource_type=resource_type, resource_id=resource_id, revision=revision, content_hash=HASH)


def result(items):
    return SimpleNamespace(items=items)


class ProductionStore:
    def __init__(self, contexts):
        self.contexts = contexts
        self.plan = SimpleNamespace(slots=[SimpleNamespace(slot_id=slot_id, responsibility_type=f"type:{slot_id}", required_capability_ids=["capability.one"], assignee=SimpleNamespace(kind=SimpleNamespace(value="digital_colleague"), resource_id=f"colleague:{slot_id}", version=2), assignee_resolution_receipt_id=f"receipt:{slot_id}") for slot_id in SLOTS])
        member = SimpleNamespace(artifact_ref=SimpleNamespace(artifact_id="artifact-1"), lineage_refs=[ref("TaskRun", "run-1")])
        self.family = SimpleNamespace(family_id="family-1", version=2, topology_status=SimpleNamespace(value="valid"), members=[member], candidate_groups=[SimpleNamespace(status=SimpleNamespace(value="conflict"))])
        self.gate = SimpleNamespace(family_id="family-1", created_at=CUTOFF, readiness=SimpleNamespace(value="review_required"), gate_set_id="gate-1", content_hash=HASH)
        self.issue = SimpleNamespace(issue_id="issue-1", version=3, status=SimpleNamespace(value="open"), severity=SimpleNamespace(value="major"), artifact_ref=SimpleNamespace(artifact_id="artifact-1", content_hash=HASH), return_stage="post", updated_at=CUTOFF)
        self.return_decision = SimpleNamespace(issue_id="issue-1", created_at=CUTOFF)

    def list_production_contexts(self, scope): return result(self.contexts)
    def get_responsibility_plan(self, scope, resource_id, revision): return self.plan
    def list_artifact_families(self, scope): return result([self.family])
    def list_media_gate_sets(self, scope): return result([self.gate])
    def list_review_issues(self, scope): return result([self.issue])
    def list_return_decisions(self, scope): return result([self.return_decision])


def context(context_id="context-1"):
    return SimpleNamespace(context_id=context_id, revision=4, content_hash=HASH, task_id="task-1", created_at=CUTOFF, responsibility_plan_ref=ref("MediaResponsibilityPlanRevision", "plan-1", 2))


def composer(*, contexts=None):
    production = ProductionStore(contexts if contexts is not None else [context()])
    start = SimpleNamespace(production_context_ref=ref("ProductionContextRevision", "context-1", 4), created_at=CUTOFF, task_run_ref=ref("TaskRun", "run-1", 1), status=SimpleNamespace(value="started"), decision_id="start-1", dependency_snapshot_hash=HASH)
    job = SimpleNamespace(job_id="job-1", task_run_ref=ref("TaskRun", "run-1"), step_run_ref=ref("StepRun", "stage-1", 2), status=SimpleNamespace(value="running"), blocker_codes=[], binding=SimpleNamespace(capability_ref=ref("CapabilityRevision", "video.compose"), binding_ref=ref("CapabilityBindingRevision", "content-officer"), provider_ref=ref("ProviderInstanceRevision", "provider-1")))
    finance = SimpleNamespace(job_ref=ref("MediaProviderJob", "job-1"), task_run_ref=ref("TaskRun", "run-1"), step_run_ref=ref("StepRun", "stage-1", 2), settlement_status=SimpleNamespace(value="settled"), settlement_decision_ref=ref("MediaSettlementDecision", "settlement-1"))
    instance = EcommerceWorkshopMediaStudioLifecycle(production_store=production, production_start_service=SimpleNamespace(list=lambda scope: result([start])), provider_job_store=SimpleNamespace(list_jobs=lambda scope, limit: result([job])), media_finance_store=SimpleNamespace(list=lambda scope, limit: result([finance])))
    return instance, production


def test_lifecycle_composes_one_context_eight_roles_and_exact_run_lineage() -> None:
    instance, _ = composer()
    view = instance.read(TenantScope("org-org", "dev-project"), cutoff=CUTOFF)

    assert view is not None
    assert [node.node_id for node in view.lifecycle] == ["prepare", "freeze_confirm", "compile_approve", "start_run", "review_return", "deliver_publish", "reconcile_effect"]
    assert [item.slot_id for item in view.responsibilities] == list(SLOTS)
    assert all(item.status == "assigned" for item in view.responsibilities)
    assert view.stages[0].task_run_id == "run-1"
    assert view.stages[0].capability_ref.resource_id == "video.compose"
    assert view.artifact_families[0].family_id == "family-1"
    assert view.artifact_families[0].conflict_count == 1
    assert view.review_issues[0].return_decision_count == 1
    assert all(command.allowed is False for command in view.command_capabilities)
    assert view.external_effects_allowed is False
    assert "MEDIA_PUBLICATION_NOT_AUTHORIZED" in view.blocker_codes


def test_lifecycle_returns_trusted_empty_without_a_context() -> None:
    instance, _ = composer(contexts=[])
    assert instance.read(TenantScope("org-org", "dev-project"), cutoff=CUTOFF) is None


def test_lifecycle_requires_an_exact_selector_when_contexts_conflict() -> None:
    instance, _ = composer(contexts=[context("context-1"), context("context-2")])
    with pytest.raises(MediaStudioLifecycleConflict, match="SELECTOR_REQUIRED"):
        instance.read(TenantScope("org-org", "dev-project"), cutoff=CUTOFF)


def test_missing_role_receipt_blocks_only_that_role_and_never_partial_assigns() -> None:
    instance, production = composer()
    production.plan.slots[2].assignee_resolution_receipt_id = None
    view = instance.read(TenantScope("org-org", "dev-project"), cutoff=CUTOFF)

    assert view is not None
    blocked = view.responsibilities[2]
    assert blocked.slot_id == "media.screenwriter"
    assert blocked.status == "blocked"
    assert blocked.assignee_id is None
    assert blocked.blocker_codes == ["MEDIA_RESPONSIBILITY_SCREENWRITER_NOT_RESOLVED"]
