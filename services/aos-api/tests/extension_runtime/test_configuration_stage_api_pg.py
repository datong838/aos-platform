"""Restricted API entry SQL, using original staging guards in disposable schemas."""
import importlib.util
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from test_lifecycle_pg import database, pytestmark
from test_configuration_store_pg import configuration_case
from test_configuration_stage_schema_pg import stage, TABLE
from aos_api.asset_registry.canonical_json import canonical_sha256


@pytest.fixture
def api(stage, database):
    conn, args, body = stage
    _, _, schema = database
    conn.execute('ALTER TABLE bundle_installation ADD COLUMN installation_pk uuid DEFAULT gen_random_uuid(), ADD COLUMN current_revision bigint DEFAULT 1')
    conn.execute('CREATE TABLE meta_membership(org_id text,project_id text,subject text,role text)')
    conn.execute('CREATE TABLE authz_tuple(org_id text,project_id text,user_key text,relation text,object_key text)')
    conn.execute("INSERT INTO meta_membership VALUES('org-org','dev-project','test-actor','admin'),('org-org','dev-project','other','admin')")
    conn.execute("INSERT INTO authz_tuple VALUES('org-org','dev-project','user:test-actor','bearer','marking:public'),('org-org','dev-project','user:other','bearer','marking:public')")
    conn.execute('CREATE TABLE bundle_installation_revision(org_id text,project_id text,installation_pk uuid,revision bigint,composition_pk uuid,lock_revision bigint,lock_hash text,permission_diff_hash text)')
    conn.execute('CREATE TABLE bundle_composition_lock(org_id text,project_id text,composition_pk uuid,revision bigint,lock_payload jsonb,lock_hash text,permission_diff_json jsonb,permission_diff_hash text)')
    composition = uuid4(); permission = dict(target=dict(markings=['public'])); lock = dict(permissionDiff=permission)
    conn.execute("INSERT INTO bundle_composition_lock VALUES('org-org','dev-project',%s,1,%s,%s,%s,%s)",
                 (composition, Jsonb(lock), canonical_sha256(lock), Jsonb(permission), canonical_sha256(permission)))
    conn.execute("INSERT INTO bundle_installation_revision SELECT org_id,project_id,installation_pk,1,%s,1,%s,%s FROM bundle_installation",
                 (composition, canonical_sha256(lock), canonical_sha256(permission)))
    path = Path(__file__).resolve().parents[2]/'alembic/versions/a0v_037_configuration_stage_api.py'
    spec = importlib.util.spec_from_file_location('stage_api_migration', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.op = SimpleNamespace(execute=lambda q: conn.execute(q.replace('public.', schema+'.').replace('pg_catalog,public,pg_temp',f'pg_catalog,{schema},pg_temp')))
    module.upgrade()
    conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_configuration_stage_api').format(sql.Identifier(schema)))
    role = 'stage_api_'+uuid4().hex
    conn.execute(sql.SQL('CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS').format(sql.Identifier(role)))
    conn.execute(sql.SQL('GRANT aos_configuration_stage_api TO {}').format(sql.Identifier(role)))
    conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(schema), sql.Identifier(role)))
    try: yield conn, args, body, role
    finally:
        conn.execute('RESET SESSION AUTHORIZATION')
        conn.execute(sql.SQL('REVOKE USAGE ON SCHEMA {} FROM {}').format(sql.Identifier(schema), sql.Identifier(role)))
        conn.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))


@contextmanager
def caller(api, *, subject='test-actor', org='org-org', privileged=False):
    conn, _, _, role = api
    if not privileged: conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(role)))
    try:
        with conn.transaction():
            conn.execute('SET LOCAL ROLE aos_configuration_stage_api')
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id','dev-project',true),set_config('aos.subject',%s,true)",(org,subject))
            yield conn
    finally: conn.execute('RESET SESSION AUTHORIZATION')


def enqueue(conn, body, key='first', subject='test-actor'):
    return conn.execute('SELECT extension_configuration_stage_enqueue_a0v_037(%s,%s,%s)', (subject,key,Jsonb(body))).fetchone()[0]


def query(conn, identity, subject='test-actor'):
    return conn.execute('SELECT extension_configuration_stage_query_a0v_037(%s,%s::uuid)',(subject,identity)).fetchone()[0]


def test_replay_and_original_subject_query(api):
    with caller(api) as conn:
        first=enqueue(conn,api[2]); assert enqueue(conn,api[2])==first
        assert query(conn,first['requestId'])['state']=='requested'
        with pytest.raises(psycopg.Error):
            with conn.transaction(): conn.execute(f'SELECT * FROM {TABLE}')
    with caller(api,subject='other') as conn:
        assert query(conn,first['requestId'],subject='other') is None
    assert api[0].execute(f'SELECT count(*) FROM {TABLE}').fetchone()[0]==1


@pytest.mark.parametrize('case', ('privileged','tenant','subject','revoked','viewer','owner','marking','corrupt_permission'))
def test_current_admission_rejects_untrusted_or_revoked_identity(api,case):
    conn,_,body,_=api
    if case=='revoked': conn.execute("DELETE FROM meta_membership WHERE subject='test-actor'")
    if case in {'viewer','owner'}: conn.execute("UPDATE meta_membership SET role=%s WHERE subject='test-actor'",(case,))
    if case=='marking': conn.execute('DELETE FROM authz_tuple')
    if case=='corrupt_permission': conn.execute("UPDATE bundle_composition_lock SET permission_diff_json='{}'")
    with pytest.raises(psycopg.Error):
        with caller(api,privileged=case=='privileged',org='dev-org' if case=='tenant' else 'org-org') as conn:
            enqueue(conn,body,subject='other' if case=='subject' else 'test-actor')
    assert api[0].execute(f'SELECT count(*) FROM {TABLE}').fetchone()[0]==0


def test_same_key_different_request_is_rejected_without_second_record(api):
    from copy import deepcopy
    with caller(api) as conn:
        first=enqueue(conn,api[2])
        changed=deepcopy(api[2]); changed['policyRef']['revision']=2
        with pytest.raises(psycopg.Error):
            with conn.transaction(): enqueue(conn,changed)
        assert query(conn,first['requestId'])['state']=='requested'
    assert api[0].execute(f'SELECT count(*) FROM {TABLE}').fetchone()[0]==1


@pytest.mark.parametrize('mutation', ("DELETE FROM meta_membership WHERE subject='test-actor'",
                                      "DELETE FROM authz_tuple WHERE user_key='user:test-actor'"))
def test_old_receipt_cannot_be_read_or_replayed_after_revocation(api,mutation):
    with caller(api) as conn: receipt=enqueue(conn,api[2])
    api[0].execute(mutation)
    with pytest.raises(psycopg.Error):
        with caller(api) as conn: query(conn,receipt['requestId'])
    with pytest.raises(psycopg.Error):
        with caller(api) as conn: enqueue(conn,api[2])


def test_subject_pending_capacity_does_not_reject_same_key_replay(api):
    with caller(api) as conn:
        receipts=[enqueue(conn,api[2],key=f'item-{i}') for i in range(8)]
        assert enqueue(conn,api[2],key='item-0')==receipts[0]
        with pytest.raises(psycopg.Error):
            with conn.transaction(): enqueue(conn,api[2],key='overflow')
    assert api[0].execute(f'SELECT count(*) FROM {TABLE}').fetchone()[0]==8


def test_tenant_capacity_is_shared_across_submitters(api):
    for i in range(9):
        subject=f'actor-{i}'
        api[0].execute("INSERT INTO meta_membership VALUES('org-org','dev-project',%s,'admin')",(subject,))
        api[0].execute("INSERT INTO authz_tuple VALUES('org-org','dev-project',%s,'bearer','marking:public')",('user:'+subject,))
    for i in range(8):
        subject=f'actor-{i}'
        with caller(api,subject=subject) as conn:
            for j in range(8): enqueue(conn,api[2],key=f'item-{j}',subject=subject)
    with pytest.raises(psycopg.Error):
        with caller(api,subject='actor-8') as conn: enqueue(conn,api[2],subject='actor-8')
    assert api[0].execute(f'SELECT count(*) FROM {TABLE}').fetchone()[0]==64


def test_cached_receipt_remains_same_after_target_changes(api):
    with caller(api) as conn: first=enqueue(conn,api[2])
    api[0].execute('UPDATE bundle_installation SET etag_version=2')
    with caller(api) as conn:
        assert enqueue(conn,api[2])==first
        with pytest.raises(psycopg.Error):
            with conn.transaction(): enqueue(conn,api[2],key='new-key-old-target')
