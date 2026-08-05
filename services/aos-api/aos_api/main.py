"""AOS API application factory — Wave-0/1/2."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aos_api.db import ensure_system_meta, init_schema
from aos_api.errors import register_exception_handlers
from aos_api.logging_facade import configure_logging, get_logger
from aos_api.middleware import TraceLogMiddleware
from aos_api.migrations import run_migrations
from aos_api.module_store import seed_modules_if_empty

# Domain router aggregates — all 505 routers grouped into 10 domain APIRouters.
# Individual router modules are imported lazily inside each factory function.
from aos_api.routers.domain_aggregates import (
    create_admin_router,
    create_agent_router,
    create_aip_router,
    create_apollo_router,
    create_data_router,
    create_infra_router,
    create_model_router,
    create_ontology_router,
    create_system_router,
    create_workshop_router,
)
from aos_api.tenant_scope import TenantScope

configure_logging()
log = get_logger("aos-api")

# Load aos-platform/.env (AGNES_* etc.) before request handlers run
try:
    from aos_api.env_load import load_dotenv

    loaded = load_dotenv()
    if loaded:
        log.info("dotenv_loaded path=%s", loaded)
except Exception:  # pragma: no cover
    log.exception("dotenv_load_failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Migration mode owns its failure policy. Keep it outside the best-effort
    # bootstrap boundary so managed-mode failures can stop application startup.
    migration_mode = run_migrations()
    mode_value = getattr(migration_mode, "value", migration_mode)
    # ``None`` preserves compatibility with the pre-W1 implementation. Once W1
    # is merged, only its explicit LEGACY_BOOTSTRAP mode may execute runtime DDL.
    legacy_bootstrap = mode_value is None or mode_value in {
        "legacy-bootstrap",
        "legacy_bootstrap",
    }
    if legacy_bootstrap:
        try:
            init_schema()
            ensure_system_meta()
            try:
                seed_modules_if_empty(TenantScope("dev-org", "dev-project"))
            except Exception:
                log.exception("startup_module_seed_failed_continue")
            try:
                from aos_api.tenant_catalog import boot_tenant_catalogs

                boot_tenant_catalogs()
            except Exception:
                log.exception("startup_tenant_catalog_failed_continue")
            try:
                from aos_api import data_os_store
                from aos_api.routers import wave_ext as wave_ext_mod

                data_os_store.boot_data_os(wave_ext_mod)
            except Exception:
                log.exception("startup_data_os_failed_continue")
            try:
                from aos_api.ec_live_executor import ec_live_executor
                from aos_api.ec_pipeline_resolvers import dataset_resolver
                from aos_api.phase5_pipeline_engine import get_engine

                eng = get_engine()
                eng.register_evidence_resolver("dataset", dataset_resolver)
                eng.register_executor("ec-live-v1", ec_live_executor)
                log.info(
                    "startup_pipeline_registered resolver=dataset executor=ec-live-v1"
                )
            except Exception:
                log.exception("startup_pipeline_registration_failed_continue")
            log.info("startup_meta_store_ok")
        except Exception:
            log.exception("startup_meta_store_failed_continue")
    else:
        log.info("startup_schema_bootstrap_skipped migration_mode=%s", mode_value)
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="aos-api", version="0.3.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        # Web :5173 · 桌面 Tauri dev :1420 · 打包壳 tauri://
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:1420",
            "http://localhost:1420",
            "tauri://localhost",
            "https://tauri.localhost",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-Id", "ETag"],
    )
    application.add_middleware(TraceLogMiddleware)
    register_exception_handlers(application)

    # ── Domain routers (505 routes in 10 domains) ──
    # Order matches original main.py first-appearance to avoid route collisions.
    application.include_router(create_infra_router())
    application.include_router(create_admin_router())
    application.include_router(create_system_router())
    application.include_router(create_agent_router())
    application.include_router(create_workshop_router())
    application.include_router(create_ontology_router())
    application.include_router(create_aip_router())
    application.include_router(create_data_router())
    application.include_router(create_model_router())
    application.include_router(create_apollo_router())

    # Reset lifespan to avoid the include_router lifi_chain with 500+ routers.
    application.router.lifespan_context = lifespan

    log.info("aos-api_app_created version=%s", application.version)
    return application


app = create_app()
