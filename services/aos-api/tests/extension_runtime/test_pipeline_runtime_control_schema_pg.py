"""Runtime control ledger constraints in a disposable schema only."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest
from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger, append as append_selection


@pytest.fixture
def control_ledger(ledger):
    conn,selection,_=ledger
    append_selection(conn,selection)
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_023_pipeline_runtime_control.py'
    spec=importlib.util.spec_from_file_location('control_ledger_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    row={name:selection[name] for name in ('org_id','project_id','installation_id','generation','pipeline_id')}
    row.update(control_id=uuid4(),revision=1,selection_id=selection['selection_id'],selection_revision=selection['revision'],
        selection_hash=selection['content_hash'],content_hash='sha256:'+'c'*64,previous_revision=None,
        previous_hash=None,request_hash='sha256:'+'d'*64,idempotency_key='first',actor='test-actor')
    return conn,row,module


def append(conn,row,payload=None):
    if payload is None:
        payload={'schemaVersion':'aos.pipeline-runtime-control-revision/v1'}
        for key in ('org_id','project_id','installation_id','generation','pipeline_id','control_id','revision','selection_id','selection_revision','selection_hash','actor'):
            name=key.split('_')[0]+''.join(part.title() for part in key.split('_')[1:])
            payload[name]=row[key] if key in ('revision','selection_revision') else str(row[key])
    columns=tuple(row)+('payload',)
    conn.execute(sql.SQL('INSERT INTO pipeline_runtime_control_revision ({}) VALUES ({})').format(
        sql.SQL(',').join(map(sql.Identifier,columns)),sql.SQL(',').join(sql.Placeholder() for _ in columns)),(*row.values(),Jsonb(payload)))


def test_control_chain_references_exact_selection(control_ledger):
    conn,row,_=control_ledger
    conn.execute('SET ROLE aos_runtime')
    append(conn,row)
    append(conn,row|dict(revision=2,previous_revision=1,previous_hash=row['content_hash'],content_hash='sha256:'+'e'*64,idempotency_key='next'))
    assert conn.execute('SELECT revision FROM pipeline_runtime_control_revision ORDER BY revision').fetchall()==[(1,),(2,)]


@pytest.mark.parametrize('mode',['selection_hash','selection_revision','pipeline','generation','tenant','predecessor','duplicate_key','null_header'])
def test_wrong_selection_or_chain_is_rejected(control_ledger,mode):
    conn,row,_=control_ledger
    append(conn,row)
    changed=row|dict(revision=2,previous_revision=1,previous_hash=row['content_hash'],idempotency_key='next')
    if mode=='selection_hash':changed['selection_hash']='sha256:'+'f'*64
    elif mode=='selection_revision':changed['selection_revision']=2
    elif mode=='pipeline':changed['pipeline_id']='another'
    elif mode=='generation':changed['generation']=uuid4()
    elif mode=='tenant':changed['org_id']='dev-org'
    elif mode=='predecessor':changed['previous_hash']='sha256:'+'f'*64
    elif mode=='duplicate_key':changed['idempotency_key']='first'
    with pytest.raises(psycopg.IntegrityError):append(conn,changed,payload={} if mode=='null_header' else None)
    assert conn.execute('SELECT count(*) FROM pipeline_runtime_control_revision').fetchone()==(1,)


@pytest.mark.parametrize('statement',["UPDATE pipeline_runtime_control_revision SET actor='other'",'DELETE FROM pipeline_runtime_control_revision','TRUNCATE pipeline_runtime_control_revision'])
def test_control_history_is_immutable(control_ledger,statement):
    conn,row,_=control_ledger;append(conn,row)
    with pytest.raises(psycopg.DatabaseError,match='immutable'):conn.execute(statement)


def test_runtime_role_tenant_isolation(control_ledger):
    conn,row,_=control_ledger;append(conn,row)
    conn.execute('SET ROLE aos_runtime')
    conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    assert conn.execute('SELECT count(*) FROM pipeline_runtime_control_revision').fetchone()==(0,)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):append(conn,row|dict(idempotency_key='other'))


def test_no_destructive_downgrade(control_ledger):
    _,_,module=control_ledger
    with pytest.raises(RuntimeError,match='retained'):module.downgrade()
