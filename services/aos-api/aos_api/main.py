"""AOS API application factory — Wave-0/1/2."""
from __future__ import annotations

import asyncio
from contextlib import suppress
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
    cron_stop = asyncio.Event()
    cron_task: asyncio.Task[None] | None = None
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
            # ── JDBC SSH 隧道预建立（boot_tenant_catalogs 之后，PG 已 ready）──
            try:
                from aos_api.jdbc_connector_runtime import prebuild_all_ssh_tunnels_from_meta_source
                prebuild_all_ssh_tunnels_from_meta_source()
            except Exception:
                log.exception("startup_jdbc_ssh_prebuild_failed_continue")
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
            # ── 从 YAML bundle 加载真实栖月汇管道（替代 demo fallback）──
            try:
                from pathlib import Path as _Path
                import time as _time
                from aos_api.phase5_pipeline_engine import get_engine as _get_engine
                from aos_api.tenant_scope import TenantScope as _TS

                _bundles_dir = (
                    _Path(__file__).resolve().parents[3]
                    / "bundles" / "platforms" / "ecommerce-niushop" / "content" / "mappings"
                )
                _eng = _get_engine()
                _scope = _TS("org-org", "dev-project")
                _count = _eng.seed_from_bundles(_scope, str(_bundles_dir))
                # 同步填充 wave_ext._datasets + _pipelines，使前端能查到数据集和管道
                if _count > 0:
                    from aos_api.routers import wave_ext as _wx
                    _items, _ = _eng.list_pipelines(_scope)
                    _now = _time.time()
                    for _p in _items:
                        _dataset_rid = f"ri.aos.main.dataset.{_p.id}"
                        _dkey = _wx._resource_key(_scope, _dataset_rid)
                        _wx._datasets[_dkey] = {
                            "rid": _dataset_rid,
                            "name": _p.name,
                            "pipelineId": _p.id,
                            "sourceId": "niushop-qyh",
                            "status": "READY",
                            "createdAt": _now,
                            "updatedAt": _now,
                            "objectTypeHint": _p.id,
                            "displayName": _p.name,
                            "orgId": _scope.org_id,
                            "projectId": _scope.project_id,
                        }
                        _wx._pipelines[_p.id] = {
                            "id": _p.id,
                            "sourceId": "niushop-qyh",
                            "target": "dataset",
                            "datasetRid": _dataset_rid,
                            "orgId": _scope.org_id,
                            "projectId": _scope.project_id,
                            "name": _p.name,
                            "status": _p.status,
                            "tags": _p.tags,
                            "description": _p.description,
                            "lastBuild": {
                                "id": f"seed-build-{_p.id}",
                                "status": "SUCCEEDED",
                                "pipelineId": _p.id,
                                "tasks": [
                                    {"name": "ingest", "status": "SUCCEEDED"},
                                    {"name": "transform", "status": "SUCCEEDED"},
                                    {"name": "sink", "status": "SUCCEEDED"},
                                ],
                                "startedAt": _now,
                                "finishedAt": _now,
                            },
                        }
                    # 标记 scope 已加载，避免 _hydrate_data_os_scope 清空上述数据
                    _wx._data_os_loaded_scopes.add(_scope.key)
                    # 持久化到 PG（确保重启后 _hydrate_data_os_scope 能从 PG 恢复）
                    for _p in _items:
                        _pl_item = _wx._pipelines.get(_p.id)
                        if _pl_item:
                            _wx._persist_safe("persist_pipeline", _scope, {**_pl_item})
                        _ds_rid = f"ri.aos.main.dataset.{_p.id}"
                        _ds_item = _wx._datasets.get(_wx._resource_key(_scope, _ds_rid))
                        if _ds_item:
                            _wx._persist_safe("persist_dataset", _scope, {**_ds_item})
                    # 强制 hydrate 从 PG 加载全部数据（包括 source/connector）
                    # 这样 _connectors 也能从 meta_source 恢复
                    _wx._hydrate_data_os_scope(_scope, force=True)

                    # Phase B: 为每个 pipeline 创建 SyncTask（绑定 pipeline_id + source_id）
                    # Phase6 引擎是纯内存的，每次启动需要重建 SyncTask
                    from aos_api.phase6_datasource_engine import get_engine as _p6eng
                    _p6 = _p6eng()
                    for _p in _items:
                        _st_id = f"sync-task-{_p.id}"
                        if _p6.get_sync_task(_st_id, scope=_scope) is None:
                            _p6.create_sync_task(
                                name=f"栖月汇-{_p.id} 同步任务",
                                source_id="niushop-qyh",
                                target_dataset=f"ri.aos.main.dataset.{_p.id}",
                                mode="full",
                                cron_expr="0 * * * *",
                                status="active",
                                owner="data-team",
                                config={"pipeline_id": _p.id},
                                scope=_scope,
                            )
                    log.info("startup_sync_tasks_seeded count=%d", len(_items))

                    # Phase D: 为每个 pipeline 创建 Schedule（wave_ext _schedules dict）
                    # 确保前端调度页能看到真实数据
                    import time as _time
                    for _p in _items:
                        _sch_id = f"sch-{_p.id}"
                        if _sch_id not in _wx._schedules:
                            _wx._schedules[_sch_id] = {
                                "id": _sch_id,
                                "cron": "0 * * * *",
                                "pipelineId": _p.id,
                                "enabled": True,
                                "name": f"栖月汇-{_p.id} 每小时同步",
                                "ingest": None,
                                "orgId": _scope.org_id,
                                "projectId": _scope.project_id,
                                "lastRun": None,
                            }
                            _wx._persist_safe("persist_schedule", _scope, _wx._schedules[_sch_id])
                    log.info("startup_schedules_seeded count=%d", len(_wx._schedules))

                    # D2.9：唯一真实目标租户下的 12 OT 统一收敛为 live pipeline
                    # 每小时 Cron；保留已有运行历史，绝不把 UI 种子历史写回数据库。
                    from aos_api.qyh_cron_scheduler import ensure_qyh_hourly_schedules

                    for _schedule in ensure_qyh_hourly_schedules():
                        _wx._schedules[_schedule["id"]] = _schedule
                    log.info("startup_qyh_real_cron_ready count=12")
                log.info("startup_seed_from_bundles count=%d dir=%s", _count, _bundles_dir)
            except Exception:
                log.exception("startup_seed_from_bundles_failed_continue")
            log.info("startup_meta_store_ok")
        except Exception:
            log.exception("startup_meta_store_failed_continue")
    else:
        log.info("startup_schema_bootstrap_skipped migration_mode=%s", mode_value)

    async def _qyh_cron_loop() -> None:
        """每 15 秒检查一次；Cron 命中按分钟数据库幂等领取。"""
        while not cron_stop.is_set():
            try:
                from aos_api.qyh_cron_scheduler import run_due_qyh

                await asyncio.to_thread(run_due_qyh)
            except Exception:
                log.exception("qyh_cron_tick_failed")
            try:
                await asyncio.wait_for(cron_stop.wait(), timeout=15)
            except TimeoutError:
                continue

    cron_task = asyncio.create_task(_qyh_cron_loop(), name="qyh-real-cron")
    log.info("startup_qyh_real_cron_worker_started interval_seconds=15")
    yield
    cron_stop.set()
    if cron_task is not None:
        cron_task.cancel()
        with suppress(asyncio.CancelledError):
            await cron_task
    # ── shutdown：清理 JDBC 缓存（SSH 隧道 + DB 连接）──
    try:
        from aos_api.jdbc_connector_runtime import jdbc_runtime_shutdown
        jdbc_runtime_shutdown()
        log.info("shutdown_jdbc_runtime_ok")
    except Exception:
        log.exception("shutdown_jdbc_runtime_failed_continue")


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

    from aos_api.ontology_contract_openapi import install_ontology_contract_openapi

    install_ontology_contract_openapi(application)

    # Reset lifespan to avoid the include_router lifi_chain with 500+ routers.
    application.router.lifespan_context = lifespan

    log.info("aos-api_app_created version=%s", application.version)
    return application


app = create_app()
