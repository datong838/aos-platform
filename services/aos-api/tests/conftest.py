import os
import uuid

# Unit tests default to in-memory TWA (181m PG via AOS_TWA_STORE=pg / auto outside tests).
os.environ.setdefault("AOS_TWA_STORE", "memory")

import pytest
import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.engine import URL

from aos_api.db import init_schema, seed_if_empty
from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.metrics import reset_metrics
from aos_api.module_store import seed_modules_if_empty
from aos_api.tenant_scope import TenantScope
from aos_api import mock_data
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _isolated_postgres_database():
    """Run the test session against a disposable database, never shared aos_meta."""
    if os.getenv("AOS_TEST_USE_SHARED_DATABASE") == "1":
        yield
        return

    base_dsn = os.getenv(
        "AOS_DATABASE_URL",
        "postgresql://aos_app:aos_dev_only_change_me@127.0.0.1:5433/aos_meta",
    )
    parts = conninfo_to_dict(base_dsn)
    database_name = f"aos_test_{uuid.uuid4().hex[:12]}"
    admin_dsn = make_conninfo(**{**parts, "dbname": parts.get("dbname") or "postgres"})
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

    previous_dsn = os.environ.get("AOS_DATABASE_URL")
    previous_twa_store = os.environ.get("AOS_TWA_STORE")
    os.environ["AOS_DATABASE_URL"] = test_dsn
    config = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    config.set_main_option(
        "script_location", os.path.join(os.path.dirname(__file__), "..", "alembic")
    )
    config.set_main_option("sqlalchemy.url", test_dsn)
    try:
        os.environ["AOS_TWA_STORE"] = "pg"
        from aos_api import twa_pg
        from aos_api.db import init_schema
        from aos_api.tenant_catalog import ensure_tenant_catalog_schema

        twa_pg.clear_mode_cache()
        command.upgrade(config, "228assetintegration")
        init_schema()
        ensure_tenant_catalog_schema()
        from aos_api.canvas_config import ensure_schema as ensure_canvas_schema
        from aos_api.module_deployments import ensure_schema as ensure_deployment_schema
        from aos_api.module_events import ensure_events_schema
        from aos_api.module_interfaces import ensure_schema as ensure_interface_schema
        from aos_api.module_queries import ensure_schema as ensure_query_schema
        from aos_api.module_store import ensure_module_schema
        from aos_api.module_variables import ensure_schema as ensure_variable_schema
        from aos_api.widget_instances import ensure_schema as ensure_widget_schema

        ensure_module_schema()
        ensure_canvas_schema()
        ensure_deployment_schema()
        ensure_events_schema()
        ensure_interface_schema()
        ensure_query_schema()
        ensure_variable_schema()
        ensure_widget_schema()
        command.upgrade(config, "head")
        os.environ["AOS_TWA_STORE"] = previous_twa_store or "memory"
        twa_pg.clear_mode_cache()
        yield
    finally:
        if previous_dsn is None:
            os.environ.pop("AOS_DATABASE_URL", None)
        else:
            os.environ["AOS_DATABASE_URL"] = previous_dsn
        if previous_twa_store is None:
            os.environ.pop("AOS_TWA_STORE", None)
        else:
            os.environ["AOS_TWA_STORE"] = previous_twa_store
        try:
            from aos_api import twa_pg

            twa_pg.clear_mode_cache()
        except Exception:
            pass
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))


@pytest.fixture()
def client():
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    # Unit tests must not hit real Agnes / network LLM
    for k in (
        "AGNES_API_KEY",
        "AGNES_BASE_URL",
        "AGNES_TEXT_MODEL",
        "AGNES_IMAGE_MODEL",
        "AOS_LITELLM_URL",
    ):
        os.environ.pop(k, None)
    os.environ["AOS_LITELLM_FALLBACK"] = "mock"
    os.environ.setdefault("AOS_TWA_STORE", "memory")
    try:
        from aos_api import twa_pg

        twa_pg.clear_mode_cache()
    except Exception:
        pass
    # ensure schema for ontology tests
    try:
        init_schema()
        seed_if_empty()
        seed_modules_if_empty(TenantScope("dev-org", "dev-project"))
        from aos_api.db import connect as _connect

        with _connect() as _c:
            _c.execute("DELETE FROM obj_instance WHERE props->>'source' IS NOT NULL")
            _c.execute("DELETE FROM meta_aip_kv WHERE key='apollo_ops_assets'")
            _c.execute("DELETE FROM meta_object_type WHERE id NOT IN ('WorkOrder','Site','Order','OrderItem')")
            _c.commit()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"PG unavailable: {exc}")
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers():
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
        "X-Trace-Id": "test-trace-1",
    }


@pytest.fixture()
def dev_principal(auth_headers):
    """构造与 ``Bearer dev`` + dev-org/dev-project header 等价的 Principal。

    供需要直接调用 ``aos_api.demo.demo_story`` Python 函数的测试使用，
    替代已下线的 ``/v1/demo/*`` HTTP 路由。
    """
    from aos_api.auth import Principal

    return Principal(
        subject="user:dev",
        org_id=auth_headers["X-Org-Id"],
        project_id=auth_headers["X-Project-Id"],
        roles=["developer", "admin"],
        markings=["public", "restricted"],
        token_kind="dev",
    )
