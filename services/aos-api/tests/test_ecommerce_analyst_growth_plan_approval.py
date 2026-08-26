from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.ecommerce_analyst_authority_contracts import (
    AnalystExactRef,
    GrowthPlanRevision,
)
from aos_api.ecommerce_analyst_growth_plan_approval import (
    ApproveGrowthPlanRequest,
    EcommerceAnalystGrowthPlanApprovalService,
    GrowthPlanApprovalBlocked,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 27, 5, 0, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
HASH = "a" * 64


def ref(plan_id: str = "plan-1", revision: int = 1, content_hash: str = HASH) -> AnalystExactRef:
    return AnalystExactRef(
        resourceType="GrowthPlanRevision",
        resourceId=plan_id,
        revision=revision,
        contentHash=content_hash,
    )


def plan(*, plan_id: str = "plan-1", lifecycle: str = "draft") -> GrowthPlanRevision:
    return GrowthPlanRevision.model_validate(
        {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "planId": plan_id,
            "revision": 1,
            "version": 1,
            "lifecycle": lifecycle,
            "decisionRef": {
                "resourceType": "DecisionSummaryRevision",
                "resourceId": "decision-1",
                "revision": 1,
                "contentHash": HASH,
            },
            "objective": "grow",
            "constraints": [],
            "budget": "10",
            "expectedEffect": "+1%",
            "confidence": 0.5,
            "stopConditions": ["stale"],
            "items": [
                {
                    "itemId": "item-1",
                    "taskType": "analysis",
                    "title": "A",
                    "objective": "A",
                }
            ],
            "approvedAt": NOW if lifecycle == "approved" else None,
            "contentHash": HASH,
            "createdBy": "aip:compiler",
            "createdAt": NOW,
        }
    )


class FakeStore:
    def __init__(self, draft: GrowthPlanRevision | None = None) -> None:
        self.draft = draft or plan()
        self.receipts: dict[str, AnalystExactRef] = {}
        self.approved: dict[tuple[str, int], GrowthPlanRevision] = {}
        self.current = True
        self.publish_calls: list[tuple] = []

    def find_plan_publication_receipt(self, scope, key):
        assert scope == SCOPE
        return self.receipts.get(key)

    def get_plan_exact(self, scope, exact_ref):
        assert scope == SCOPE
        if exact_ref.revision == 1 and exact_ref.resource_id == self.draft.plan_id:
            return self.draft
        return self.approved[(exact_ref.resource_id, exact_ref.revision)]

    def is_current_plan(self, scope, exact_ref):
        assert scope == SCOPE
        return self.current

    def publish_plan(self, scope, actor, key, item, *, expected_version):
        assert scope == SCOPE
        self.publish_calls.append((actor, key, item, expected_version))
        exact_ref = ref(item.plan_id, item.revision, item.content_hash)
        self.approved[(item.plan_id, item.revision)] = item
        self.receipts[key] = exact_ref
        return exact_ref


def request(plan_id: str = "plan-1") -> ApproveGrowthPlanRequest:
    return ApproveGrowthPlanRequest(draftRef=ref(plan_id))


def test_approve_creates_adjacent_server_owned_approved_successor_and_replays() -> None:
    store = FakeStore()
    service = EcommerceAnalystGrowthPlanApprovalService(store, clock=lambda: NOW)
    first = service.approve(
        SCOPE,
        "plan-1",
        request(),
        expected_version=1,
        idempotency_key="approve-1",
        actor="user:reviewer",
    )
    assert first.lifecycle == "approved" and first.replayed is False
    assert first.external_effects_allowed is False
    approved = store.publish_calls[0][2]
    assert approved.revision == approved.version == 2
    assert approved.prior_ref == ref()
    assert approved.lifecycle.value == "approved"
    assert approved.approved_at == approved.created_at == NOW
    assert approved.created_by == "user:reviewer"
    assert approved.content_hash != HASH

    replay = service.approve(
        SCOPE,
        "plan-1",
        request(),
        expected_version=1,
        idempotency_key="approve-1",
        actor="user:reviewer",
    )
    assert replay.replayed is True and replay.approved_ref == first.approved_ref
    assert len(store.publish_calls) == 1


@pytest.mark.parametrize(
    ("expected_version", "lifecycle", "current", "message"),
    [
        (2, "draft", True, "stale"),
        (1, "approved", True, "only a DRAFT"),
        (1, "draft", False, "not the current"),
    ],
)
def test_approve_fails_closed_for_stale_non_draft_or_non_current(
    expected_version, lifecycle, current, message
) -> None:
    store = FakeStore(plan(lifecycle=lifecycle))
    store.current = current
    service = EcommerceAnalystGrowthPlanApprovalService(store, clock=lambda: NOW)
    with pytest.raises(GrowthPlanApprovalBlocked, match=message):
        service.approve(
            SCOPE,
            "plan-1",
            request(),
            expected_version=expected_version,
            idempotency_key="approve",
            actor="user:reviewer",
        )
    assert store.publish_calls == []


def test_approve_rejects_path_drift_and_idempotency_actor_or_draft_reuse() -> None:
    store = FakeStore()
    service = EcommerceAnalystGrowthPlanApprovalService(store, clock=lambda: NOW)
    with pytest.raises(ValueError, match="match"):
        service.approve(
            SCOPE,
            "other-plan",
            request(),
            expected_version=1,
            idempotency_key="approve",
            actor="user:reviewer",
        )
    service.approve(
        SCOPE,
        "plan-1",
        request(),
        expected_version=1,
        idempotency_key="approve",
        actor="user:reviewer",
    )
    with pytest.raises(GrowthPlanApprovalBlocked, match="different approval"):
        service.approve(
            SCOPE,
            "plan-1",
            request(),
            expected_version=1,
            idempotency_key="approve",
            actor="user:other",
        )
    with pytest.raises(GrowthPlanApprovalBlocked, match="different approval"):
        service.approve(
            SCOPE,
            "plan-2",
            request("plan-2"),
            expected_version=1,
            idempotency_key="approve",
            actor="user:reviewer",
        )
