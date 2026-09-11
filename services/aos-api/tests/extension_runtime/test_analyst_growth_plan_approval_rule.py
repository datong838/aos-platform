"""Pure package approval rules; Receipt and current-head authority remain host-owned."""

from __future__ import annotations

from datetime import UTC, datetime
import importlib
from pathlib import Path
import subprocess
import sys

import pytest

from aos_api.ecommerce_analyst_authority_contracts import (
    AnalystExactRef as HostExactRef,
    GrowthPlanRevision as HostGrowthPlanRevision,
)
from aos_api.ecommerce_analyst_growth_plan_approval import (
    ApproveGrowthPlanRequest,
    EcommerceAnalystGrowthPlanApprovalService,
)
from aos_api.tenant_scope import TenantScope


ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / "bundles/solutions/ecommerce-growth/backend"
NOW = datetime(2026, 9, 12, 1, 0, tzinfo=UTC)
HASH = "a" * 64
SCOPE = TenantScope("org-org", "dev-project")


@pytest.fixture
def package(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    contracts = importlib.import_module(
        "ecommerce_growth.ecommerce_analyst_authority_contracts"
    )
    approval = importlib.import_module(
        "ecommerce_growth.ecommerce_analyst_growth_plan_approval"
    )
    return contracts, approval


def host_ref() -> HostExactRef:
    return HostExactRef(
        resourceType="GrowthPlanRevision",
        resourceId="plan-1",
        revision=1,
        contentHash=HASH,
    )


def host_plan(*, lifecycle: str = "draft") -> HostGrowthPlanRevision:
    return HostGrowthPlanRevision.model_validate(
        {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "planId": "plan-1",
            "revision": 1,
            "version": 1,
            "lifecycle": lifecycle,
            "decisionRef": {
                "resourceType": "DecisionSummaryRevision",
                "resourceId": "decision-1",
                "revision": 1,
                "contentHash": HASH,
            },
            "objective": "形成内部内容任务",
            "constraints": ["禁止外部发布"],
            "budget": "100.00",
            "expectedEffect": "待真实窗口核验",
            "confidence": 0.5,
            "stopConditions": ["来源失效"],
            "items": [
                {
                    "itemId": "item-1",
                    "taskType": "content",
                    "title": "准备商品介绍",
                    "objective": "核对商品事实",
                }
            ],
            "approvedAt": NOW if lifecycle == "approved" else None,
            "contentHash": HASH,
            "createdBy": "aip:compiler",
            "createdAt": NOW,
        }
    )


class HostStore:
    def __init__(self, draft: HostGrowthPlanRevision) -> None:
        self.draft = draft
        self.published = None

    def find_plan_publication_receipt(self, scope, key):
        return None

    def get_plan_exact(self, scope, exact_ref):
        assert scope == SCOPE and exact_ref == host_ref()
        return self.draft

    def is_current_plan(self, scope, exact_ref):
        return scope == SCOPE and exact_ref == host_ref()

    def publish_plan(self, scope, actor, key, item, *, expected_version):
        assert scope == SCOPE and actor == "user:reviewer" and expected_version == 1
        self.published = item
        return HostExactRef(
            resourceType="GrowthPlanRevision",
            resourceId=item.plan_id,
            revision=item.revision,
            contentHash=item.content_hash,
        )


def approve(package, **overrides):
    contracts, approval = package
    draft = host_plan(lifecycle=overrides.pop("lifecycle", "draft"))
    values = {
        "draft": contracts.GrowthPlanRevision.model_validate(
            draft.model_dump(mode="json", by_alias=True)
        ),
        "draft_ref": contracts.AnalystExactRef.model_validate(
            host_ref().model_dump(mode="json", by_alias=True)
        ),
        "plan_id": "plan-1",
        "expected_version": 1,
        "is_current": True,
        "actor": "user:reviewer",
        "approved_at": NOW,
    }
    values.update(overrides)
    return approval.approve_growth_plan_successor(**values)


def test_package_successor_matches_existing_host_service(package) -> None:
    store = HostStore(host_plan())
    EcommerceAnalystGrowthPlanApprovalService(store, clock=lambda: NOW).approve(
        SCOPE,
        "plan-1",
        ApproveGrowthPlanRequest(draftRef=host_ref()),
        expected_version=1,
        idempotency_key="approve-1",
        actor="user:reviewer",
    )
    successor = approve(package)
    assert successor.model_dump(mode="json", by_alias=True) == store.published.model_dump(
        mode="json", by_alias=True
    )
    assert successor.revision == successor.version == 2
    assert successor.prior_ref.content_hash == HASH
    assert successor.lifecycle.value == "approved"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"plan_id": "other"}, "match"),
        ({"expected_version": 2}, "If-Match"),
        ({"is_current": False}, "not the current"),
        ({"is_current": 1}, "not the current"),
        ({"lifecycle": "approved"}, "only a DRAFT"),
        ({"actor": " "}, "actor"),
        ({"approved_at": datetime(2026, 9, 12)}, "timezone"),
    ],
)
def test_package_approval_fails_closed(package, overrides: dict, message: str) -> None:
    with pytest.raises((ValueError, RuntimeError), match=message):
        approve(package, **overrides)


def test_package_rejects_draft_reference_content_substitution(package) -> None:
    contracts, _ = package
    forged = contracts.AnalystExactRef(
        resourceType="GrowthPlanRevision",
        resourceId="plan-1",
        revision=1,
        contentHash="b" * 64,
    )
    with pytest.raises(RuntimeError, match="exact reference"):
        approve(package, draft_ref=forged)


def test_standalone_import_never_loads_platform_modules() -> None:
    program = """
import sys
class DenyPlatform:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "aos_api" or fullname.startswith("aos_api."):
            raise AssertionError("platform import forbidden: " + fullname)
sys.meta_path.insert(0, DenyPlatform())
sys.path.insert(0, sys.argv[1])
from ecommerce_growth.ecommerce_analyst_growth_plan_approval import approve_growth_plan_successor
assert callable(approve_growth_plan_successor)
assert not any(name.startswith("aos_api") for name in sys.modules)
"""
    subprocess.run(
        [sys.executable, "-I", "-c", program, str(BACKEND)],
        check=True,
        capture_output=True,
        text=True,
    )
