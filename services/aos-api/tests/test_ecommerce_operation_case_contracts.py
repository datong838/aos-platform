from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_operation_case_contracts import (
    AutomationKillDecisionRevision,
    CaseMembershipDecisionRevision,
    ExactOriginalRef,
    KillCheckpoint,
)


NOW = datetime(2026, 8, 24, tzinfo=UTC)
TENANT = {"orgId": "org-org", "projectId": "dev-project"}
HASH = "a" * 64


def _original(identifier: str = "order-1") -> dict[str, object]:
    return {
        "tenant": TENANT,
        "resourceType": "Order",
        "resourceId": identifier,
        "contentHash": HASH,
        "sourceUpdatedAt": NOW,
    }


def test_exact_original_ref_is_tenant_bound_and_rejects_naive_time() -> None:
    item = ExactOriginalRef.model_validate(_original())
    assert item.tenant.org_id == "org-org"
    with pytest.raises(ValidationError, match="timezone"):
        ExactOriginalRef.model_validate(
            {**_original(), "sourceUpdatedAt": NOW.replace(tzinfo=None)}
        )


def test_membership_split_preserves_original_multiset_count() -> None:
    item = CaseMembershipDecisionRevision.model_validate(
        {
            "tenant": TENANT,
            "decisionId": "membership-1",
            "revision": 1,
            "decisionType": "split",
            "predecessorCaseRefs": [{"resourceId": "case-1", "revision": 3, "contentHash": HASH}],
            "successorCaseRefs": [
                {"resourceId": "case-2", "revision": 1, "contentHash": HASH},
                {"resourceId": "case-3", "revision": 1, "contentHash": HASH},
            ],
            "movedOriginals": [_original()],
            "beforeTotal": 1,
            "afterTotal": 1,
            "unmatchedCount": 0,
            "conflictedCount": 0,
            "actor": "user:operator",
            "reason": "separate fulfillment exception",
            "contentHash": HASH,
            "createdAt": NOW,
        }
    )
    assert item.before_total == item.after_total == 1

    with pytest.raises(ValidationError, match="multiset"):
        CaseMembershipDecisionRevision.model_validate(
            {**item.model_dump(mode="json", by_alias=True), "afterTotal": 2}
        )


def test_kill_decision_requires_all_three_runtime_checkpoints() -> None:
    item = AutomationKillDecisionRevision.model_validate(
        {
            "tenant": TENANT,
            "decisionId": "kill-1",
            "revision": 1,
            "state": "active",
            "scopeHash": HASH,
            "checkpoints": ["proposal", "lease", "executor"],
            "actor": "user:operator",
            "reason": "contain automation",
            "contentHash": HASH,
            "createdAt": NOW,
        }
    )
    assert set(item.checkpoints) == set(KillCheckpoint)
    with pytest.raises(ValidationError, match="proposal, lease and executor"):
        AutomationKillDecisionRevision.model_validate(
            {**item.model_dump(mode="json", by_alias=True), "checkpoints": ["proposal", "lease"]}
        )
