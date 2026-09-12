"""Schedule approval history constraints in a dedicated schema, never live data."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg import errors,sql
from test_pipeline_source_claim_owner_pg import claim_case
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_selection_schema_pg import ledger
from test_lifecycle_pg import database,pytestmark


@pytest.fixture
def binding_case(claim_case):
    conn,claims,args,controls,draft,selections=claim_case
    conn.execute('RESET ROLE')
    conn.execute('ALTER TABLE meta_schedule ADD PRIMARY KEY(org_id,project_id,id)')
    conn.execute('ALTER TABLE meta_schedule_run ADD COLUMN IF NOT EXISTS executor_stopped boolean')
    # Simulate installations with permissive inherited defaults.
    conn.execute(sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT ALL ON TABLES TO aos_runtime').format(sql.Identifier(claims._journal.schema)))
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_025_pipeline_schedule_control_binding.py'
    spec=importlib.util.spec_from_file_location('schedule_binding_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=conn.execute)
    try:module.upgrade()
    finally:conn.execute(sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA {} REVOKE ALL ON TABLES FROM aos_runtime').format(sql.Identifier(claims._journal.schema)))
    conn.execute('SET ROLE aos_runtime')
    row=dict(org_id=args['scope'].org_id,project_id=args['scope'].project_id,schedule_id='schedule',
        binding_id=uuid4(),revision=1,installation_id=draft.installation_ref.installation_id,generation=draft.generation,
        pipeline_id=draft.pipeline_id,control_id=args['control_ref'].resource_id.removeprefix('pipeline-control-'),
        control_revision=args['control_ref'].revision,control_hash=args['control_ref'].content_hash,
        actor=args['actor'],content_hash='sha256:'+'a'*64,previous_revision=None,previous_hash=None,
        request_hash='sha256:'+'b'*64,idempotency_key='first')
    return conn,row


def insert(conn,row):
    conn.execute(sql.SQL('INSERT INTO pipeline_schedule_control_binding ({}) VALUES ({})').format(
        sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row)),tuple(row.values()))


def test_history_chain_and_immutable_runtime_rights(binding_case):
    conn,first=binding_case
    insert(conn,first)
    second=first|dict(revision=2,previous_revision=1,previous_hash=first['content_hash'],content_hash='sha256:'+'c'*64,idempotency_key='next')
    insert(conn,second)
    assert conn.execute('SELECT count(*) FROM pipeline_schedule_control_binding').fetchone()=={'count':2}
    for verb in ('UPDATE','DELETE','TRUNCATE','TRIGGER','REFERENCES'):
        assert conn.execute('SELECT has_table_privilege(current_user,%s,%s) AS allowed',('pipeline_schedule_control_binding',verb)).fetchone()=={'allowed':False}
    for statement in ('UPDATE pipeline_schedule_control_binding SET actor=actor','DELETE FROM pipeline_schedule_control_binding','TRUNCATE pipeline_schedule_control_binding'):
        with pytest.raises(errors.InsufficientPrivilege):conn.execute(statement)
    conn.execute('RESET ROLE')
    for statement in ('UPDATE pipeline_schedule_control_binding SET actor=actor','DELETE FROM pipeline_schedule_control_binding','TRUNCATE pipeline_schedule_control_binding'):
        with pytest.raises(errors.RaiseException):conn.execute(statement)


@pytest.mark.parametrize('mode',['control','schedule','generation','skip','predecessor','family','duplicate'])
def test_invalid_reference_or_chain_is_rejected(binding_case,mode):
    conn,first=binding_case
    insert(conn,first)
    row=first|dict(revision=2,previous_revision=1,previous_hash=first['content_hash'],content_hash='sha256:'+'c'*64,idempotency_key='next')
    if mode=='control':row['control_hash']='sha256:'+'f'*64
    elif mode=='schedule':row['schedule_id']='missing'
    elif mode=='generation':row['generation']=uuid4()
    elif mode=='skip':row['revision']=3
    elif mode=='predecessor':row['previous_hash']='sha256:'+'f'*64
    elif mode=='family':row['binding_id']=uuid4()
    else:row['idempotency_key']='first'
    with pytest.raises((errors.ForeignKeyViolation,errors.CheckViolation,errors.UniqueViolation)):insert(conn,row)


def test_negative_tenant_cannot_read_or_insert_positive(binding_case):
    conn,row=binding_case
    insert(conn,row)
    conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    assert conn.execute('SELECT count(*) FROM pipeline_schedule_control_binding').fetchone()=={'count':0}
    with pytest.raises(errors.InsufficientPrivilege):insert(conn,row|{'revision':2})
