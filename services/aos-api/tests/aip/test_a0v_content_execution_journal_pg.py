import importlib.util
import os
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from psycopg import errors
from test_aip_budget_reservation_pg import (
    database, seed, runtime_connection, content_generate_command, ROOT,
)
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal, ContentExecutionConflict
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentGenerateHostService, ReviewAdvanceHostService,
    TransactionBoundConnectFactory,
)
from aos_api.tenant_scope import TenantScope

pytestmark = pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='isolated PostgreSQL opt-in')


def test_host_budget_and_content_command_commit_or_rollback_together(database):
    spec = importlib.util.spec_from_file_location(
        'journal_migration', ROOT/'alembic/versions/a0v_003_content_execution_journal.py'
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=database.owner.execute)
    migration.upgrade()
    scope = TenantScope('org-org', 'dev-project')
    factory = runtime_connection(database)
    request, _, _ = seed(database, scope, task_id='host-journal', upper=100, now=datetime.now(UTC))
    command = {'operation': 'content.generate', 'requestHash': 'sha256:'+'a'*64}
    with factory(scope) as conn:
        host = HostTransaction(conn)
        budget = AipBudgetReservationStore(
            TransactionBoundConnectFactory(host, scope),
            authority_schema=database.schema, storage_schema=database.schema,
        )
        held = budget.reserve(scope, request, actor='test')
        rid = held.reservation_ref.resource_id
        assert host.enqueue_content_command(
            scope=scope, reservation_id=rid,
            budget_request_hash=request.request_hash(), command=command,
            storage_schema=database.schema,
        ) == command
        assert host.read_content_command(
            scope=scope, reservation_id=rid, storage_schema=database.schema,
        ) == {'command': command, 'result': None}
    with factory(scope) as conn:
        assert ContentExecutionJournal(storage_schema=database.schema).read(
            conn, scope, rid
        )['command'] == command
    rollback_request, _, _ = seed(
        database, scope, task_id='host-journal-rollback', upper=100,
        now=datetime.now(UTC),
    )
    rolled = []
    with pytest.raises(RuntimeError, match='rollback witness'):
        with factory(scope) as conn:
            with conn.transaction():
                host = HostTransaction(conn)
                budget = AipBudgetReservationStore(
                    TransactionBoundConnectFactory(host, scope),
                    authority_schema=database.schema, storage_schema=database.schema,
                )
                held = budget.reserve(scope, rollback_request, actor='test')
                rolled.append(held.reservation_ref.resource_id)
                host.enqueue_content_command(
                    scope=scope, reservation_id=rolled[0],
                    budget_request_hash=rollback_request.request_hash(),
                    command=command, storage_schema=database.schema,
                )
                raise RuntimeError('rollback witness')
    assert rolled
    assert database.owner.execute(
        'SELECT 1 FROM aip_budget_reservation WHERE reservation_id=%s', (rolled[0],)
    ).fetchone() is None
    assert database.owner.execute(
        'SELECT 1 FROM ecommerce_content_execution_command WHERE reservation_id=%s', (rolled[0],)
    ).fetchone() is None


def test_v2_host_pending_receipt_stays_exact_after_budget_submission(database, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        'journal_migration', ROOT/'alembic/versions/a0v_003_content_execution_journal.py'
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=database.owner.execute)
    migration.upgrade()
    scope = TenantScope('org-org', 'dev-project')
    factory = runtime_connection(database)
    request, refs, _ = seed(
        database, scope, task_id='host-pending', upper=100, now=datetime.now(UTC),
    )
    command = content_generate_command(request)
    monkeypatch.setattr(
        ReviewAdvanceHostService, '_revalidate_growth_plan',
        staticmethod(lambda **_: SimpleNamespace(sales_weapon_method=object())),
    )
    monkeypatch.setattr(
        ContentGenerateHostService, '_budget_store',
        staticmethod(lambda host, bound_scope: AipBudgetReservationStore(
            TransactionBoundConnectFactory(host, bound_scope),
            authority_schema=database.schema, storage_schema=database.schema,
        )),
    )
    monkeypatch.setattr(
        ContentGenerateHostService, '_runtime_command_authority',
        staticmethod(lambda *_: None),
    )
    original_enqueue = HostTransaction.enqueue_content_command
    original_read = HostTransaction.read_content_command
    monkeypatch.setattr(
        HostTransaction, 'enqueue_content_command',
        lambda self, **kwargs: original_enqueue(self, storage_schema=database.schema, **kwargs),
    )
    monkeypatch.setattr(
        HostTransaction, 'read_content_command',
        lambda self, **kwargs: original_read(self, storage_schema=database.schema, **kwargs),
    )
    service = ContentGenerateHostService()
    with factory(scope) as conn:
        host = HostTransaction(conn)
        receipt = service.execute(
            transaction=host, scope=scope, dispatch_ref=object(), command=command,
            checked_at=None, occurred_at=None,
        )
        assert receipt['state'] == 'PENDING'
        assert service.verify_receipt(
            transaction=host, scope=scope, dispatch=None,
            command=command, receipt=receipt,
        ) == receipt
    rid = receipt['budgetReservationRef']['resourceId']
    submitted = AipBudgetReservationStore(
        factory, authority_schema=database.schema, storage_schema=database.schema,
    ).submit(scope, rid, provider_ref=refs['provider'],
             provider_idempotency_hash='8'*64, actor='test')
    assert submitted.state.value == 'submitted'
    monkeypatch.setattr(
        ContentGenerateHostService, '_runtime_command_authority',
        staticmethod(lambda *_: receipt),
    )
    with factory(scope) as conn:
        host = HostTransaction(conn)
        assert service.verify_receipt(
            transaction=host, scope=scope, dispatch=None,
            command=command, receipt=receipt,
        ) == receipt
        assert service.execute(
            transaction=host, scope=scope, dispatch_ref=object(), command=command,
            checked_at=None, occurred_at=None,
        ) == receipt


def test_journal_is_durable_immutable_and_scoped(database):
    spec = importlib.util.spec_from_file_location('journal_migration', ROOT/'alembic/versions/a0v_003_content_execution_journal.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=database.owner.execute)
    migration.upgrade()
    migration.downgrade()
    migration.upgrade()
    scope = TenantScope('org-org', 'dev-project')
    factory = runtime_connection(database)
    request, refs, _ = seed(database, scope, task_id='journal', now=datetime.now(UTC))
    budget = AipBudgetReservationStore(factory, authority_schema=database.schema)
    held = budget.reserve(scope, request, actor='test')
    rid = held.reservation_ref.resource_id
    journal = ContentExecutionJournal(storage_schema=database.schema)
    command = {'operation': 'content.generate', 'requestHash': 'sha256:'+'a'*64}
    from concurrent.futures import ThreadPoolExecutor
    def enqueue_once():
        with factory(scope) as conn:
            return journal.enqueue(conn, scope, rid, budget_request_hash=request.request_hash(), command=command)
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: enqueue_once(), range(2)))
    assert outcomes == [command, command]
    first = outcomes[0]
    assert database.owner.execute('SELECT count(*) AS n FROM ecommerce_content_execution_command').fetchone()['n'] == 1
    with factory(scope) as conn:
        assert journal.enqueue(conn, scope, rid, budget_request_hash=request.request_hash(), command=command) == first
        with pytest.raises(ContentExecutionConflict):
            journal.enqueue(conn, scope, rid, budget_request_hash=request.request_hash(), command=command | {'extra': 1})
    with factory(TenantScope('dev-org','dev-project')) as conn:
        assert journal.read(conn, TenantScope('dev-org','dev-project'), rid) is None
        # Passing a positive scope cannot bypass the negative transaction RLS.
        assert journal.read(conn, scope, rid) is None
    with factory(scope) as conn:
        with pytest.raises(ContentExecutionConflict):
            journal.record_result(conn, scope, rid, provider_request_ref={'bad': 1}, result={'answer':'text'})
    submitted = budget.submit(scope, rid, provider_ref=refs['provider'], provider_idempotency_hash='8'*64, actor='test')
    request_ref = submitted.provider_request_receipt_ref.model_dump(mode='json', by_alias=True, exclude_none=True)
    with factory(scope) as conn:
        result = journal.record_result(conn, scope, rid, provider_request_ref=request_ref, result={'answer':'approved public facts'})
    with factory(scope) as conn:
        assert journal.record_result(conn, scope, rid, provider_request_ref=request_ref, result={'answer':'approved public facts'}) == result
        with pytest.raises(ContentExecutionConflict):
            journal.record_result(conn, scope, rid, provider_request_ref=request_ref, result={'answer':'different'})
        assert journal.read(conn, scope, rid)['result'] == {'answer':'approved public facts'}
        for operation in ('UPDATE ecommerce_content_execution_command SET command_payload=\'{}\'', 'DELETE FROM ecommerce_content_execution_result'):
            with pytest.raises(errors.InsufficientPrivilege), conn.transaction():
                conn.execute(operation)
    with factory(scope) as conn:
        conn.execute("SELECT set_config('aos.org_id','',true),set_config('aos.project_id','',true)")
        assert journal.read(conn, scope, rid) is None
        with pytest.raises(ContentExecutionConflict):
            journal.enqueue(conn, scope, rid, budget_request_hash=request.request_hash(), command=command)
    with pytest.raises(errors.RaiseException), database.owner.transaction():
        database.owner.execute("UPDATE ecommerce_content_execution_command SET command_payload='{}'")
    with pytest.raises(errors.RaiseException), database.owner.transaction():
        migration.downgrade()
