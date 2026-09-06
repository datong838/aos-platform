from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
import threading
import uuid

import psycopg
from psycopg import sql
import pytest

from test_lifecycle_pg import database,seed,pytestmark
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore,RuntimeConflict

SCOPE=dict(org_id='org-org',project_id='dev-project')


def accepted(conn):
    installation,_=seed(conn)
    conn.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
    with conn.transaction():
        return RuntimeOperationStore().accept(conn,**SCOPE,installation_id=installation,kind='runtime-apply',
            idempotency_key='outbox',requested_by='tester',expected_installation_etag=1,
            deadline=datetime.now(timezone.utc)+timedelta(minutes=1))


def test_outbox_claim_commit_retry_ack_and_rollback(database):
    from aos_api.extension_runtime.outbox_store import RuntimeOutboxStore
    conn,_,_=database
    operation=accepted(conn);store=RuntimeOutboxStore()
    before=conn.execute('SELECT revision,status,phase FROM extension_runtime_operation ORDER BY operation_id').fetchall()
    with pytest.raises(RuntimeError):
        with conn.transaction():
            assert store.claim(conn,**SCOPE).attempt==1
            raise RuntimeError('rollback')
    with conn.transaction():first=store.claim(conn,**SCOPE)
    assert first.operation_id==operation.operation_id and first.event_type=='accepted' and first.attempt==1
    with conn.transaction():assert store.claim(conn,**SCOPE) is None
    with conn.transaction():store.retry(conn,**SCOPE,lease=first,delay_seconds=1)
    with conn.transaction():assert store.claim(conn,**SCOPE) is None
    conn.execute("UPDATE extension_runtime_outbox SET next_attempt=clock_timestamp()-interval '1 second'")
    with conn.transaction():second=store.claim(conn,**SCOPE)
    assert second.attempt==2 and second.event_id==first.event_id
    for method in (store.ack,store.retry):
        with pytest.raises(RuntimeConflict):
            with conn.transaction():method(conn,**SCOPE,lease=first)
    with conn.transaction():store.ack(conn,**SCOPE,lease=second)
    with conn.transaction():assert store.claim(conn,**SCOPE) is None
    assert conn.execute('SELECT revision,status,phase FROM extension_runtime_operation ORDER BY operation_id').fetchall()==before


@pytest.mark.parametrize('mode',['expired','tenant','attempt','operation','sequence','type','hash','lease_seconds','bool','foreign_consumer'])
def test_outbox_rejects_untrusted_or_stale_claims(database,mode):
    from dataclasses import replace
    from aos_api.extension_runtime.outbox_store import RuntimeOutboxStore
    conn,_,_=database;accepted(conn);store=RuntimeOutboxStore()
    if mode=='hash':
        conn.execute('ALTER TABLE extension_runtime_event DISABLE TRIGGER immutable_history')
        conn.execute("UPDATE extension_runtime_event SET payload_hash=%s",('sha256:'+'f'*64,))
        with pytest.raises(RuntimeConflict):
            with conn.transaction():store.claim(conn,**SCOPE)
        assert conn.execute('SELECT attempt FROM extension_runtime_outbox').fetchone()==(0,)
        return
    if mode in ('lease_seconds','bool'):
        with pytest.raises(ValueError):
            with conn.transaction():store.claim(conn,**SCOPE,lease_seconds=301 if mode=='lease_seconds' else True)
        return
    if mode=='foreign_consumer':
        conn.execute("UPDATE extension_runtime_outbox SET consumer_id='other-consumer'")
        with conn.transaction():assert store.claim(conn,**SCOPE) is None
        return
    with conn.transaction():lease=store.claim(conn,**SCOPE)
    if mode=='expired':conn.execute("UPDATE extension_runtime_outbox SET claim_until=clock_timestamp()-interval '1 second'")
    if mode=='attempt':lease=replace(lease,attempt=lease.attempt+1)
    if mode=='operation':lease=replace(lease,operation_id=uuid.uuid4())
    if mode=='sequence':lease=replace(lease,sequence=lease.sequence+1)
    if mode=='type':lease=replace(lease,event_type='different')
    scope=SCOPE if mode!='tenant' else {**SCOPE,'org_id':'dev-org'}
    with pytest.raises((RuntimeConflict,PermissionError)):
        with conn.transaction():store.ack(conn,**scope,lease=lease)
    assert conn.execute('SELECT delivered_at FROM extension_runtime_outbox').fetchone()==(None,)


def test_two_connections_claim_one_event_once(database):
    from aos_api.extension_runtime.outbox_store import RuntimeOutboxStore
    conn,_,schema=database;accepted(conn)
    barrier=threading.Barrier(2)
    def claim():
        with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True) as worker:
            worker.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            worker.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
            barrier.wait(timeout=3)
            with worker.transaction():return RuntimeOutboxStore().claim(worker,**SCOPE)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(claim) for _ in range(2)]
        values=[f.result(timeout=5) for f in futures]
    assert sum(v is not None for v in values)==1
    assert conn.execute('SELECT attempt FROM extension_runtime_outbox').fetchone()==(1,)


def test_ack_waiting_on_row_lock_rechecks_expiration(database):
    import time
    from aos_api.extension_runtime.outbox_store import RuntimeOutboxStore
    conn,_,schema=database;accepted(conn);store=RuntimeOutboxStore()
    with conn.transaction():lease=store.claim(conn,**SCOPE,lease_seconds=1)
    with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True) as worker:
        worker.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        worker.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
        worker.execute("SET statement_timeout='5s'")
        def ack():
            with worker.transaction():store.ack(worker,**SCOPE,lease=lease)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with conn.transaction():
                conn.execute('SELECT event_id FROM extension_runtime_outbox FOR UPDATE')
                future=pool.submit(ack)
                end=time.monotonic()+2
                while not conn.execute('SELECT cardinality(pg_blocking_pids(%s))>0',(worker.info.backend_pid,)).fetchone()[0]:
                    assert time.monotonic()<end
                    time.sleep(.01)
                conn.execute('SELECT pg_sleep(1.1)')
            with pytest.raises(RuntimeConflict,match='expired'):future.result(timeout=3)
    with conn.transaction():reclaimed=store.claim(conn,**SCOPE)
    assert reclaimed.attempt==2
    with conn.transaction():store.ack(conn,**SCOPE,lease=reclaimed)
