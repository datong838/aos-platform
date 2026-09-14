"""Schema integrity only; existing ingress fixture is not a group-read authorization."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import psycopg
from psycopg.types.json import Jsonb
import pytest
from test_lifecycle_pg import database,pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case


@pytest.fixture
def group_schema(executor_case):
    executor,conn,args,state=executor_case
    original=executor.prepare(**args)
    conn.execute('RESET ROLE')
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_045_snapshot_group_journal.py'
    spec=importlib.util.spec_from_file_location('snapshot_group_schema',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=conn.execute);module.upgrade();conn.execute('SET ROLE aos_runtime')
    return conn,args,original


def claim(conn,args,group_id,*,count=1,actor='test-actor'):
    conn.execute('INSERT INTO pipeline_snapshot_group_claim(org_id,project_id,group_id,actor,request_hash,member_count,binding) VALUES(%s,%s,%s,%s,%s,%s,%s)',(*args['scope'].key,group_id,actor,'sha256:'+'1'*64,count,Jsonb({'fixture':True})))


def member(conn,args,group_id):
    conn.execute('INSERT INTO pipeline_snapshot_group_member(org_id,project_id,group_id,ordinal,run_id) VALUES(%s,%s,%s,1,%s)',(*args['scope'].key,group_id,args['run_id']))


def input_row(conn,args,group_id,*,bad_hash=False,mutate=None):
    original=conn.execute('SELECT envelope_hash FROM ecommerce_ingress_command WHERE run_id=%s',(args['run_id'],)).fetchone()['envelope_hash']
    manifest={'members':[{'runId':args['run_id'],'envelopeHash':'0'*64 if bad_hash else original,'rowsHash':'sha256:'+'2'*64,'rowCount':1}]}
    if mutate is not None:mutate(manifest)
    conn.execute("INSERT INTO pipeline_snapshot_group_input(org_id,project_id,group_id,request_hash,read_started_at,read_completed_at,snapshot_basis,manifest_hash,manifest) VALUES(%s,%s,%s,%s,clock_timestamp(),clock_timestamp(),'innodb-repeatable-read',%s,%s)",(*args['scope'].key,group_id,'sha256:'+'1'*64,'sha256:'+'3'*64,Jsonb(manifest)))


def test_complete_group_and_bound_original_input_commit(group_schema):
    conn,args,_=group_schema;group_id=uuid4()
    with conn.transaction():claim(conn,args,group_id);member(conn,args,group_id);input_row(conn,args,group_id)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_input').fetchone()['n']==1


@pytest.mark.parametrize('fault',['missing_member','incomplete','actor','input_hash'])
def test_invalid_group_rolls_back_entire_transaction(group_schema,fault):
    conn,args,_=group_schema;group_id=uuid4()
    with pytest.raises(psycopg.Error),conn.transaction():
        claim(conn,args,group_id,count=2 if fault=='incomplete' else 1,actor='other' if fault=='actor' else 'test-actor')
        if fault!='missing_member':member(conn,args,group_id)
        if fault=='input_hash':input_row(conn,args,group_id,bad_hash=True)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_claim').fetchone()['n']==0


def test_original_source_claim_cannot_join_two_groups(group_schema):
    conn,args,_=group_schema;first=uuid4()
    with conn.transaction():claim(conn,args,first);member(conn,args,first)
    with pytest.raises(psycopg.Error),conn.transaction():
        second=uuid4();claim(conn,args,second);member(conn,args,second)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_claim').fetchone()['n']==1


def test_group_history_is_immutable_and_tenant_isolated(group_schema):
    conn,args,_=group_schema;group_id=uuid4()
    with conn.transaction():claim(conn,args,group_id);member(conn,args,group_id)
    for statement in ('UPDATE pipeline_snapshot_group_claim SET actor=actor','DELETE FROM pipeline_snapshot_group_member','TRUNCATE pipeline_snapshot_group_claim CASCADE'):
        with pytest.raises(psycopg.Error),conn.transaction():conn.execute(statement)
    with conn.transaction():
        conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_claim').fetchone()['n']==0
        with pytest.raises(psycopg.Error),conn.transaction():claim(conn,args,uuid4())


@pytest.mark.parametrize('fault',['empty','wrong_run','boolean_count','extra','bad_rows_hash'])
def test_input_manifest_cannot_smuggle_incomplete_or_unbound_members(group_schema,fault):
    conn,args,_=group_schema;group_id=uuid4()
    def mutate(body):
        if fault=='empty':body['members']=[]
        elif fault=='wrong_run':body['members'][0]['runId']='other-run'
        elif fault=='boolean_count':body['members'][0]['rowCount']=True
        elif fault=='extra':body['members'][0]['extra']='not-allowed'
        else:body['members'][0]['rowsHash']='invalid'
    with pytest.raises(psycopg.Error),conn.transaction():
        claim(conn,args,group_id);member(conn,args,group_id);input_row(conn,args,group_id,mutate=mutate)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_claim').fetchone()['n']==0


def test_table_owner_cannot_overwrite_group_history(group_schema):
    conn,args,_=group_schema;group_id=uuid4()
    with conn.transaction():claim(conn,args,group_id);member(conn,args,group_id)
    conn.execute('RESET ROLE')
    with pytest.raises(psycopg.Error),conn.transaction():conn.execute('UPDATE pipeline_snapshot_group_claim SET actor=actor')
    conn.execute('SET ROLE aos_runtime')
