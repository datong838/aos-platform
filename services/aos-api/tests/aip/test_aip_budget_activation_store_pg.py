"""Formal budget preview and independent decision in disposable PostgreSQL."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from aos_api.aip_budget_activation_store import (
    AipBudgetActivationStore,
    BudgetActivationConflict,
    BudgetActivationDenied,
)
from aos_api.aip_budget_contracts import BudgetLifecycle, BudgetRevisionCreate
from aos_api.aip_budget_store import AipBudgetAuthorityStore
from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def principal(subject: str, *, kind: str = "oidc") -> Principal:
    return Principal(subject=subject, org_id=SCOPE.org_id,
                     project_id=SCOPE.project_id, token_kind=kind)


def setup_case():
    suffix = uuid4().hex
    maker, checker, other = (f"test-maker-{suffix}", f"test-checker-{suffix}", f"test-other-{suffix}")
    with connect(SCOPE) as conn:
        conn.execute("INSERT INTO meta_org(id,name) VALUES(%s,'test org') ON CONFLICT DO NOTHING",
                     (SCOPE.org_id,))
        conn.execute(
            "INSERT INTO meta_workspace(org_id,project_id,name) VALUES(%s,%s,'test workspace') ON CONFLICT DO NOTHING",
            SCOPE.key,
        )
        for subject, role in ((maker, "owner"), (checker, "admin"), (other, "viewer")):
            conn.execute(
                "INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,%s)",
                (*SCOPE.key, subject, role),
            )
        conn.commit()
    now = datetime.now(UTC)
    budget_id = f"test:activation:{suffix}"
    draft = BudgetRevisionCreate(
        budgetId=budget_id, revision=1, environment="development", currency="CNY",
        dailyLimitMinor=500, monthlyLimitMinor=5000, alertThresholdPct=80,
        hardStop=True, unknownUsageBehavior="block",
        effectiveFrom=now - timedelta(minutes=1), effectiveUntil=now + timedelta(days=30),
        owner="test:business-owner", overBudgetApprover="display name only", lifecycle="draft",
    )
    AipBudgetAuthorityStore().publish(SCOPE, maker, f"draft:{suffix}", draft)
    target = draft.model_copy(update={"revision": 2, "lifecycle": BudgetLifecycle.ACTIVE})
    return principal(maker), principal(checker), principal(other), target


def test_current_two_members_create_exact_preview_and_decision_without_active_budget() -> None:
    maker, checker, _, target = setup_case()
    store = AipBudgetActivationStore()
    preview = store.create_preview(maker, target, checker.subject, "preview-1", expected_head_version=1)
    assert preview["budgetId"] == target.budget_id
    assert preview["checkerSubject"] == checker.subject
    assert preview["externalUsageProven"] is False
    assert preview["activationEligible"] is False
    reviewed = store.get_preview(checker, preview["previewId"])
    assert reviewed["target"]["dailyLimitMinor"] == 500
    assert reviewed["target"]["monthlyLimitMinor"] == 5000
    assert reviewed["target"]["overBudgetApprover"] == "display name only"
    assert reviewed["internalLedgerCheckedAt"]
    assert store.create_preview(maker, target, checker.subject, "preview-1", expected_head_version=1) == preview
    decision = store.decide(checker, preview["previewId"], "decision-1", decision="approved")
    assert decision["previewHash"] == preview["previewHash"]
    assert decision["decision"] == "approved"
    assert decision["activationEligible"] is False
    assert store.decide(checker, preview["previewId"], "decision-1", decision="approved") == decision
    with connect(SCOPE) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_budget_revision WHERE org_id=%s AND project_id=%s AND budget_id=%s AND lifecycle='active'",
            (*SCOPE.key, target.budget_id),
        ).fetchone()["n"] == 0


def test_dev_same_actor_wrong_checker_and_target_drift_fail_closed() -> None:
    maker, checker, other, target = setup_case()
    store = AipBudgetActivationStore()
    with pytest.raises(BudgetActivationDenied, match="FORMAL_IDENTITY"):
        store.create_preview(principal(maker.subject, kind="dev"), target, checker.subject,
                             "dev", expected_head_version=1)
    with pytest.raises(BudgetActivationDenied, match="CHECKER"):
        store.create_preview(maker, target, maker.subject, "same", expected_head_version=1)
    with pytest.raises(BudgetActivationDenied, match="CHECKER"):
        store.create_preview(maker, target, other.subject, "viewer", expected_head_version=1)
    preview = store.create_preview(maker, target, checker.subject, "valid", expected_head_version=1)
    with pytest.raises(BudgetActivationDenied, match="REVIEWER"):
        store.get_preview(other, preview["previewId"])
    with pytest.raises(BudgetActivationDenied, match="CHECKER"):
        store.decide(maker, preview["previewId"], "maker-decision", decision="approved")
    with pytest.raises(BudgetActivationConflict, match="IDEMPOTENCY"):
        store.create_preview(maker, target.model_copy(update={"daily_limit_minor": 501}),
                             checker.subject, "valid", expected_head_version=1)
    with pytest.raises(BudgetActivationDenied, match="FORMAL_IDENTITY"):
        store.decide(principal(checker.subject, kind="dev"), preview["previewId"],
                     "dev-decision", decision="approved")


def test_decision_rechecks_draft_head_and_replay_rechecks_current_membership() -> None:
    maker, checker, _, target = setup_case()
    store = AipBudgetActivationStore()
    preview = store.create_preview(maker, target, checker.subject, "head-preview", expected_head_version=1)
    next_draft = target.model_copy(update={"revision": 2, "lifecycle": BudgetLifecycle.DRAFT})
    AipBudgetAuthorityStore().publish(SCOPE, maker.subject, f"next-draft:{uuid4().hex}",
                                      next_draft, expected_version=1)
    with pytest.raises(BudgetActivationDenied, match="HEAD"):
        store.decide(checker, preview["previewId"], "stale-decision", decision="approved")

    maker2, checker2, _, target2 = setup_case()
    preview2 = store.create_preview(maker2, target2, checker2.subject,
                                    "replay-preview", expected_head_version=1)
    store.decide(checker2, preview2["previewId"], "replay-decision", decision="approved")
    with connect(SCOPE) as conn:
        conn.execute(
            "DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s",
            (*SCOPE.key, checker2.subject),
        )
        conn.commit()
    with pytest.raises(BudgetActivationDenied, match="CHECKER_MEMBERSHIP"):
        store.decide(checker2, preview2["previewId"], "replay-decision", decision="approved")


def test_approved_decision_can_be_immutably_revoked_by_current_maker() -> None:
    maker, checker, _, target = setup_case()
    store = AipBudgetActivationStore()
    preview = store.create_preview(maker, target, checker.subject,
                                   "revoke-preview", expected_head_version=1)
    decision = store.decide(checker, preview["previewId"],
                            "approve-before-revoke", decision="approved")
    revoked = store.revoke(maker, decision["decisionId"], "revoke-once",
                           reason="configuration changed")
    assert revoked["decisionId"] == decision["decisionId"]
    assert store.revoke(maker, decision["decisionId"], "revoke-once",
                        reason="configuration changed") == revoked
    with pytest.raises(BudgetActivationConflict, match="ALREADY_REVOKED"):
        store.revoke(checker, decision["decisionId"], "revoke-again", reason="second")
    with connect(SCOPE) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_budget_activation_revocation WHERE org_id=%s AND project_id=%s AND decision_id=%s",
            (*SCOPE.key, decision["decisionId"]),
        ).fetchone()["n"] == 1
