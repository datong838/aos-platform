"""Reader probes use only the dedicated ephemeral database fixture."""
import uuid
import psycopg
from psycopg import sql
import pytest
from test_lifecycle_pg import database, pytestmark
import hashlib


def test_reader_real_tenant_bounds_and_parameter_injection(database, monkeypatch):
    from aos_api.extension_runtime.storage_ports import read_registered_rows, StorageRoleDenied
    admin, _, schema = database
    role="ar1c_"+uuid.uuid4().hex
    admin.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS").format(sql.Identifier(role)))
    try:
        admin.execute("CREATE TABLE products(org_id text,project_id text,id bigint,name text)")
        admin.execute("INSERT INTO products VALUES('org-org','dev-project',1,'栖月汇商品'),('dev-org','dev-project',2,'隔离记录')")
        admin.execute("ALTER TABLE products ENABLE ROW LEVEL SECURITY")
        admin.execute("ALTER TABLE products FORCE ROW LEVEL SECURITY")
        admin.execute("CREATE POLICY tenant ON products USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))")
        admin.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(schema),sql.Identifier(role)))
        admin.execute(sql.SQL("GRANT SELECT ON products TO {}").format(sql.Identifier(role)))
        from test_admission import fixture as signed_release
        from aos_api.extension_runtime.admission import admit_query_registry
        def signed_sql(files):
            files["artifacts/product-query.sql"]=f"SELECT name FROM {schema}.products WHERE id >= $1".encode()
        release,_=signed_release(signed_sql,namespace=schema)
        definition=admit_query_registry(**{k:v for k,v in release.items() if k not in {"platform","driver"}})[0]
        args=dict(raw=definition.raw,expected_hash=definition.expected_hash,
                  table=definition.table,column_types=dict(definition.column_types),
                  parameter=1,org_id="org-org",project_id="dev-project")
        with pytest.raises(StorageRoleDenied):
            read_registered_rows(admin,**args)
        with psycopg.connect(host="127.0.0.1",port=18432,user=role,dbname="postgres",autocommit=True) as conn:
            import aos_api.extension_runtime.storage_ports as ports
            original_guard=ports.require_runtime_role
            def concurrent_ddl_guard(*args, **kwargs):
                admin.execute("SET lock_timeout='100ms'")
                try:
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        admin.execute("ALTER TABLE products DISABLE ROW LEVEL SECURITY")
                finally:
                    admin.execute("RESET lock_timeout")
                return original_guard(*args,**kwargs)
            with monkeypatch.context() as patch:
                patch.setattr(ports,"require_runtime_role",concurrent_ddl_guard)
                assert read_registered_rows(conn,**args)==(("栖月汇商品",),)
            with conn.transaction():
                conn.execute("SELECT 1")
                with pytest.raises(StorageRoleDenied):
                    read_registered_rows(conn,**args)
            text_raw=f"SELECT name FROM {schema}.products WHERE name = $1".encode()
            assert read_registered_rows(conn,**{**args,"raw":text_raw,
                "expected_hash":"sha256:"+hashlib.sha256(text_raw).hexdigest(),
                "parameter":"' OR 1=1 --"})==()
            with pytest.raises(ValueError):
                read_registered_rows(conn,**{**args,"parameter":"1 OR 1=1"})
            assert conn.execute("SELECT current_setting('aos.org_id',true)").fetchone()[0] in (None, "")
            admin.execute("INSERT INTO products VALUES('org-org','dev-project',3,'另一个商品')")
            with pytest.raises(ValueError):
                read_registered_rows(conn,**args,limit=1)
            admin.execute("UPDATE products SET name=repeat('长',2000) WHERE id=3")
            with pytest.raises(ValueError):
                read_registered_rows(conn,**args)
            admin.execute("UPDATE products SET name='正常' WHERE id=3")
            admin.execute("INSERT INTO products SELECT 'org-org','dev-project',g,repeat('x',4096) FROM generate_series(10,270) g")
            with pytest.raises(ValueError,match="registry limit"):
                read_registered_rows(conn,**args,limit=500)
            import aos_api.extension_runtime.storage_ports as ports
            ticks=iter([0.0,11.0,12.0,13.0])
            with monkeypatch.context() as patch:
                patch.setattr(ports,"monotonic",lambda:next(ticks),raising=False)
                with pytest.raises(TimeoutError):
                    read_registered_rows(conn,**args,limit=500)
            assert conn.execute("SELECT current_setting('aos.org_id',true)").fetchone()[0] in (None, "")
    finally:
        admin.execute(sql.SQL("REVOKE ALL ON products FROM {}").format(sql.Identifier(role)))
        admin.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM {}").format(sql.Identifier(schema),sql.Identifier(role)))
        admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
