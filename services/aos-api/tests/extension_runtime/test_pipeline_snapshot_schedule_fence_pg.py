"""Original claim entry points must respect current persisted group ownership."""
from contextlib import contextmanager
from uuid import uuid4
import pytest

pytest_plugins=('test_pipeline_snapshot_schedule_definition_pg',)

from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.pipeline_snapshot_schedule_claim import PipelineSnapshotScheduleClaimOwner


@pytest.fixture
def grouped(definition_case,monkeypatch):
    conn,owner,args=definition_case
    first=owner.configure(conn,**args)
    import aos_api.pipeline_schedule_claim as single
    @contextmanager
    def connection(scope):
        assert scope==args['scope']
        with conn.transaction():yield conn
    monkeypatch.setattr(single,'_connection',connection)
    return conn,owner,args,first,single


@pytest.mark.parametrize('enabled',[True,False])
def test_single_claim_rejects_group_member_even_if_legacy_flag_is_enabled(grouped,enabled):
    conn,owner,args,first,single=grouped
    if enabled:
        owner.transition(conn,**{k:args[k] for k in ('scope','definition_id','actor')},
            intent='enable',expected_ref=first['ref'],idempotency_key='enable')
    # Simulate a legacy toggle: this is not group authority.
    conn.execute('UPDATE meta_schedule SET enabled=true')
    binding=args['bindings'][0]
    with pytest.raises(RuntimeConflict,match='group'),conn.transaction():
        with single.schedule_claim_connection(args['scope'],schedule_id=binding.schedule_id,binding=binding):
            pytest.fail('group member reached singleton executor')


def test_unqualified_group_claim_cannot_bypass_definition(grouped):
    conn,owner,args,first,_=grouped
    owner.transition(conn,**{k:args[k] for k in ('scope','definition_id','actor')},
        intent='enable',expected_ref=first['ref'],idempotency_key='enable')
    claims=PipelineSnapshotScheduleClaimOwner(controls=owner._groups._groups._controls)
    with pytest.raises(ValueError,match='definition'),conn.transaction():
        claims.claim(conn,scope=args['scope'],group_id=str(uuid4()),actor=args['actor'],
            scheduled_for=conn.execute("SELECT date_trunc('minute',clock_timestamp()) AS t").fetchone()['t'],
            trigger='manual',bindings=args['bindings'])
    assert conn.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n']==0


def test_retire_releases_singleton_only_after_explicit_enable(grouped):
    conn,owner,args,first,single=grouped
    owner.transition(conn,**{k:args[k] for k in ('scope','definition_id','actor')},
        intent='retire',expected_ref=first['ref'],idempotency_key='retire')
    binding=args['bindings'][0]
    with pytest.raises(RuntimeConflict,match='enabled'):
        with single.schedule_claim_connection(args['scope'],schedule_id=binding.schedule_id,binding=binding):
            pytest.fail('retirement must leave member disabled')
    conn.execute('UPDATE meta_schedule SET enabled=true WHERE id=%s',(binding.schedule_id,))
    with single.schedule_claim_connection(args['scope'],schedule_id=binding.schedule_id,binding=binding):pass


def test_cron_excludes_members_but_keeps_unassigned_schedule(grouped,monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import aos_api.qyh_cron_scheduler as cron
    conn,owner,args,first,_=grouped
    owner.transition(conn,**{k:args[k] for k in ('scope','definition_id','actor')},
        intent='enable',expected_ref=first['ref'],idempotency_key='enable')
    conn.execute("""INSERT INTO meta_schedule(id,org_id,project_id,name,cron,pipeline_id,enabled,ingest)
        SELECT 'ungrouped',org_id,project_id,'unassigned','* * * * *',pipeline_id,true,ingest FROM meta_schedule LIMIT 1""")
    @contextmanager
    def connection(scope):
        assert scope==args['scope']
        with conn.transaction():yield conn
    calls=[]
    monkeypatch.setattr(cron,'connect',connection)
    monkeypatch.setattr(cron,'execute_schedule',lambda scope,schedule_id,**kw:calls.append(schedule_id) or {'id':schedule_id})
    result=cron.run_due_qyh(datetime(2026,9,16,8,0,tzinfo=ZoneInfo('Asia/Shanghai')))
    assert calls==['ungrouped']
    assert result==[{'id':'ungrouped'}]


def test_bound_ingress_recovery_guard_rejects_group_members(grouped):
    from aos_api.pipeline_controlled_snapshot_ingress import ControlledSnapshotIngress
    from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
    from aos_api.ecom_consistency_store import EcomConsistencyStore
    conn,owner,args,first,_=grouped
    owner.transition(conn,**{k:args[k] for k in ('scope','definition_id','actor')},
        intent='enable',expected_ref=first['ref'],idempotency_key='enable')
    ingress=ControlledSnapshotIngress(claims=PipelineSourceClaimOwner(controls=owner._groups._groups._controls),
        store=object.__new__(EcomConsistencyStore),connect=lambda:None,schedule_binding=args['bindings'][0])
    with pytest.raises(RuntimeConflict,match='group'),conn.transaction():
        ingress._guard_binding(conn,args['scope'])
