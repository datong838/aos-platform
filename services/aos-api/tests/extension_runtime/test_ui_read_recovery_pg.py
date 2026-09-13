import pytest
from test_ui_read_worker_store_pg import queue,attempt_case,database,short_request,claim,SCOPE,pytestmark
from aos_api.extension_runtime.generation_attempts import PostgresRuntimeAttemptStore
from aos_api.extension_runtime.ui_read_recovery import expire_ui_read_deliveries
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.tenant_scope import TenantScope


def expire(conn,**kwargs):
    with conn.transaction():return expire_ui_read_deliveries(conn=conn,scope=SCOPE,**kwargs)


def test_requested_expiry_is_bounded_and_idempotent(queue):
    conn,*_=queue;requests=[short_request(queue) for _ in range(2)]
    assert expire(conn)==()
    conn.execute('SELECT pg_sleep(0.6)')
    first=expire(conn,limit=1);second=expire(conn,limit=1)
    assert len(first)==len(second)==1 and set(first+second)==set(requests)
    assert expire(conn)==()
    assert conn.execute('SELECT count(*) FROM extension_runtime_execution_attempt').fetchone()==(0,)


def test_claimed_expiry_waits_for_existing_attempt_recovery(queue):
    conn,*_=queue;request=short_request(queue);value=claim(conn,request)
    conn.execute('SELECT pg_sleep(0.6)')
    assert expire(conn)==()
    assert conn.execute('SELECT state FROM extension_runtime_execution_attempt').fetchone()==('running',)
    with conn.transaction():
        recovered=PostgresRuntimeAttemptStore().abandon_expired_reads(conn,org_id=SCOPE.org_id,project_id=SCOPE.project_id)
    assert recovered==(value.attempt_id,)
    assert expire(conn)==(request,)
    assert claim(conn,request) is None
    assert expire(conn)==()
    assert conn.execute('SELECT count(*) FROM extension_runtime_execution_attempt').fetchone()==(1,)


def test_running_claim_does_not_starve_other_expired_delivery(queue):
    conn,*_=queue;pending=short_request(queue);claim(conn,pending);ready=short_request(queue)
    conn.execute('SELECT pg_sleep(0.6)')
    assert expire(conn,limit=1)==(ready,)
    assert conn.execute('SELECT state FROM extension_runtime_ui_read_request WHERE request_id=%s',(pending,)).fetchone()==('claimed',)


def test_foreign_scope_and_invalid_limit(queue):
    conn,*_=queue;short_request(queue)
    with pytest.raises(RuntimeConflict):expire(conn,limit=True)
    conn.execute('SELECT pg_sleep(0.6)')
    conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    with conn.transaction():
        assert expire_ui_read_deliveries(conn=conn,scope=TenantScope('dev-org','dev-project'))==()
    assert conn.execute("SELECT count(*) FROM extension_runtime_ui_read_request WHERE state='expired'").fetchone()==(0,)
