"""Keep independent queue work moving without retrying unknown submissions."""
from contextlib import contextmanager
from types import SimpleNamespace
import os

import pytest

from aos_api.ecommerce_content_execution_composition import CurrentContentRunner
from aos_api.ecommerce_content_execution_worker import ContentExecutionFailure
from aos_api.tenant_scope import TenantScope
from test_aip_budget_reservation_pg import database


SCOPE = TenantScope("org-org", "dev-project")


def runner_with_items(items, outcomes):
    runner = object.__new__(CurrentContentRunner)
    calls = []

    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield object()

    def run_one(scope, reservation_id):
        assert scope == SCOPE
        calls.append(reservation_id)
        outcome = outcomes[reservation_id]
        if isinstance(outcome, Exception):
            raise outcome
        return {"status": outcome}

    runner.connect = connect
    runner.journal = SimpleNamespace(list_held=lambda *_args, **_kwargs: list(items))
    runner.worker = SimpleNamespace(run_one=run_one)
    return runner, calls


@pytest.mark.parametrize("message", [
    "provider outcome unknown; reconciliation required",
    "provider outcome unknown; reconciliation persistence failed",
    "provider result persistence failed; do not resubmit",
])
def test_unknown_or_result_persistence_failure_does_not_stop_independent_item(message):
    runner, calls = runner_with_items(["unknown", "independent"], {
        "unknown": ContentExecutionFailure(message), "independent": "RESULT_RECORDED",
    })
    assert runner.run_pending(SCOPE) == [
        {"reservationId": "unknown", "status": "RECONCILE_REQUIRED"},
        {"reservationId": "independent", "status": "RESULT_RECORDED"},
    ]
    assert calls == ["unknown", "independent"]


def test_unknown_is_not_manually_added_back_after_original_selector_excludes_it():
    items = ["unknown", "independent"]
    runner, calls = runner_with_items(items, {
        "unknown": ContentExecutionFailure("unknown"), "independent": "RESULT_RECORDED",
    })
    recorded = []
    runner.run_recorded = lambda *_args, **_kwargs: recorded.append("accounting") or []
    first = runner.run_once(SCOPE)
    assert first["pending"][0]["status"] == "RECONCILE_REQUIRED"
    items.clear()  # Native journal excludes submitted/unknown and recorded results.
    second = runner.run_once(SCOPE)
    assert second["pending"] == []
    assert calls == ["unknown", "independent"]
    assert recorded == ["accounting"] * 4


def test_unclassified_failure_is_not_silently_hidden_or_called_completed():
    runner, calls = runner_with_items(["bad", "independent"], {
        "bad": RuntimeError("unexpected failure"), "independent": "RESULT_RECORDED",
    })
    with pytest.raises(RuntimeError, match="unexpected failure"):
        runner.run_pending(SCOPE)
    assert calls == ["bad"]


@pytest.mark.skipif(os.getenv("AOS_EXTENSION_PG_TEST") != "1", reason="isolated PostgreSQL opt-in")
def test_native_unknown_hold_survives_while_independent_result_is_recorded(database):
    from datetime import UTC, datetime
    from psycopg.types.json import Jsonb
    from test_a0v_content_execution_worker_pg import setup
    from test_aip_budget_reservation_pg import seed, content_generate_command
    from aos_api.ecommerce_content_execution_worker import ContentExecutionWorker
    from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal, _payload
    from aos_api.ecommerce_growth_runtime_adapters import ContentGenerateHostService

    scope, factory, budget, first_id, prepare = setup(
        database, command_factory=content_generate_command,
    )
    request, _, _ = seed(database, scope, task_id="independent-next", upper=1, now=datetime.now(UTC))
    second_id = budget.reserve(scope, request, actor="isolated-test").reservation_ref.resource_id
    journal = ContentExecutionJournal(storage_schema=database.schema)
    with factory(scope) as conn:
        journal.enqueue(conn, scope, second_id, budget_request_hash=request.request_hash(),
                        command=content_generate_command(request))
    database.owner.execute("""CREATE TABLE ecommerce_growth_runtime_command_receipt (
        org_id text,project_id text,operation_id text,idempotency_key text,
        request_hash text,response jsonb)""")
    database.owner.execute("GRANT SELECT ON ecommerce_growth_runtime_command_receipt TO aos_runtime")
    for reservation_id in [first_id, second_id]:
        with factory(scope) as conn:
            command = journal.read(conn, scope, reservation_id)["command"]
        receipt = ContentGenerateHostService._pending_receipt(
            command, budget.get(scope, reservation_id),
            ContentGenerateHostService._budget_request(command), replayed=False,
        )
        database.owner.execute("""INSERT INTO ecommerce_growth_runtime_command_receipt
            VALUES(%s,%s,'ecommerce_growth_content_generate',%s,%s,%s)""",
            (*scope.key, command["idempotencyKey"], "sha256:" + _payload(command)[1], Jsonb(receipt)))

    calls = []
    def invoke(*_args):
        calls.append("bounded-test-invocation")
        if len(calls) == 1:
            raise TimeoutError("test-only unknown outcome")
        return {"answer": "独立任务的测试内容"}

    runner = CurrentContentRunner(connect_factory=factory, storage_schema=database.schema)
    runner.worker = ContentExecutionWorker(factory, prepare=prepare, invoke=invoke,
                                         storage_schema=database.schema)
    assert runner.run_pending(scope) == [
        {"reservationId": first_id, "status": "RECONCILE_REQUIRED"},
        {"reservationId": second_id, "status": "RESULT_RECORDED"},
    ]
    assert budget.get(scope, first_id).state.value == "unknown"
    assert budget.get(scope, first_id).actual_minor is None
    with factory(scope) as conn:
        assert journal.read(conn, scope, first_id)["result"] is None
        assert journal.read(conn, scope, second_id)["result"]["answer"] == "独立任务的测试内容"
        assert conn.execute("SELECT count(*) AS n FROM aip_capability_provider_request_receipt").fetchone()["n"] == 2
    assert runner.run_pending(scope) == []
    assert runner.run_pending(TenantScope("dev-org", "dev-project")) == []
    assert len(calls) == 2
