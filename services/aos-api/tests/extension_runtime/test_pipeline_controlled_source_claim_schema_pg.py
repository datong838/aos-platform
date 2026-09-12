"""Claims bind existing runs to exact controls in an isolated PostgreSQL schema."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest
from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_runtime_control_schema_pg import control_ledger, append as append_control


@pytest.fixture
def claims(control_ledger):
    conn,control,_=control_ledger
    append_control(conn,control)
    conn.execute('CREATE TABLE meta_schedule_run(org_id text,project_id text,id text,UNIQUE(org_id,project_id,id))')
    conn.execute('INSERT INTO meta_schedule_run VALUES(%s,%s,%s)',(control['org_id'],control['project_id'],'run-one'))
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_024_pipeline_controlled_source_claim.py'
    spec=importlib.util.spec_from_file_location('source_claim_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    row={name:control[name] for name in ('org_id','project_id','installation_id','generation','pipeline_id','control_id')}
    row.update(run_id='run-one',control_revision=control['revision'],control_hash=control['content_hash'],call_ordinal=1,actor='current-actor')
    return conn,row,module


def append(conn,row):
    conn.execute(sql.SQL('INSERT INTO pipeline_controlled_source_claim ({}) VALUES ({})').format(
        sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row)),tuple(row.values()))


def test_runtime_can_append_only_exact_bound_claim(claims):
    conn,row,_=claims
    conn.execute('SET ROLE aos_runtime')
    append(conn,row)
    assert conn.execute('SELECT run_id,call_ordinal FROM pipeline_controlled_source_claim').fetchall()==[('run-one',1)]


@pytest.mark.parametrize('field,value',[
    ('run_id','nonexistent'),('pipeline_id','another'),('generation',uuid4()),('control_id',uuid4()),
    ('control_revision',2),('control_hash','sha256:'+'f'*64),('org_id','dev-org'),('call_ordinal',0),('call_ordinal',33),('actor',''),
])
def test_invalid_binding_is_rejected(claims,field,value):
    conn,row,_=claims
    with pytest.raises(psycopg.IntegrityError):append(conn,row|{field:value})
    assert conn.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()==(0,)


@pytest.mark.parametrize('same_run',[False,True])
def test_run_and_call_ordinal_cannot_be_duplicated(claims,same_run):
    conn,row,_=claims;append(conn,row)
    conn.execute('INSERT INTO meta_schedule_run VALUES(%s,%s,%s)',(row['org_id'],row['project_id'],'run-two'))
    changed=row|({'call_ordinal':2} if same_run else {'run_id':'run-two'})
    with pytest.raises(psycopg.IntegrityError):append(conn,changed)


@pytest.mark.parametrize('statement',["UPDATE pipeline_controlled_source_claim SET actor='other'",'DELETE FROM pipeline_controlled_source_claim','TRUNCATE pipeline_controlled_source_claim'])
def test_claim_cannot_be_erased_or_changed(claims,statement):
    conn,row,_=claims;append(conn,row)
    with pytest.raises(psycopg.DatabaseError,match='immutable'):conn.execute(statement)


def test_tenant_canary_cannot_read_or_append(claims):
    conn,row,_=claims;append(conn,row)
    conn.execute('SET ROLE aos_runtime')
    conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    assert conn.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()==(0,)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):append(conn,row)


def test_default_grants_do_not_expand_claim_permissions(database):
    conn,_,schema=database
    conn.execute(sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT ALL ON TABLES TO aos_runtime').format(sql.Identifier(schema)))
    claims.__wrapped__(control_ledger.__wrapped__(ledger.__wrapped__(database)))
    assert conn.execute("SELECT has_table_privilege('aos_runtime','pipeline_controlled_source_claim','UPDATE'),has_table_privilege('aos_runtime','pipeline_controlled_source_claim','DELETE'),has_table_privilege('aos_runtime','pipeline_controlled_source_claim','TRUNCATE')").fetchone()==(False,False,False)


def test_claim_history_cannot_be_downgraded(claims):
    with pytest.raises(RuntimeError,match='retained'):claims[2].downgrade()
