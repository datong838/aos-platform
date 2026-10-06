"""Registry physical isolation; complete anchored registration is a later gate."""
from tests.aip.test_provider_capacity_request_pg import original_inputs
from tests.aip.test_provider_capacity_formal_boundary_pg import isolated_owner


def test_publication_registry_default_empty_private(original_inputs):
    from aos_api.aip_provider_capacity_publication_registry import OWNER, PUBLISHER, SCHEMA, TABLES
    with isolated_owner() as conn:
        schema = conn.execute('SELECT nspowner=%s::regrole AS owner FROM pg_namespace WHERE nspname=%s',
            (OWNER, SCHEMA)).fetchone()
        assert schema == dict(owner=True)
        for name in TABLES:
            assert conn.execute('SELECT count(*) AS n FROM '+SCHEMA+'.'+name).fetchone()['n'] == 0


import hashlib
import psycopg
import pytest
from aos_api.aip_provider_capacity_publication_registry import OWNER, PUBLISHER, SCHEMA, TABLES, reserved_role_sql


@pytest.mark.parametrize('role',[PUBLISHER,'aos_runtime','aos_provider_capacity_issuer'])
def test_existing_callers_cannot_read_write_or_parse_registry(role):
    with isolated_owner() as conn:
        for statement in (f'SELECT * FROM {SCHEMA}.root_snapshot',
                          f'DELETE FROM {SCHEMA}.registry_epoch',
                          f"SELECT {SCHEMA}.read_root_identifier_literal('\"a\"')"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction():
                    conn.execute('SET LOCAL ROLE '+role)
                    conn.execute(statement)


def test_registry_catalog_has_no_login_bypass_or_public_writer():
    with isolated_owner() as conn:
        for role in (OWNER,PUBLISHER):
            r=conn.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(role,)).fetchone()
            assert r and not any(r.values())
        rows=conn.execute('SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,c.relowner=%s::regrole AS owner FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind=%s',(OWNER,SCHEMA,'r')).fetchall()
        assert {r['relname'] for r in rows}==set(TABLES)
        assert all(r['relrowsecurity'] and r['relforcerowsecurity'] and r['owner'] for r in rows)
        assert conn.execute('SELECT count(*) AS n FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname=%s AND c.contype=%s AND (c.condeferrable OR c.condeferred)',(SCHEMA,'f')).fetchone()['n']==0


def test_owner_scope_and_immutable_snapshot():
    raw=b'{"trustRoots":[]}'
    digest='sha256:'+hashlib.sha256(raw).hexdigest()
    with isolated_owner() as conn:
        # Savepoint rollback leaves the registry empty; administrative fixture is not trusted initialization.
        try:
            with conn.transaction():
                conn.execute('SET LOCAL ROLE '+OWNER)
                conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
                conn.execute(f'INSERT INTO {SCHEMA}.root_snapshot VALUES(%s,%s,%s,%s,0)',('org-org','dev-project',digest,raw))
                for operation in ('UPDATE '+SCHEMA+'.root_snapshot SET root_count=0','DELETE FROM '+SCHEMA+'.root_snapshot'):
                    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='CAPACITY_PUBLICATION_IMMUTABLE'):
                        with conn.transaction():conn.execute(operation)
                conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
                assert conn.execute(f'SELECT count(*) AS n FROM {SCHEMA}.root_snapshot').fetchone()['n']==0
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with conn.transaction():
                        conn.execute(f'INSERT INTO {SCHEMA}.root_snapshot VALUES(%s,%s,%s,%s,0)',('org-org','dev-project',digest,raw))
                raise _RollbackFixture()
        except _RollbackFixture:pass


class _RollbackFixture(Exception):pass


@pytest.mark.parametrize('flag',['LOGIN','INHERIT','BYPASSRLS'])
def test_reserved_publisher_drift_is_rejected_without_repair(flag):
    with isolated_owner() as conn:
        try:
            with conn.transaction():
                conn.execute('ALTER ROLE '+PUBLISHER+' '+flag)
                with pytest.raises(psycopg.errors.InsufficientPrivilege,match='CAPACITY_PUBLICATION_RESERVED_ROLE_DRIFT'):
                    with conn.transaction():conn.execute(reserved_role_sql(PUBLISHER))
                raise _RollbackFixture()
        except _RollbackFixture:pass


def test_snapshot_digest_and_origin_parent_links_are_enforced():
    with isolated_owner() as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.transaction():
                conn.execute(f'INSERT INTO {SCHEMA}.root_snapshot VALUES(%s,%s,%s,%s,0)',
                    ('org-org','dev-project','sha256:'+'0'*64,b'{"trustRoots":[]}'))
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with conn.transaction():
                raw=b'test-only-untrusted-origin'
                conn.execute(f'INSERT INTO {SCHEMA}.origin VALUES(%s,%s,%s,%s,%s,%s,%s)',
                    ('org-org','dev-project',hashlib.sha256(raw).hexdigest(),raw,b'x'*64,'sha256:'+'1'*64,'sha256:'+'2'*64))
