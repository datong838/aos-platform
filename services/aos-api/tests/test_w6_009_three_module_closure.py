from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_three_module_closure import (
    BindThreeModuleEffectRequest,
    BindThreeModuleHandoffRequest,
    BindThreeModuleUsageRequest,
    CanonicalItemOutcome,
    ClosureExactRef,
    ClosureState,
    CompileThreeModuleClosureRequest,
    EcommerceWorkshopThreeModuleClosureService,
    ThreeModule,
    ThreeModuleClosureRevision,
    ThreeModuleEffectBindingRevision,
    ThreeModuleHandoffBindingRevision,
    ThreeModuleItemOutcome,
    ThreeModuleUsageBindingRevision,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 25, 9, tzinfo=UTC)
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")


def ref(kind: str, identity: str, digest: str = "a" * 64) -> ClosureExactRef:
    return ClosureExactRef(resourceType=kind, resourceId=identity, revision=1, contentHash=f"sha256:{digest}", receiptId=f"receipt-{identity}")


class FakeStore:
    def __init__(self) -> None:
        source = ref("CreatorBatchStartDecisionRevision", "creator-start-1")
        self.items = [
            ThreeModuleItemOutcome(itemKey="lane-1", originalStatus="applied", canonicalOutcome="succeeded", originalRef=ref(source.resource_type, f"{source.resource_id}:lane-1"), receiptRef=ref("ActionReceipt", "action-1")),
            ThreeModuleItemOutcome(itemKey="lane-2", originalStatus="unknown", canonicalOutcome="unknown", originalRef=ref(source.resource_type, f"{source.resource_id}:lane-2"), receiptRef=ref("ActionReceipt", "action-2")),
        ]
        self.closure: ThreeModuleClosureRevision | None = None
        self.usage: ThreeModuleUsageBindingRevision | None = None
        self.effect: ThreeModuleEffectBindingRevision | None = None
        self.handoff: ThreeModuleHandoffBindingRevision | None = None

    def resolve_domain_items(self, scope, module, source_ref):
        assert scope == SCOPE and module is ThreeModule.CREATOR
        return self.items

    def append_closure(self, scope, item):
        self.closure = item
        return item

    def require_closure(self, scope, exact_ref):
        assert self.closure is not None and exact_ref.resource_id == self.closure.closure_id
        return self.closure

    def resolve_usage(self, scope, receipt_id):
        return {"usageReceiptRef": ref("UsageReceipt", receipt_id), "lineageId": "lineage-server-exact", "quality": "unknown", "quantity": None, "unit": "tokens", "adjustmentTotal": 0.0, "settlement": "unknown"}

    def append_usage_binding(self, scope, item):
        self.usage = item
        return item

    def resolve_effect(self, scope, review_id, source_ref):
        return {"effectReviewRef": ref("EffectReviewRevision", review_id), "maturityStatus": "immature", "accepted": True, "effectCompleted": False, "sampleCount": 3, "minSample": 10, "cutoffAt": NOW, "observedAt": NOW}

    def append_effect_binding(self, scope, item):
        self.effect = item
        return item

    def resolve_handoff(self, scope, handoff_id):
        return {"handoffRef": ref("HandoffEnvelope", handoff_id), "transportStatus": "consumed", "businessDecision": "request_more", "taskRef": {"resourceType": "Task", "resourceId": "task-1", "revision": "1", "authority": "postgresql"}, "taskRunRef": {"resourceType": "TaskRun", "resourceId": "run-1", "revision": "1", "authority": "postgresql"}, "disclosureRefCount": 3}

    def append_handoff_binding(self, scope, item):
        self.handoff = item
        return item

    def latest_bindings(self, scope, module):
        return {"closure": self.closure, "usage": self.usage, "effect": self.effect, "handoff": self.handoff}


def closure_ref(value: ThreeModuleClosureRevision) -> ClosureExactRef:
    return ref("ThreeModuleClosureRevision", value.closure_id, value.content_hash)


def test_compile_rebuilds_partial_from_original_items() -> None:
    store = FakeStore()
    service = EcommerceWorkshopThreeModuleClosureService(store)
    value = service.compile(SCOPE, CompileThreeModuleClosureRequest(module="creator", sourceRef=ref("CreatorBatchStartDecisionRevision", "creator-start-1")), "tester", now=NOW)
    assert value.ledger.state is ClosureState.PARTIAL
    assert value.ledger.succeeded == value.ledger.unknown == 1
    assert [item.original_status for item in value.items] == ["applied", "unknown"]


def test_source_type_drift_is_rejected() -> None:
    with pytest.raises(ValidationError, match="sourceRef type drifted"):
        CompileThreeModuleClosureRequest(module="creator", sourceRef=ref("PriceDispositionRevision", "price-1"))


@pytest.mark.parametrize(
    "factory",
    [
        lambda: BindThreeModuleUsageRequest(closureRef=ref("TaskRun", "run-1"), usageReceiptId="usage-1"),
        lambda: BindThreeModuleEffectRequest(closureRef=ref("TaskRun", "run-1"), effectReviewId="effect-1"),
        lambda: BindThreeModuleHandoffRequest(closureRef=ref("TaskRun", "run-1"), handoffId="handoff-1"),
    ],
)
def test_binding_closure_ref_type_drift_is_rejected(factory) -> None:
    with pytest.raises(ValidationError, match="closureRef drifted"):
        factory()


def test_unknown_usage_never_invents_zero() -> None:
    with pytest.raises(ValidationError, match="unknown usage"):
        ThreeModuleUsageBindingRevision(tenant={"orgId": "org-org", "projectId": "dev-project"}, bindingId="u", closureRef=ref("ThreeModuleClosureRevision", "c"), usageReceiptRef=ref("UsageReceipt", "r"), lineageId="server-lineage", quality="unknown", quantity=0, unit="tokens", adjustmentTotal=0, settlement="unknown", contentHash="b" * 64, boundAt=NOW)


def test_mature_is_the_only_effect_completed_state() -> None:
    with pytest.raises(ValidationError, match="canonical maturity"):
        ThreeModuleEffectBindingRevision(tenant={"orgId": "org-org", "projectId": "dev-project"}, bindingId="e", closureRef=ref("ThreeModuleClosureRevision", "c"), effectReviewRef=ref("EffectReviewRevision", "r"), maturityStatus="immature", accepted=True, effectCompleted=True, sampleCount=3, minSample=10, cutoffAt=NOW, observedAt=NOW, contentHash="c" * 64, boundAt=NOW)


def test_five_axes_stay_independent_in_contribution_view() -> None:
    store = FakeStore()
    service = EcommerceWorkshopThreeModuleClosureService(store)
    closure = service.compile(SCOPE, CompileThreeModuleClosureRequest(module="creator", sourceRef=ref("CreatorBatchStartDecisionRevision", "creator-start-1")), "tester", now=NOW)
    exact = closure_ref(closure)
    service.bind_usage(SCOPE, BindThreeModuleUsageRequest(closureRef=exact, usageReceiptId="usage-1"), now=NOW)
    service.bind_effect(SCOPE, BindThreeModuleEffectRequest(closureRef=exact, effectReviewId="effect-1"), now=NOW)
    service.bind_handoff(SCOPE, BindThreeModuleHandoffRequest(closureRef=exact, handoffId="handoff-1"), now=NOW)
    view = service.contribution_view(SCOPE, ThreeModule.CREATOR, now=NOW)
    assert view.latest_closure.ledger.state is ClosureState.PARTIAL
    assert view.latest_usage.settlement == "unknown"
    assert view.latest_effect.maturity_status == "immature"
    assert view.latest_handoff.business_decision == "request_more"
    assert "THREE_MODULE_EFFECT_IMMATURE" in view.blockers
    assert not view.handoff_consume_allowed and not view.memory_promotion_allowed and not view.external_effects_allowed


def test_empty_view_is_fail_closed_and_keeps_163_164_lineage() -> None:
    view = EcommerceWorkshopThreeModuleClosureService(FakeStore()).contribution_view(SCOPE, ThreeModule.CUSTOMER, now=NOW)
    assert view.logic_id == "ecommerce-customer-relationship"
    assert view.primary_colleague == "私域管家"
    assert view.atomic_skill_ids
    assert view.blockers == ["THREE_MODULE_CLOSURE_NOT_COMPILED", "THREE_MODULE_USAGE_NOT_BOUND", "THREE_MODULE_EFFECT_NOT_BOUND", "THREE_MODULE_HANDOFF_NOT_BOUND"]


def test_migration_is_additive_rls_and_forced() -> None:
    text = (Path(__file__).parents[1] / "alembic/versions/w6_009_three_module_closure.py").read_text()
    assert 'down_revision: str | Sequence[str] | None = "w6_008"' in text
    assert text.count("FORCE ROW LEVEL SECURITY") == 1
    assert "for table in _BINDING_TABLES" in text
    assert "GRANT SELECT, INSERT" in text
    assert "UPDATE " not in text and "DELETE " not in text


def test_no_external_action_surface_is_exported() -> None:
    import aos_api.ecommerce_workshop_three_module_closure as module
    names = set(module.__all__)
    assert not any(token in name.lower() for name in names for token in ("send", "dispatch", "consume", "promote"))
