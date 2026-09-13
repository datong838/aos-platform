"""Evidence of historical default-ACL inheritance and the row-lock dependency."""
import importlib.util
from types import SimpleNamespace

import psycopg

from test_investigation_description_store_pg import database, pytestmark, ROOT


def test_historical_dispatch_ddl_inherits_dml_and_direct_lock_needs_update(database):
    owner=database.owner
    owner.execute('CREATE TABLE extension_runtime_binding(org_id text,project_id text,installation_id uuid,generation uuid,PRIMARY KEY(org_id,project_id,installation_id,generation))')
    owner.execute('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO aos_runtime')
    path=ROOT/'alembic/versions/ar2_001_ecommerce_dispatch_authority.py'
    spec=importlib.util.spec_from_file_location('historical_dispatch_acl',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=owner.execute);migration.upgrade()
    privileges=owner.execute("""SELECT has_table_privilege('aos_runtime','extension_operation_dispatch_binding','SELECT') AS read,
        has_table_privilege('aos_runtime','extension_operation_dispatch_binding','INSERT') AS insert,
        has_table_privilege('aos_runtime','extension_operation_dispatch_binding','UPDATE') AS update,
        has_table_privilege('aos_runtime','extension_operation_dispatch_binding','DELETE') AS delete""").fetchone()
    assert all(privileges.values())
    owner.execute('REVOKE INSERT,UPDATE,DELETE ON extension_operation_dispatch_binding FROM aos_runtime')
    owner.execute('SET ROLE aos_runtime')
    try:
        assert owner.execute('SELECT * FROM extension_operation_dispatch_binding WHERE false').fetchall()==[]
        import pytest
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            owner.execute('SELECT * FROM extension_operation_dispatch_binding WHERE false FOR UPDATE')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            owner.execute('UPDATE extension_operation_dispatch_binding SET operation_fence=false WHERE false')
    finally:
        owner.execute('RESET ROLE')
