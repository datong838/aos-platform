"""Run the frozen native a0v_166 savepoint diagnostic once on the exact lab."""

from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "services" / "aos-api"
TESTS = API / "tests"
MIGRATION = API / "alembic" / "versions" / "a0v_166_dispatch_refresh_activation_chain.py"
NATIVE_TEST = TESTS / "extension_runtime" / "test_dispatch_refresh_activation_chain_pg.py"
DATABASE_URL_ENV = "AOS_NATIVE166_DATABASE_URL"
EXPECTED_DATABASE_URL = (
    "postgresql+psycopg://aos_app@127.0.0.1:18458/"
    "aos_refresh_activation_native?application_name=qyh-native166-r882&connect_timeout=5"
)
DATABASE = "aos_refresh_activation_native"
DATABASE_OID = 16384
CLUSTER = "qyh-canonical166-8af8248e67b4128101100eda"
ADMINISTRATOR_ROLE = "aos_app"
MIGRATION_SHA256 = "28d65323629bf349a52f84737e56a5befeefbc1b7a396bb28aece44fa1dedd86"
NATIVE_TEST_SHA256 = "06d04fd9d3604fb9d0101bb20183fef16e27779b7aff1f948db226fc53410c23"


def admitted_database_url(environ):
    value = environ.get(DATABASE_URL_ENV)
    if value != EXPECTED_DATABASE_URL:
        raise RuntimeError("exact local database URL required")
    return value


def require_file_pin(path, expected):
    actual = sha256(Path(path).read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError("source pin differs")
    return actual


def history_summary(rows):
    encoded = "\n".join(rows).encode("utf-8")
    return {"count": len(rows), "sha256": sha256(encoded).hexdigest()}


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         default=str, ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def _load_native_test():
    sys.path.insert(0, str(TESTS))
    try:
        from extension_runtime import test_dispatch_refresh_activation_chain_pg as native
    finally:
        sys.path.pop(0)
    return native


def _set_tenant(conn):
    conn.exec_driver_sql(
        "SELECT set_config('aos.org_id','org-org',true),"
        "set_config('aos.project_id','dev-project',true)"
    ).one()


def _state(conn, native, migration_module):
    key = dict(native.query(conn, migration_module.KEY_SQL).one())
    seal = dict(native.query(conn, migration_module.SEAL_SQL).one())
    writer = dict(native.query(conn, migration_module.WRITER_SQL).one())
    rows = native.history(conn)
    return {
        "key": list(key["pk_columns"]),
        "history": history_summary(rows),
        "sealSha256": _digest(seal),
        "writerSha256": _digest(writer),
    }


def public_result(*, before, after, source_hashes):
    return {
        "schema": "aos-native166-savepoint-result/v1",
        "knownOutcome": "SAVEPOINT_UPGRADE_AND_ROLLBACK_GREEN",
        "database": DATABASE,
        "databaseOid": DATABASE_OID,
        "clusterName": CLUSTER,
        "administratorRole": ADMINISTRATOR_ROLE,
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "sourceHashes": source_hashes,
        "before": before,
        "after": after,
        "persistentStateRestored": before == after,
        "businessAcceptance": False,
    }


def run(environ):
    database_url = admitted_database_url(environ)
    source_hashes = {
        "migration": require_file_pin(MIGRATION, MIGRATION_SHA256),
        "native_test": require_file_pin(NATIVE_TEST, NATIVE_TEST_SHA256),
    }
    native = _load_native_test()
    import importlib.util
    spec = importlib.util.spec_from_file_location("native166_migration_r882", MIGRATION)
    migration_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration_module)

    engine = create_engine(database_url, poolclass=NullPool)
    before = None
    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                _set_tenant(conn)
                version = conn.exec_driver_sql(
                    "SELECT version_num FROM public.alembic_version"
                ).scalar_one()
                if version != "a0v_165":
                    raise RuntimeError("exact pre166 alembic head required")
                before = _state(conn, native, migration_module)
                binding = native.NativeMigrationBinding(
                    connection=conn,
                    database_oid=DATABASE_OID,
                    migration_sha256=MIGRATION_SHA256,
                    cluster_name=CLUSTER,
                    administrator_role=ADMINISTRATOR_ROLE,
                )
                config = type("NativeConfig", (), {
                    "option": type("NativeOptions", (), {
                        "noconftest": True,
                        "showlocals": False,
                    })(),
                    "stash": {native.NATIVE_MIGRATION: binding},
                })()
                admitted = native._isolated_postgres_database.__wrapped__(config)
                native.test_original_upgrade_preserves_history_and_native_savepoint_restores_authority(
                    admitted
                )
                if _state(conn, native, migration_module) != before:
                    raise RuntimeError("transaction state not restored after native diagnostic")
            finally:
                transaction.rollback()

        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                _set_tenant(conn)
                version = conn.exec_driver_sql(
                    "SELECT version_num FROM public.alembic_version"
                ).scalar_one()
                if version != "a0v_165":
                    raise RuntimeError("persistent alembic head changed")
                after = _state(conn, native, migration_module)
            finally:
                transaction.rollback()
    finally:
        engine.dispose()

    result = public_result(before=before, after=after, source_hashes=source_hashes)
    if not result["persistentStateRestored"]:
        raise RuntimeError("persistent state differs after rollback")
    return result


if __name__ == "__main__":
    print(json.dumps(run(os.environ), ensure_ascii=False, sort_keys=True, indent=2))
