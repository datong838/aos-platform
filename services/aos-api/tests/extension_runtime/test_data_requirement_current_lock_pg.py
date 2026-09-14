"""Original Requirement CAS versus exact head lock, only isolated 18432 schema."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

from test_lifecycle_pg import database, pytestmark
from tests.test_data_requirement_store import requirement
from aos_api.business_investigation_shared_contracts import DataRequirementStatus
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
from aos_api.data_requirement_store import DataRequirementStore, DataRequirementConflict, DataRequirementValidationError, canonical_revision_content_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope

SCOPE=TenantScope(org_id='org-org',project_id='dev-project')


@pytest.fixture
def head_case(database):
    conn,role,schema=database;conn.row_factory=dict_row
    root=Path(__file__).resolve().parents[2]/'alembic/versions'
    nodes=ast.walk(ast.parse((root/'aip4_001_eval_lineage_observability_contract.py').read_text()))
    guard=next(n.value for n in nodes if isinstance(n,ast.Constant) and isinstance(n.value,str)
        and n.value.strip().startswith('CREATE FUNCTION guard_aip4_append_only()'))
    conn.execute(guard)
    def execute(statement):
        statement=statement.replace('SET search_path = pg_catalog, public',f'SET search_path = pg_catalog,"{schema}",public')
        statement=statement.replace('public.data_requirement_head',f'"{schema}".data_requirement_head')
        return conn.execute(statement)
    for filename in ('biw2_001_data_requirement_authority.py','biw2_002_data_requirement_cas.py',
                     'a0v_049_data_requirement_current_lock.py'):
        spec=importlib.util.spec_from_file_location('head_lock_ddl',root/filename)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.op=NS(execute=execute);module.upgrade()
    conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_runtime').format(sql.Identifier(schema)))
    conn.execute('SET ROLE aos_runtime')
    conn.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
    store=DataRequirementStore(TransactionBoundConnectFactory(HostTransaction(conn),SCOPE))
    req=requirement()
    with conn.transaction():
        saved=store.request(SCOPE,req.created_by,'head-lock-original',req,expected_version=0)
    return conn,role,schema,store,req,saved.exact_ref


def cancelled(req,ref):
    result=req.model_copy(update=dict(revision=2,prior_ref=ref,status=DataRequirementStatus.CANCELLED))
    result=DataRequirementRevisionRecord.model_validate(result.model_dump())
    return result.model_copy(update={'content_hash':canonical_revision_content_hash(result)})


def test_original_cancel_cannot_cross_locked_requirement_then_succeeds(head_case):
    conn,_,schema,store,req,ref=head_case
    with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',
                         autocommit=True,row_factory=dict_row) as other:
        other.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        other.execute('SET ROLE aos_runtime')
        other.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
        second=DataRequirementStore(TransactionBoundConnectFactory(HostTransaction(other),SCOPE))
        with conn.transaction():
            assert store.lock_current(SCOPE,ref)==req
            with pytest.raises(psycopg.errors.LockNotAvailable),other.transaction():
                other.execute("SET LOCAL lock_timeout='150ms'")
                second.cancel(SCOPE,req.created_by,'head-lock-cancel',cancelled(req,ref),expected_version=1)
            assert store.get_current(SCOPE,req.requirement_id)==req
        with other.transaction():
            result=second.cancel(SCOPE,req.created_by,'head-lock-cancel',cancelled(req,ref),expected_version=1)
        assert result.version==2
        with pytest.raises(DataRequirementConflict),conn.transaction():store.lock_current(SCOPE,ref)
        assert conn.execute('SELECT count(*) AS n FROM data_requirement_event').fetchone()['n']==2


@pytest.mark.parametrize('fault',['hash','revision','kind','receipt','boolean','canary','project'])
def test_lock_rejects_wrong_or_cross_tenant_authority(head_case,fault):
    conn,_,_,store,_,ref=head_case
    if fault=='hash':ref=ref.model_copy(update={'content_hash':'sha256:'+'f'*64})
    elif fault=='revision':ref=ref.model_copy(update={'revision':2})
    elif fault=='kind':ref=ref.model_copy(update={'resource_type':'Evidence'})
    elif fault=='receipt':ref=ref.model_copy(update={'receipt_id':'other'})
    elif fault=='boolean':ref=ref.model_copy(update={'revision':True})
    elif fault=='canary':conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    elif fault=='project':conn.execute("SELECT set_config('aos.project_id','other',false)")
    with pytest.raises((DataRequirementConflict,DataRequirementValidationError)),conn.transaction():
        store.lock_current(SCOPE,ref)


def test_lock_function_does_not_grant_table_writes_or_public_execution(head_case):
    conn,role,_,store,req,ref=head_case
    with conn.transaction():assert store.lock_current(SCOPE,ref)==req
    with pytest.raises(psycopg.errors.InsufficientPrivilege),conn.transaction():
        conn.execute('UPDATE data_requirement_head SET version=version+1')
    with pytest.raises(psycopg.errors.InsufficientPrivilege),conn.transaction():
        conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
        conn.execute('SELECT * FROM data_requirement_lock_current_a0v_049(%s,%s,%s)',
            (ref.resource_id,ref.revision,ref.content_hash))
