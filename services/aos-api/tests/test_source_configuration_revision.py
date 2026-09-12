from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aos_api.db import connect
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")


def upsert(conn, source_id, props=None):
    return conn.execute("""INSERT INTO meta_source(id,type,status,org_id,project_id,props)
        VALUES(%s,'jdbc','registered',%s,%s,%s)
        ON CONFLICT(org_id,project_id,id) DO UPDATE SET props=EXCLUDED.props,updated_at=NOW()
        RETURNING configuration_revision""", (source_id, *SCOPE.key, Jsonb(props or {}))).fetchone()["configuration_revision"]


def test_actual_change_only_and_history_never_contains_connection_properties():
    source_id = "config-test-" + uuid4().hex
    with connect(SCOPE) as conn:
        first = upsert(conn, source_id, {"test_private": "must-not-appear"})
        store = SourceConfigurationRevisionStore(HostTransaction(conn), SCOPE)
        original = store.read_current(source_id)
        assert original.revision_id == first
        assert store.read_exact(original.ref) == original
        assert "must-not-appear" not in str(original)
        assert upsert(conn, source_id, {"test_private": "must-not-appear"}) == first
        conn.execute("UPDATE meta_source SET updated_at=clock_timestamp() WHERE org_id=%s AND project_id=%s AND id=%s", (*SCOPE.key, source_id))
        assert store.read_current(source_id).ref == original.ref
        second = upsert(conn, source_id, {"test_private": "changed"})
        assert second != first and store.read_current(source_id).prior_revision_id == first
        assert store.read_exact(original.ref) == original
        assert conn.execute("SELECT count(*) AS n FROM data_source_configuration_revision WHERE source_id=%s", (source_id,)).fetchone()["n"] == 2
        conn.rollback()
    with connect(SCOPE) as conn:
        assert SourceConfigurationRevisionStore(HostTransaction(conn), SCOPE).read_exact(original.ref) is None


def test_caller_tokens_identity_moves_and_history_mutations_are_rejected():
    source_id = "config-test-" + uuid4().hex
    with connect(SCOPE) as conn:
        first = upsert(conn, source_id)
        for sql, args in [
            ("UPDATE meta_source SET configuration_revision=%s WHERE org_id=%s AND project_id=%s AND id=%s", (uuid4(), *SCOPE.key, source_id)),
            ("UPDATE meta_source SET id=%s WHERE org_id=%s AND project_id=%s AND id=%s", ("moved", *SCOPE.key, source_id)),
            ("DELETE FROM data_source_configuration_revision WHERE source_id=%s", (source_id,)),
            ("UPDATE data_source_configuration_revision SET status='changed' WHERE source_id=%s", (source_id,)),
        ]:
            with pytest.raises(psycopg.Error) as error:
                with conn.transaction():
                    conn.execute(sql, args)
            assert error.value.sqlstate == ("SC001" if "meta_source" in sql else "42501")
        with pytest.raises(psycopg.Error) as error:
            with conn.transaction():
                conn.execute("INSERT INTO meta_source(id,org_id,project_id,configuration_revision) VALUES(%s,%s,%s,%s)",
                             ("injected", *SCOPE.key, first))
        assert error.value.sqlstate == "SC001"
        conn.rollback()


def test_delete_retains_history_and_recreate_uses_new_identity():
    source_id = "config-test-" + uuid4().hex
    with connect(SCOPE) as conn:
        first = upsert(conn, source_id)
        store = SourceConfigurationRevisionStore(HostTransaction(conn), SCOPE)
        original = store.read_current(source_id)
        conn.execute("DELETE FROM meta_source WHERE org_id=%s AND project_id=%s AND id=%s", (*SCOPE.key, source_id))
        assert store.read_current(source_id) is None and store.read_exact(original.ref) == original
        assert upsert(conn, source_id) != first
        assert store.read_current(source_id).prior_revision_id is None
        conn.rollback()


def test_temporary_tables_cannot_shadow_authoritative_history_or_current_source():
    source_id = "config-test-" + uuid4().hex
    with connect(SCOPE) as conn:
        conn.execute("CREATE TEMP TABLE data_source_configuration_revision (LIKE public.data_source_configuration_revision INCLUDING DEFAULTS)")
        first = upsert(conn, source_id)
        assert conn.execute("SELECT count(*) AS n FROM public.data_source_configuration_revision WHERE source_id=%s", (source_id,)).fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM pg_temp.data_source_configuration_revision").fetchone()["n"] == 0
        store = SourceConfigurationRevisionStore(HostTransaction(conn), SCOPE)
        original = store.read_current(source_id)
        assert original.revision_id == first
        conn.execute("CREATE TEMP TABLE meta_source (LIKE public.meta_source)")
        assert store.read_current(source_id) == original
        assert store.read_exact(original.ref) == original
        conn.rollback()


def test_runtime_concurrent_noop_history_permissions_and_canary():
    from concurrent.futures import ThreadPoolExecutor
    source_id = "config-test-" + uuid4().hex

    def save(_):
        with connect(SCOPE) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            result = upsert(conn, source_id, {"fixture": True})
            conn.commit()
            return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        tokens = list(pool.map(save, range(2)))
    assert tokens[0] == tokens[1]
    with connect(SCOPE) as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        store = SourceConfigurationRevisionStore(HostTransaction(conn), SCOPE)
        original = store.read_current(source_id)
        assert conn.execute("SELECT count(*) AS n FROM public.data_source_configuration_revision WHERE source_id=%s", (source_id,)).fetchone()["n"] == 1
        for statement in [
            "INSERT INTO public.data_source_configuration_revision SELECT * FROM public.data_source_configuration_revision LIMIT 1",
            "DELETE FROM public.data_source_configuration_revision",
            "UPDATE public.data_source_configuration_revision SET status='changed'",
            "TRUNCATE public.data_source_configuration_revision",
        ]:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction():
                    conn.execute(statement)
    canary = TenantScope("dev-org", "dev-project")
    with connect(canary) as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        store = SourceConfigurationRevisionStore(HostTransaction(conn), canary)
        assert store.read_current(source_id) is None
        assert store.read_exact(original.ref) is None
        assert conn.execute("SELECT count(*) AS n FROM public.data_source_configuration_revision WHERE source_id=%s", (source_id,)).fetchone()["n"] == 0


def test_exact_read_rejects_safe_metadata_or_reference_drift():
    from copy import deepcopy
    from tests.test_source_read_observation_evidence import Connection
    source_id = "config-test-" + uuid4().hex
    with connect(SCOPE) as conn:
        token = upsert(conn, source_id)
        store = SourceConfigurationRevisionStore(HostTransaction(conn), SCOPE)
        original = store.read_current(source_id)
        row = conn.execute("SELECT * FROM public.data_source_configuration_revision WHERE revision_id=%s", (token,)).fetchone()
        for field, value in [("org_id", "dev-org"), ("status", "changed"), ("source_id", "other"),
                             ("content_hash", "0" * 64), ("authority", {}),
                             ("authority", {**row["authority"], "configurationIdentityOnly": 1}),
                             ("recorded_at", None)]:
            changed = deepcopy(row)
            changed[field] = value
            with pytest.raises(ValueError):
                SourceConfigurationRevisionStore(HostTransaction(Connection(changed)), SCOPE).read_exact(original.ref)
        with pytest.raises(ValueError):
            store.read_exact(original.ref.model_copy(update={"content_hash": "sha256:" + "0" * 64}))
        conn.rollback()


def test_migration_backfills_current_identity_and_refuses_nonempty_downgrade():
    from alembic import command
    from sqlalchemy.exc import DBAPIError
    from tests.aip._migration_test_support import isolated_aip_migration_database
    with isolated_aip_migration_database("source_config", migration_target="ar2_009") as (config, _):
        source_id = "config-migration-" + uuid4().hex
        with connect(SCOPE) as conn:
            conn.execute("INSERT INTO public.meta_source(id,type,status,org_id,project_id,props) VALUES(%s,'jdbc','registered',%s,%s,%s)",
                         (source_id, *SCOPE.key, Jsonb({"fixture": "private-value"})))
            conn.commit()
        command.upgrade(config, "ar2_010")
        with connect(SCOPE) as conn:
            original = SourceConfigurationRevisionStore(HostTransaction(conn), SCOPE).read_current(source_id)
            assert original is not None and original.prior_revision_id is None
            assert "private-value" not in str(original)
        with pytest.raises(DBAPIError, match="cannot remove source configuration history"):
            command.downgrade(config, "ar2_009")
        with connect(SCOPE) as conn:
            assert SourceConfigurationRevisionStore(HostTransaction(conn), SCOPE).read_exact(original.ref) == original


def test_empty_migration_can_downgrade_and_upgrade():
    from alembic import command
    from tests.aip._migration_test_support import isolated_aip_migration_database
    with isolated_aip_migration_database("source_empty", migration_target="ar2_010") as (config, _):
        command.downgrade(config, "ar2_009")
        command.upgrade(config, "ar2_010")
