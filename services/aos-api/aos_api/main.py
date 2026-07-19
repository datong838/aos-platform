"""AOS API application factory — Wave-0/1/2."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aos_api.db import init_schema, seed_if_empty
from aos_api.module_store import seed_modules_if_empty
from aos_api.errors import register_exception_handlers
from aos_api.logging_facade import configure_logging, get_logger
from aos_api.middleware import TraceLogMiddleware
from aos_api.routers import (
    actions,
    analytics,
    auth_oidc,
    authz,
    buddy,
    drafts,
    health,
    me,
    metrics,
    modules,
    object_sets,
    ontology,
    orgs,
    ops_tenants,
    ops_version_matrix,
    plugins,
    runtime_write,
    wave_ext,
    workspaces,
)

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
    try:
        init_schema()
        seed_if_empty()
        try:
            seed_modules_if_empty()
        except Exception:
            log.exception("startup_module_store_failed_continue")
        log.info("startup_meta_store_ok")
    except Exception:
        log.exception("startup_meta_store_failed_continue")
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="aos-api", version="0.3.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-Id"],
    )
    application.add_middleware(TraceLogMiddleware)
    register_exception_handlers(application)
    application.include_router(health.router)
    application.include_router(metrics.router)
    application.include_router(auth_oidc.router)
    application.include_router(authz.router)
    application.include_router(me.router)
    application.include_router(orgs.router)
    application.include_router(ops_tenants.router)
    application.include_router(ops_version_matrix.router)
    application.include_router(workspaces.router)
    application.include_router(buddy.router)
    application.include_router(modules.router)
    application.include_router(plugins.router)
    application.include_router(object_sets.router)
    application.include_router(ontology.router)
    application.include_router(actions.router)
    application.include_router(drafts.router)
    application.include_router(runtime_write.router)
    application.include_router(analytics.router)
    application.include_router(wave_ext.router)
    log.info("aos-api_app_created version=%s", application.version)
    return application


app = create_app()
