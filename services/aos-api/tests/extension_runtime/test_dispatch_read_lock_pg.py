import importlib.util
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from test_dispatch_first_registration_atomic_pg import registered_db, receipt_db, database, pytestmark, ROOT, run
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS


@pytest.fixture
def locked_db(registered_db):
    case=registered_db;owner=case.db.owner
    owner.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(case.login)))
    owner.execute('GRANT INSERT,UPDATE,DELETE ON extension_operation_dispatch_binding TO aos_runtime,aos_extension_maintainer')
    owner.execute('GRANT UPDATE(operation_fence) ON extension_operation_dispatch_binding TO aos_runtime')
    path=ROOT/'alembic/versions/a0v_028_dispatch_read_lock.py'
    spec=importlib.util.spec_from_file_location('dispatch_read_lock',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=owner.execute);migration.upgrade()
    run(case)
    return case


@contextmanager
def runtime(case,*,scope=('org-a','project-a'),serializable=True,privileged=False,role='aos_runtime'):
    with psycopg.connect(**{**case.db.pg,'user':'postgres' if privileged else case.login},row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL '+('SERIALIZABLE' if serializable else 'READ COMMITTED'))
        conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope)
        yield conn


def read(conn,case,group=None):
    return conn.execute('SELECT * FROM public.extension_dispatch_lock_group_a0v_028(%s)',(group or case.request['groupId'],)).fetchall()


def test_read_lock_preserves_fenced_receipt_and_no_write_privileges(locked_db):
    case=locked_db
    with runtime(case) as conn:
        rows=read(conn,case)
        assert [r['operation_id'] for r in rows]==sorted(ECOMMERCE_GROWTH_OPERATIONS)
        assert all(r['operation_fence'] is True and r['handler_kind']=='legacy' for r in rows)
        assert conn.execute("SELECT has_any_column_privilege(current_user,'public.extension_operation_dispatch_binding','UPDATE') AS allowed").fetchone()['allowed'] is False
    assert run(case)['replayed'] is True


@pytest.mark.parametrize('role',['aos_runtime','aos_extension_maintainer'])
@pytest.mark.parametrize('statement',[
    'UPDATE extension_operation_dispatch_binding SET operation_fence=false WHERE false',
    'DELETE FROM extension_operation_dispatch_binding WHERE false',
    'INSERT INTO extension_operation_dispatch_binding SELECT * FROM extension_operation_dispatch_binding WHERE false',
    'TRUNCATE extension_operation_dispatch_binding',
    'SELECT * FROM extension_operation_dispatch_binding FOR UPDATE',
])
def test_ordinary_roles_direct_mutation_and_lock_denied(locked_db,statement,role):
    with runtime(locked_db,role=role) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute(statement)


@pytest.mark.parametrize('kind',['canary','missing','empty-scope','read-committed','superuser','maintainer'])
def test_unqualified_call_rejected(locked_db,kind):
    kwargs={}
    if kind=='canary':kwargs['scope']=('org-canary','project-a')
    if kind=='empty-scope':kwargs['scope']=('','')
    if kind=='read-committed':kwargs['serializable']=False
    if kind=='superuser':kwargs['privileged']=True
    if kind=='maintainer':kwargs['role']='aos_extension_maintainer'
    with runtime(locked_db,**kwargs) as conn:
        with pytest.raises(psycopg.Error):read(conn,locked_db,str(uuid4()) if kind=='missing' else None)


@pytest.mark.parametrize('kind',['partial','extra','unknown'])
def test_group_must_be_exactly_nine_known_operations(locked_db,kind):
    case=locked_db
    if kind=='partial':case.db.owner.execute('DELETE FROM extension_operation_dispatch_binding WHERE operation_id=%s',(ECOMMERCE_GROWTH_OPERATIONS[0],))
    elif kind=='unknown':case.db.owner.execute("UPDATE extension_operation_dispatch_binding SET operation_id='unknown_operation' WHERE operation_id=%s",(ECOMMERCE_GROWTH_OPERATIONS[0],))
    else:
        case.db.owner.execute('''INSERT INTO extension_operation_dispatch_binding(org_id,project_id,operation_id,handler_kind,operation_fence,revision,cutover_group_id,cutover_group_revision,updated_by)
            VALUES('org-a','project-a','unknown_operation','legacy',true,1,%s,1,'fixture')''',(case.request['groupId'],))
    with runtime(case) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):read(conn,case)


def test_other_writer_blocked_until_lock_transaction_finishes(locked_db):
    case=locked_db
    with runtime(case) as conn:
        read(conn,case)
        with pytest.raises(psycopg.errors.LockNotAvailable):
            with case.db.owner.transaction():
                case.db.owner.execute("SET LOCAL lock_timeout='150ms'")
                case.db.owner.execute('UPDATE extension_operation_dispatch_binding SET revision=revision+1 WHERE operation_id=%s',(ECOMMERCE_GROWTH_OPERATIONS[0],))
    with case.db.owner.transaction():
        case.db.owner.execute("SET LOCAL lock_timeout='1s'")
        case.db.owner.execute('UPDATE extension_operation_dispatch_binding SET revision=revision+1 WHERE operation_id=%s',(ECOMMERCE_GROWTH_OPERATIONS[0],))


def test_rollback_releases_group_locks(locked_db):
    case=locked_db
    with pytest.raises(RuntimeError,match='fixture rollback'):
        with runtime(case) as conn:
            read(conn,case)
            raise RuntimeError('fixture rollback')
    with case.db.owner.transaction():
        case.db.owner.execute("SET LOCAL lock_timeout='1s'")
        case.db.owner.execute('UPDATE extension_operation_dispatch_binding SET revision=revision+1 WHERE operation_id=%s',(ECOMMERCE_GROWTH_OPERATIONS[0],))
