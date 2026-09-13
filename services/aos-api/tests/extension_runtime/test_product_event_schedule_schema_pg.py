import importlib.util
from pathlib import Path
from types import SimpleNamespace
import psycopg
from psycopg.types.json import Jsonb
import pytest

from test_lifecycle_pg import database, pytestmark


def migration(name, conn):
    path=Path(__file__).resolve().parents[2]/'alembic/versions'/name
    spec=importlib.util.spec_from_file_location('event_schema_test_'+name,path)
    item=importlib.util.module_from_spec(spec);spec.loader.exec_module(item)
    item.op=SimpleNamespace(execute=conn.execute)
    return item


@pytest.fixture
def schema_case(database):
    conn,_,_=database
    conn.execute('CREATE TABLE ecommerce_investigation_case_head(org_id text,project_id text,case_id text,PRIMARY KEY(org_id,project_id,case_id))')
    conn.execute('CREATE TABLE ecommerce_investigation_case_revision(org_id text,project_id text,case_id text,revision bigint,PRIMARY KEY(org_id,project_id,case_id,revision))')
    conn.execute("CREATE FUNCTION guard_ecommerce_investigation_case_biw4_001() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable fixture'; END $$")
    migration('biw8_001_investigation_schedule_policy.py',conn).upgrade()
    conn.execute("INSERT INTO ecommerce_investigation_case_head VALUES ('org-org','dev-project','case')")
    conn.execute("INSERT INTO ecommerce_investigation_case_revision VALUES ('org-org','dev-project','case',1)")
    return conn,migration('a0v_039_product_event_schedule_schema.py',conn)


def insert(conn, name, kind='initial_checkup', cadence='once', schema='aos.ecommerce.business-investigation-schedule-policy/v1'):
    conn.execute('''INSERT INTO ecommerce_investigation_schedule_policy_revision
        (org_id,project_id,schedule_policy_id,revision,case_id,case_revision,analysis_type,policy_kind,cadence,
         enabled,content_hash,authority_data,created_by,created_at)
        VALUES ('org-org','dev-project',%s,1,'case',1,'initial_store_analysis',%s,%s,false,%s,%s,'fixture',now())''',
        (name,kind,cadence,'sha256:'+'a'*64,Jsonb({} if schema is None else {'schemaVersion':schema})))


def test_upgrade_preserves_old_rows_and_function_and_accepts_only_event_pair(schema_case):
    conn,new=schema_case
    insert(conn,'old')
    before=conn.execute("SELECT pg_get_functiondef(oid) FROM pg_proc WHERE pronamespace=current_schema()::regnamespace AND proname='ecommerce_investigation_schedule_policy_put_biw8_001'").fetchone()[0]
    with conn.transaction():new.upgrade()
    insert(conn,'event','product_event','event','aos.ecommerce.product-event-schedule-policy/v1')
    for kind,cadence,version in [('product_event','once','aos.ecommerce.product-event-schedule-policy/v1'),
        ('initial_checkup','event','aos.ecommerce.product-event-schedule-policy/v1'),
        ('initial_checkup','once','aos.ecommerce.product-event-schedule-policy/v1'),('product_event','event',None),('product_event','event','wrong')]:
        with pytest.raises(psycopg.errors.CheckViolation),conn.transaction():insert(conn,'bad',kind,cadence,version)
    assert conn.execute('SELECT count(*) FROM ecommerce_investigation_schedule_policy_revision').fetchone()[0]==2
    assert conn.execute("SELECT pg_get_functiondef(oid) FROM pg_proc WHERE pronamespace=current_schema()::regnamespace AND proname='ecommerce_investigation_schedule_policy_put_biw8_001'").fetchone()[0]==before
    with pytest.raises(psycopg.errors.CheckViolation),conn.transaction():new.downgrade()


def test_empty_event_history_can_revert(schema_case):
    conn,new=schema_case
    with conn.transaction():new.upgrade()
    insert(conn,'old')
    with conn.transaction():new.downgrade()
    insert(conn,'old-after')
    with pytest.raises(psycopg.errors.CheckViolation),conn.transaction():
        insert(conn,'event','product_event','event','aos.ecommerce.product-event-schedule-policy/v1')
