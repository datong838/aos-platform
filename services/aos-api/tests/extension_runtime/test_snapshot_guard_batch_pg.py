"""Bounded metadata reads preserve exact authority, measured at real PG cursor."""
import pytest
import psycopg

pytest_plugins=('test_snapshot_schedule_execution_guard_pg',)
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner as Owner
from aos_api.tenant_scope import TenantScope


def test_latest_many_preserves_order_missing_and_latest(defined):
    conn,_,_,claim,args,_=defined
    bindings=args['bindings']
    selected=(bindings[-1],bindings[0])
    owner=Owner(controls=claim._groups._controls)
    newest=owner.bind(conn,scope=args['scope'],schedule_id=selected[0].schedule_id,
        actor=args['actor'],control_ref=selected[0].control_ref,
        previous_ref=selected[0].ref,idempotency_key='batch-newest')
    result=Owner.read_latest_many(conn,scope=args['scope'],
        schedule_ids=(selected[0].schedule_id,'absent-schedule',selected[1].schedule_id))
    assert result==(newest,None,selected[1])


@pytest.mark.parametrize('ids',[(),('duplicate','duplicate'),tuple(str(n) for n in range(13)),('',)])
def test_latest_many_rejects_invalid_bounds(defined,ids):
    conn,_,_,_,args,_=defined
    with pytest.raises((TypeError,ValueError)):
        Owner.read_latest_many(conn,scope=args['scope'],schedule_ids=ids)


def test_latest_many_rejects_other_tenant(defined):
    conn,_,_,_,args,_=defined
    with pytest.raises(PermissionError):
        Owner.read_latest_many(conn,scope=TenantScope('dev-org','dev-project'),
            schedule_ids=(args['bindings'][0].schedule_id,))


def test_group_guard_has_two_bounded_binding_reads(guarded,monkeypatch):
    conn,_,_,claims,args,_=guarded
    queries=[]
    execute=psycopg.Cursor.execute
    def counted(self,query,*pos,**kw):
        if isinstance(query,str) and 'pipeline_schedule_control_binding' in query and 'SELECT' in query:
            queries.append(query)
        return execute(self,query,*pos,**kw)
    monkeypatch.setattr(psycopg.Cursor,'execute',counted)
    assert claims.reserve(conn,**args).created
    assert len(queries)==2
    assert all('DISTINCT ON' in query for query in queries)


def test_batch_binding_read_cannot_be_shadowed(defined):
    conn,_,_,_,args,_=defined
    conn.execute('CREATE TEMP TABLE pipeline_schedule_control_binding AS SELECT * FROM public.pipeline_schedule_control_binding WHERE false')
    expected=tuple(args['bindings'])
    assert Owner.read_latest_many(conn,scope=args['scope'],
        schedule_ids=tuple(b.schedule_id for b in expected))==expected


def test_guard_rejects_member_pointing_to_older_definition_revision(guarded):
    conn,_,_,claims,args,_=guarded
    with pytest.raises(ValueError,match='member authority'),conn.transaction():
        conn.execute('RESET ROLE')
        # Deliberately stage an invalid association inside the test transaction;
        # production constraints stay enabled and rollback discards it.
        conn.execute('SET CONSTRAINTS snapshot_definition_current_head_fk,snapshot_definition_member_complete DEFERRED')
        conn.execute('UPDATE pipeline_snapshot_schedule_current_member SET revision=1')
        conn.execute('SET LOCAL ROLE aos_runtime')
        claims.reserve(conn,**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0
