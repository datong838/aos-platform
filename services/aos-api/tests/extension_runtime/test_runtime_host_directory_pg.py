"""Real role/CAS checks in a disposable database on the isolated AR1 cluster."""
import asyncio
import importlib.util
import os
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import uuid

import psycopg
from psycopg import sql
import pytest

from aos_api.extension_runtime.runtime_identity import (
    RuntimeDatabaseIdentity,
    probe_runtime_database_identity,
    require_isolated_runtime_identities,
)
from aos_api.extension_runtime.generation_attempts import (
    GenerationDrainReader,
    PostgresRuntimeAttemptStore,
)
from aos_api.extension_runtime.oci_driver import CleanupOnlyOciDriver, OciDriver
from aos_api.extension_runtime.production_runtime import (
    RuntimeWorkerDependencies,
    select_production_runtime_host,
)
from aos_api.extension_runtime.current_permission import CurrentControlPermission
from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.aip_runtime_configuration_sources import (
    build_current_configuration_authorization,
)
from aos_api.extension_runtime.configuration_authorization import (
    CurrentConfigurationPermission,
)
from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent

pytestmark = pytest.mark.skipif(
    os.getenv("AOS_EXTENSION_PG_TEST") != "1", reason="dedicated database opt-in required"
)


@pytest.fixture
def directory_database():
    suffix = uuid.uuid4().hex[:12]
    database = "ar1_directory_" + suffix
    first_role = "aos_ext_host_" + suffix
    second_role = "aos_ext_other_" + suffix
    password = "isolated-" + suffix
    admin_dsn = "postgresql://postgres@127.0.0.1:18432/postgres"
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        if admin.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'").fetchone() is None:
            admin.execute("CREATE ROLE aos_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS")
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
            sql.Identifier(first_role), sql.Literal(password)
        ))
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
            sql.Identifier(second_role), sql.Literal(password)
        ))
    database_dsn = f"postgresql://postgres@127.0.0.1:18432/{database}"
    try:
        with psycopg.connect(database_dsn, autocommit=True) as conn:
            conn.execute("CREATE TABLE twa_workspace(org_id text,project_id text,name text,PRIMARY KEY(org_id,project_id))")
            conn.execute("CREATE TABLE bundle_installation(org_id text,project_id text,installation_id uuid,etag_version bigint NOT NULL DEFAULT 1,PRIMARY KEY(org_id,project_id,installation_id))")
            # Reproduce the exact TI6 adoption marker used by production tenant
            # transactions without importing unrelated application tables.
            conn.execute("CREATE TABLE bundle_composition(org_id text,project_id text)")
            conn.execute("ALTER TABLE bundle_composition ENABLE ROW LEVEL SECURITY")
            conn.execute(
                """CREATE POLICY tenant_scope_bundle_composition_ti6
                       ON bundle_composition
                    USING (org_id=current_setting('aos.org_id',true)
                       AND project_id=current_setting('aos.project_id',true))"""
            )
            conn.execute("INSERT INTO twa_workspace VALUES"
                         "('org-org','dev-project','isolated'),"
                         "('other-org','other-project','other'),"
                         "('a','b/c','slash-one'),('a/b','c','slash-two')")
            for revision in (
                "ar1_001_extension_runtime_authority.py",
                "ar1_003_runtime_host_directory.py",
                "ar1_004_runtime_execution_attempt.py",
            ):
                path = Path(__file__).resolve().parents[2] / "alembic/versions" / revision
                spec = importlib.util.spec_from_file_location("test_" + revision, path)
                migration = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration)
                migration.op = SimpleNamespace(execute=conn.execute)
                migration.upgrade()
            conn.execute(sql.SQL("GRANT aos_extension_directory TO {},{}").format(
                sql.Identifier(first_role), sql.Identifier(second_role)
            ))
        yield database_dsn, first_role, second_role, password
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s", (database,))
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(first_role)))
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(second_role)))


def _hash(char):
    return "sha256:" + char * 64


def _bind(conn, role, host, expected, key, digest, *, enabled=True):
    return conn.execute(
        "SELECT extension_runtime_bind_host_identity(%s,%s,%s,%s,'maintainer',%s,%s)",
        (role, host, enabled, expected, key, digest),
    ).fetchone()[0]


def _assign(conn, org, project, host, state, expected, key, digest):
    return conn.execute(
        "SELECT extension_runtime_set_host_assignment(%s,%s,%s,%s,%s,'maintainer',%s,%s)",
        (org, project, host, state, expected, key, digest),
    ).fetchone()[0]


def test_directory_is_empty_by_default_and_database_binds_each_session_host(directory_database):
    dsn, first_role, second_role, password = directory_database
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert _bind(admin, first_role, "host-one", 0, "bind-one", _hash("a")) == 1
        assert _bind(admin, second_role, "host-two", 0, "bind-two", _hash("b")) == 1
    for role in (first_role, second_role):
        with psycopg.connect(dsn.replace("postgres@", f"{role}:{password}@")) as conn:
            conn.read_only = True
            assert conn.execute("SELECT * FROM extension_runtime_read_host_assignments()").fetchall() == []
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SELECT * FROM extension_runtime_host_assignment")
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert _assign(admin, "org-org", "dev-project", "host-one", "assigned", 0, "assign-one", _hash("c")) == 1
        assert _assign(admin, "other-org", "other-project", "host-two", "assigned", 0, "assign-two", _hash("d")) == 1
    with psycopg.connect(dsn.replace("postgres@", f"{first_role}:{password}@")) as conn:
        conn.read_only = True
        assert conn.execute("SELECT * FROM extension_runtime_read_host_assignments()").fetchall() == [("org-org", "dev-project", 1)]
    with psycopg.connect(dsn.replace("postgres@", f"{second_role}:{password}@")) as conn:
        conn.read_only = True
        assert conn.execute("SELECT * FROM extension_runtime_read_host_assignments()").fetchall() == [("other-org", "other-project", 1)]


def test_assignment_commands_are_monotonic_idempotent_and_append_only(directory_database):
    dsn, first_role, second_role, _ = directory_database
    with psycopg.connect(dsn, autocommit=True) as conn:
        _bind(conn, first_role, "host-one", 0, "bind-one", _hash("a"))
        _bind(conn, second_role, "host-two", 0, "bind-two", _hash("b"))
        assert _assign(conn, "org-org", "dev-project", "host-one", "assigned", 0, "assign", _hash("c")) == 1
        assert _assign(conn, "org-org", "dev-project", "host-one", "assigned", 99, "assign", _hash("c")) == 1
        with pytest.raises(psycopg.errors.RaiseException, match="idempotency conflict"):
            _assign(conn, "org-org", "dev-project", "host-one", "assigned", 1, "assign", _hash("d"))
        with pytest.raises(psycopg.errors.RaiseException, match="revision conflict"):
            _assign(conn, "org-org", "dev-project", "host-two", "assigned", 0, "transfer-old", _hash("e"))
        assert _assign(conn, "org-org", "dev-project", "host-two", "assigned", 1, "transfer", _hash("f")) == 2
        assert _assign(conn, "org-org", "dev-project", None, "revoked", 2, "revoke", _hash("0")) == 3
        assert conn.execute("SELECT revision,state,host_id FROM extension_runtime_host_assignment").fetchone() == (3, "revoked", None)
        assert conn.execute("SELECT revision FROM extension_runtime_host_assignment_revision ORDER BY revision").fetchall() == [(1,), (2,), (3,)]
        for statement in (
            "UPDATE extension_runtime_host_assignment_revision SET actor=actor",
            "DELETE FROM extension_runtime_host_command_receipt",
            "TRUNCATE extension_runtime_host_identity_revision",
        ):
            with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
                conn.execute(statement)


def test_directory_login_cannot_write_or_call_maintenance_commands(directory_database):
    dsn, first_role, _, password = directory_database
    with psycopg.connect(dsn, autocommit=True) as admin:
        _bind(admin, first_role, "host-one", 0, "bind", _hash("a"))
    with psycopg.connect(dsn.replace("postgres@", f"{first_role}:{password}@")) as conn:
        with pytest.raises(psycopg.errors.RaiseException, match="read-only"):
            conn.execute("SELECT * FROM extension_runtime_read_host_assignments()")
        conn.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "SELECT extension_runtime_set_host_assignment('org-org','dev-project','host-one','assigned',0,'x','x',%s)",
                (_hash("a"),),
            )


def test_concurrent_cross_host_assignment_has_one_cas_winner(directory_database):
    dsn, first_role, second_role, _ = directory_database
    with psycopg.connect(dsn, autocommit=True) as admin:
        _bind(admin, first_role, "host-one", 0, "bind-one", _hash("a"))
        _bind(admin, second_role, "host-two", 0, "bind-two", _hash("b"))

    def assign(host, key, digest):
        try:
            with psycopg.connect(dsn, autocommit=True) as conn:
                return _assign(conn, "org-org", "dev-project", host, "assigned", 0, key, digest)
        except psycopg.errors.RaiseException as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(lambda args: assign(*args), (
            ("host-one", "race-one", _hash("c")),
            ("host-two", "race-two", _hash("d")),
        )))
    assert results.count(1) == 1
    assert sum("revision conflict" in str(value) for value in results) == 1
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert admin.execute("SELECT count(*) FROM extension_runtime_host_assignment").fetchone() == (1,)
        assert admin.execute("SELECT count(*) FROM extension_runtime_host_assignment_revision").fetchone() == (1,)


def test_scope_command_identity_is_unambiguous_when_parts_contain_slashes(directory_database):
    dsn, first_role, _, _ = directory_database
    with psycopg.connect(dsn, autocommit=True) as conn:
        _bind(conn, first_role, "host-one", 0, "bind", _hash("a"))
        assert _assign(conn, "a", "b/c", "host-one", "assigned", 0, "same-key", _hash("b")) == 1
        assert _assign(conn, "a/b", "c", "host-one", "assigned", 0, "same-key", _hash("c")) == 1
        assert conn.execute("SELECT org_id,project_id FROM extension_runtime_host_assignment ORDER BY 1,2").fetchall() == [("a", "b/c"), ("a/b", "c")]


def test_recreated_same_name_database_role_does_not_inherit_old_host_identity(directory_database):
    dsn, first_role, _, password = directory_database
    with psycopg.connect(dsn, autocommit=True) as conn:
        _bind(conn, first_role, "host-one", 0, "bind", _hash("a"))
        _assign(conn, "org-org", "dev-project", "host-one", "assigned", 0, "assign", _hash("b"))
        old_oid = conn.execute("SELECT database_role_oid FROM extension_runtime_host_identity WHERE database_role=%s", (first_role,)).fetchone()[0]
    admin_dsn = "postgresql://postgres@127.0.0.1:18432/postgres"
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(first_role)))
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
            sql.Identifier(first_role), sql.Literal(password)
        ))
        admin.execute(sql.SQL("GRANT aos_extension_directory TO {}").format(sql.Identifier(first_role)))
        new_oid = admin.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (first_role,)).fetchone()[0]
    assert new_oid != old_oid
    with psycopg.connect(dsn.replace("postgres@", f"{first_role}:{password}@")) as conn:
        conn.read_only = True
        with pytest.raises(psycopg.errors.NoDataFound):
            conn.execute("SELECT * FROM extension_runtime_read_host_assignments()")


def test_database_observation_rejects_two_dsn_spellings_for_the_same_principal(directory_database):
    dsn, first_role, _, password = directory_database
    role_dsn = dsn.replace("postgres@", f"{first_role}:{password}@")
    with psycopg.connect(role_dsn + "?application_name=directory") as first:
        observed_directory = probe_runtime_database_identity(
            first, protected_relations=("extension_runtime_host_assignment",),
        )
    with psycopg.connect(role_dsn + "?application_name=runtime") as second:
        observed_runtime = probe_runtime_database_identity(
            second, protected_relations=("extension_runtime_host_assignment",),
        )
    assert observed_directory.session_user == observed_runtime.session_user == first_role
    assert observed_directory.role_oid == observed_runtime.role_oid
    observed_web = RuntimeDatabaseIdentity(
        authority=observed_directory.authority,
        session_user="isolated-web",
        role_oid=observed_directory.role_oid + 100000,
        directory_member=False,
        runtime_member=False,
        privileged=False,
        owns_protected_relation=False,
    )
    with pytest.raises(RuntimeError, match="principals must differ"):
        require_isolated_runtime_identities(
            directory=observed_directory,
            runtime=observed_runtime,
            web=observed_web,
        )


def test_null_expected_revision_cannot_bypass_identity_or_assignment_cas(directory_database):
    dsn, first_role, _, _ = directory_database
    with psycopg.connect(dsn, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.RaiseException, match="invalid runtime host identity"):
            _bind(conn, first_role, "host-one", None, "null-bind", _hash("a"))
        assert conn.execute("SELECT count(*) FROM extension_runtime_host_identity").fetchone() == (0,)
        _bind(conn, first_role, "host-one", 0, "bind", _hash("b"))
        with pytest.raises(psycopg.errors.RaiseException, match="invalid runtime host assignment"):
            _assign(conn, "org-org", "dev-project", "host-one", "assigned", None, "null-assign", _hash("c"))
        assert conn.execute("SELECT count(*) FROM extension_runtime_host_assignment").fetchone() == (0,)


def test_owner_probe_is_fixed_to_public_schema_not_session_search_path(directory_database):
    dsn, first_role, _, password = directory_database
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("ALTER TABLE extension_runtime_host_assignment OWNER TO {}").format(
            sql.Identifier(first_role)
        ))
    role_dsn = dsn.replace("postgres@", f"{first_role}:{password}@")
    with psycopg.connect(role_dsn, options="-c search_path=pg_catalog") as conn:
        observed = probe_runtime_database_identity(
            conn, protected_relations=("extension_runtime_host_assignment",),
        )
    assert observed.owns_protected_relation is True


def test_revoked_directory_role_cannot_receive_assignment_but_identity_can_be_disabled(directory_database):
    dsn, first_role, _, _ = directory_database
    with psycopg.connect(dsn, autocommit=True) as conn:
        assert _bind(conn, first_role, "host-one", 0, "bind", _hash("a")) == 1
        old_oid = conn.execute(
            "SELECT database_role_oid FROM extension_runtime_host_identity "
            "WHERE database_role=%s", (first_role,),
        ).fetchone()[0]
        conn.execute(sql.SQL("REVOKE aos_extension_directory FROM {}").format(
            sql.Identifier(first_role)
        ))
        with pytest.raises(psycopg.errors.RaiseException, match="identity unavailable"):
            _assign(
                conn, "org-org", "dev-project", "host-one", "assigned", 0,
                "stale-role", _hash("b"),
            )
        assert _bind(
            conn, first_role, "host-one", 1, "disable", _hash("c"), enabled=False,
        ) == 2
        assert conn.execute(
            "SELECT enabled,database_role_oid,host_id,revision "
            "FROM extension_runtime_host_identity WHERE database_role=%s",
            (first_role,),
        ).fetchone() == (False, old_oid, "host-one", 2)


def test_production_selector_uses_real_directory_roles_and_runtime_drain(directory_database):
    dsn, directory_role, _, password = directory_database
    suffix = uuid.uuid4().hex[:12]
    runtime_role = "aos_ext_runtime_" + suffix
    web_role = "aos_ext_web_" + suffix
    installation = uuid.uuid4()
    generation = uuid.uuid4()
    admin_dsn = "postgresql://postgres@127.0.0.1:18432/postgres"
    with psycopg.connect(admin_dsn, autocommit=True) as cluster:
        for role in (runtime_role, web_role):
            cluster.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
        cluster.execute(sql.SQL("GRANT aos_runtime TO {}").format(sql.Identifier(runtime_role)))
    try:
        with psycopg.connect(dsn, autocommit=True) as admin:
            _bind(admin, directory_role, "host-one", 0, "bind-production", _hash("7"))
            _assign(
                admin, "org-org", "dev-project", "host-one", "assigned", 0,
                "assign-production", _hash("8"),
            )
            admin.execute(
                "INSERT INTO bundle_installation VALUES('org-org','dev-project',%s,1)",
                (installation,),
            )
            admin.execute(
                """INSERT INTO extension_runtime_binding
                   (org_id,project_id,installation_id,generation,installation_revision,
                    package_lock_ref,profile_ref,config_ref,desired_state,observed_state,
                    enabled,operation_fence,execution_epoch)
                   VALUES('org-org','dev-project',%s,%s,1,'{}','test','{}',
                          'enabled','ready',true,false,1)""",
                (installation, generation),
            )

        from psycopg.rows import dict_row

        @contextmanager
        def directory_connect():
            role_dsn = dsn.replace("postgres@", f"{directory_role}:{password}@")
            with psycopg.connect(role_dsn, row_factory=dict_row) as conn:
                conn.read_only = True
                yield conn

        @contextmanager
        def runtime_connect():
            role_dsn = dsn.replace("postgres@", f"{runtime_role}:{password}@")
            with psycopg.connect(role_dsn, row_factory=dict_row) as conn:
                yield conn

        @contextmanager
        def web_connect():
            role_dsn = dsn.replace("postgres@", f"{web_role}:{password}@")
            with psycopg.connect(role_dsn, row_factory=dict_row) as conn:
                yield conn

        selected = select_production_runtime_host(
            enabled=True,
            directory_connect=directory_connect,
            runtime_connect=runtime_connect,
            web_connect=web_connect,
            dependencies=RuntimeWorkerDependencies(
                installation_store=PostgresInstallationStore(),
                configuration_authorize=build_current_configuration_authorization(
                    permission=CurrentConfigurationPermission(
                        installation_store=PostgresInstallationStore()
                    )
                ),
                disable_permission=CurrentControlPermission(
                    operation=DISABLE_RUNTIME_OPERATION
                ),
                drain_reader=GenerationDrainReader(),
                cleanup_driver=CleanupOnlyOciDriver(
                    OciDriver(context="colima-aos-extension")
                ),
                disable_dependent=EcommerceGrowthDisableDependent(),
            ),
        )
        assert selected.status == "ACTIVE"
        with runtime_connect() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute(
                    "SELECT set_config('aos.org_id','org-org',true),"
                    "set_config('aos.project_id','dev-project',true)"
                )
                attempt = PostgresRuntimeAttemptStore().begin(
                    conn,
                    org_id="org-org",
                    project_id="dev-project",
                    installation_id=installation,
                    generation=generation,
                    execution_epoch=1,
                    operation_kind="signed_read",
                    operation_key="products.read",
                    idempotency_key="selector-host-recovery",
                    request_hash=_hash("9"),
                    owner_token="selector-owner-" + "x" * 32,
                    lease_until=datetime.now(timezone.utc)
                    + timedelta(milliseconds=120),
                )
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(
                """UPDATE extension_runtime_binding
                      SET desired_state='disabled',observed_state='draining',
                          enabled=false,operation_fence=true,execution_epoch=2,
                          revision=revision+1
                    WHERE org_id='org-org' AND project_id='dev-project'
                      AND installation_id=%s AND generation=%s""",
                (installation, generation),
            )
            admin.execute("SELECT pg_sleep(.15)")

        tick = asyncio.run(selected.host.run_once())
        assert tick.tenants[0].recovered_attempts == (attempt.attempt_id,)
        with runtime_connect() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute(
                    "SELECT set_config('aos.org_id','org-org',true),"
                    "set_config('aos.project_id','dev-project',true)"
                )
                assert GenerationDrainReader()(
                    conn,
                    org_id="org-org",
                    project_id="dev-project",
                    installation_id=installation,
                    generation=generation,
                    fence_epoch=2,
                ) is True
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as cluster:
            cluster.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(runtime_role)))
            cluster.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(web_role)))
