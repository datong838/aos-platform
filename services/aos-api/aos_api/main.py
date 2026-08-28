"""AOS API application factory — Wave-0/1/2."""
from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

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


def _qyh_cron_worker_enabled() -> bool:
    """Keep production Cron on by default, with an explicit local-test off switch."""
    return os.getenv("AOS_QYH_CRON_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


@dataclass(frozen=True)
class _ProviderHealthLoopSelection:
    maintainer: Any | None
    status: str
    error_code: str | None = None


def _build_provider_health_startup():
    """Construct the canonical runtime without starting it or hiding authority."""
    from aos_api.aip_provider_health_maintenance import (
        refresh_ecommerce_readiness_from_authorized_runtime,
        refresh_provider_health_from_authorized_runtime,
    )
    from aos_api.aip_provider_health_maintenance_startup import (
        build_provider_health_maintenance_startup,
    )

    return build_provider_health_maintenance_startup(
        refresh_health=refresh_provider_health_from_authorized_runtime,
        refresh_readiness=refresh_ecommerce_readiness_from_authorized_runtime,
    )


def _select_provider_health_maintenance() -> _ProviderHealthLoopSelection:
    """Fail closed to no loop while retaining only a stable diagnostic code."""
    from aos_api.aip_provider_health_maintenance_runtime import (
        ProviderHealthRuntimeAssemblyError,
    )
    from aos_api.aip_provider_health_maintenance_startup import (
        ProviderHealthStartupPreflightError,
    )

    try:
        startup = _build_provider_health_startup()
    except (
        ProviderHealthStartupPreflightError,
        ProviderHealthRuntimeAssemblyError,
    ) as exc:
        return _ProviderHealthLoopSelection(
            maintainer=None,
            status="PROVIDER_HEALTH_MAINTENANCE_STARTUP_FAILED_CLOSED",
            error_code=exc.code,
        )
    if startup.runtime is None:
        return _ProviderHealthLoopSelection(
            maintainer=None,
            status=startup.preflight.status,
        )
    return _ProviderHealthLoopSelection(
        maintainer=startup.runtime.maintainer,
        status="PROVIDER_HEALTH_MAINTENANCE_STARTUP_RUNTIME_GREEN",
    )

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
    provider_health_stop = asyncio.Event()
    provider_health_task: asyncio.Task[None] | None = None
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
                    from aos_api.qyh_cron_scheduler import (
                        QYH_DAILY_CRON_BY_PIPELINE,
                        ensure_qyh_staggered_daily_schedules,
                    )

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
                                cron_expr=QYH_DAILY_CRON_BY_PIPELINE.get(_p.id, "0 2 * * *"),
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
                                "cron": QYH_DAILY_CRON_BY_PIPELINE.get(_p.id, "0 2 * * *"),
                                "pipelineId": _p.id,
                                "enabled": True,
                                "name": f"栖月汇-{_p.id} 每日错峰同步",
                                "ingest": None,
                                "orgId": _scope.org_id,
                                "projectId": _scope.project_id,
                                "lastRun": None,
                            }
                            _wx._persist_safe("persist_schedule", _scope, _wx._schedules[_sch_id])
                    log.info("startup_schedules_seeded count=%d", len(_wx._schedules))

                    # D2.9：唯一真实目标租户下的 12 OT 统一收敛为 live pipeline
                    # 每日一次、分小时错峰 Cron；保留已有运行历史，绝不把 UI 种子历史写回数据库。
                    for _schedule in ensure_qyh_staggered_daily_schedules():
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

    # ── OKF Wiki 冷启动(含 Procedural Playbook) + 三层运行记忆冷启动（in-memory，best-effort）──
    try:
        from aos_api.okf_wiki_cold_start import seed_okf_wiki_cold_start

        _wiki_count = seed_okf_wiki_cold_start()
        if _wiki_count:
            log.info("startup_okf_wiki_cold_start_seeded count=%d", _wiki_count)
    except Exception:
        log.exception("startup_okf_wiki_cold_start_failed_continue")

    try:
        from aos_api.demo.seed_memory_cold_start import seed_memory_cold_start

        _mem_result = seed_memory_cold_start()
        if _mem_result.get("total"):
            log.info("startup_memory_cold_start_seeded %s", _mem_result)
    except Exception:
        log.exception("startup_memory_cold_start_failed_continue")

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

    if _qyh_cron_worker_enabled():
        cron_task = asyncio.create_task(_qyh_cron_loop(), name="qyh-real-cron")
        log.info("startup_qyh_real_cron_worker_started interval_seconds=15")
    else:
        log.info("startup_qyh_real_cron_worker_disabled explicit=true")

    from aos_api.aip_provider_health_maintenance import maintenance_interval_seconds

    provider_health_selection = _select_provider_health_maintenance()

    async def _provider_health_loop() -> None:
        maintainer = provider_health_selection.maintainer
        if maintainer is None:
            return
        interval = maintenance_interval_seconds()
        while not provider_health_stop.is_set():
            try:
                result = await asyncio.to_thread(maintainer.run_once)
                log.info(
                    "aip_text_provider_health_tick status=%s stage=%s "
                    "observation_id=%s expires_at=%s",
                    result.get("status"),
                    result.get("stage"),
                    result.get("observationId"),
                    result.get("expiresAt"),
                )
            except Exception:
                log.exception("aip_text_provider_health_tick_failed_closed")
            try:
                await asyncio.wait_for(provider_health_stop.wait(), timeout=interval)
            except TimeoutError:
                continue

    if provider_health_selection.maintainer is not None:
        provider_health_task = asyncio.create_task(
            _provider_health_loop(), name="aip-text-provider-health-maintenance"
        )
        log.info(
            "startup_aip_text_provider_health_maintenance interval_seconds=%d",
            maintenance_interval_seconds(),
        )
    elif provider_health_selection.error_code is not None:
        log.warning(
            "startup_aip_text_provider_health_maintenance_failed_closed code=%s",
            provider_health_selection.error_code,
        )
    else:
        log.info(
            "startup_aip_text_provider_health_maintenance_inactive status=%s",
            provider_health_selection.status,
        )
    yield
    cron_stop.set()
    provider_health_stop.set()
    if cron_task is not None:
        cron_task.cancel()
        with suppress(asyncio.CancelledError):
            await cron_task
    if provider_health_task is not None:
        provider_health_task.cancel()
        with suppress(asyncio.CancelledError):
            await provider_health_task
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
