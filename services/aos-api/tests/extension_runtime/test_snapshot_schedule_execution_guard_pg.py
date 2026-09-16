"""Definition authority is required inside original source/recovery transactions."""
import pytest
pytest_plugins=('test_defined_snapshot_schedule_claim_pg',)
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner


@pytest.fixture
def guarded(defined):
    conn,definitions,common,owner,args,enabled=defined
    schedule=owner.claim(conn,**args)
    claims=PipelineSourceClaimOwner(controls=owner._groups._controls)
    member=schedule['members'][0]
    command=dict(scope=args['scope'],run_id=member['runId'],actor=args['actor'],control_ref=member['controlRef'])
    return conn,definitions,common,claims,command,enabled


def test_enabled_group_source_claim_replays_without_reading_source(guarded):
    conn,_,_,claims,args,_=guarded
    first=claims.reserve(conn,**args)
    assert first.created
    assert not claims.reserve(conn,**args).created
    assert claims.read_current(conn,**args)==first.record
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==1


@pytest.mark.parametrize('method',['reserve','read_current','read_saved_current','read_completed_current'])
def test_stop_cannot_be_bypassed_by_legacy_enabled_flag(guarded,method):
    conn,definitions,common,claims,args,enabled=guarded
    if method!='reserve':claims.reserve(conn,**args)
    definitions.transition(conn,**common,intent='disable',expected_ref=enabled['ref'],idempotency_key='stop')
    conn.execute('UPDATE meta_schedule SET enabled=true')
    with pytest.raises(ValueError,match='definition'):
        getattr(claims,method)(conn,**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==(0 if method=='reserve' else 1)


def test_assigned_schedule_cannot_adopt_unrecorded_run(guarded):
    conn,_,_,claims,args,_=guarded
    conn.execute('''INSERT INTO meta_schedule_run(id,org_id,project_id,schedule_id,scheduled_for,trigger,status)
        SELECT 'unrecorded-run',org_id,project_id,schedule_id,scheduled_for+interval '1 minute','manual','running'
        FROM meta_schedule_run WHERE id=%s''',(args['run_id'],))
    with pytest.raises(ValueError,match='definition'):
        claims.reserve(conn,**(args|{'run_id':'unrecorded-run'}))
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0


def test_group_member_cannot_enter_single_source_prepare(guarded,monkeypatch):
    from contextlib import contextmanager
    from aos_api.pipeline_controlled_snapshot_ingress import ControlledSnapshotIngress
    from aos_api.ecom_consistency_store import EcomConsistencyStore
    import aos_api.pipeline_controlled_snapshot_ingress as module
    conn,_,_,claims,args,_=guarded
    ingress=ControlledSnapshotIngress(claims=claims,store=object.__new__(EcomConsistencyStore),connect=lambda:None)
    @contextmanager
    def transaction(scope,*,run_id):
        assert scope==args['scope'] and run_id==args['run_id']
        with conn.transaction():yield conn
    monkeypatch.setattr(ingress,'_run_transaction',transaction)
    monkeypatch.setattr(module,'read_selected_snapshot',lambda **kw:pytest.fail('group reached single source reader'))
    with pytest.raises(ValueError,match='whole-group'):
        ingress.prepare(**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0


def test_other_member_disabled_stops_whole_group_before_claim(guarded):
    conn,_,_,claims,args,_=guarded
    conn.execute('''UPDATE meta_schedule SET enabled=false WHERE id=(SELECT schedule_id FROM meta_schedule_run
        WHERE id<>%s ORDER BY id LIMIT 1)''',(args['run_id'],))
    with pytest.raises(ValueError,match='member authority'):
        claims.reserve(conn,**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0


def test_changed_binding_cannot_reuse_old_definition_run(guarded):
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    conn,_,_,claims,args,_=guarded
    schedule=conn.execute('SELECT schedule_id FROM meta_schedule_run WHERE id=%s',(args['run_id'],)).fetchone()['schedule_id']
    binding=PipelineScheduleControlOwner.read_latest(conn,scope=args['scope'],schedule_id=schedule)
    PipelineScheduleControlOwner(controls=claims._controls).bind(conn,scope=args['scope'],schedule_id=schedule,
        actor=args['actor'],control_ref=binding.control_ref,previous_ref=binding.ref,idempotency_key='changed-binding')
    with pytest.raises(ValueError,match='original binding'):
        claims.reserve(conn,**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0


def test_group_metadata_unreadable_is_not_treated_as_singleton(guarded):
    import psycopg
    conn,_,_,claims,args,_=guarded
    with conn.transaction():
        conn.execute('RESET ROLE')
        conn.execute('REVOKE SELECT ON pipeline_snapshot_schedule_member FROM aos_runtime')
        conn.execute('SET LOCAL ROLE aos_runtime')
        with pytest.raises(psycopg.errors.InsufficientPrivilege),conn.transaction():
            claims.reserve(conn,**args)
        raise psycopg.Rollback
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0


@pytest.mark.parametrize('fault',['other-group','subset'])
def test_source_group_must_match_original_whole_schedule_claim(guarded,defined,fault):
    from uuid import uuid4
    from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
    from aos_api.pipeline_snapshot_group_claim_owner import PipelineSnapshotGroupClaimOwner
    conn,_,_,claims,args,_=guarded
    _,_,_,owner,original,_=defined
    receipt=owner.read(conn,scope=args['scope'],group_id=original['group_id'])
    bindings=tuple((PipelineExactRef.model_validate(m['controlRef']),m['runId']) for m in receipt['members'])
    with pytest.raises(ValueError,match='original group'),conn.transaction():
        PipelineSnapshotGroupClaimOwner(claims=claims).reserve(conn,scope=args['scope'],actor=args['actor'],
            group_id=str(uuid4()) if fault=='other-group' else original['group_id'],
            bindings=bindings[:1] if fault=='subset' else bindings)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0
