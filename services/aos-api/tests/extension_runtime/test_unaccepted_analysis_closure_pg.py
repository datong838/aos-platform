"""A held initialization may close only with fenced, absent target authority."""
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb
from aos_api.tenant_scope import TenantScope
from aos_api.asset_registry.canonical_json import canonical_sha256
from test_ecommerce_growth_cutover_pg import database, _connection, _migration
from test_event_control_dispatch_lifecycle_pg import dispatch_db, _seed, _request, _transition

pytestmark = pytest.mark.skipif(__import__('os').getenv('AOS_EXTENSION_PG_TEST') != '1', reason='isolated PG required')


@pytest.fixture
def closure_db(dispatch_db):
    db = dispatch_db
    db.owner.execute('''CREATE TABLE ecommerce_growth_runtime_command_receipt(
        org_id text,project_id text,operation_id text,idempotency_key text)''')
    db.owner.execute('''CREATE TABLE ecommerce_investigation_run(
        org_id text,project_id text,run_id text,trigger_key text)''')
    _migration(Path(__file__).resolve().parents[2], 'a0v_043_product_event_origin.py', db.owner, schema=db.schema)
    _migration(Path(__file__).resolve().parents[2], 'a0v_060_unaccepted_analysis_closure.py', db.owner, schema=db.schema)
    return db


def seed(db):
    scope = TenantScope('org-org', 'dev-project')
    ids = _seed(db, scope)
    _transition(db, scope, _request(ids, 'expand', 11, 'expand'))
    fence = _transition(db, scope, _request(ids, 'fence', 12, 'fence'))
    occurrence = str(uuid4())
    db.owner.execute('''INSERT INTO automation_schedule_binding(org_id,project_id,policy_id,policy_revision,
        policy_hash,operation_id,installation_id,generation,execution_epoch,timezone,cadence,effective_from,approved,enabled)
        VALUES(%s,%s,'product-change-current',1,%s,'ecommerce_growth_analysis_advance',%s,%s,3,
        'Asia/Shanghai','event',clock_timestamp()-interval '1 hour',true,false)''',
        (*scope.key, 'sha256:'+'a'*64, ids[0], ids[1]))
    db.owner.execute('''INSERT INTO automation_occurrence(org_id,project_id,occurrence_id,policy_id,policy_revision,
        policy_hash,operation_id,installation_id,generation,execution_epoch,trigger_source,source_event_id,status,deadline)
        VALUES(%s,%s,%s,'product-change-current',1,%s,'ecommerce_growth_analysis_advance',%s,%s,3,
        'event',repeat('e',64),'needs_attention',clock_timestamp()-interval '1 minute')''',
        (*scope.key, occurrence, 'sha256:'+'a'*64, ids[0], ids[1]))
    db.owner.execute('''INSERT INTO automation_occurrence_dispatch_attempt(org_id,project_id,attempt_id,
        occurrence_id,claim_owner,target_idempotency_key,status,claimed_at,claim_until)
        VALUES(%s,%s,%s,%s,'worker','target-1','unknown',clock_timestamp()-interval '2 minutes',
        clock_timestamp()-interval '1 minute')''', (*scope.key,uuid4(),occurrence))
    origin = dict(orgId=scope.org_id,projectId=scope.project_id,occurrenceId=occurrence,
                  sourceEventId='e'*64,runId='source-run-1',actor='fixture-operator')
    db.owner.execute('INSERT INTO ecommerce_product_event_origin(org_id,project_id,occurrence_id,source_event_id,run_id,actor,content_hash) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                     (*scope.key,occurrence,origin['sourceEventId'],origin['runId'],origin['actor'],canonical_sha256(origin)))
    request = dict(schemaVersion='aos.ecommerce.unaccepted-analysis-closure/v1', occurrenceId=occurrence,
        fenceReceiptId=fence['receiptId'], fenceContentHash=fence['contentHash'], idempotencyKey='close-1')
    return scope, ids, request


def close(db, scope, request, *, runtime=False, actor='fixture-operator'):
    with _connection(db, runtime=runtime)(scope) as conn:
        value = conn.execute('SELECT ecommerce_unaccepted_analysis_close_a0v_060(%s,%s) AS value',
                             (Jsonb(request), actor)).fetchone()['value']
        conn.commit()
        return value


def test_close_retains_unknown_snapshot_and_unblocks_formal_drain(closure_db):
    db=closure_db; scope,ids,request=seed(db)
    value=close(db,scope,request)
    assert value['priorAttempt']['status']=='unknown'
    assert value['targetEvidence']['receiptCount']==value['targetEvidence']['runCount']==0
    assert value['businessAccepted'] is False
    assert close(db,scope,request)['replayed'] is True
    assert db.owner.execute('SELECT status,receipt_ref FROM automation_occurrence').fetchone()==dict(status='cancelled',receipt_ref=None)
    assert db.owner.execute('SELECT status FROM automation_occurrence_dispatch_attempt').fetchone()['status']=='closed_unaccepted'
    _transition(db,scope,_request(ids,'shrink',13,'shrink'))
    with pytest.raises(Exception):
        db.owner.execute('DELETE FROM ecommerce_unaccepted_analysis_closure_receipt')


@pytest.mark.parametrize('reason',['target_receipt','run','unfenced','binding_enabled','lease','accepted','actor','tenant','runtime'])
def test_no_absence_or_current_authority_means_no_closure(closure_db,reason):
    db=closure_db; scope,ids,request=seed(db)
    if reason=='target_receipt':
        db.owner.execute("INSERT INTO ecommerce_growth_runtime_command_receipt VALUES('org-org','dev-project','ecommerce_growth_analysis_advance','target-1')")
    if reason=='run':
        db.owner.execute("INSERT INTO ecommerce_investigation_run VALUES('org-org','dev-project','run-any','target-1')")
    if reason=='unfenced':
        db.owner.execute('UPDATE extension_operation_dispatch_binding SET operation_fence=false')
    if reason=='binding_enabled':
        db.owner.execute('UPDATE automation_schedule_binding SET enabled=true')
    if reason=='lease':
        db.owner.execute("UPDATE automation_occurrence_dispatch_attempt SET claim_until=clock_timestamp()+interval '1 hour'")
    if reason=='accepted':
        db.owner.execute("UPDATE automation_occurrence SET status='accepted'")
    with pytest.raises(Exception):
        close(db,TenantScope('dev-org','dev-project') if reason=='tenant' else scope,request,
              runtime=reason=='runtime',actor='missing' if reason=='actor' else 'fixture-operator')
    assert db.owner.execute('SELECT count(*) AS n FROM ecommerce_unaccepted_analysis_closure_receipt').fetchone()['n']==0
    assert db.owner.execute('SELECT status FROM automation_occurrence_dispatch_attempt').fetchone()['status']=='unknown'


@pytest.mark.parametrize('table',['automation_occurrence','automation_occurrence_dispatch_attempt'])
def test_closed_state_cannot_be_reopened_or_forged(closure_db,table):
    db=closure_db;scope,ids,request=seed(db)
    state='cancelled' if table=='automation_occurrence' else 'closed_unaccepted'
    with pytest.raises(Exception,match='immutable closure receipt required'):
        db.owner.execute(f"UPDATE {table} SET status=%s",(state,))
    close(db,scope,request)
    with pytest.raises(Exception,match='terminal'):
        db.owner.execute(f"UPDATE {table} SET status='needs_attention'" if table=='automation_occurrence'
                         else f"UPDATE {table} SET status='unknown'")


def test_closure_waits_for_original_host_dispatch_lock(closure_db):
    from psycopg.errors import LockNotAvailable
    db=closure_db;scope,ids,request=seed(db)
    with _connection(db)(scope) as locked:
        # Use test owner for the first writer; ordinary runtime uses restricted group lock.
        db.owner.execute('BEGIN')
        try:
            db.owner.execute('SELECT 1 FROM extension_operation_dispatch_binding ORDER BY operation_id FOR UPDATE')
            locked.execute("SET LOCAL lock_timeout='100ms'")
            with pytest.raises(LockNotAvailable):
                locked.execute('SELECT ecommerce_unaccepted_analysis_close_a0v_060(%s,%s)',
                               (Jsonb(request),'fixture-operator'))
        finally:
            db.owner.execute('ROLLBACK')
    assert close(db,scope,request)['businessAccepted'] is False


def test_replay_drift_and_raw_receipt_writes_are_rejected(closure_db):
    db=closure_db;scope,ids,request=seed(db)
    close(db,scope,request)
    with pytest.raises(Exception,match='idempotency drift'):
        close(db,scope,{**request,'occurrenceId':str(uuid4())})
    with _connection(db)(scope) as conn:
        with pytest.raises(Exception):
            conn.execute('TRUNCATE ecommerce_unaccepted_analysis_closure_receipt')


def test_deterministic_run_identity_alone_blocks_closure(closure_db):
    import hashlib
    db=closure_db;scope,ids,request=seed(db)
    run='analysis-'+hashlib.sha256('\x1f'.join((*scope.key,'target-1')).encode()).hexdigest()[:32]
    db.owner.execute('INSERT INTO ecommerce_investigation_run VALUES(%s,%s,%s,%s)',(*scope.key,run,'different-trigger'))
    with pytest.raises(Exception,match='target accepted'):
        close(db,scope,request)


@pytest.mark.parametrize('missing',['origin','fence_hash','fence_id','extra_field'])
def test_origin_and_exact_fence_are_required(closure_db,missing):
    db=closure_db;scope,ids,request=seed(db)
    if missing=='origin':
        # A fresh occurrence has no origin; never mutate existing immutable history.
        db.owner.execute('ALTER TABLE ecommerce_product_event_origin DISABLE TRIGGER product_event_origin_immutable')
        db.owner.execute('DELETE FROM ecommerce_product_event_origin')
        db.owner.execute('ALTER TABLE ecommerce_product_event_origin ENABLE TRIGGER product_event_origin_immutable')
    if missing=='fence_hash':request['fenceContentHash']='sha256:'+'0'*64
    if missing=='fence_id':request['fenceReceiptId']=str(uuid4())
    if missing=='extra_field':request['accepted']=True
    with pytest.raises(Exception):close(db,scope,request)
    assert db.owner.execute('SELECT status FROM automation_occurrence').fetchone()['status']=='needs_attention'
