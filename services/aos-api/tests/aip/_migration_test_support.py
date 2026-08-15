from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.engine import URL


ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def isolated_aip_migration_database(prefix: str) -> Iterator[tuple[Config, str]]:
    """Create a fully bootstrapped disposable database for downgrade contracts."""
    parts = conninfo_to_dict(os.environ["AOS_DATABASE_URL"])
    database_name = f"aos_test_{prefix}_{uuid4().hex[:12]}"
    admin_dsn = make_conninfo(**{**parts, "dbname": "postgres"})
    test_dsn = URL.create(
        "postgresql",
        username=parts.get("user"),
        password=parts.get("password"),
        host=parts.get("host"),
        port=int(parts["port"]) if parts.get("port") else None,
        database=database_name,
    ).render_as_string(hide_password=False)
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))

    previous_dsn = os.environ["AOS_DATABASE_URL"]
    previous_twa_store = os.environ.get("AOS_TWA_STORE")
    try:
        os.environ["AOS_DATABASE_URL"] = test_dsn
        os.environ["AOS_TWA_STORE"] = "pg"
        from aos_api import data_os_store, tenant_catalog, twa_pg

        twa_pg.clear_mode_cache()
        tenant_catalog._schema_ready = False
        data_os_store._schema_ready = False
        config = Config(ROOT / "alembic.ini")
        config.set_main_option("script_location", str(ROOT / "alembic"))
        config.set_main_option("sqlalchemy.url", test_dsn)
        command.upgrade(config, "228assetintegration")

        from aos_api.canvas_config import ensure_schema as ensure_canvas_schema
        from aos_api.data_os_store import ensure_data_os_schema
        from aos_api.db import connect, init_schema
        from aos_api.module_deployments import ensure_schema as ensure_deployment_schema
        from aos_api.module_events import ensure_events_schema
        from aos_api.module_interfaces import ensure_schema as ensure_interface_schema
        from aos_api.module_queries import ensure_schema as ensure_query_schema
        from aos_api.module_store import ensure_module_schema
        from aos_api.module_variables import ensure_schema as ensure_variable_schema
        from aos_api.routers.drafts import ensure_draft_schema
        from aos_api.tenant_catalog import ensure_tenant_catalog_schema
        from aos_api.widget_instances import ensure_schema as ensure_widget_schema

        init_schema()
        ensure_tenant_catalog_schema()
        with connect() as conn:
            conn.execute(
                "INSERT INTO twa_org (id,name) VALUES ('dev-org','测试组织') "
                "ON CONFLICT (id) DO NOTHING"
            )
            conn.execute(
                "INSERT INTO twa_workspace (org_id,project_id,name) "
                "VALUES ('dev-org','dev-project','测试工作区') "
                "ON CONFLICT (org_id,project_id) DO NOTHING"
            )
            conn.commit()
        ensure_module_schema()
        ensure_canvas_schema()
        ensure_deployment_schema()
        ensure_events_schema()
        ensure_interface_schema()
        ensure_query_schema()
        ensure_variable_schema()
        ensure_widget_schema()
        ensure_draft_schema()
        command.upgrade(config, "head")
        ensure_data_os_schema()
        yield config, test_dsn
    finally:
        os.environ["AOS_DATABASE_URL"] = previous_dsn
        if previous_twa_store is None:
            os.environ.pop("AOS_TWA_STORE", None)
        else:
            os.environ["AOS_TWA_STORE"] = previous_twa_store
        try:
            from aos_api import twa_pg

            twa_pg.clear_mode_cache()
        finally:
            with psycopg.connect(admin_dsn, autocommit=True) as conn:
                conn.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid <> pg_backend_pid()",
                    (database_name,),
                )
                conn.execute(
                    sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name))
                )
