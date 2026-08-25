"""W7-10 exact Candidate -> Impact -> Action -> Receipt contribution tests."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from aos_api.ecommerce_workshop_media_publish import EcommerceWorkshopMediaPublish
from aos_api.tenant_scope import TenantScope


CUTOFF = datetime(2026, 8, 26, tzinfo=UTC)
HASH = "a" * 64
BINDING = "b" * 64


def ref(resource_type: str, resource_id: str, revision: int = 1, content_hash: str = HASH):
    return SimpleNamespace(resource_type=resource_type, resource_id=resource_id, revision=revision, content_hash=content_hash)


def result(items):
    return SimpleNamespace(items=items)


class ProductionStore:
    def __init__(self) -> None:
        variant = SimpleNamespace(artifact_id="variant-1", content_hash=HASH)
        self.family = SimpleNamespace(
            family_id="family-1",
            version=3,
            current_revision=4,
            members=[SimpleNamespace(artifact_ref=variant, family_revision=4)],
            candidate_groups=[SimpleNamespace(selected_ref=variant)],
        )
        self.gate = SimpleNamespace(
            gate_set_id="gate-1",
            content_hash=HASH,
            readiness=SimpleNamespace(value="ready"),
            eligible_for_approval=True,
            artifact_ref=variant,
            variant_platform="douyin",
            variant_profile="short-video",
        )
        external = SimpleNamespace(
            capability_ref=ref("CapabilityRevision", "content.publish", 2),
            capability_binding_ref=ref("CapabilityBindingRevision", "binding-1", 3),
        )
        self.preview = SimpleNamespace(
            preview_id="preview-1",
            revision=2,
            content_hash=HASH,
            action_binding_hash=BINDING,
            readiness=SimpleNamespace(value="ready"),
            lifecycle=SimpleNamespace(value="frozen"),
            expires_at=CUTOFF + timedelta(hours=2),
            external_action_binding=external,
            binding_refs=[],
            plan_ref=ref("PlanRevision", "plan-1", 5),
        )

    def list_artifact_families(self, scope): return result([self.family])
    def list_media_gate_sets(self, scope): return result([self.gate])
    def list_impact_previews(self, scope): return result([self.preview])


def proposal():
    item = SimpleNamespace(
        id="proposal-1",
        action_type=SimpleNamespace(action_type_id="content.publish"),
        impact_preview_ref=ref("ImpactPreviewRevision", "preview-1", 2),
        action_binding_hash=BINDING,
        payload={"publishCandidate": {"familyId": "family-1", "familyVersion": 3, "selectedVariantRef": {"artifactId": "variant-1", "contentHash": HASH}, "gateSetRef": {"gateSetId": "gate-1", "contentHash": HASH}}},
        version=7,
        proposal_hash=HASH,
        status=SimpleNamespace(value="approved"),
    )
    return SimpleNamespace(proposal=item, approvals=[SimpleNamespace(id="approval-1")])


class ActionStore:
    def __init__(self, items=None) -> None: self.items = [proposal()] if items is None else items
    def list_proposals(self, scope, limit=100): return self.items


class Execution:
    def __init__(self, receipts=None) -> None: self.receipts = [] if receipts is None else receipts; self.scopes = []
    def get_execution_view_for_scope(self, scope, proposal_id):
        self.scopes.append(scope)
        return SimpleNamespace(proposal=proposal().proposal, lease=None, attempt=None, receipts=self.receipts)


def receipt(outcome="unknown"):
    return SimpleNamespace(
        id="receipt-1", receipt_kind="initial", status=SimpleNamespace(value="accepted"),
        provider_outcome=outcome, reconciliation_status="pending" if outcome == "unknown" else "not_required",
        request_fingerprint=HASH, response_hash=None, action_binding_hash=BINDING,
        usage_receipt_refs=[], lineage_source_ref=None,
    )


def test_composes_exact_publish_contribution_without_enabling_execution() -> None:
    production, execution = ProductionStore(), Execution()
    service = EcommerceWorkshopMediaPublish(production_store=production, action_store=ActionStore(), action_execution=execution)
    items, blockers = service.read(TenantScope("org-org", "dev-project"), cutoff=CUTOFF)

    assert blockers == []
    assert len(items) == 1
    item = items[0]
    assert item.candidate.family_id == "family-1"
    assert item.candidate.variant_ref.resource_id == "variant-1"
    assert item.impact.logic_ref.resource_id == "plan-1"
    assert [ref.resource_id for ref in item.impact.atomic_skill_refs] == ["binding-1", "content.publish"]
    assert item.action.action_binding_hash == BINDING
    assert item.receipt is None
    assert item.handoff.status == "required"
    assert item.external_effects_allowed is False
    assert execution.scopes == [TenantScope("org-org", "dev-project")]


def test_rejects_variant_or_binding_drift_instead_of_partial_projection() -> None:
    production = ProductionStore()
    production.gate.content_hash = "c" * 64
    service = EcommerceWorkshopMediaPublish(production_store=production, action_store=ActionStore(), action_execution=Execution())

    items, blockers = service.read(TenantScope("org-org", "dev-project"), cutoff=CUTOFF)
    assert items == []
    assert blockers == ["MEDIA_PUBLISH_BINDING_INVALID_OR_DRIFTED", "MEDIA_PUBLISH_CONTRIBUTION_NOT_AVAILABLE"]


def test_unknown_receipt_keeps_reconcile_and_manual_evidence_distinct() -> None:
    service = EcommerceWorkshopMediaPublish(production_store=ProductionStore(), action_store=ActionStore(), action_execution=Execution([receipt()]))
    items, blockers = service.read(TenantScope("org-org", "dev-project"), cutoff=CUTOFF)

    assert blockers == []
    item = items[0]
    assert item.receipt is not None and item.receipt.provider_outcome == "unknown"
    assert item.handoff.status == "required"
    assert "MEDIA_PUBLISH_OUTCOME_REQUIRES_RECONCILIATION" in item.blocker_codes


def test_trusted_empty_requires_canonical_publish_proposal() -> None:
    service = EcommerceWorkshopMediaPublish(production_store=ProductionStore(), action_store=ActionStore([]), action_execution=Execution())
    assert service.read(TenantScope("org-org", "dev-project"), cutoff=CUTOFF) == ([], ["MEDIA_PUBLISH_ACTION_PROPOSAL_NOT_AVAILABLE"])
