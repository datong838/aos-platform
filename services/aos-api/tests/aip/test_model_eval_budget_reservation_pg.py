"""Isolated PostgreSQL proof for the first Model Eval budget hold schema."""

import psycopg
import pytest
from concurrent.futures import ThreadPoolExecutor
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
