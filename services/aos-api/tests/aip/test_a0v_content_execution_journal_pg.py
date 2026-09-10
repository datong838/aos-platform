import importlib.util
import os
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from psycopg import errors
from test_aip_budget_reservation_pg import database, seed, runtime_connection, ROOT
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal, ContentExecutionConflict
from aos_api.tenant_scope import TenantScope

pytestmark = pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='isolated PostgreSQL opt-in')


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

