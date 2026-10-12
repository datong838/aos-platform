"""Native durable dispatch fencing; fixture rows are not business executions."""
import importlib.util
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from threading import Barrier

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
import pytest

from aos_api.aip_signed_skill_eval_intent_store import SignedSkillEvalIntentStore, SkillEvalIntentConflict
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('org-org', 'dev-project')
CANARY = TenantScope('dev-org', 'dev-project')
STORE = SignedSkillEvalIntentStore()


@pytest.fixture(scope='module')
def dispatch_schema():
    dsn = os.environ['AOS_DATABASE_URL']
    parts = conninfo_to_dict(dsn)
    assert (parts['host'], parts['port']) == ('127.0.0.1', '18431')
    assert parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')
    schema = 'skill_dispatch_' + uuid4().hex
    migration = Path(__file__).resolve().parents[2] / 'alembic/versions/a0v_160_skill_eval_dispatch_intent.py'
    spec = importlib.util.spec_from_file_location('dispatch_migration', migration)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    statements = []
    with patch.object(mod.op, 'execute', statements.append):
        mod.upgrade()
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0] == '7695416748450308141'
        created_role = conn.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_aip_eval_writer'").fetchone() is None
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        conn.execute('CREATE TABLE twa_workspace(org_id text, project_id text, PRIMARY KEY(org_id,project_id))')
        conn.execute('INSERT INTO twa_workspace VALUES (%s,%s),(%s,%s)', (*SCOPE.key, *CANARY.key))
        conn.execute('CREATE TABLE aip_eval_run(org_id text,project_id text,run_id text,status text,version bigint,target_ref jsonb,PRIMARY KEY(org_id,project_id,run_id))')
        for statement in statements:
            conn.execute(statement)
        conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_aip_eval_writer,aos_runtime').format(sql.Identifier(schema)))
        conn.commit()
    yield dsn, schema
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        if created_role:
            conn.execute('DROP ROLE aos_aip_eval_writer')


def writer(resource, scope=SCOPE, *, role='aos_aip_eval_writer', isolation='SERIALIZABLE'):
    dsn, schema = resource
    conn = psycopg.connect(dsn, row_factory=dict_row)
    assert isolation in {'SERIALIZABLE', 'READ COMMITTED'}
    conn.execute('SET TRANSACTION ISOLATION LEVEL ' + isolation)
    conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
    conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
    conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
    return conn


@pytest.fixture
def intent(dispatch_schema):
    dsn, schema = dispatch_schema
    run = 'new-fixture-' + uuid4().hex
    with psycopg.connect(dsn) as conn:
        conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        conn.execute("INSERT INTO aip_eval_run VALUES(%s,%s,%s,'queued',1,'{\"assetType\":\"skill_template\"}')", (*SCOPE.key, run))
        conn.commit()
    key = 'fixture-key-' + uuid4().hex
    with writer(dispatch_schema) as conn:
        value = STORE.create(conn, SCOPE, run_id=run, idempotency_key=key, request_hash='a'*64)
        conn.commit()
    # Test-only lifecycle seed in the session-owned schema, never a business Run.
    with psycopg.connect(dsn) as conn:
        conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        conn.execute("UPDATE aip_eval_run SET status='running',version=2 WHERE run_id=%s", (run,))
        conn.commit()
    return value


def test_create_exact_replay_and_contract_conflict(dispatch_schema, intent):
    with writer(dispatch_schema) as conn:
        assert STORE.create(conn, SCOPE, run_id=intent['run_id'], idempotency_key=intent['idempotency_key'], request_hash='a'*64)['intent_id'] == intent['intent_id']
    with pytest.raises(SkillEvalIntentConflict):
        with writer(dispatch_schema) as conn:
            STORE.create(conn, SCOPE, run_id=intent['run_id'], idempotency_key=intent['idempotency_key'], request_hash='b'*64)


def test_one_dispatch_persists_and_replay_never_claims(dispatch_schema, intent):
    with writer(dispatch_schema) as conn:
        claim = STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=1, case_id='case-1', purpose='target', input_hash='c'*64)
        assert claim is not None
        conn.commit()
    with writer(dispatch_schema) as conn:
        assert STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=2, case_id='case-1', purpose='target', input_hash='c'*64) is None
        assert STORE.get(conn, SCOPE, intent['intent_id'])['version'] == 2


def test_stale_version_and_changed_input_refuse(dispatch_schema, intent):
    with writer(dispatch_schema) as conn:
        STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=1, case_id='case-1', purpose='target', input_hash='c'*64)
        conn.commit()
    for version, digest in [(1, 'c'*64), (2, 'd'*64)]:
        with pytest.raises(SkillEvalIntentConflict):
            with writer(dispatch_schema) as conn:
                STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=version, case_id='case-1', purpose='target', input_hash=digest)


def test_unknown_preserves_dispatch_without_resend(dispatch_schema, intent):
    with writer(dispatch_schema) as conn:
        claim = STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=1, case_id='case-1', purpose='target', input_hash='c'*64)
        STORE.observe(conn, SCOPE, dispatch_id=claim, state='unknown', result_hash=None)
        conn.commit()
    with writer(dispatch_schema) as conn:
        assert STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=2, case_id='case-1', purpose='target', input_hash='c'*64) is None
        STORE.observe(conn, SCOPE, dispatch_id=claim, state='result_observed', result_hash='d'*64)
        conn.commit()
    with writer(dispatch_schema) as conn:
        assert len(STORE.observations(conn, SCOPE, claim)) == 2


def test_late_failure_rolls_back_claim_and_version(dispatch_schema, intent):
    with pytest.raises(psycopg.errors.CheckViolation):
        with writer(dispatch_schema) as conn:
            STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=1, case_id='case-1', purpose='target', input_hash='c'*64)
            conn.execute("INSERT INTO aip_skill_eval_dispatch_observation VALUES(%s,%s,'invalid','invalid',NULL,now())", SCOPE.key)
    with writer(dispatch_schema) as conn:
        assert STORE.get(conn, SCOPE, intent['intent_id'])['version'] == 1
        assert STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=1, case_id='case-1', purpose='target', input_hash='c'*64) is not None


def test_cross_tenant_and_runtime_cannot_claim(dispatch_schema, intent):
    with writer(dispatch_schema, CANARY) as conn:
        assert STORE.get(conn, CANARY, intent['intent_id']) is None
        with pytest.raises(SkillEvalIntentConflict):
            STORE.claim(conn, CANARY, intent_id=intent['intent_id'], expected_version=1, case_id='case-1', purpose='target', input_hash='c'*64)
    with writer(dispatch_schema, role='aos_runtime') as conn:
        assert STORE.get(conn, SCOPE, intent['intent_id']) is not None
        with pytest.raises(SkillEvalIntentConflict):
            STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=1, case_id='case-1', purpose='target', input_hash='c'*64)


@pytest.mark.parametrize('statement', ['UPDATE aip_skill_eval_dispatch SET input_hash=input_hash', 'DELETE FROM aip_skill_eval_dispatch', 'TRUNCATE aip_skill_eval_dispatch'])
def test_writer_cannot_erase_or_rewrite_dispatch(dispatch_schema, intent, statement):
    with writer(dispatch_schema) as conn:
        STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=1, case_id='case-1', purpose='target', input_hash='c'*64)
        conn.commit()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with writer(dispatch_schema) as conn:
            conn.execute(statement)


def test_concurrent_claim_has_one_winner(dispatch_schema, intent):
    barrier = Barrier(2)
    def claim(_):
        try:
            with writer(dispatch_schema) as conn:
                conn.execute("SET LOCAL lock_timeout='5s'")
                barrier.wait(timeout=5)
                result = STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=1,
                                     case_id='case-1', purpose='target', input_hash='c'*64)
                conn.commit()
                return 'new' if result else 'existing'
        except (SkillEvalIntentConflict, psycopg.errors.SerializationFailure):
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(claim, [1, 2])) == ['conflict', 'new']
    with writer(dispatch_schema) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_skill_eval_dispatch WHERE intent_id=%s', (intent['intent_id'],)).fetchone()['n'] == 1


def test_completed_run_cannot_dispatch(dispatch_schema, intent):
    dsn, schema = dispatch_schema
    with psycopg.connect(dsn) as conn:
        conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        conn.execute("UPDATE aip_eval_run SET status='succeeded' WHERE run_id=%s", (intent['run_id'],))
        conn.commit()
    with pytest.raises(SkillEvalIntentConflict, match='running Skill Run'):
        with writer(dispatch_schema) as conn:
            STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=1, case_id='case-1', purpose='target', input_hash='c'*64)


def test_runtime_sql_write_and_cross_scope_insert_are_denied(dispatch_schema, intent):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with writer(dispatch_schema, role='aos_runtime') as conn:
            conn.execute('UPDATE aip_skill_eval_intent SET version=version+1 WHERE intent_id=%s', (intent['intent_id'],))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with writer(dispatch_schema, CANARY) as conn:
            conn.execute('INSERT INTO aip_skill_eval_intent(org_id,project_id,intent_id,run_id,idempotency_key,request_hash) VALUES(%s,%s,%s,%s,%s,%s)',
                (*SCOPE.key, 'forbidden', intent['run_id'], 'forbidden-key', 'f'*64))


def test_direct_writer_identity_change_is_denied(dispatch_schema, intent):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with writer(dispatch_schema) as conn:
            conn.execute("UPDATE aip_skill_eval_intent SET request_hash=%s WHERE intent_id=%s", ('f'*64, intent['intent_id']))


@pytest.mark.parametrize('mode', ['autocommit', 'isolation'])
def test_unsafe_transaction_mode_is_rejected(dispatch_schema, intent, mode):
    with writer(dispatch_schema, isolation='READ COMMITTED' if mode == 'isolation' else 'SERIALIZABLE') as conn:
        if mode == 'autocommit':
            conn.commit()
            conn.autocommit = True
        with pytest.raises(SkillEvalIntentConflict):
            STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=1, case_id='case-1', purpose='target', input_hash='c'*64)


def test_writer_has_no_run_update_or_login_authority(dispatch_schema):
    with writer(dispatch_schema) as conn:
        assert conn.execute("SELECT has_table_privilege('aip_eval_run','UPDATE') AS allowed").fetchone()['allowed'] is False
        row = conn.execute("SELECT rolcanlogin,rolsuper,rolbypassrls,rolinherit FROM pg_roles WHERE rolname=current_user").fetchone()
        assert all(value is False for value in row.values())


def test_observation_exact_replay_cannot_replace_result(dispatch_schema, intent):
    with writer(dispatch_schema) as conn:
        dispatch = STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=1, case_id='case-1', purpose='target', input_hash='c'*64)
        STORE.observe(conn, SCOPE, dispatch_id=dispatch, state='result_observed', result_hash='d'*64)
        STORE.observe(conn, SCOPE, dispatch_id=dispatch, state='result_observed', result_hash='d'*64)
        assert len(STORE.observations(conn, SCOPE, dispatch)) == 1
        conn.commit()
    for state, digest in [('result_observed','e'*64), ('unknown',None)]:
        with pytest.raises(SkillEvalIntentConflict):
            with writer(dispatch_schema) as conn:
                STORE.observe(conn, SCOPE, dispatch_id=dispatch, state=state, result_hash=digest)


@pytest.mark.parametrize('statement', [
    'UPDATE aip_skill_eval_dispatch SET input_hash=input_hash',
    'DELETE FROM aip_skill_eval_dispatch',
    'UPDATE aip_skill_eval_intent SET version=version+2',
    "UPDATE aip_skill_eval_intent SET request_hash=repeat('f',64)",
])
def test_native_immutable_trigger_blocks_privileged_drift(dispatch_schema, intent, statement):
    with writer(dispatch_schema) as conn:
        STORE.claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=1,
                    case_id='case-1', purpose='target', input_hash='c'*64)
        conn.commit()
    dsn, schema = dispatch_schema
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        with psycopg.connect(dsn) as conn:
            conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            conn.execute(statement)


@pytest.mark.parametrize('scenario',['missing_target','unobserved','unknown','wrong_case','wrong_input'])
def test_judge_requires_matching_observed_target_before_claim(dispatch_schema,intent,scenario):
    version=1
    if scenario!='missing_target':
        with writer(dispatch_schema) as conn:
            target=STORE.claim(conn,SCOPE,intent_id=intent['intent_id'],expected_version=1,
                case_id='case-1',purpose='target',input_hash='c'*64)
            if scenario not in {'unobserved'}:
                STORE.observe(conn,SCOPE,dispatch_id=target,
                    state='unknown' if scenario=='unknown' else 'result_observed',
                    result_hash=None if scenario=='unknown' else 'd'*64)
            conn.commit()
        version=2
    with pytest.raises(SkillEvalIntentConflict,match='observed Target'):
        with writer(dispatch_schema) as conn:
            STORE.claim(conn,SCOPE,intent_id=intent['intent_id'],expected_version=version,
                case_id='case-2' if scenario=='wrong_case' else 'case-1',purpose='judge',
                input_hash='f'*64 if scenario=='wrong_input' else 'c'*64)
    with writer(dispatch_schema) as conn:
        assert STORE.get(conn,SCOPE,intent['intent_id'])['version']==version
        assert conn.execute("SELECT count(*) AS n FROM aip_skill_eval_dispatch WHERE intent_id=%s AND purpose='judge'",(intent['intent_id'],)).fetchone()['n']==0


def test_judge_after_observed_target_claims_once(dispatch_schema,intent):
    with writer(dispatch_schema) as conn:
        target=STORE.claim(conn,SCOPE,intent_id=intent['intent_id'],expected_version=1,
            case_id='case-1',purpose='target',input_hash='c'*64)
        STORE.observe(conn,SCOPE,dispatch_id=target,state='result_observed',result_hash='d'*64)
        judge=STORE.claim(conn,SCOPE,intent_id=intent['intent_id'],expected_version=2,
            case_id='case-1',purpose='judge',input_hash='c'*64)
        assert judge is not None
        conn.commit()
    with writer(dispatch_schema) as conn:
        assert STORE.claim(conn,SCOPE,intent_id=intent['intent_id'],expected_version=3,
            case_id='case-1',purpose='judge',input_hash='c'*64) is None
        assert STORE.get(conn,SCOPE,intent['intent_id'])['version']==3
