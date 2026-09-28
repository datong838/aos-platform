"""A current approval remains non-consumable without external cost authority."""

from uuid import uuid4

import pytest

from aos_api.aip_budget_activation_store import AipBudgetActivationStore, BudgetActivationDenied
from aos_api.aip_budget_contracts import BudgetLifecycle
from aos_api.aip_budget_store import AipBudgetAuthorityStore
from aos_api.auth import Principal
from aos_api.db import connect
from test_aip_budget_activation_store_pg import SCOPE, setup_case


def _approved_case():
    maker, checker, _, target = setup_case()
    store = AipBudgetActivationStore()
    suffix = uuid4().hex
    preview = store.create_preview(maker, target, checker.subject,
                                   f"consume-preview:{suffix}", expected_head_version=1)
    decision = store.decide(checker, preview["previewId"],
                            f"consume-decision:{suffix}", decision="approved")
    return store, maker, checker, target, decision


def test_approved_decision_requires_external_usage_authority_without_side_effect():
    store, maker, _, target, decision = _approved_case()
    with connect(SCOPE) as conn:
        before = conn.execute("SELECT count(*) AS n FROM aip_budget_activation_receipt").fetchone()["n"]
    with pytest.raises(BudgetActivationDenied, match="EXTERNAL_USAGE_PROOF_REQUIRED"):
        store.precheck_consumption(maker, decision["decisionId"], target_hash=decision["targetHash"])
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_budget_activation_receipt").fetchone()["n"] == before
        assert conn.execute("""SELECT count(*) AS n FROM aip_budget_revision
            WHERE org_id=%s AND project_id=%s AND budget_id=%s AND lifecycle='active'""",
            (*SCOPE.key, target.budget_id)).fetchone()["n"] == 0


def test_revoked_decision_denied_before_external_proof_check():
    store, maker, _, _, decision = _approved_case()
    store.revoke(maker, decision["decisionId"], f"revoke:{uuid4().hex}", reason="withdrawn")
    with pytest.raises(BudgetActivationDenied, match="REVOKED"):
        store.precheck_consumption(maker, decision["decisionId"], target_hash=decision["targetHash"])


def test_stale_head_denied_before_external_proof_check():
    store, maker, _, target, decision = _approved_case()
    next_draft = target.model_copy(update={"revision": 2, "lifecycle": BudgetLifecycle.DRAFT})
    AipBudgetAuthorityStore().publish(SCOPE, maker.subject, f"next:{uuid4().hex}",
                                      next_draft, expected_version=1)
    with pytest.raises(BudgetActivationDenied, match="HEAD_DRIFT"):
        store.precheck_consumption(maker, decision["decisionId"], target_hash=decision["targetHash"])


def test_removed_checker_and_non_oidc_or_cross_tenant_cannot_precheck():
    store, maker, checker, _, decision = _approved_case()
    with pytest.raises(BudgetActivationDenied, match="FORMAL_IDENTITY"):
        store.precheck_consumption(
            Principal(subject=maker.subject, org_id=SCOPE.org_id,
                      project_id=SCOPE.project_id, token_kind="dev"),
            decision["decisionId"], target_hash=decision["targetHash"])
    with pytest.raises(BudgetActivationDenied, match="DECISION_MISSING"):
        store.precheck_consumption(
            Principal(subject=maker.subject, org_id="dev-org",
                      project_id="dev-project", token_kind="oidc"),
            decision["decisionId"], target_hash=decision["targetHash"])
    with connect(SCOPE) as conn:
        conn.execute("DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s",
                     (*SCOPE.key, checker.subject))
    with pytest.raises(BudgetActivationDenied, match="CHECKER_MEMBERSHIP"):
        store.precheck_consumption(maker, decision["decisionId"], target_hash=decision["targetHash"])
