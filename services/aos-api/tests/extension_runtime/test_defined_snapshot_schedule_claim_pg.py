"""Defined claims bind exact enabled configuration; no actual source reads."""
from uuid import uuid4
import pytest

pytest_plugins=('test_pipeline_snapshot_schedule_definition_pg',)
from aos_api.pipeline_snapshot_schedule_claim import PipelineSnapshotScheduleClaimOwner


@pytest.fixture
def defined(definition_case):
    conn,definitions,args=definition_case
    first=definitions.configure(conn,**args)
    common={k:args[k] for k in ('scope','definition_id','actor')}
    enabled=definitions.transition(conn,**common,intent='enable',expected_ref=first['ref'],idempotency_key='enable')
    owner=PipelineSnapshotScheduleClaimOwner(controls=definitions._groups._groups._controls)
    command=dict(scope=args['scope'],group_id=str(uuid4()),actor=args['actor'],
        scheduled_for=conn.execute("SELECT date_trunc('minute',clock_timestamp()) AS t").fetchone()['t'],
        trigger='manual',bindings=args['bindings'],definition_ref=enabled['ref'])
    return conn,definitions,common,owner,command,enabled


def test_exact_enabled_definition_is_in_immutable_claim_and_replay(defined):
    conn,_,_,owner,args,_=defined
    value=owner.claim(conn,**args)
    assert value['schemaVersion']=='aos.snapshot-schedule-claim/v2'
    assert value['request']['definitionRef']==args['definition_ref']
    assert owner.claim(conn,**args)==value
    assert len(value['members'])==12
    conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
    assert conn.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n']==12
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0


@pytest.mark.parametrize('fault',['stale','actor','kind','hash'])
def test_invalid_definition_claim_leaves_zero_runs(defined,fault):
    conn,_,_,owner,args,_=defined
    from copy import deepcopy
    bad=deepcopy(args)
    if fault=='actor':bad['actor']='wrong-executor'
    elif fault=='stale':bad['definition_ref']['revision']-=1
    elif fault=='kind':bad['definition_ref']['resourceType']='Other'
    else:bad['definition_ref']['contentHash']='sha256:'+'0'*64
    with pytest.raises((ValueError,PermissionError)),conn.transaction():owner.claim(conn,**bad)
    assert conn.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n']==0


def test_disabled_definition_stops_replay_but_retains_historical_receipt(defined):
    conn,definitions,common,owner,args,enabled=defined
    value=owner.claim(conn,**args)
    definitions.transition(conn,**common,intent='disable',expected_ref=enabled['ref'],idempotency_key='stop')
    with pytest.raises(ValueError),conn.transaction():owner.claim(conn,**args)
    assert owner.read(conn,scope=args['scope'],group_id=args['group_id'])==value
    assert conn.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n']==12


@pytest.mark.parametrize('fault',['hash','kind','legacy-bypass'])
def test_database_rejects_rehashed_definition_mismatch(defined,fault):
    import psycopg
    from psycopg.types.json import Jsonb
    from copy import deepcopy
    from aos_api.asset_registry.canonical_json import canonical_sha256
    conn,_,_,owner,args,_=defined
    with conn.transaction():
        value=deepcopy(owner.claim(conn,**args))
        raise psycopg.Rollback
    request=value['request']
    if fault=='legacy-bypass':
        value['schemaVersion']='aos.snapshot-schedule-claim/v1'
        request['schemaVersion']='aos.snapshot-schedule-request/v1'
        del request['definitionRef']
    elif fault=='hash':request['definitionRef']['contentHash']='sha256:'+'0'*64
    else:request['definitionRef']['resourceType']='Other'
    # Recompute both hashes, so failure must be the actual definition association.
    with pytest.raises(psycopg.errors.CheckViolation,match='definition authority'),conn.transaction():
        conn.execute('SET CONSTRAINTS snapshot_schedule_claim_complete,snapshot_schedule_member_complete DEFERRED')
        for member in value['members']:
            conn.execute('''INSERT INTO meta_schedule_run(id,org_id,project_id,schedule_id,scheduled_for,trigger,status)
                VALUES(%s,%s,%s,%s,%s,'manual','running')''',
                (member['runId'],*args['scope'].key,member['scheduleId'],args['scheduled_for']))
        conn.execute('''INSERT INTO pipeline_snapshot_schedule_claim
            (org_id,project_id,group_id,actor,scheduled_for,trigger,request_hash,request,content_hash,record)
            VALUES(%s,%s,%s,%s,%s,'manual',%s,%s,%s,%s)''',
            (*args['scope'].key,args['group_id'],args['actor'],args['scheduled_for'],
             canonical_sha256(request),Jsonb(request),canonical_sha256(value),Jsonb(value)))
        for ordinal,member in enumerate(value['members'],1):
            ref=member['bindingRef']
            conn.execute('''INSERT INTO pipeline_snapshot_schedule_member
                (org_id,project_id,group_id,ordinal,schedule_id,binding_id,binding_revision,binding_hash,run_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (*args['scope'].key,args['group_id'],ordinal,member['scheduleId'],
                 ref['resourceId'].removeprefix('schedule-control-'),ref['revision'],ref['contentHash'],member['runId']))
        conn.execute('SET CONSTRAINTS snapshot_schedule_claim_complete,snapshot_schedule_member_complete IMMEDIATE')
    assert conn.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n']==0
