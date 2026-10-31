"""Native a0v166 migration diagnostic; never provisions or selects a database.

Collection is offline. Execution requires a separately authorized new PG lab.
This slice does not establish the two-installation lifecycle or M2 acceptance.
"""
from dataclasses import dataclass
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import psycopg
from psycopg.rows import dict_row
import pytest
from sqlalchemy.engine import Connection


NATIVE_MIGRATION = pytest.StashKey[object]()
NATIVE_OWNER = pytest.StashKey[object]()
MIGRATION = (Path(__file__).resolve().parents[2] / "alembic" / "versions"
             / "a0v_166_dispatch_refresh_activation_chain.py")
DATABASE = "aos_refresh_activation_native"
ROLE = "aos_refresh_activation_native_migrator"
OWNER_SOURCES = (
    "ecommerce_dispatch_configuration_owner.py",
    "ecommerce_dispatch_configuration_contracts.py",
    "ecommerce_dispatch_configuration_receipt.py",
    "ecommerce_growth_cutover.py",
    "ecommerce_growth_cutover_current_approval.py",
)


@dataclass(frozen=True, repr=False)
class NativeRefreshScenario:
    old_command: dict
    old_actor: str
    new_command: dict
    new_actor: str
    owner_source_hashes: dict


@dataclass(frozen=True, repr=False)
class NativeMigrationBinding:
    connection: Connection
    database_oid: int
    migration_sha256: str
    scenario: NativeRefreshScenario | None = None
    cluster_name: str | None = None
    administrator_role: str = "postgres"


@dataclass(frozen=True, repr=False)
class NativeOwnerBinding:
    connection: Connection
    database_oid: int
    migration_sha256: str
    scenario: NativeRefreshScenario | None = None
    cluster_name: str | None = None


def require(value, message):
    if not value:
        raise AssertionError(message)


def query(conn, statement):
    try:
        return conn.exec_driver_sql(statement).mappings()
    except Exception:
        # No native row, SQL parameter or driver diagnostic in test output.
        raise AssertionError("native migration query failed") from None


def history(conn):
    rows = query(conn, """SELECT row_to_json(r)::text AS value
        FROM public.extension_dispatch_configuration_refresh_receipt r
        ORDER BY org_id,project_id,cutover_group_id,activation_operation_id,revision
        LIMIT 8193""").all()
    require(2 <= len(rows) <= 8192, "bounded nonempty original refresh history required")
    require(sum(len(row["value"].encode("utf-8")) for row in rows) <= 8388608,
            "visible original refresh history exceeds diagnostic byte budget")
    return tuple(row["value"] for row in rows)


def require_native_identity(identity, binding, *, deployment):
    if deployment:
        expected_role = binding.administrator_role
        lab_prefix = (
            {"postgres": "qyh-native166-", "aos_app": "qyh-canonical166-"}
            .get(expected_role) if type(expected_role) is str else None
        )
    else:
        expected_role = ROLE
        lab_prefix = ("qyh-native166-", "qyh-canonical166-")
    require(lab_prefix is not None
            and identity["db"] == DATABASE and identity["db_oid"] == binding.database_oid
            and identity["current_role"] == identity["session_role"] == expected_role
            and identity["rolcanlogin"] is True
            and type(binding.cluster_name) is str
            and binding.cluster_name.startswith(lab_prefix)
            and identity["cluster_name"] == binding.cluster_name
            and 160000 <= identity["version"] < 170000
            and identity["replication"] == "origin"
            and identity["org"] == "org-org" and identity["project"] == "dev-project",
            "new PG16 lab identity or tenant differs")
    if deployment:
        require(identity["rolsuper"] is True
                and identity.get("database_owner") == expected_role,
                "new PG16 lab identity or tenant differs")
    else:
        require(all(identity[key] is False for key in
                    ("rolsuper", "rolbypassrls", "rolcreatedb", "rolcreaterole", "rolreplication"))
                and identity["maintainer_member"] is True
                and identity["maintainer_set"] is True,
                "new PG16 lab identity or tenant differs")


def _native_binding(pytestconfig, *, deployment):
    require(pytestconfig.option.noconftest is True and not pytestconfig.option.showlocals,
            "explicit native runner without bootstrap or locals required")
    key = NATIVE_MIGRATION if deployment else NATIVE_OWNER
    expected_type = NativeMigrationBinding if deployment else NativeOwnerBinding
    binding = pytestconfig.stash.get(key, None)
    require(type(binding) is expected_type,
            "independently admitted migration lab required; no default connection")
    conn = binding.connection
    require(type(conn) is Connection and conn.dialect.name == "postgresql"
            and not conn.closed and conn.in_transaction()
            and conn.get_execution_options().get("isolation_level") != "AUTOCOMMIT",
            "real transactional PostgreSQL connection required")
    driver = conn.connection.driver_connection
    require(type(driver) is psycopg.Connection and driver.autocommit is False,
            "real non-autocommit psycopg connection required")
    require(type(binding.database_oid) is int and binding.database_oid > 0
            and sha256(MIGRATION.read_bytes()).hexdigest() == binding.migration_sha256,
            "independently pinned source and database OID required")
    # These settings affect this already-injected connection's transaction only.
    query(conn, "SELECT set_config('statement_timeout','10000ms',true), "
                "set_config('lock_timeout','1000ms',true)").one()
    identity = query(conn, """SELECT current_database() AS db,d.oid AS db_oid,
        current_user AS current_role,session_user AS session_role,
        pg_get_userbyid(d.datdba) AS database_owner,
        r.rolsuper,r.rolbypassrls,r.rolcreatedb,r.rolcreaterole,r.rolreplication,r.rolcanlogin,
        current_setting('server_version_num')::int AS version,
        current_setting('session_replication_role') AS replication,
        current_setting('aos.org_id',true) AS org,
        current_setting('aos.project_id',true) AS project,
        current_setting('cluster_name') AS cluster_name,
        pg_has_role(session_user,'aos_extension_maintainer','member') AS maintainer_member,
        pg_has_role(session_user,'aos_extension_maintainer','set') AS maintainer_set
        FROM pg_catalog.pg_database d JOIN pg_catalog.pg_roles r
          ON r.rolname=session_user WHERE d.datname=current_database()""").one()
    require_native_identity(identity, binding, deployment=deployment)
    if not deployment:
        require(conn.get_isolation_level() == "SERIALIZABLE",
                "isolated Owner diagnostic requires serializable transaction")
        query(conn, "SET LOCAL ROLE aos_extension_maintainer")
    return binding


@pytest.fixture(scope="module", autouse=True)
def _native_pytest_mode(pytestconfig):
    require(pytestconfig.option.noconftest is True and not pytestconfig.option.showlocals,
            "explicit native runner without bootstrap or locals required")


@pytest.fixture(scope="module")
def _isolated_postgres_database(pytestconfig):
    # Explicit new-lab deployment principal; never a business caller.
    return _native_binding(pytestconfig, deployment=True)


@pytest.fixture(scope="module")
def _native_owner_database(pytestconfig):
    # Separate restricted LOGIN; no migration or fallback to deployment binding.
    return _native_binding(pytestconfig, deployment=False)


def test_original_upgrade_preserves_history_and_native_savepoint_restores_authority(
        _isolated_postgres_database):
    conn = _isolated_postgres_database.connection
    spec = importlib.util.spec_from_file_location("native_refresh_migration", MIGRATION)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    # Actual Alembic operation adapter, not a fake op or a SQL recording stub.
    migration.op = Operations(MigrationContext.configure(conn))
    key_before = dict(query(conn, migration.KEY_SQL).one())
    seal_before = dict(query(conn, migration.SEAL_SQL).one())
    writer_before = dict(query(conn, migration.WRITER_SQL).one())
    require(key_before["pk_columns"] == migration.OLD_KEY,
            "diagnostic requires the original pre166 key")
    rows_before = history(conn)
    transaction = conn.begin_nested()
    try:
        # Freeze the whole table while comparing pre/post history and metadata.
        query(conn, "LOCK TABLE public.extension_dispatch_configuration_refresh_receipt "
                    "IN ACCESS EXCLUSIVE MODE")
        require(history(conn) == rows_before, "history changed before native upgrade")
        try:
            migration.upgrade()
        except Exception:
            raise AssertionError("original native upgrade failed") from None
        require(dict(query(conn, migration.KEY_SQL).one())["pk_columns"] == migration.NEW_KEY,
                "native activation-scoped key was not installed")
        require(history(conn) == rows_before, "upgrade changed original refresh rows")
        require(dict(query(conn, migration.SEAL_SQL).one()) == seal_before,
                "upgrade changed guards, triggers, policies, owner or table ACL")
        writer_after = dict(query(conn, migration.WRITER_SQL).one())
        require(writer_after["shape"] == writer_before["shape"]
                and writer_after["acl_valid"] is True
                and writer_after["body"] == migration._body(migration.REFRESH_SQL),
                "native writer definition or authority differs")
    finally:
        transaction.rollback()
    require(dict(query(conn, migration.KEY_SQL).one()) == key_before
            and dict(query(conn, migration.SEAL_SQL).one()) == seal_before
            and dict(query(conn, migration.WRITER_SQL).one()) == writer_before
            and history(conn) == rows_before and conn.in_transaction(),
            "real savepoint rollback did not restore original authority and history")


def test_original_owner_new_activation_starts_at_one_and_old_receipt_replays(
        _native_owner_database):
    """Prepared original A2 history and ready B1 input; no fabricated parent rows."""
    from aos_api.ecommerce_dispatch_configuration_contracts import DispatchConfigurationRefreshRequest
    from aos_api.ecommerce_dispatch_configuration_owner import EcommerceDispatchConfigurationOwner
    from aos_api.ecommerce_dispatch_configuration_receipt import decode_receipt
    from aos_api.ecommerce_growth_host_composition import EVENT_CONTROL_OPERATION
    from aos_api.tenant_scope import TenantScope

    binding = _native_owner_database
    scenario = binding.scenario
    require(type(scenario) is NativeRefreshScenario,
            "explicit original-owner cross-activation scenario required; no fallback")
    require(type(scenario.owner_source_hashes) is dict
            and set(scenario.owner_source_hashes) == set(OWNER_SOURCES),
            "complete independently pinned original Owner sources required")
    require(type(binding) is NativeOwnerBinding,
            "separate restricted Owner binding required")
    directory = MIGRATION.parents[2] / "aos_api"
    for name in OWNER_SOURCES:
        require(sha256((directory / name).read_bytes()).hexdigest()
                == scenario.owner_source_hashes[name], "original Owner source changed")
    require(type(scenario.old_command) is dict and type(scenario.new_command) is dict,
            "explicit original command dictionaries required")
    old = DispatchConfigurationRefreshRequest.model_validate_json(
        json.dumps(scenario.old_command, allow_nan=False))
    new = DispatchConfigurationRefreshRequest.model_validate_json(
        json.dumps(scenario.new_command, allow_nan=False))
    require((old.org_id, old.project_id) == (new.org_id, new.project_id)
            == ("org-org", "dev-project") and old.cutover_group_id == new.cutover_group_id
            and old.installation_ref.installation_id != new.installation_ref.installation_id
            and old.generation != new.generation
            and old.source_authority_ref.resource_type == "DispatchConfigurationRefreshReceipt"
            and old.source_authority_ref.revision == 1
            and new.source_authority_ref.resource_type == "CutoverResumeReceipt"
            and new.source_authority_ref.revision == 1,
            "same group, old second refresh and new installation resume required")
    conn = binding.connection
    spec = importlib.util.spec_from_file_location("native_refresh_owner_migration", MIGRATION)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    key_before = dict(query(conn, migration.KEY_SQL).one())
    writer_before = dict(query(conn, migration.WRITER_SQL).one())
    require(key_before["pk_columns"] == migration.NEW_KEY
            and writer_before["body"] == migration._body(migration.REFRESH_SQL)
            and writer_before["acl_valid"] is True,
            "separately deployed original166 authority required")
    rows_before = history(conn)
    def dispatch_snapshot():
        try:
            rows = conn.exec_driver_sql("""SELECT *
                FROM public.extension_operation_dispatch_binding
                WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s::uuid
                ORDER BY operation_id LIMIT 11""",
                (new.org_id, new.project_id, new.cutover_group_id)).mappings().all()
        except Exception:
            raise AssertionError("original dispatch snapshot unavailable") from None
        expected = set(new.operation_ids) | {EVENT_CONTROL_OPERATION}
        require(len(rows) == len(expected) == 10
                and {row['operation_id'] for row in rows} == expected,
                "exact business and event-control group required")
        return {row['operation_id']: dict(row) for row in rows}

    dispatch_before = dispatch_snapshot()
    transaction = conn.begin_nested()
    try:
        query(conn, "LOCK TABLE public.extension_dispatch_configuration_refresh_receipt "
                    "IN ACCESS SHARE MODE")
        require(history(conn) == rows_before, "original history changed before diagnostic")
        try:
            prior_row = conn.exec_driver_sql("""SELECT *
                FROM public.extension_dispatch_configuration_refresh_receipt
                WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s::uuid
                  AND idempotency_key=%s""",
                (old.org_id, old.project_id, old.cutover_group_id, old.idempotency_key)
            ).mappings().one()
            prior = decode_receipt(dict(prior_row))
        except Exception:
            raise AssertionError("original prepared old receipt is unavailable or invalid") from None
        require(prior["ref"]["revision"] == 2 and prior["request"] == old.wire()
                and prior["body"]["actor"] == scenario.old_actor,
                "exact original second refresh and actor required")
        # The real original Owner performs both current approval checks. No SQL
        # function shortcut, approval replacement, connector or setup callback.
        owner = EcommerceDispatchConfigurationOwner()
        scope = TenantScope("org-org", "dev-project")
        driver = conn.connection.driver_connection
        original_factory = driver.row_factory

        def call_original(command, actor):
            require(conn.in_transaction() and driver.autocommit is False,
                    "same original transaction required")
            try:
                conn.exec_driver_sql("SET LOCAL ROLE aos_extension_maintainer")
                driver.row_factory = dict_row
                return owner.execute(driver, scope=scope, command=deepcopy(command), actor=actor)
            except Exception:
                raise AssertionError("original approved native Owner call failed") from None
            finally:
                driver.row_factory = original_factory

        first = call_original(scenario.new_command, scenario.new_actor)
        require(first["ref"]["revision"] == 1 and first["request"] == new.wire()
                and first["body"]["activationOperationId"] != prior["body"]["activationOperationId"],
                "new actual activation must start its own first refresh")
        # Only known successful returns are replayed, on this same transaction.
        require(call_original(scenario.new_command, scenario.new_actor) == first,
                "known new receipt replay differs")
        require(call_original(scenario.old_command, scenario.old_actor) == prior,
                "another activation incorrectly invalidated the old known receipt")
        dispatch_after = dispatch_snapshot()
        require(dispatch_after[EVENT_CONTROL_OPERATION] == dispatch_before[EVENT_CONTROL_OPERATION],
                "business refresh changed separate event-control authority")
        for operation in new.operation_ids:
            before, after = dispatch_before[operation], dispatch_after[operation]
            require(before['cutover_group_revision'] == new.expected_group_revision
                    and before['execution_epoch'] == new.source_execution_epoch,
                    "prepared business dispatch source differs")
            expected = dict(before, execution_epoch=new.target_execution_epoch,
                            revision=before['revision']+1,
                            cutover_group_revision=new.expected_group_revision+1,
                            updated_by=scenario.new_actor)
            require(set(after) == set(expected)
                    and all(after[name] == value for name, value in expected.items()
                            if name != 'updated_at')
                    and after['updated_at'] is not None
                    and after['updated_at'].utcoffset() is not None,
                    "business dispatch result differs from original Owner transition")
        rows_after = history(conn)
        require(len(rows_after) == len(rows_before) + 1
                and set(rows_before).issubset(rows_after),
                "Owner changed history or inserted more than one new receipt")
    finally:
        transaction.rollback()
    require(dict(query(conn, migration.KEY_SQL).one()) == key_before
            and dict(query(conn, migration.WRITER_SQL).one()) == writer_before
            and history(conn) == rows_before and dispatch_snapshot() == dispatch_before
            and conn.in_transaction(),
            "cross-activation diagnostic rollback did not restore original state")
