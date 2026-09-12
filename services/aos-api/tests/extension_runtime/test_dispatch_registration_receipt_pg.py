import importlib.util
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_sha256
from test_investigation_description_store_pg import database, pytestmark, ROOT


@pytest.fixture
def receipt_db(database):
    conn=database.owner
    conn.execute('CREATE TABLE extension_runtime_binding(org_id text,project_id text,installation_id uuid,generation uuid,PRIMARY KEY(org_id,project_id,installation_id,generation))')
    path=ROOT/'alembic/versions/a0v_026_dispatch_registration_receipt.py'
    spec=importlib.util.spec_from_file_location('registration_receipt_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    installation,generation=uuid4(),uuid4()
    conn.execute("INSERT INTO extension_runtime_binding VALUES('org-a','project-a',%s,%s)",(installation,generation))
    return database,installation,generation


def insert(receipt_db,*,key='key-1',group=None,corrupt=False,mutate=None):
    database,installation,generation=receipt_db
    group=group or uuid4();identity=uuid4()
    body=dict(schemaVersion='aos.ecommerce.first-dispatch-registration-receipt/v1',
        tenant=dict(orgId='org-a',projectId='project-a'),installationId=str(installation),
        generation=str(generation),groupId=str(group),receiptId=str(identity),
        requestHash='sha256:'+'1'*64,idempotencyKey=key,actor='actor')
    if mutate:mutate(body)
    digest='sha256:'+'0'*64 if corrupt else canonical_sha256(body)
    database.owner.execute('''INSERT INTO extension_dispatch_registration_receipt
        (org_id,project_id,receipt_id,installation_id,generation,group_id,idempotency_key,request_hash,payload,content_hash)
        VALUES('org-a','project-a',%s,%s,%s,%s,%s,%s,%s,%s)''',
        (identity,installation,generation,group,key,body['requestHash'],Jsonb(body),digest))
    return group


def test_valid_hash_and_hash_drift(receipt_db):
    insert(receipt_db)
    with pytest.raises(psycopg.Error):insert(receipt_db,key='key-2',corrupt=True)
    assert receipt_db[0].owner.execute('SELECT count(*) AS n FROM extension_dispatch_registration_receipt').fetchone()['n']==1


@pytest.mark.parametrize('command',['UPDATE extension_dispatch_registration_receipt SET content_hash=content_hash',
    'DELETE FROM extension_dispatch_registration_receipt','TRUNCATE extension_dispatch_registration_receipt'])
def test_even_owner_cannot_rewrite_history(receipt_db,command):
    insert(receipt_db)
    with pytest.raises(psycopg.Error):receipt_db[0].owner.execute(command)


def test_group_and_idempotency_are_unique(receipt_db):
    group=insert(receipt_db)
    with pytest.raises(psycopg.errors.UniqueViolation):insert(receipt_db)
    with pytest.raises(psycopg.errors.UniqueViolation):insert(receipt_db,key='different',group=group)


@pytest.mark.parametrize('field',['tenant','installationId','groupId','schemaVersion','receiptId'])
def test_rehashed_wrong_identity_is_rejected(receipt_db,field):
    def mutate(body):
        body[field]=dict(orgId='other',projectId='project-a') if field=='tenant' else 'wrong'
    with pytest.raises(psycopg.errors.CheckViolation):insert(receipt_db,mutate=mutate)


def test_runtime_read_scope_and_no_direct_write(receipt_db):
    insert(receipt_db);db=receipt_db[0]
    with psycopg.connect(**db.pg,autocommit=True) as conn:
        conn.execute('SET ROLE aos_runtime')
        conn.execute("SELECT set_config('aos.org_id','org-a',false),set_config('aos.project_id','project-a',false)")
        assert conn.execute('SELECT count(*) FROM extension_dispatch_registration_receipt').fetchone()[0]==1
        conn.execute("SELECT set_config('aos.org_id','other',false)")
        assert conn.execute('SELECT count(*) FROM extension_dispatch_registration_receipt').fetchone()[0]==0
        for action in ('INSERT','UPDATE','DELETE','TRUNCATE'):
            assert conn.execute("SELECT has_table_privilege(current_user,'extension_dispatch_registration_receipt',%s)",(action,)).fetchone()[0] is False
        for statement in ('INSERT INTO extension_dispatch_registration_receipt SELECT * FROM extension_dispatch_registration_receipt',
            'UPDATE extension_dispatch_registration_receipt SET content_hash=content_hash',
            'DELETE FROM extension_dispatch_registration_receipt','TRUNCATE extension_dispatch_registration_receipt'):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute(statement)
