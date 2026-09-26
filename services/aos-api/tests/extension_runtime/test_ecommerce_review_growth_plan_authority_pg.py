from datetime import UTC, datetime

import pytest

from aos_api.db import connect_serializable
from aos_api.ecommerce_analyst_authority_contracts import GrowthPlanRevision, SalesWeaponMethod
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    ReviewAdvanceHostService,
    TransactionBoundConnectFactory,
)
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_authority_contracts import sales_weapon_method


SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 9, 9, 5, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64


def plan(*, plan_id: str, revision: int, lifecycle: str, content_hash: str) -> GrowthPlanRevision:
    item = GrowthPlanRevision.model_validate(
        {
            "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "planId": plan_id,
            "revision": revision,
            "version": revision,
            "priorRef": None
            if revision == 1
            else {
                "resourceType": "GrowthPlanRevision",
                "resourceId": plan_id,
                "revision": revision - 1,
                "contentHash": HASH_A,
            },
            "lifecycle": lifecycle,
            "decisionRef": {
                "resourceType": "DecisionSummaryRevision",
                "resourceId": "decision-1",
                "revision": 1,
                "contentHash": HASH_A,
            },
            "objective": "提升会员复购",
            "constraints": ["保持毛利"],
            "budget": "10",
            "expectedEffect": "复购率提升",
            "confidence": 0.7,
            "stopConditions": ["库存不足"],
            "items": [
                {
                    "itemId": "campaign-1",
                    "taskType": "content_campaign",
                    "title": "会员复购活动",
                    "objective": "形成七夕会员活动",
                }
            ],
            "approvedAt": NOW if lifecycle == "approved" else None,
            "contentHash": content_hash,
            "createdBy": "user:reviewer",
            "createdAt": NOW,
        }
    )
    return item.model_copy(update={"content_hash": canonical_hash(
        item.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
    )})


def command(item: GrowthPlanRevision, *, content_hash: str | None = None) -> dict[str, object]:
    return {
        "growthPlanRef": {
            "resourceType": "GrowthPlanRevision",
            "resourceId": item.plan_id,
            "revision": item.revision,
            "contentHash": "sha256:" + (content_hash or item.content_hash),
        }
    }


def test_approved_sales_weapon_method_is_persisted_under_exact_plan_hash():
    with connect_serializable(SCOPE) as conn:
        transaction = HostTransaction(conn)
        store = EcommerceAnalystAuthorityStore(TransactionBoundConnectFactory(transaction, SCOPE))
        original = plan(plan_id="review-sales-weapon-method", revision=1,
                        lifecycle="approved", content_hash=HASH_A)
        item = original.model_copy(update={
            "sales_weapon_method": SalesWeaponMethod.model_validate(sales_weapon_method()),
        })
        item = item.model_copy(update={"content_hash": canonical_hash(
            item.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
        )})
        exact = store.publish_plan(SCOPE, "user:reviewer", "review-sales-weapon-method-1",
                                   item, expected_version=0)
        readback = store.get_plan_exact(SCOPE, exact)
        assert readback.sales_weapon_method == item.sales_weapon_method
        assert readback.content_hash != original.content_hash
        conn.rollback()


def test_review_growth_plan_requires_current_approved_public_owner_and_rolls_back():
    host = ReviewAdvanceHostService()
    with connect_serializable(SCOPE) as conn:
        transaction = HostTransaction(conn)
        store = EcommerceAnalystAuthorityStore(TransactionBoundConnectFactory(transaction, SCOPE))
        approved = plan(
            plan_id="review-growth-plan-approved",
            revision=1,
            lifecycle="approved",
            content_hash=HASH_A,
        )
        store.publish_plan(
            SCOPE,
            "user:reviewer",
            "review-growth-plan-approved-1",
            approved,
            expected_version=0,
        )
        host._revalidate_growth_plan(
            transaction=transaction,
            scope=SCOPE,
            command=command(approved),
        )

        with pytest.raises(ValueError, match="current exact"):
            host._revalidate_growth_plan(
                transaction=transaction,
                scope=SCOPE,
                command=command(approved, content_hash=HASH_B),
            )

        successor = plan(
            plan_id=approved.plan_id,
            revision=2,
            lifecycle="approved",
            content_hash=HASH_B,
        )
        store.publish_plan(
            SCOPE,
            "user:reviewer",
            "review-growth-plan-approved-2",
            successor,
            expected_version=1,
        )
        with pytest.raises(ValueError, match="current exact"):
            host._revalidate_growth_plan(
                transaction=transaction,
                scope=SCOPE,
                command=command(approved),
            )
        host._revalidate_growth_plan(
            transaction=transaction,
            scope=SCOPE,
            command=command(successor),
        )

        draft = plan(
            plan_id="review-growth-plan-draft",
            revision=1,
            lifecycle="draft",
            content_hash=HASH_A,
        )
        store.publish_plan(
            SCOPE,
            "user:reviewer",
            "review-growth-plan-draft-1",
            draft,
            expected_version=0,
        )
        with pytest.raises(ValueError, match="current and APPROVED"):
            host._revalidate_growth_plan(
                transaction=transaction,
                scope=SCOPE,
                command=command(draft),
            )

        with pytest.raises(ValueError, match="current exact"):
            host._revalidate_growth_plan(
                transaction=transaction,
                scope=CANARY,
                command=command(successor),
            )

        conn.execute(
            "CREATE TEMP TABLE ecommerce_analyst_growth_plan_head "
            "(LIKE public.ecommerce_analyst_growth_plan_head INCLUDING DEFAULTS)"
        )
        conn.execute(
            "CREATE TEMP TABLE ecommerce_analyst_growth_plan_revision "
            "(LIKE public.ecommerce_analyst_growth_plan_revision INCLUDING DEFAULTS)"
        )
        conn.execute(
            "CREATE TEMP TABLE ecommerce_analyst_authority_receipt "
            "(LIKE public.ecommerce_analyst_authority_receipt INCLUDING DEFAULTS)"
        )
        host._revalidate_growth_plan(
            transaction=transaction,
            scope=SCOPE,
            command=command(successor),
        )

        conn.rollback()
        assert conn.execute(
            "SELECT count(*) AS n FROM public.ecommerce_analyst_growth_plan_head "
            "WHERE org_id=%s AND project_id=%s AND plan_id IN (%s,%s)",
            (*SCOPE.key, approved.plan_id, draft.plan_id),
        ).fetchone()["n"] == 0
