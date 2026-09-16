"""Atomic original schedule runs; source/installation assets remain named fixtures."""
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import psycopg
import pytest

pytest_plugins = ('test_analysis_snapshot_native_claims_pg',)

from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
from aos_api.pipeline_snapshot_schedule_claim import PipelineSnapshotScheduleClaimOwner
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def schedule_group(native_claims_case,request):
    conn, source_group, args, _, _ = native_claims_case
    # Only disposable, never-consumed fixture runs are removed. The assertion
    # below will count runs actually created by the product claim Owner.
    conn.execute('RESET ROLE')
    rows = conn.execute('DELETE FROM meta_schedule_run RETURNING id,schedule_id').fetchall()
    by_run = {r['id']:r['schedule_id'] for r in rows}
    conn.execute('SET LOCAL ROLE aos_runtime')
    bindings = []
    schedule_owner = PipelineScheduleControlOwner(controls=source_group._claims._controls)
    source_bindings=args['bindings'][:-1] if getattr(request,'param',None)=='eleven' else args['bindings']
    for ref, run in source_bindings:
        bindings.append(schedule_owner.bind(conn, scope=args['scope'], schedule_id=by_run[run],
            control_ref=ref, actor=args['actor'], idempotency_key='group-bind-'+run))
    owner = PipelineSnapshotScheduleClaimOwner(controls=source_group._claims._controls)
    slot = conn.execute("SELECT date_trunc('minute',clock_timestamp()) AS slot").fetchone()['slot']
    return conn, owner, dict(scope=args['scope'], group_id=str(uuid4()), actor=args['actor'],
        scheduled_for=slot, trigger='cron', bindings=tuple(bindings))


def test_atomic_twelve_runs_replay_without_source_claims(schedule_group):
    conn, owner, args = schedule_group
    first = owner.claim(conn, **args)
    assert owner.claim(conn, **args) == first
    conn.execute('SET CONSTRAINTS snapshot_schedule_claim_complete, snapshot_schedule_member_complete IMMEDIATE')
    assert len(first['members']) == 12
    for table, count in [('meta_schedule_run',12),('pipeline_snapshot_schedule_claim',1),
                         ('pipeline_snapshot_schedule_member',12),('pipeline_controlled_source_claim',0),
                         ('pipeline_snapshot_group_input',0)]:
        assert conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] == count
    assert owner.read(conn, scope=args['scope'], group_id=args['group_id']) == first
    with pytest.raises(ValueError, match='request differs'):
        owner.claim(conn, **(args | {'trigger':'manual'}))
    with pytest.raises(psycopg.Error), conn.transaction():
        conn.execute('UPDATE pipeline_snapshot_schedule_claim SET actor=actor')
    conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
    assert owner.read(conn, scope=TenantScope('dev-org','dev-project'), group_id=args['group_id']) is None


@pytest.mark.parametrize('fault', ['disabled','active-run','slot','binding','actor','missing'])
def test_group_refuses_partial_or_unqualified_claims(schedule_group, fault):
    conn, owner, args = schedule_group
    last = sorted(args['bindings'], key=lambda x:x.schedule_id)[-1]
    if fault == 'disabled':
        conn.execute('UPDATE meta_schedule SET enabled=false WHERE id=%s',(last.schedule_id,))
    elif fault == 'active-run':
        conn.execute("INSERT INTO meta_schedule_run(id,org_id,project_id,schedule_id,scheduled_for,trigger,status) VALUES('prior',%s,%s,%s,%s,'manual','running')",
            (*args['scope'].key,last.schedule_id,args['scheduled_for']-timedelta(minutes=1)))
    elif fault == 'slot':
        args = args | {'scheduled_for':args['scheduled_for']+timedelta(minutes=1)}
    elif fault == 'binding':
        altered = replace(last, ref=last.ref.model_copy(update={'revision':2}))
        args = args | {'bindings':tuple(altered if b==last else b for b in args['bindings'])}
    elif fault == 'actor':
        args = args | {'actor':'different-actor'}
    elif fault == 'missing':
        args = args | {'bindings':args['bindings'][:-1]}
    with pytest.raises((ValueError,PermissionError)), conn.transaction():
        owner.claim(conn, **args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_claim').fetchone()['n'] == 0
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_member').fetchone()['n'] == 0
    assert conn.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n'] == (1 if fault=='active-run' else 0)


def test_database_rejects_header_without_all_members(schedule_group):
    from copy import deepcopy
    from psycopg.types.json import Jsonb
    from aos_api.asset_registry.canonical_json import canonical_sha256
    conn, owner, args = schedule_group
    original = owner.claim(conn, **args)
    broken = deepcopy(original)
    broken['request']['groupId'] = str(uuid4())
    request = broken['request']
    with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
        conn.execute('''INSERT INTO pipeline_snapshot_schedule_claim
            (org_id,project_id,group_id,actor,scheduled_for,trigger,request_hash,request,content_hash,record)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (*args['scope'].key,request['groupId'],args['actor'],args['scheduled_for'],args['trigger'],
             canonical_sha256(request),Jsonb(request),canonical_sha256(broken),Jsonb(broken)))
        conn.execute('SET CONSTRAINTS snapshot_schedule_claim_complete IMMEDIATE')
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_claim').fetchone()['n'] == 1


def test_temporary_tables_cannot_substitute_immutable_claim(schedule_group):
    conn, owner, args = schedule_group
    original = owner.claim(conn, **args)
    conn.execute('CREATE TEMP TABLE pipeline_snapshot_schedule_claim (LIKE public.pipeline_snapshot_schedule_claim INCLUDING ALL)')
    conn.execute('CREATE TEMP TABLE pipeline_snapshot_schedule_member (LIKE public.pipeline_snapshot_schedule_member INCLUDING ALL)')
    assert owner.read(conn, scope=args['scope'], group_id=args['group_id']) == original
    assert owner.claim(conn, **args) == original
    conn.execute('SET CONSTRAINTS snapshot_schedule_claim_complete, snapshot_schedule_member_complete IMMEDIATE')
