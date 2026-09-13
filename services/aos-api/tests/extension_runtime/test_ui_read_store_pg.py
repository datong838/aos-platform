from concurrent.futures import ThreadPoolExecutor
from threading import Event

import psycopg
from psycopg import sql
import pytest

from test_ui_read_request_pg import queue, attempt_case, database, HASH, pytestmark
from aos_api.extension_runtime.ui_read_store import enqueue_ui_read
from aos_api.extension_runtime.ui_read_contracts import UiReadRequest
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('org-org', 'dev-project')


@pytest.fixture
def admission(queue):
    conn, installation, generation, role = queue
    conn.execute('CREATE TABLE meta_membership(org_id text,project_id text,subject text,role text)')
    conn.execute("INSERT INTO meta_membership VALUES('org-org','dev-project','reader','reader'),('org-org','dev-project','other','reader')")
    request = UiReadRequest.model_validate(dict(schemaVersion='aos.runtime-ui-read-request/v1',
        operationId='analyst_workspace_view_v1', moduleId='ecommerce.analyst',
        target=dict(installationId=str(installation), installationRevision=1, generation=str(generation),
            executionEpoch=1, bindingRevision=1, route='/workshop/analyst', resourceHash=HASH)))
    return conn, request


def enqueue(conn, request, key='same', subject='reader'):
    with conn.transaction():
        return enqueue_ui_read(conn=conn, scope=SCOPE, subject=subject, idempotency_key=key, request=request)


def test_same_key_replays_without_new_request_and_conflict_fails(admission):
    conn, request = admission
    first = enqueue(conn, request)
    assert enqueue(conn, request) == first
    with pytest.raises(RuntimeConflict, match='conflicts'):
        enqueue(conn, request.model_copy(update={'caseLimit': 10}))
    assert conn.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone() == (1,)
    assert enqueue(conn, request, subject='other').request_id != first.request_id


def test_current_membership_and_tenant_required_even_on_replay(admission):
    conn, request = admission
    enqueue(conn, request)
    conn.execute("DELETE FROM meta_membership WHERE subject='reader'")
    with pytest.raises(RuntimeConflict, match='membership'): enqueue(conn, request)
    conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    with pytest.raises(RuntimeConflict, match='scope'): enqueue(conn, request, subject='other')


def test_subject_capacity_and_replay_at_capacity(admission):
    conn, request = admission
    first = enqueue(conn, request, key='0')
    for index in range(1,8): enqueue(conn, request, key=str(index))
    with pytest.raises(RuntimeConflict, match='capacity'): enqueue(conn, request, key='overflow')
    assert enqueue(conn, request, key='0') == first
    enqueue(conn, request, subject='other')
    assert conn.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone() == (9,)


def test_caller_rollback_and_no_implicit_transaction(admission):
    conn, request = admission
    with pytest.raises(RuntimeError):
        enqueue_ui_read(conn=conn, scope=SCOPE, subject='reader', idempotency_key='x', request=request)
    with pytest.raises(ValueError):
        with conn.transaction():
            enqueue_ui_read(conn=conn, scope=SCOPE, subject='reader', idempotency_key='x', request=request)
            raise ValueError('abort caller')
    assert conn.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone() == (0,)
    with conn.transaction():
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        with pytest.raises(RuntimeConflict, match='read committed'): enqueue_ui_read(conn=conn,scope=SCOPE,subject='reader',idempotency_key='x',request=request)


def test_concurrent_final_slot_is_not_oversubscribed(admission):
    conn, request = admission
    for index in range(7): enqueue(conn, request, key=str(index))
    schema = conn.execute('SELECT current_schema()').fetchone()[0]
    started = Event()
    def contender():
        with psycopg.connect(host='127.0.0.1', port=18432, user='postgres', dbname='postgres', autocommit=True) as second:
            second.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            second.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
            second.execute("SET statement_timeout='5s'")
            started.set()
            with pytest.raises(RuntimeConflict, match='capacity'):
                enqueue(second, request, key='contender')
    with ThreadPoolExecutor(max_workers=1) as pool:
        with conn.transaction():
            enqueue_ui_read(conn=conn,scope=SCOPE,subject='reader',idempotency_key='winner',request=request)
            future = pool.submit(contender)
            assert started.wait(2)
        future.result(timeout=6)
    assert conn.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone() == (8,)


def test_tenant_capacity_spans_subjects(admission):
    conn, request = admission
    for member in range(8):
        subject = f'member-{member}'
        conn.execute("INSERT INTO meta_membership VALUES('org-org','dev-project',%s,'reader')",(subject,))
        for index in range(8): enqueue(conn,request,key=str(index),subject=subject)
    with pytest.raises(RuntimeConflict,match='capacity'): enqueue(conn,request,subject='other')
    assert conn.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone() == (64,)


def test_stale_binding_is_rejected_by_insert_guard(admission):
    conn, request = admission
    with pytest.raises(psycopg.Error,match='runtime unavailable'):
        enqueue(conn, request.model_copy(update={'target':request.target.model_copy(update={'bindingRevision':2})}))
    assert conn.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone() == (0,)
