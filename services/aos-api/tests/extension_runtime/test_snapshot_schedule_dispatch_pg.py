"""Dispatch candidates are routing evidence, never execution authority."""
from datetime import UTC, datetime, timedelta
import pytest
from aos_api.tenant_scope import TenantScope
from aos_api.pipeline_snapshot_schedule_dispatch import snapshot_slot_group_id,PipelineSnapshotScheduleDispatch

pytest_plugins=('test_snapshot_schedule_runtime_pg','test_snapshot_group_recovery_authority_pg')


def test_slot_identity_is_utc_and_tenant_bound():
    scope=TenantScope('org-org','dev-project');identifier='00000000-0000-4000-8000-000000000001'
    now=datetime(2026,9,16,8,0,tzinfo=UTC)
    from datetime import timezone
    expected=snapshot_slot_group_id(scope,identifier,now)
    assert snapshot_slot_group_id(scope,identifier,now.astimezone(timezone(timedelta(hours=8))))==expected
    assert snapshot_slot_group_id(scope,identifier,now+timedelta(minutes=1))!=expected
    assert snapshot_slot_group_id(TenantScope('dev-org','dev-project'),identifier,now)!=expected
    for invalid in (now.replace(tzinfo=None),now+timedelta(seconds=1)):
        with pytest.raises(ValueError):snapshot_slot_group_id(scope,identifier,invalid)


def test_original_unfinished_group_blocks_later_slot_without_source(runtime_case):
    runtime,args,state,api,common,enabled,_=runtime_case
    dispatch=PipelineSnapshotScheduleDispatch(definitions=runtime._definitions,claims=runtime._claims)
    read=dict(scope=args['scope'],definition_id=common['definition_id'],now=args['scheduled_for'])
    with runtime._transaction(args['scope']) as conn:
        before=dispatch.inspect(conn,**read)
        assert before['executionAuthorized'] is False
        assert before['status'] in ('due','not_due')
        bindings=runtime._definitions._saved_bindings(conn,args['scope'],enabled['body'])
        runtime._claims.claim(conn,**{k:v for k,v in args.items() if k!='definition_ref'},
            definition_ref=args['definition_ref'],bindings=bindings)
    with runtime._transaction(args['scope']) as conn:
        pending=dispatch.inspect(conn,**(read|dict(now=read['now']+timedelta(minutes=1))))
        assert pending['status']=='original_group_pending' and pending['groupIds']==[args['group_id']]
        conn.execute("UPDATE meta_schedule_run SET status='failed',executor_stopped=true,finished_at=clock_timestamp()")
    with runtime._transaction(args['scope']) as conn:
        failed=dispatch.inspect(conn,**(read|dict(now=read['now']+timedelta(minutes=2))))
        assert failed['status']=='original_group_pending' and failed['groupIds']==[args['group_id']]
        assert conn.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n']==12
    assert state['calls']==0


def test_disabled_and_negative_scope_cannot_produce_candidate(runtime_case):
    runtime,args,state,api,common,enabled,_=runtime_case
    dispatch=PipelineSnapshotScheduleDispatch(definitions=runtime._definitions,claims=runtime._claims)
    api.transition(**common,intent='disable',expected_ref=enabled['ref'],idempotency_key='dispatch-disable')
    with runtime._transaction(args['scope']) as conn:
        result=dispatch.inspect(conn,scope=args['scope'],definition_id=common['definition_id'],now=args['scheduled_for'])
        assert result['status']=='disabled' and result['executionAuthorized'] is False
    negative=TenantScope('dev-org','dev-project')
    with runtime._transaction(negative) as conn:
        with pytest.raises(LookupError):dispatch.inspect(conn,scope=negative,definition_id=common['definition_id'],now=args['scheduled_for'])
    assert state['calls']==0


def test_completed_slot_is_preserved_across_definition_revision(runtime_case):
    runtime,args,state,api,common,enabled,_=runtime_case
    dispatch=PipelineSnapshotScheduleDispatch(definitions=runtime._definitions,claims=runtime._claims)
    with runtime._transaction(args['scope']) as conn:
        bindings=runtime._definitions._saved_bindings(conn,args['scope'],enabled['body'])
        runtime._claims.claim(conn,**{k:v for k,v in args.items() if k!='definition_ref'},
            definition_ref=args['definition_ref'],bindings=bindings)
        # Named routing-only fixture; this is not Store completion evidence.
        conn.execute("UPDATE meta_schedule_run SET status='succeeded',executor_id='ec-live-v1',executor_stopped=true,finished_at=clock_timestamp()")
    disabled=api.transition(**common,intent='disable',expected_ref=enabled['ref'],idempotency_key='dispatch-pause')
    newest=api.transition(**common,intent='enable',expected_ref=disabled['ref'],idempotency_key='dispatch-enable')
    with runtime._transaction(args['scope']) as conn:
        same=dispatch.inspect(conn,scope=args['scope'],definition_id=common['definition_id'],now=args['scheduled_for'])
        assert same['status']=='slot_completed' and same['groupIds']==[args['group_id']]
        assert same['definitionRef']==newest['ref']
        # Explicit clock at the next day's approved cron minute; still no execution.
        due=args['scheduled_for'].replace(hour=0,minute=0)+timedelta(days=1)
        next_slot=dispatch.inspect(conn,scope=args['scope'],definition_id=common['definition_id'],now=due)
        assert next_slot['status']=='due' and next_slot['executionAuthorized'] is False
        assert next_slot['groupId']==snapshot_slot_group_id(args['scope'],common['definition_id'],due)
        assert next_slot['actor']==newest['body']['executor']
    assert state['calls']==0


def test_recovery_only_definition_never_produces_new_slot(authority_case):
    runtime,owner,command,state,receipt,authority,args=authority_case
    dispatch=PipelineSnapshotScheduleDispatch(definitions=runtime._definitions,claims=runtime._claims)
    with runtime._transaction(command['scope']) as conn:
        # Named completed routing fixture, not a claim of business completion.
        conn.execute("UPDATE meta_schedule_run SET status='succeeded',executor_id='ec-live-v1',executor_stopped=true,finished_at=clock_timestamp()")
        now=conn.execute("SELECT clock_timestamp() AS now").fetchone()['now']+timedelta(days=1)
        result=dispatch.inspect(conn,scope=command['scope'],
            definition_id=receipt['body']['currentDefinitionRef']['resourceId'].removeprefix('snapshot-schedule-'),now=now)
        assert result['status']=='recovery_only' and result['executionAuthorized'] is False
    assert state['calls']==1
