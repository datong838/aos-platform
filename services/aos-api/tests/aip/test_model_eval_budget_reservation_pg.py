"""Isolated PostgreSQL proof for the first Model Eval budget hold schema."""

import psycopg
import pytest
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

from aos_api.aip_action_models import DecideActionProposalRequest
from aos_api.aip_model_eval_action import propose_model_eval_request, decide_model_eval_request
from aos_api.aip_model_eval_request_store import AipModelEvalRequestStore
from aos_api.aip_budget_cost_runtime import shared_risk_totals
from aos_api.auth import Principal
from aos_api.db import get_dsn, connect_serializable
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope
from tests.aip.test_model_eval_request_pg import seeded_approved_model_eval_request
from tests.aip.test_budget_cost_consumer_pg import caller, consume
from tests.aip.test_budget_cost_issuer_pg import issuer_factory, command
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer


def test_model_eval_hold_schema_is_tenant_scoped_and_append_only():
    with psycopg.connect(get_dsn()) as conn:
        rows = conn.execute("""
            SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,
                   has_table_privilege('aos_runtime',c.oid,'SELECT') AS can_read,
                   has_table_privilege('aos_runtime',c.oid,'INSERT') AS can_insert,
                   has_table_privilege('aos_runtime',c.oid,'UPDATE') AS can_update,
                   has_table_privilege('aos_runtime',c.oid,'DELETE') AS can_delete
              FROM pg_class c
             WHERE c.relnamespace='public'::regnamespace
               AND c.relname IN ('aip_model_eval_budget_reservation',
                                 'aip_model_eval_budget_reservation_bucket')
             ORDER BY c.relname
        """).fetchall()
        assert len(rows) == 2
        for row in rows:
            assert row[1:3] == (True, True)
            assert row[3:7] == (True, True, False, False)
        guards = conn.execute("""
            SELECT tgrelid::regclass::text,tgname FROM pg_trigger
             WHERE tgrelid IN ('aip_model_eval_budget_reservation'::regclass,
                               'aip_model_eval_budget_reservation_bucket'::regclass)
               AND NOT tgisinternal
        """).fetchall()
        for table in ('aip_model_eval_budget_reservation',
                      'aip_model_eval_budget_reservation_bucket'):
            assert any(name.startswith('trg_') and 'append_only' in name
                       for rel, name in guards if rel == table)


def test_approved_model_eval_holds_real_shared_budget_buckets_once():
    from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore

    scope, first, request, proposal, approved, budget, _, _ = (
        seeded_approved_model_eval_request(stop_after_approval=True)
    )
    with psycopg.connect(get_dsn()) as owner:
        event_id = owner.execute("""SELECT approval_event_id
            FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s
              AND proposal_id=%s AND decision='approved'""",
            (*scope.key, proposal.proposal.id)).fetchone()[0]
    store = AipModelEvalBudgetReservationStore()
    with connect_serializable(scope) as conn:
        held = store.hold(conn, scope, first["request_id"], event_id)
    with connect_serializable(scope) as conn:
        replay = store.hold(conn, scope, first["request_id"], event_id)
    assert replay["reservation_id"] == held["reservation_id"]
    with connect_serializable(scope) as conn:
        assert shared_risk_totals(conn, scope, budget.budget_id) == (1, 200)
        buckets = conn.execute("""SELECT bucket_kind,account_id,held_minor
            FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s
              AND account_id IN (%s,%s,%s) ORDER BY bucket_kind""",
            (*scope.key, f"model-eval/{first['request_id']}",
             f"{budget.budget_id}:daily", f"{budget.budget_id}:pilot"),
        ).fetchall()
    assert len(buckets) == 3
    assert all(int(row["held_minor"]) == request.upper_bound_minor for row in buckets)


def test_eval_hold_rejects_wrong_approval_and_rolls_back_all_buckets():
    from aos_api.aip_model_eval_budget_reservation import (
        AipModelEvalBudgetReservationStore, ModelEvalBudgetBlocked,
    )

    scope, first, _, proposal, _, budget, _, _ = (
        seeded_approved_model_eval_request(stop_after_approval=True)
    )
    store = AipModelEvalBudgetReservationStore()
    with connect_serializable(scope) as conn:
        with pytest.raises(ModelEvalBudgetBlocked, match="checker event"):
            store.hold(conn, scope, first["request_id"], "not-an-approval")
    with psycopg.connect(get_dsn()) as owner:
        event_id = owner.execute("""SELECT approval_event_id
            FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s
              AND proposal_id=%s AND decision='approved'""",
            (*scope.key, proposal.proposal.id)).fetchone()[0]
    with pytest.raises(RuntimeError, match="force rollback"):
        with connect_serializable(scope) as conn:
            store.hold(conn, scope, first["request_id"], event_id)
            raise RuntimeError("force rollback")
    with connect_serializable(scope) as conn:
        assert conn.execute("""SELECT count(*) AS n
            FROM aip_model_eval_budget_reservation WHERE request_id=%s""",
            (first["request_id"],)).fetchone()["n"] == 0
        assert conn.execute("""SELECT count(*) AS n FROM aip_budget_bucket
            WHERE org_id=%s AND project_id=%s AND account_id=%s
              AND held_minor>0""", (*scope.key, f"{budget.budget_id}:daily")
        ).fetchone()["n"] == 0


def _approval_event(scope, proposal_id):
    with psycopg.connect(get_dsn()) as owner:
        return owner.execute("""SELECT approval_event_id
            FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s
              AND proposal_id=%s AND decision='approved'""",
            (*scope.key, proposal_id)).fetchone()[0]


def _second_approved_request(scope, first, request):
    second = AipModelEvalRequestStore().create(
        scope, "test-maker", f"second-{first['request_id']}",
        request.model_copy(update={"upper_bound_minor": 400}),
    )
    maker = Principal(subject="test-maker", org_id=scope.org_id,
                      project_id=scope.project_id, roles=["owner"], token_kind="oidc")
    checker = Principal(subject="test-checker", org_id=scope.org_id,
                        project_id=scope.project_id, roles=["admin"], token_kind="oidc")
    second_proposal = propose_model_eval_request(
        maker, second["request_id"], f"proposal-{second['request_id']}",
        request.expires_at,
    )
    approve = DecideActionProposalRequest.model_validate({
        "expectedProposalVersion": second_proposal.proposal.version,
        "expectedProposalHash": second_proposal.proposal.proposal_hash,
        "decision": "approved", "reason": "second bounded request",
        "approvalExpiresAt": request.expires_at,
    })
    decide_model_eval_request(checker, second_proposal.proposal.id,
                              f"approve-{second['request_id']}", approve)
    return second, _approval_event(scope, second_proposal.proposal.id)


def test_second_approved_eval_cannot_overspend_shared_daily_bucket():
    from aos_api.aip_model_eval_budget_reservation import (
        AipModelEvalBudgetReservationStore, ModelEvalBudgetBlocked,
    )

    scope, first, request, proposal, _, budget, _, _ = (
        seeded_approved_model_eval_request(stop_after_approval=True)
    )
    store = AipModelEvalBudgetReservationStore()
    with connect_serializable(scope) as conn:
        store.hold(conn, scope, first["request_id"],
                   _approval_event(scope, proposal.proposal.id))
    second, second_event = _second_approved_request(scope, first, request)
    with pytest.raises(ModelEvalBudgetBlocked, match="daily budget limit exceeded"):
        with connect_serializable(scope) as conn:
            store.hold(conn, scope, second["request_id"], second_event)
    with connect_serializable(scope) as conn:
        daily = conn.execute("""SELECT held_minor FROM aip_budget_bucket
            WHERE org_id=%s AND project_id=%s AND bucket_kind='daily'
              AND account_id=%s""", (*scope.key, f"{budget.budget_id}:daily")
        ).fetchone()
        assert int(daily["held_minor"]) == 200
        assert conn.execute("""SELECT count(*) AS n FROM aip_model_eval_budget_reservation
            WHERE request_id=%s""", (second["request_id"],)).fetchone()["n"] == 0


def test_two_approved_evals_cannot_concurrently_overspend_daily_bucket():
    from aos_api.aip_model_eval_budget_reservation import (
        AipModelEvalBudgetReservationStore, ModelEvalBudgetBlocked,
    )

    scope, first, request, proposal, _, budget, _, _ = (
        seeded_approved_model_eval_request(stop_after_approval=True)
    )
    second, second_event = _second_approved_request(scope, first, request)
    first_event = _approval_event(scope, proposal.proposal.id)
    barrier = Barrier(2)

    def attempt(request_id, event_id):
        try:
            with connect_serializable(scope) as conn:
                barrier.wait(timeout=5)
                return AipModelEvalBudgetReservationStore().hold(
                    conn, scope, request_id, event_id)
        except (ModelEvalBudgetBlocked, psycopg.errors.SerializationFailure) as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(attempt, first["request_id"], first_event)
        b = pool.submit(attempt, second["request_id"], second_event)
        outcomes = (a.result(timeout=20), b.result(timeout=20))
    assert sum(isinstance(value, dict) for value in outcomes) == 1
    with connect_serializable(scope) as conn:
        daily = conn.execute("""SELECT held_minor FROM aip_budget_bucket
            WHERE org_id=%s AND project_id=%s AND bucket_kind='daily'
              AND account_id=%s""", (*scope.key, f"{budget.budget_id}:daily")
        ).fetchone()
        assert int(daily["held_minor"]) in (200, 400)
        assert conn.execute("""SELECT count(*) AS n FROM aip_model_eval_budget_reservation
            WHERE request_id IN (%s,%s)""",
            (first["request_id"], second["request_id"])).fetchone()["n"] == 1


def test_natural_eval_expiry_blocks_new_hold_and_keeps_prior_hold():
    from aos_api.aip_model_eval_budget_reservation import (
        AipModelEvalBudgetReservationStore, ModelEvalBudgetBlocked,
    )

    scope, held_request, held_application, held_proposal, _, budget, _, _ = (
        seeded_approved_model_eval_request(
            stop_after_approval=True, expiry_after=timedelta(seconds=20),
        )
    )
    _, unheld_request, unheld_application, unheld_proposal, _, _, _, _ = (
        seeded_approved_model_eval_request(
            stop_after_approval=True, expiry_after=timedelta(seconds=20),
        )
    )
    store = AipModelEvalBudgetReservationStore()
    held_event = _approval_event(scope, held_proposal.proposal.id)
    unheld_event = _approval_event(scope, unheld_proposal.proposal.id)
    with connect_serializable(scope) as conn:
        held = store.hold(conn, scope, held_request["request_id"], held_event)
    wait_until = max(held_application.expires_at,
                     unheld_application.expires_at)
    time.sleep(max(0, (wait_until - datetime.now(UTC)).total_seconds() + 0.25))
    for request_id, event_id in (
        (held_request["request_id"], held_event),
        (unheld_request["request_id"], unheld_event),
    ):
        with pytest.raises(ModelEvalBudgetBlocked, match="current immutable"):
            with connect_serializable(scope) as conn:
                store.hold(conn, scope, request_id, event_id)
    with connect_serializable(scope) as conn:
        rows = conn.execute("""SELECT request_id,reservation_id,state
            FROM aip_model_eval_budget_reservation
            WHERE request_id IN (%s,%s)""", (
                held_request["request_id"], unheld_request["request_id"],
            )).fetchall()
        assert rows == [{"request_id": held_request["request_id"],
                         "reservation_id": held["reservation_id"],
                         "state": "held"}]
        buckets = conn.execute("""SELECT bucket_kind,held_minor FROM aip_budget_bucket
            WHERE org_id=%s AND project_id=%s
              AND account_id IN (%s,%s,%s) ORDER BY bucket_kind""", (
                *scope.key, f"model-eval/{held_request['request_id']}",
                f"{budget.budget_id}:daily", f"{budget.budget_id}:pilot",
            )).fetchall()
        assert len(buckets) == 3
        assert all(int(row["held_minor"]) == held_application.upper_bound_minor
                   for row in buckets)


def test_model_eval_hold_requires_serializable_runtime_tenant():
    from aos_api.aip_model_eval_budget_reservation import (
        AipModelEvalBudgetReservationStore, ModelEvalBudgetBlocked,
    )

    scope, first, _, proposal, _, _, _, _ = (
        seeded_approved_model_eval_request(stop_after_approval=True)
    )
    event_id = _approval_event(scope, proposal.proposal.id)
    store = AipModelEvalBudgetReservationStore()
    with pytest.raises(ModelEvalBudgetBlocked, match="SERIALIZABLE"):
        with connect(scope) as conn:
            store.hold(conn, scope, first["request_id"], event_id)
    canary = TenantScope("dev-org", "dev-project")
    with pytest.raises(ModelEvalBudgetBlocked, match="current immutable"):
        with connect_serializable(canary) as conn:
            store.hold(conn, canary, first["request_id"], event_id)
    with connect_serializable(scope) as conn:
        assert conn.execute("""SELECT count(*) AS n FROM aip_model_eval_budget_reservation
            WHERE request_id=%s""", (first["request_id"],)).fetchone()["n"] == 0


@pytest.mark.parametrize("provider_model_id,expected_allowed,revoke_after_hold", [
    ("candidate-model", True, False),
    ("different-model", False, False),
    ("candidate-model", True, True),
])
def test_formal_signed_development_risk_counts_original_eval_hold(
    caller, issuer_factory, https_signer, provider_model_id, expected_allowed,
    revoke_after_hold,
):
    from uuid import uuid4
    from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
    from aos_api.aip_budget_cost_proposal_store import BudgetCostProposalStore
    from aos_api.aip_budget_cost_runtime import require_cost_risk, BudgetCostRuntimeBlocked
    from aos_api.aip_budget_reservation_contracts import BudgetExactRef
    from aos_api.aip_budget_reservation_store import BudgetReservationBlocked
    from aos_api.aip_budget_store import AipBudgetAuthorityStore
    from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevision
    from aos_api.aip_model_runtime_contracts import (
        ProviderInstanceRevision, ModelPriceSnapshotRevision,
    )
    from aos_api.aip_model_eval_budget_reservation import (
        AipModelEvalBudgetReservationStore, ModelEvalBudgetBlocked,
    )
    from tests.aip.test_budget_cost_proposal_pg import case
    from tests.aip._runtime_guard_history_fixture import produce_formal_provider
    from tests.aip.test_budget_cost_configuration_pg import derive

    scope = TenantScope("org-org", "dev-project")
    maker, checker, _, basis, key = case()
    provider = produce_formal_provider(scope, maker.subject,
                                       "eval-risk-provider-" + uuid4().hex)
    basis.basis.provider = basis.basis.provider.model_copy(update={
        "asset_id": provider.provider_instance_id,
        "content_hash": provider.content_hash,
    })
    basis.basis.max_requests = 2 if revoke_after_hold else 1
    basis.basis.total_risk_minor = (
        basis.basis.per_request_risk_minor * basis.basis.max_requests)
    saved = BudgetCostProposalStore().create(maker, basis, key)
    decision = BudgetCostIssuer(issuer_factory).execute(
        command(https_signer[0], checker, saved))
    with caller() as conn:
        consume(conn, saved, decision)
        configured = derive(conn, saved, decision)
    refs = configured["receipt"]
    budget = AipBudgetAuthorityStore().get(scope, refs["budgetRef"]["assetId"])
    with psycopg.connect(get_dsn()) as owner:
        policy_row = owner.execute("""SELECT payload FROM aip_model_governance_policy_revision
            WHERE org_id=%s AND project_id=%s AND policy_kind='budget'
              AND policy_id=%s AND revision=%s""",
            (*scope.key, refs["policyRef"]["assetId"], refs["policyRef"]["revision"])
        ).fetchone()
        price_row = owner.execute("""SELECT payload FROM aip_model_price_snapshot_revision
            WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s
              AND revision=%s""",
            (*scope.key, refs["priceRef"]["assetId"], refs["priceRef"]["revision"])
        ).fetchone()
    policy = BudgetPolicyRevision.model_validate(policy_row[0])
    price = ModelPriceSnapshotRevision.model_validate(price_row[0])
    scope, first, request, proposal, _, _, _, _ = seeded_approved_model_eval_request(
        stop_after_approval=True,
        formal_sources=(budget, policy, provider, price),
        upper_bound_minor=basis.basis.per_request_risk_minor,
        provider_model_id=provider_model_id,
    )
    event_id = _approval_event(scope, proposal.proposal.id)
    if not expected_allowed:
        with pytest.raises(ModelEvalBudgetBlocked, match="development cost.*model"):
            with connect_serializable(scope) as conn:
                AipModelEvalBudgetReservationStore().hold(
                    conn, scope, first["request_id"], event_id)
        with connect_serializable(scope) as conn:
            assert conn.execute("""SELECT count(*) AS n
                FROM aip_model_eval_budget_reservation WHERE request_id=%s""",
                (first["request_id"],)).fetchone()["n"] == 0
        return
    with connect_serializable(scope) as conn:
        AipModelEvalBudgetReservationStore().hold(
            conn, scope, first["request_id"], event_id)
    assert request.upper_bound_minor == basis.basis.per_request_risk_minor
    budget_ref = BudgetExactRef(
        resourceType="BudgetRevision", resourceId=budget.budget_id,
        revision=budget.revision, contentHash="sha256:" + budget.content_hash,
    )
    price_ref = BudgetExactRef(
        resourceType="ModelPriceSnapshotRevision", resourceId=price.price_snapshot_id,
        revision=price.revision, contentHash="sha256:" + price.content_hash,
    )
    provider_ref = BudgetExactRef(
        resourceType="ProviderInstanceRevision",
        resourceId=provider.provider_instance_id,
        revision=provider.revision,
        contentHash="sha256:" + provider.content_hash,
    )
    if revoke_after_hold:
        with connect_serializable(scope) as conn:
            require_cost_risk(conn, scope, budget_ref, price_ref,
                              basis.basis.per_request_risk_minor,
                              provider_ref=provider_ref)
        BudgetCostIssuer(issuer_factory).execute(command(
            https_signer[0], maker, saved, operation="revoke", decision=None,
            reason="withdraw before second Eval hold"))
        _, second, _, second_proposal, _, _, _, _ = seeded_approved_model_eval_request(
            stop_after_approval=True,
            formal_sources=(budget, policy, provider, price),
            upper_bound_minor=basis.basis.per_request_risk_minor,
            provider_model_id=provider_model_id,
        )
        second_event_id = _approval_event(scope, second_proposal.proposal.id)
        with pytest.raises(BudgetReservationBlocked,
                           match="BUDGET_COST_CURRENT_RISK_AUTHORITY_REQUIRED"):
            with connect_serializable(scope) as conn:
                AipModelEvalBudgetReservationStore().hold(
                    conn, scope, second["request_id"], second_event_id)
        with connect_serializable(scope) as conn:
            repeated = AipModelEvalBudgetReservationStore().hold(
                conn, scope, first["request_id"], event_id)
            assert repeated["request_id"] == first["request_id"]
        with connect_serializable(scope) as conn:
            assert conn.execute("""SELECT count(*) AS n
                FROM aip_model_eval_budget_reservation WHERE request_id=%s""",
                (second["request_id"],)).fetchone()["n"] == 0
            original = conn.execute("""SELECT reservation_id FROM
                aip_model_eval_budget_reservation WHERE request_id=%s
                  AND state='held'""", (first["request_id"],)).fetchone()
            assert original is not None
            links = conn.execute("""SELECT count(*) AS n,
                sum(reserved_minor) AS total FROM aip_model_eval_budget_reservation_bucket
                WHERE reservation_id=%s""", (original["reservation_id"],)).fetchone()
            assert links == {"n": 3, "total": 3 * basis.basis.per_request_risk_minor}
        return
    with pytest.raises(BudgetCostRuntimeBlocked, match="RISK_AUTHORITY_REQUIRED"):
        with connect_serializable(scope) as conn:
            require_cost_risk(conn, scope, budget_ref, price_ref,
                              basis.basis.per_request_risk_minor,
                              provider_ref=provider_ref)
    with connect_serializable(scope) as conn:
        require_cost_risk(conn, scope, budget_ref, price_ref,
                          basis.basis.per_request_risk_minor, new_hold=False)


@pytest.mark.parametrize("drift", ["price", "budget_policy"])
def test_approved_eval_cannot_hold_after_current_price_or_policy_head_moves(drift):
    from uuid import uuid4
    from aos_api.aip_model_eval_budget_reservation import (
        AipModelEvalBudgetReservationStore, ModelEvalBudgetBlocked,
    )
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
    from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevisionCreate
    from tests.aip.test_aip7_model_runtime_store import rehashed

    scope, first, _, proposal, _, budget, policy, price = (
        seeded_approved_model_eval_request(stop_after_approval=True)
    )
    event_id = _approval_event(scope, proposal.proposal.id)
    if drift == "price":
        next_price = rehashed(price, revision=2, inputTokenPrice="0.03")
        published = AipModelRuntimeStore().publish_price_snapshot(
            scope, "test-maker", "eval-price-drift-" + uuid4().hex,
            next_price, expected_version=1,
        )
        assert published.revision == 2
    else:
        body = policy.model_dump(mode="json", by_alias=True)
        for field in ("tenant", "contentHash", "createdBy", "createdAt"):
            body.pop(field, None)
        body.update(revision=2, lifecycle="draft")
        next_policy = BudgetPolicyRevisionCreate.model_validate(body)
        published = AipModelGovernancePolicyStore().publish_budget(
            scope, "test-maker", "eval-policy-drift-" + uuid4().hex,
            next_policy, expected_version=1,
        )
        assert published.revision == 2
    with pytest.raises(ModelEvalBudgetBlocked,
                       match="original Model Eval checker authority drifted"):
        with connect_serializable(scope) as conn:
            AipModelEvalBudgetReservationStore().hold(
                conn, scope, first["request_id"], event_id)
    with connect_serializable(scope) as conn:
        assert conn.execute("""SELECT count(*) AS n FROM aip_model_eval_budget_reservation
            WHERE request_id=%s""", (first["request_id"],)).fetchone()["n"] == 0
        assert conn.execute("""SELECT COALESCE(sum(held_minor),0) AS n
            FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s
              AND account_id LIKE %s""",
            (*scope.key, budget.budget_id + ":%"),
        ).fetchone()["n"] == 0
