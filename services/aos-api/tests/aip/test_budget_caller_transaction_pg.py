"""Ordinary budget holds share the actual caller transaction; no send permission."""
from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, BudgetReservationBlocked, BudgetReservationConflict
from aos_api.tenant_scope import TenantScope
from tests.aip.test_aip_budget_reservation_pg import PG, seed

pytest_plugins = ('tests.aip.test_aip_budget_reservation_pg',)
SCOPE = TenantScope('org-org','dev-project')


@contextmanager
def caller(database):
    conn = psycopg.connect(**PG,row_factory=dict_row)
    conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
    try:
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(database.schema)))
        conn.execute('SET LOCAL ROLE aos_runtime')
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        yield conn
    finally:
        if not conn.closed:
            conn.rollback()
        conn.close()


def snapshot(database):
    return [database.owner.execute(sql.SQL('SELECT count(*) AS n FROM {}.{} WHERE org_id=%s AND project_id=%s')
        .format(sql.Identifier(database.schema),sql.Identifier(table)),SCOPE.key).fetchone()['n']
        for table in ['aip_capability_invocation','aip_budget_reservation','aip_budget_reservation_bucket','aip_budget_reservation_event']]


@pytest.mark.parametrize('finish',['commit','rollback','exception'])
def test_budget_hold_keeps_actual_caller_transaction(database,finish):
    request,_,_ = seed(database,SCOPE,task_id='caller-budget-'+uuid4().hex)
    def forbidden_factory(*args,**kwargs):
        pytest.fail('caller budget must not open another connection')
    store = AipBudgetReservationStore(forbidden_factory,authority_schema=database.schema)
    with caller(database) as conn:
        before = conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        held = store.reserve_in_transaction(conn,SCOPE,request,actor='tester')
        assert held.state=='held' and not held.replayed
        assert conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()==before
        assert snapshot(database)==[0,0,0,0]
        replay = store.reserve_in_transaction(conn,SCOPE,request,actor='tester')
        assert replay.replayed and replay.reservation_ref==held.reservation_ref
        assert snapshot(database)==[0,0,0,0]
        with pytest.raises(BudgetReservationConflict):
            store.reserve_in_transaction(conn,SCOPE,request.model_copy(update={'upper_bound_minor':request.upper_bound_minor+1}),actor='tester')
        if finish=='commit':
            conn.commit()
            assert snapshot(database)==[1,1,3,1]
            row = database.owner.execute(sql.SQL('SELECT sum(held_minor) AS held,sum(submitted_minor+settled_minor+unknown_minor) AS other FROM {}.aip_budget_bucket').format(sql.Identifier(database.schema))).fetchone()
            assert row=={'held':request.upper_bound_minor*3,'other':0}
        elif finish=='rollback':
            conn.rollback()
            assert snapshot(database)==[0,0,0,0]
        else:
            try:
                raise RuntimeError('synthetic downstream failure after genuine hold')
            except RuntimeError:
                conn.rollback()
            assert snapshot(database)==[0,0,0,0]
        print('budget caller proof',finish,'same_native_xid_pid observer_invisible_before_finish')


@pytest.mark.parametrize('fault',['facade','idle','readonly','isolation','role','tenant','autocommit','closed','scope','request_bool','request_kind','actor'])
def test_budget_caller_rejects_context_without_writes(database,fault):
    request,_,_ = seed(database,SCOPE,task_id='caller-negative-'+uuid4().hex)
    store = AipBudgetReservationStore(authority_schema=database.schema)
    with caller(database) as conn:
        candidate = conn;scope = SCOPE;actor = 'tester'
        if fault=='facade':
            class Facade:
                def __getattr__(self,name):return getattr(conn,name)
            candidate = Facade()
        elif fault=='idle':conn.rollback()
        elif fault in ['readonly','isolation','autocommit']:
            conn.rollback()
            if fault=='readonly':conn.read_only=True
            elif fault=='isolation':conn.isolation_level=psycopg.IsolationLevel.READ_COMMITTED
            else:conn.autocommit=True
            if fault!='autocommit':
                conn.execute('SET LOCAL ROLE aos_runtime')
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
        elif fault=='role':conn.execute('RESET ROLE')
        elif fault=='tenant':conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        elif fault=='closed':conn.close()
        elif fault=='scope':scope=None
        elif fault=='request_bool':request=request.model_copy(update={'upper_bound_minor':True})
        elif fault=='request_kind':request=request.model_copy(update={'task_ref':request.task_ref.model_copy(update={'resource_type':'ModelEvalRequest'})})
        else:actor=' tester '
        with pytest.raises((BudgetReservationBlocked,ValueError)):
            store.reserve_in_transaction(candidate,scope,request,actor=actor)
        assert snapshot(database)==[0,0,0,0]
