from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from test_ui_read_request_pg import queue, attempt_case, database, insert, HASH, pytestmark
from aos_api.extension_runtime.ui_read_worker_store import claim_ui_read,complete_ui_read
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.tenant_scope import TenantScope

SCOPE=TenantScope('org-org','dev-project')


def claim(conn,request):
    with conn.transaction():return claim_ui_read(conn=conn,scope=SCOPE,request_id=request,snapshot_hash=HASH)


def complete(conn,value,**kwargs):
    with conn.transaction():return complete_ui_read(conn=conn,scope=SCOPE,claim=value,**kwargs)


def test_once_claim_and_atomic_success_without_token_in_repr(queue):
    conn,*_=queue;request=insert(queue)
    value=claim(conn,request)
    assert value.owner_token not in repr(value)
    assert claim(conn,request) is None
    assert complete(conn,value,result={})=='succeeded'
    assert claim(conn,request) is None
    assert conn.execute(
        'SELECT state,terminal_reason_code,terminal_error_type FROM extension_runtime_execution_attempt'
    ).fetchone()==('succeeded',None,None)
    with pytest.raises(RuntimeConflict):complete(conn,value,result={})


def test_claim_rollback_reverts_attempt_and_delivery(queue):
    conn,*_=queue;request=insert(queue)
    with pytest.raises(ValueError):
        with conn.transaction():
            claim_ui_read(conn=conn,scope=SCOPE,request_id=request,snapshot_hash=HASH)
            raise ValueError('caller abort')
    assert conn.execute('SELECT state FROM extension_runtime_ui_read_request').fetchone()==('requested',)
    assert conn.execute('SELECT count(*) FROM extension_runtime_execution_attempt').fetchone()==(0,)
    assert claim(conn,request) is not None


@pytest.mark.parametrize('kind',['failure','stale-runtime','forged-owner','forged-target'])
def test_failure_and_claim_identity(queue,kind):
    conn,*_=queue;value=claim(conn,insert(queue))
    if kind=='forged-owner':
        with pytest.raises(RuntimeConflict):complete(conn,replace(value,owner_token='different-'+'x'*40),result={})
    elif kind=='forged-target':
        request=value.request.model_copy(update={'target':value.request.target.model_copy(update={'bindingRevision':2})})
        with pytest.raises(RuntimeConflict):complete(conn,replace(value,request=request),result={})
    else:
        if kind=='stale-runtime':conn.execute("UPDATE extension_runtime_binding SET enabled=false,operation_fence=true,observed_state='draining',execution_epoch=2,revision=revision+1")
        assert complete(conn,value,**({'failure_code':'READ_FAILED'} if kind=='failure' else {'result':{}}))=='failed'
        assert conn.execute('SELECT result_json FROM extension_runtime_ui_read_request').fetchone()==(None,)
        expected='READ_FAILED' if kind=='failure' else 'READ_RUNTIME_CHANGED'
        assert conn.execute(
            'SELECT state,terminal_reason_code,terminal_error_type FROM extension_runtime_execution_attempt'
        ).fetchone()==('failed',expected,None)


def test_two_connections_only_one_claim(queue):
    conn,*_=queue;request=insert(queue)
    schema=conn.execute('SELECT current_schema()').fetchone()[0];started=Event()
    def contender():
        with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True) as second:
            second.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            second.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
            second.execute("SET statement_timeout='5s'");started.set()
            return claim(second,request)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with conn.transaction():
            first=claim_ui_read(conn=conn,scope=SCOPE,request_id=request,snapshot_hash=HASH)
            future=pool.submit(contender);assert started.wait(2)
        assert future.result(timeout=6) is None
    assert first is not None
    assert conn.execute('SELECT count(*) FROM extension_runtime_execution_attempt').fetchone()==(1,)


def short_request(queue):
    conn,*_=queue;original=insert(queue);short=uuid4()
    conn.execute('''INSERT INTO extension_runtime_ui_read_request
        (org_id,project_id,request_id,subject,idempotency_key,request_hash,installation_id,generation,execution_epoch,
         operation_id,module_id,target_json,case_limit,run_limit,state,deadline)
        SELECT org_id,project_id,%s,subject,%s,request_hash,installation_id,generation,execution_epoch,
         operation_id,module_id,target_json,case_limit,run_limit,'requested',clock_timestamp()+interval '500 milliseconds'
        FROM extension_runtime_ui_read_request WHERE request_id=%s''',(short,str(short),original))
    return short


def test_expired_claim_discards_result(queue):
    conn,*_=queue;short=short_request(queue)
    value=claim(conn,short)
    conn.execute('SELECT pg_sleep(0.6)')
    assert complete(conn,value,result={})=='expired'
    assert conn.execute('SELECT result_json,failure_code FROM extension_runtime_ui_read_request WHERE request_id=%s',(short,)).fetchone()==(None,'READ_DEADLINE_EXPIRED')
    assert conn.execute(
        'SELECT terminal_reason_code,terminal_error_type FROM extension_runtime_execution_attempt'
    ).fetchone()==('READ_DEADLINE_EXPIRED',None)


def test_result_storage_failure_rolls_back_attempt_settlement(queue):
    conn,*_=queue;value=claim(conn,insert(queue))
    with pytest.raises(psycopg.errors.CheckViolation):complete(conn,value,result={'oversized':'x'*900001})
    assert conn.execute('SELECT state FROM extension_runtime_execution_attempt').fetchone()==('running',)
    assert conn.execute('SELECT state,result_json FROM extension_runtime_ui_read_request').fetchone()==('claimed',None)


def test_foreign_scope_cannot_claim_positive_request(queue):
    conn,*_=queue;request=insert(queue)
    conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    with conn.transaction():
        assert claim_ui_read(conn=conn,scope=TenantScope('dev-org','dev-project'),request_id=request,snapshot_hash=HASH) is None
    assert conn.execute('SELECT count(*) FROM extension_runtime_execution_attempt').fetchone()==(0,)
