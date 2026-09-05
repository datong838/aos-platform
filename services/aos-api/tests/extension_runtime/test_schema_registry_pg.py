from concurrent.futures import ThreadPoolExecutor
import threading
import psycopg
from psycopg import sql
import pytest
from test_lifecycle_pg import database,pytestmark


def test_schema_same_version_is_applied_once_across_connections(database):
    from aos_api.extension_runtime.schema_registry import SchemaRequirement,apply_once,require_installed
    conn,role,schema=database
    conn.execute(sql.SQL("GRANT CREATE ON SCHEMA {} TO {}").format(sql.Identifier(schema),sql.Identifier(role)))
    requirement=SchemaRequirement("example","1","sha256:"+"a"*64)
    barrier=threading.Barrier(2)
    calls=[]
    def run():
        with psycopg.connect(host="127.0.0.1",port=18432,user="postgres",dbname="postgres",autocommit=True) as other:
            other.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            other.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
            barrier.wait(timeout=5)
            with other.transaction():
                def migration(db):
                    calls.append(1)
                    db.execute("CREATE TABLE example_new_data(id bigint)")
                return apply_once(other,requirement,migration)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(run) for _ in range(2)]
        assert sorted(f.result(timeout=10) for f in futures)==[False,True]
    assert calls==[1]
    with conn.transaction():require_installed(conn,[requirement])
    assert conn.execute("SELECT count(*) FROM extension_schema_installation").fetchone()[0]==1


def test_schema_conflict_missing_and_callback_failure_rollback(database):
    from aos_api.extension_runtime.schema_registry import SchemaRequirement,apply_once,require_installed
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    conn,_,_=database
    requirement=SchemaRequirement("example","1","sha256:"+"a"*64)
    with pytest.raises(LookupError):
        with conn.transaction():require_installed(conn,[requirement])
    def bad(db):
        db.execute("CREATE TABLE partial_migration(id bigint)")
        raise ValueError("test migration failed")
    with pytest.raises(ValueError):
        with conn.transaction():apply_once(conn,requirement,bad)
    assert conn.execute("SELECT to_regclass('partial_migration')").fetchone()[0] is None
    assert conn.execute("SELECT count(*) FROM extension_schema_installation").fetchone()[0]==0
    with conn.transaction():assert apply_once(conn,requirement,lambda db:None)
    conflict=SchemaRequirement("example","1","sha256:"+"b"*64)
    with pytest.raises(RuntimeConflict):
        with conn.transaction():apply_once(conn,conflict,lambda db:pytest.fail("no DDL on conflict"))
    with pytest.raises(RuntimeConflict):
        with conn.transaction():require_installed(conn,[conflict])


def test_runtime_role_can_read_but_not_apply_schema(database):
    from aos_api.extension_runtime.schema_registry import SchemaRequirement,apply_once,require_installed
    conn,_,schema=database
    requirement=SchemaRequirement("example","1","sha256:"+"a"*64)
    with conn.transaction():apply_once(conn,requirement,lambda db:None)
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))
    conn.execute("SET ROLE aos_runtime")
    with conn.transaction():require_installed(conn,[requirement])
    with pytest.raises(PermissionError):
        with conn.transaction():apply_once(conn,requirement,lambda db:pytest.fail("runtime must not execute migration"))


def test_schema_rejects_async_callback_without_applied_receipt(database):
    from aos_api.extension_runtime.schema_registry import SchemaRequirement,apply_once
    conn,_,_=database
    async def not_executed(db):
        raise AssertionError("must not dispatch async migrations")
    with pytest.raises(ValueError):
        with conn.transaction():apply_once(conn,SchemaRequirement("example","1","sha256:"+"a"*64),not_executed)
    assert conn.execute("SELECT count(*) FROM extension_schema_installation").fetchone()[0]==0
