"""An enabled saved-input recovery definition must never grant a new read."""
from copy import deepcopy
from datetime import datetime
from uuid import uuid4
import pytest
import psycopg
from psycopg.types.json import Jsonb

pytest_plugins=('test_snapshot_group_recovery_receipt_pg',)
from aos_api.asset_registry.canonical_json import canonical_sha256


def test_recovery_definition_rejects_ordinary_claim_before_new_runs(renewal_row):
    runtime,args,row,state=renewal_row
    with runtime._transaction(args['scope']) as conn:
        current=runtime._definitions.read(conn,scope=args['scope'],definition_id=str(row['definition_id']))
        bindings=runtime._definitions._saved_bindings(conn,args['scope'],current['body'])
        with pytest.raises(ValueError,match='recovery-only'),conn.transaction():
            runtime._claims.claim(conn,scope=args['scope'],group_id=str(uuid4()),actor=args['actor'],
                scheduled_for=args['scheduled_for'],trigger='manual',bindings=bindings,definition_ref=current['ref'])
        assert conn.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n']==12
        assert runtime._claims.read(conn,scope=args['scope'],group_id=args['group_id'])['request']['definitionRef']==args['definition_ref']
    assert state['calls']==1


def test_direct_rehashed_header_cannot_bypass_recovery_only_mode(renewal_row):
    runtime,args,row,state=renewal_row
    with runtime._transaction(args['scope']) as conn:
        original=runtime._claims.read(conn,scope=args['scope'],group_id=args['group_id'])
        current=runtime._definitions.read(conn,scope=args['scope'],definition_id=str(row['definition_id']))
        request=deepcopy(original['request'])
        request.update(groupId=str(uuid4()),definitionRef=current['ref'],members=current['body']['members'])
        record=dict(schemaVersion='aos.snapshot-schedule-claim/v2',request=request,
            members=[dict(m,runId='not-created-'+str(i)) for i,m in enumerate(request['members'])])
        with pytest.raises(psycopg.errors.CheckViolation,match='recovery-only'),conn.transaction():
            conn.execute('''INSERT INTO public.pipeline_snapshot_schedule_claim
                (org_id,project_id,group_id,actor,scheduled_for,trigger,request_hash,request,content_hash,record)
                VALUES(%s,%s,%s,%s,%s,'manual',%s,%s,%s,%s)''',
                (*args['scope'].key,request['groupId'],args['actor'],datetime.fromisoformat(request['scheduledFor']),
                 canonical_sha256(request),Jsonb(request),canonical_sha256(record),Jsonb(record)))
        assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_claim').fetchone()['n']==1
        assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==12
    assert state['calls']==1
